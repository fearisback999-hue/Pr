"""The operator's assistant — ask it anything about YOUR business state and the engine.

It "knows everything" the honest way: at answer time it compiles the live state of your
database (board, verdicts, lifecycle, playbook progress, next actions, config) plus the
engine's built-in knowledge (commands, fees, SLAs, sourcing, the kill/scale rules) into
a context document, and answers strictly from that.

Two modes, always labeled:
  • LLM mode (ANTHROPIC_API_KEY set): Claude answers from the compiled context, under a
    system prompt that forbids inventing numbers — if the context doesn't contain it,
    it says so and points at the command that computes it.
  • Offline mode: deterministic routing — the question is matched to the relevant
    knowledge sections and live data, which are returned directly. Less fluent, same
    truth.

It never executes anything. Every answer that implies an action names the command; you
run it. (Same guardrail as everywhere else: the assistant advises, the operator acts.)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .config import CONFIG
from .db import Database
from .guide import all_steps
from .llm import LLMClient, LLMUnavailable
from .playbook import current_phase, overall
from .reports.scorecard import verdict

# ── static knowledge (kept in sync with the modules it summarizes) ──────────────
KNOWLEDGE: dict[str, str] = {
    "commands": (
        "Key commands (all `python -m tt_engine.cli …`):\n"
        "- data in: `import-csv <file> --source kalodata|fastmoss`, `add`, `add-metric`, "
        "`add-supplier <id> --cost X --ship-cost Y` (REQUIRED before economics scores)\n"
        "- detect/score: `daily`, `find --top 5`, `scorecard <id>`, `search --q …`, `next`\n"
        "- deep-dive: `analyze <id>` (SWOT/risks/offers), `optimize <id>` (true fee stack "
        "+ offer sweep), `creative-pack <id>`, `landing <id>`, `packet <id>`\n"
        "- live tests: `log-test <id> --spend X --revenue Y` daily, `validate <id>` "
        "(48h kill timer), `log-result <id> --decision kill|scale`\n"
        "- business: `playbook`, `playbook-check <step>`, `capital`, `pod`, `roadmap`, "
        "`report-monthly`, `recalibrate`\n"
        "- dashboard: `serve` → http://127.0.0.1:8787"
    ),
    "fees": (
        "TikTok Shop fee stack (verified 2026-07, reverify — schedules change): 6% "
        "referral fee on most US categories (5% select jewelry; 3% new-seller promo for "
        "30 days) + ~1–3.8% payment processing + the affiliate commission YOU set "
        "(10–30% typical). The scorer uses 6%-only for comparability; `optimize <id>` "
        "shows the TRUE stack — judge ads against the true break-even, not the 6%-only one."
    ),
    "shipping": (
        "Shipping/SLAs: tracking 'In Transit' within 2 business days, 'Delivered' within "
        "~6 (dropship compliance); On-Time Delivery Rate feeds your Shop Performance "
        "Score — slow shipping throttles reach platform-wide. Source US warehouses: CJ "
        "Dropshipping (3–7d, free, native TikTok integration), HyperSKU (2–4d, private "
        "agent, branding). Scale a proven winner to FBT (TikTok's own fulfillment, "
        "optional per the Feb 2026 policy). Cross-border only via whitelisted carriers. "
        "Never straight AliExpress ePacket (10–20d kills account health)."
    ),
    "fulfillment": (
        "Order fulfillment: the engine never places supplier orders (founding guardrail "
        "— no automatic spending). Use the supplier platform's official TikTok Shop "
        "integration instead: CJ / AutoDS / Zendrop auto-sync and fulfill orders under "
        "authorization you grant at connection time. Playbook step: sup-auto-fulfill."
    ),
    "killscale": (
        "Kill/scale rules: below break-even ROAS for 48 straight hours = KILL (hard "
        "timer, trend can't save it); CTR <1% not improving = kill; refunds >5% = kill. "
        "Scale needs ALL of: CTR ≥1.5%, ROAS >1.15× break-even, stable refunds, a clear "
        "winning creative. Log spend daily (`log-test`) or the timer math breaks. "
        "$150–300 fixed test budget per product; most tests lose — that's structural."
    ),
    "scoring": (
        "Scoring: 100 points across viral demo (20), market demand (20), competition "
        "timing (15), economics (20), content potential (15), brand potential (10). "
        "Hard gates disqualify regardless of total: margin <45%, return-risk ≥10%, "
        "branded/trademarked, restricted category, commodity-saturated (saturation ≥65). "
        "TEST = gates clear AND ≥80. Lifecycle stages: brand_new / early_trend / growing "
        "/ peaking / oversaturated / dead — only the first two after brand_new are worth "
        "new money. Every scorecard shows every component and the data behind it."
    ),
    "sourcing_products": (
        "Finding products: export CSVs from Kalodata/FastMoss (filter: 7d growth >100%, "
        "sellers <15, price $15–50) → `import-csv` → `daily` → `scorecard`. Free "
        "scouting: TikTok Creative Center Top Ads, the Shop tab, #TikTokMadeMeBuyIt — "
        "then `add` + `add-metric` what you observe. A winner in data: steep multi-day "
        "growth, low-but-rising competition, defensible niche (not commodity), $15–50, "
        "45%+ margin at a real quote, demonstrable on camera in 3 seconds."
    ),
    "million": (
        "Road to $1M: $1M revenue in 24mo ≈ $42k/mo ≈ 31 orders/day ≈ 2 winners at "
        "scale (~$160k take-home at 16% blended margin). $1M PROFIT needs ~$5–7M revenue "
        "at blended margins — organic-first content (~35% margin) nearly halves that. "
        "Median seller does ~$1,150/mo; <10% survive year one. `roadmap` computes your "
        "exact ladder."
    ),
    "roster": (
        "The actor roster: run ~10–12 personas, each a creator bible in "
        "docs/persona/*.md, each posting from its OWN dedicated account. More "
        "accounts = more shots at reach AND a spread-out cadence that stays "
        "shadowban-safe (no one account looks automated). `personas` lists the "
        "roster; each actor has a slug you reference in a video spec. One persona per "
        "account, consistent — the opposite of a spam signal."
    ),
    "video_spec": (
        "Composable video specs: every generation is THREE separately-editable parts "
        "— ACTOR (a roster persona), PRODUCT, and PROMPT (+ shot mode). Edit any one "
        "without disturbing the others, review the assembled result, and fix it "
        "BEFORE generating — so a bad prompt is corrected on the page, not after "
        "burning credits. `draft new <product> --actor <slug>` creates one (seeds the "
        "prompt); `draft set <id> --prompt \"...\"` edits just the prompt; `draft "
        "show <id>` reviews the three parts + assembled preview; `draft approve <id>` "
        "marks it ready. Generation stays the separate confirmed spend step — you "
        "only ever pay for a spec you've already reviewed."
    ),
    "organic": (
        "Organic marketing (free views) is the cheapest lever. The 2026 algorithm "
        "weights completion rate (~70% is the reach threshold), watch time, shares, "
        "comments, and repeat views — things no bot fakes. Wins for a small account: "
        "TikTok serves on quality not follower count (zero-follower clips can pop if "
        "the first 3s land); post what people SEARCH (say the keyword, TikTok SEO); "
        "series (Part 1/2/3) beat standalone; 4–6 posts/week for 8+ weeks before "
        "judging; reply-to-comment clips are the highest-trust free content. Keep "
        "clips short (8–15s), hook in 3s, make the last second worth reaching. "
        "`organic` prints the full playbook; the AIGC label stays on, YOU post."
    ),
    "ideas": (
        "Product options (not one at a time): `ideas` is a menu of researched "
        "archetypes that fit the model — precision hobby tools, material-story "
        "accessories, satisfying organization systems, problem-specific pet gear, "
        "defensible-fit apparel, sensory desk items, routine props (not supplements), "
        "niche audio, one-job kitchen tools, aesthetic problem-solvers. Each is "
        "demonstrable, defensible (not commodity), $10–45, with an honest AI-creator "
        "fit and watch-out. They're DIRECTIONS TO VALIDATE, not guaranteed winners — "
        "confirm demand (repeat creators, 'where can I buy' comments, multi-day "
        "consistency), low saturation (<50 sellers, <500 reviews), and 25–40%+ margin, "
        "then run them through the engine's gates + score on real Kalodata/FastMoss data."
    ),
    "authenticity": (
        "Making AI video look authentic: the honest number is you'll KEEP ~30% of "
        "what you generate (operators report ~2 usable clips in 7 with hands) — so "
        "generate ~4× what you need and DISCARD the tells; that discipline is the "
        "trick, not one lucky render. Nobody can promise 'identical to a real person'. "
        "The engine bakes in the craft (iPhone look, one coherent setting, exactly two "
        "imperfections, real skin/blinking, pinned face/voice, keyframe-first). Hunt "
        "tells on a PHONE at feed size: hands, dead eyes, morphing text, floating "
        "product, lip-sync, continuity. Favour shots that hide hard failures (hands "
        "still/out of frame, face-covered mirror selfies, short 8s clips). Outcome "
        "proof stays REAL footage. If faces keep failing, use the FALLBACK LADDER "
        "(`shot-mode`): full → face_light (face hidden) → faceless (chest-down / "
        "hands / POV, voiceover not lip-sync). Faceless deletes the two hardest "
        "classes and often looks MORE real — e.g. shorts as a chest-down try-on. "
        "`production <id> --mode faceless` or set the store default. Label stays on. "
        "`authenticity` prints the full guide."
    ),
    "account_safety": (
        "Will a bot get us shadowbanned? Not for LABELED AI content — TikTok "
        "requires the AIGC label (the engine enforces it) and does NOT restrict "
        "reach for disclosed AI videos. What DOES get accounts reach-restricted is "
        "automated account OPERATION: auto-posting via unofficial tools, bought/faked "
        "engagement, engagement pods, inhuman cadence, aggressive follow/unfollow, "
        "device farms. This engine never touches your account — it plans, YOU post "
        "from the app. Safe cadence ~1–4 posts/day per account, warm new accounts "
        "up, one persona per account, vary content, engage for real. `account-safety` "
        "prints the full checklist + the recover-your-reach playbook. It's compliance, "
        "not evasion — the fix is to not bot the risky parts, not to hide a bot."
    ),
    "autopilot": (
        "Autopilot runs the loop, but the KEY decisions stay yours. `autopilot run` "
        "proposes each product's next action into a queue; `autopilot preflight` maps "
        "what's automated vs. what needs you. Four kinds: DECISION (the product pick — "
        "'which products' is always yours; approve=select, reject=pass; NEVER auto), "
        "INTERNAL (re-score, build pack, export, record kill/scale — flip to auto per "
        "stage via `autopilot policy <stage> auto` once trusted), EXTERNAL (generation "
        "spends money — approval required FOREVER), MANUAL (you do it off-engine: "
        "supplier quotes, daily ad logging, and the POST button; clears itself when "
        "the DB shows the work). The product-selection GATE means the creative→"
        "generate→export chain only runs for products you've selected — even with "
        "internal stages on full-auto. So maximally hands-off = you pick products, "
        "approve spend, hit post; the engine does the rest. Everything is an audit "
        "trail; rejections stick until the world moves."
    ),
    "production": (
        "The video production runbook (`production <id>`) is the keyframe-first "
        "Seedance pipeline, filled in per scene: (1) generate the ACTOR image once "
        "(iPhone-15-Pro framing, flaws on person + scene, never the word "
        "'photorealism'); (2) per scene, a first-frame image of that actor in one "
        "room (+ product photo when shown) — one room per ad; (3) animate each frame "
        "in Seedance with the dialogue in the prompt (starting frames hold the "
        "character); (4) ONE voice — ElevenLabs video-to-voice lip-syncs it onto "
        "on-camera clips, text-to-voice (same voice) for narration; (5) assemble in "
        "CapCut with auto-captions + real B-roll. It PLANS only — generation stays "
        "the confirmed `creative`/autopilot `generate` step, and the AIGC label is "
        "non-negotiable at export. For volume, `slideshows <id>` plans photo-mode "
        "carousels (~3/day per store; images cost ~10× less than video) — slide 1 "
        "is the face-covered mirror-selfie style (fewer AI tells, converts better); "
        "the '550/day' agency number is spread across many brands, not one account. "
        "For CLOTHING, `production <id>` gives the fit-check runbook instead: post "
        "from the persona's own creator account (not the brand — try-ons must read "
        "organic), an aspirational model, and the GARMENT SWAP — upload your real "
        "clothing photo(s) with front/back angles and the model is synthesized "
        "wearing your EXACT garment in short ~8s clips. Break-even is computed from "
        "your true margin (not a parroted '2–3 sales')."
    ),
    "ai_creator": (
        "The AI creator program: ONE labeled persona (Soul ID) posts ~2×/day; the "
        "best organic posts get Spark-boosted on the standard $200 test budget with "
        "the same 48h kill discipline. Every product gets an AI-CREATOR FIT score "
        "(folded into the EV queue): handling products (accessories/hobby/home) the "
        "persona can carry alone; outcome products (pet behavior, skin, supplements) "
        "need REAL affiliate footage for proof — a generated 'result' is fabricated "
        "evidence, and the AIGC label discloses the method, not that the outcome "
        "happened. Every persona-driven sale keeps the ~15% affiliate cut. "
        "`ai-plan <id>` prints the per-product plan; the AIGC label is on every "
        "post, always — export refuses without it."
    ),
    "selection": (
        "The test queue ranks by EXPECTED VALUE, not score: EV = p(win)·payoff − "
        "p(lose)·loss at the TRUE fee stack (referral + payment + affiliate). p(win) "
        "anchors on the ~20% disciplined-beginner hit rate, shifted by score edge, "
        "data confidence, and lifecycle — it orders the queue; the 48h kill timer "
        "decides after money moves. Each product also gets a revenue CEILING (market "
        "× capture × lifecycle headroom, capped at ~$40k/mo) and a '×N = $100k month' "
        "count — a flawless product that ceilings at $8k is fine for reps, wrong for "
        "scale. Gated, below-threshold, and unpriced products get refusals, never "
        "numbers. `select` prints the queue; `scale` itemizes the $100k month "
        "(~3 winners, ~$20k/mo ads, ~$42k working capital at defaults)."
    ),
    "data_sources": (
        "Data sources: CSV exports + official APIs only. The engine will not scrape "
        "TikTok/Amazon/Meta/Reddit etc. — ToS-prohibited and it's the repo's founding "
        "guardrail. Kalodata/EchoTik API adapters are ready for keys in feeds/."
    ),
}

_ROUTES = [
    (("fee", "commission", "referral", "payment", "take-rate", "profit", "margin"), "fees"),
    (("ship", "delivery", "warehouse", "supplier", "cj", "hypersku", "fbt", "source",
      "sourcing", "buy"), "shipping"),
    (("fulfil", "fulfill", "order", "automat"), "fulfillment"),
    (("kill", "scale", "roas", "test", "budget", "spend", "validate"), "killscale"),
    (("score", "gate", "verdict", "lifecycle", "saturat", "commodity", "confidence"),
     "scoring"),
    (("find", "product", "winner", "niche", "trend", "kalodata", "fastmoss", "research"),
     "sourcing_products"),
    (("roster", "actors", "multiple actor", "10 actor", "12 actor", "different "
      "account", "many account", "personas"), "roster"),
    (("video spec", "draft", "editable", "edit the prompt", "three part", "3 part",
      "three section", "before generating", "waste credit", "waste the credit",
      "before we generate", "composable"), "video_spec"),
    (("organic", "free views", "algorithm", "watch time", "completion", "for you",
      "fyp", "views", "grow", "reach", "hashtag", "trending sound", "seo"), "organic"),
    (("idea", "ideas", "what to sell", "what should i sell", "options", "product "
      "options", "what could i sell", "niche to", "categories to sell"), "ideas"),
    (("authentic", "look real", "realistic", "look fake", "uncanny", "identical",
      "usable rate", "discard", "tells", "quality of the video"), "authenticity"),
    (("shadowban", "shadow ban", "banned", "ban", "reduced reach", "flagged",
      "account safety", "account health", "spam", "detected", "detection"),
     "account_safety"),
    (("autopilot", "automate", "automatic", "approval", "approve", "hands-off",
      "auto mode"), "autopilot"),
    (("production", "runbook", "seedance", "keyframe", "first frame", "actor image",
      "capcut", "elevenlabs", "eleven labs", "lip sync", "lip-sync", "voice",
      "slideshow", "carousel", "photo mode"), "production"),
    (("ai creator", "persona", "soul", "spark", "ai fit", "ai-fit", "organic post",
      "boost"), "ai_creator"),
    (("expected value", " ev", "ceiling", "100k", "$100k", "queue", "which product",
      "what to test", "capacity", "working capital"), "selection"),
    (("million", "1m", "revenue", "goal", "rich", "money"), "million"),
    (("scrape", "scraping", "amazon", "reddit", "api", "data source"), "data_sources"),
    (("command", "cli", "how do i", "help", "start"), "commands"),
]


def build_context(db: Database) -> str:
    """The live-state document the assistant answers from. Compact by design."""
    lines = ["=== LIVE STATE (from your database, right now) ==="]

    scores = db.board()
    if scores:
        lines.append("Board (latest score per product):")
        for s in scores[:12]:
            p = db.get_product(s.product_id)
            v = verdict(s.gates_passed, s.total)
            gate = f" gates: {', '.join(s.gate_failures)}" if s.gate_failures else ""
            lines.append(f"- {s.product_id} ({p.name if p else '?'}): {s.total:.0f}/100 "
                         f"[{v}]{gate}")
    else:
        lines.append("Board: empty — no products scored yet (run `daily` after importing).")

    steps = all_steps(db)
    if steps:
        lines.append("Next actions (most urgent first):")
        for st in steps[:6]:
            lines.append(f"- [{st.stage}] {st.product_id}: {st.action}"
                         + (f" → `{st.command}`" if st.command else ""))

    done, total = overall(db)
    phase = current_phase(db)
    lines.append(f"Playbook: {done}/{total} steps complete; current phase: "
                 f"{phase.name if phase else 'all phases complete'}")

    lines.append("Config: "
                 + ("LLM key set" if CONFIG.llm_available else "no LLM key (offline fallbacks)")
                 + "; "
                 + ("Higgsfield ready" if CONFIG.higgsfield_available
                    else "Higgsfield not configured (creative dry-runs)"))

    lines.append("\n=== ENGINE KNOWLEDGE ===")
    for name, text in KNOWLEDGE.items():
        lines.append(f"[{name}]\n{text}")
    return "\n".join(lines)


_SYSTEM = (
    "You are the operator's assistant inside their TikTok Shop product engine's "
    "dashboard. Answer from the provided context ONLY. Rules: never invent numbers or "
    "state facts the context doesn't contain — if it's not there, say so and name the "
    "engine command that computes it. Recommend commands for actions; never claim to "
    "have executed anything. Be concise and direct. Money-relevant caveats (fees change, "
    "most tests lose) stay in."
)


@dataclass
class AssistantAnswer:
    text: str
    mode: str                        # "llm" | "offline"
    sections: list[str] = field(default_factory=list)


def answer(db: Database, question: str, llm: Optional[LLMClient] = None) -> AssistantAnswer:
    llm = llm or LLMClient()
    context = build_context(db)

    if llm.available:
        try:
            reply = llm.complete_text(
                _SYSTEM, f"{context}\n\n=== QUESTION ===\n{question}", max_tokens=1500)
            return AssistantAnswer(text=reply, mode="llm")
        except LLMUnavailable:
            pass  # fall through to the deterministic router

    # ── offline routing: match the question to knowledge sections + live state ──
    q = question.lower()
    matched: list[str] = []
    for keywords, section in _ROUTES:
        if any(k in q for k in keywords) and section not in matched:
            matched.append(section)
    if not matched:
        matched = ["commands"]

    parts: list[str] = []
    # If they name a product id we know, lead with its live state.
    for s in db.board():
        if s.product_id.lower() in q:
            p = db.get_product(s.product_id)
            v = verdict(s.gates_passed, s.total)
            gate = (" Gate failures: " + "; ".join(s.gate_failures)) if s.gate_failures else ""
            parts.append(f"**{s.product_id}** ({p.name if p else '?'}): {s.total:.0f}/100 "
                         f"[{v}].{gate} Full math: `scorecard {s.product_id}` · deep-dive: "
                         f"`analyze {s.product_id}` · profit: `optimize {s.product_id}`")
            break
    # "What do I do" questions lead with the guide.
    if any(k in q for k in ("what do i", "next", "todo", "should i do")):
        steps = all_steps(db)
        if steps:
            parts.append("**Your next actions (from the live guide):**")
            parts += [f"- {st.action}" + (f" → `{st.command}`" if st.command else "")
                      for st in steps[:4]]
    parts += [f"**{name.replace('_', ' ')}:** {KNOWLEDGE[name]}" for name in matched[:3]]
    parts.append("_Offline mode (no ANTHROPIC_API_KEY) — answers are routed from the "
                 "engine's knowledge + your live data, not generated._")
    return AssistantAnswer(text="\n\n".join(parts), mode="offline", sections=matched)
