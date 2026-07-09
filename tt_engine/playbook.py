"""The zero-to-hero checklist: every step of running a TikTok Shop dropshipping
business (plus the Etsy print-on-demand side stream), in order, from "no business yet"
to "profitable and scaling."

This is deliberately the one thing the rest of the engine does NOT cover on its own:
ENGINE finds products, scores them, and manages the creative/test/kill-scale loop —
but starting a real business also means an entity, a bank account, tax registration,
platform accounts, and an ads account, none of which live in a database. This module
is the map that connects "I have nothing" to "the engine is doing its job" to
"I'm scaling a winner," with a command or a clear manual action at every step.

Two kinds of steps:
  • AUTO — the engine can see it in the DB/config and checks it off for you.
  • MANUAL — happens outside the engine (a website, a bank, an accountant); you
    check it off yourself once it's done (`playbook-check <step_id>`).

Legal/tax/entity items are described at the level of "here is what to go figure out,"
not as legal or tax advice — requirements vary by country, state, and situation.
Verify specifics with a licensed professional and the current platform terms; rules
and fee structures on TikTok Shop/Etsy change over time, so don't treat any number
here as gospel.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from .config import CONFIG
from .db import Database


@dataclass
class PlaybookStep:
    id: str
    phase: str
    title: str
    detail: str
    category: str                 # legal | financial | platform | sourcing | product |
                                   # creative | ads | outreach | ops
    command: str = ""             # CLI command reference, "" if purely off-engine
    auto: Optional[Callable[[Database], bool]] = None   # None = manual check-off only

    def is_done(self, db: Database, manual_state: dict) -> bool:
        if self.auto is not None:
            return bool(self.auto(db))
        return bool(manual_state.get(self.id, {}).get("done"))


def _cli(cmd: str) -> str:
    return f"python -m tt_engine.cli {cmd}"


# ── auto-detect probes (cheap DB/config checks — no re-scoring) ────────────────
def _has_supplier(db: Database) -> bool:
    return any(db.suppliers_for(p.id) for p in db.all_products())


def _has_metrics(db: Database) -> bool:
    return any(db.metrics_for(p.id) for p in db.all_products())


def _has_test_verdict(db: Database) -> bool:
    return any(s.gates_passed and s.total >= CONFIG.score_threshold for s in db.board())


def _has_reviews(db: Database) -> bool:
    return any(p.reviews for p in db.all_products())


def _soul_id_set(db: Database) -> bool:
    return bool(CONFIG.higgsfield_soul_id)


def _has_creative_plan(db: Database) -> bool:
    return any(c.format != "Manual" for p in db.all_products() for c in db.creatives_for(p.id))


def _mcp_configured(db: Database) -> bool:
    return bool(CONFIG.higgsfield_mcp_url)


def _has_generated_asset(db: Database) -> bool:
    return any(c.status in ("ready", "exported") for p in db.all_products()
              for c in db.creatives_for(p.id))


def _has_exported_asset(db: Database) -> bool:
    return any(c.status == "exported" for p in db.all_products() for c in db.creatives_for(p.id))


def _has_live_test(db: Database) -> bool:
    return any(db.tests_for_product(p.id) for p in db.all_products())


def _has_concluded_result(db: Database) -> bool:
    return any(db.latest_result(p.id) for p in db.all_products())


def _has_scale_result(db: Database) -> bool:
    return any((r := db.latest_result(p.id)) and r.decision == "scale"
              for p in db.all_products())


PHASES = [
    "0 — Business foundation",
    "1 — Platform accounts",
    "2 — Capital & budget",
    "3 — Supplier setup",
    "4 — Find a product (ENGINE)",
    "5 — Listing & offer",
    "6 — Psychology & creative (ENGINE)",
    "7 — Paid traffic & testing",
    "8 — Creator / affiliate outreach",
    "9 — Scale the winner",
    "10 — Etsy POD (parallel stream)",
    "11 — Financial hygiene & compliance",
    "12 — Systemize (hero)",
]

STEPS: list[PlaybookStep] = [
    # ── 0. Business foundation ──────────────────────────────────────────────
    PlaybookStep("biz-structure", PHASES[0], "Choose a business structure",
        "Sole proprietorship is fastest to start; an LLC separates your personal assets "
        "from business liability (returns, chargebacks, product-liability claims). Most "
        "sellers start sole-prop and form an LLC once revenue is real. Not legal advice — "
        "10 minutes with an accountant or attorney here saves real pain later.",
        "legal"),
    PlaybookStep("biz-ein", PHASES[0], "Register the business / get a tax ID",
        "If you formed an LLC (or want to keep your SSN off supplier/platform forms), "
        "get an EIN (US) or the equivalent business tax ID for your country. Free direct "
        "from your tax authority — never pay a third-party 'EIN service' for this.",
        "legal"),
    PlaybookStep("biz-bank", PHASES[0], "Open a dedicated business bank account",
        "Every dollar in and out of the business goes through ONE account, separate from "
        "personal. This is what makes bookkeeping, tax prep, and 'am I actually "
        "profitable' possible to answer honestly.",
        "financial"),
    PlaybookStep("biz-tax-reg", PHASES[0], "Check sales-tax / VAT registration requirements",
        "Requirements vary hugely by country and state, and by whether the platform "
        "collects tax on your behalf (TikTok Shop/Etsy often do, in many jurisdictions, "
        "but not all — and not for every tax you owe). Confirm your actual obligation with "
        "a professional before you assume it's handled.",
        "legal"),
    PlaybookStep("biz-books", PHASES[0], "Set up bookkeeping from day one",
        "A spreadsheet or a tool like Wave/QuickBooks — either is fine, but start before "
        "the first sale. Retrofitting six months of transactions is how people give up on "
        "taxes entirely. `capital` gives you the cash-flow math; it is not bookkeeping.",
        "financial"),

    # ── 1. Platform accounts ────────────────────────────────────────────────
    PlaybookStep("tt-seller", PHASES[1], "Create & verify your TikTok Shop seller account",
        "Register in TikTok Shop Seller Center and complete identity/business "
        "verification. Requirements (docs, region eligibility) change — check current "
        "requirements in Seller Center for your country before assuming eligibility.",
        "platform"),
    PlaybookStep("tt-payout", PHASES[1], "Link your payout bank account",
        "Set this in Seller Center to the SAME business bank account from step "
        "`biz-bank` — do not let payouts land somewhere your bookkeeping doesn't see.",
        "platform"),
    PlaybookStep("tt-shipping", PHASES[1], "Set shipping settings & return/refund policy",
        "Ship-by times, return window, and refund policy are account-health inputs — "
        "the `health` command models exactly this (ship days, refund rate). Set policy "
        "you can actually hit; missed ship times throttle your reach.",
        "platform", command="health --ship-days 4 --refund-rate 0.03"),
    PlaybookStep("tt-restricted", PHASES[1], "Read TikTok Shop's prohibited/restricted list",
        "Know your category's rules BEFORE sourcing — this is exactly what the engine's "
        "restricted-category hard gate checks automatically once a product is in the DB, "
        "but you should also know the rules yourself; platform policy changes.",
        "platform"),

    # ── 2. Capital & budget ─────────────────────────────────────────────────
    PlaybookStep("cap-plan", PHASES[2], "Run the capital & cash-flow plan",
        "TikTok holds payouts for a lag period, so there is a gap between paying your "
        "supplier and getting paid. `capital` computes payout float, runway, and how "
        "many product tests you can actually afford before deciding to test anything.",
        "financial", command="capital --capital 5000 --test-budget 300 --daily-ad 50 --daily-cogs 30"),
    PlaybookStep("cap-per-test", PHASES[2], "Set a fixed per-product test budget and stick to it",
        "Pick a number ($150–300 is a common starting range) BEFORE you fall in love with "
        "a product. The 48-hour kill timer only protects you if you also cap the spend "
        "you're willing to lose finding out.",
        "financial"),

    # ── 3. Supplier setup ────────────────────────────────────────────────────
    PlaybookStep("sup-account", PHASES[3], "Create a supplier-platform account",
        "CJ Dropshipping, Zendrop, AutoDS, or a direct 1688/Alibaba relationship — pick "
        "one to start. US-warehouse suppliers cost more per unit but cut shipping time, "
        "which matters a lot for TikTok Shop's ship-time account-health scoring.",
        "sourcing"),
    PlaybookStep("sup-real-quote", PHASES[3], "Get a REAL landed-cost quote and add it",
        "The engine refuses to score Economics on a guess — no placeholder cost, ever. "
        "Get the actual unit + shipping cost from your supplier and enter it; this is "
        "what unlocks every downstream score.",
        "sourcing", command="add-supplier <id> --cost X --ship-cost Y", auto=_has_supplier),
    PlaybookStep("sup-sample", PHASES[3], "Order a physical sample before scaling spend",
        "Photos lie. Order the product yourself, check real quality/fit/function, before "
        "you put ad budget behind it — this is the single most skipped step and the most "
        "common cause of a refund spiral no scorecard will predict.",
        "sourcing"),

    # ── 4. Find a product — this is the engine's core job ──────────────────
    PlaybookStep("data-in", PHASES[4], "Get real market data into the engine",
        "Import a Kalodata/FastMoss CSV export, or add a product you found by hand. "
        "Momentum needs a real multi-day series — one day of data tells you nothing.",
        "product", command="import-csv exports/kalodata.csv --source kalodata",
        auto=_has_metrics),
    PlaybookStep("first-test-verdict", PHASES[4], "Find your first TEST-verdict product",
        "Run `daily`, then `scorecard <id>` for anything close to the bar. TEST means "
        "gates clear AND score ≥ threshold — every sub-score and every gate is shown, "
        "not a black box.",
        "product", command="daily && scorecard <id>", auto=_has_test_verdict),

    # ── 5. Listing & offer ──────────────────────────────────────────────────
    PlaybookStep("listing-live", PHASES[5], "Create the live product listing",
        "Title, price, images/video, and description. Run every claim through the "
        "compliance guardrail mentally: no fabricated medical/absolute claims — TikTok "
        "and the FTC both enforce this, and it's a fast way to lose the shop.",
        "product"),
    PlaybookStep("offer-set", PHASES[5], "Set your price against the margin floor, not a guess",
        "Your scorecard already shows break-even ROAS and max allowable CAC for the "
        "current price — use those numbers to set the listing price, not vibes.",
        "financial", command="scorecard <id>"),

    # ── 6. Psychology & creative ────────────────────────────────────────────
    PlaybookStep("psych-run", PHASES[6], "Paste top comments/reviews and run the psychology pass",
        "The single clearest psychological trigger — not five vague ones — becomes the "
        "spine of every ad. Set ANTHROPIC_API_KEY for the LLM pass; without it you get a "
        "deterministic fallback (it tells you which).",
        "creative", command="psych <id> --file comments.txt", auto=_has_reviews),
    PlaybookStep("soul-id", PHASES[6], "Set ONE Soul ID persona for the whole store",
        "HIGGSFIELD_SOUL_ID in .env. One recurring face/voice across every ad, every "
        "product — mixing personas reads as inconsistent and the engine will warn you "
        "if creatives disagree.",
        "creative", command="(.env) HIGGSFIELD_SOUL_ID=...", auto=_soul_id_set),
    PlaybookStep("creative-plan", PHASES[6], "Build the creative brief (dry-run, free)",
        "Plans the batch across formats (UGC-Reaction, HyperMotion-Reveal, ASMR, "
        "POV-BeforeAfter, Unboxing) from the psychology spine + hooks. No cost until you "
        "confirm.",
        "creative", command="creative <id>", auto=_has_creative_plan),
    PlaybookStep("mcp-configure", PHASES[6], "Configure the Higgsfield MCP endpoint",
        "HIGGSFIELD_MCP_URL in .env. Until this is set, `creative` always dry-runs — "
        "which is the safe default. Set it when you're ready to actually spend on "
        "generation.",
        "creative", command="(.env) HIGGSFIELD_MCP_URL=...", auto=_mcp_configured),
    PlaybookStep("creative-generate", PHASES[6], "Confirm generation for a TEST-verdict product",
        "`--confirm` is the only way this spends money — required every time, no "
        "exceptions, gated on the product actually being at TEST verdict.",
        "creative", command="creative <id> --confirm", auto=_has_generated_asset),
    PlaybookStep("creative-export", PHASES[6], "Export creatives and upload to TikTok",
        "The export manifest BLOCKS any asset missing its AIGC disclosure — that's not "
        "optional, it's how the shop stays compliant and off enforcement radar.",
        "creative", command="export-creatives <id>", auto=_has_exported_asset),

    # ── 7. Paid traffic & testing ───────────────────────────────────────────
    PlaybookStep("ads-account", PHASES[7], "Create a TikTok Ads Manager account",
        "Separate from your Shop Seller Center login. This is where Spark Ads campaigns "
        "actually run — the engine never places an ad or spends a dollar for you.",
        "ads"),
    PlaybookStep("ads-pixel", PHASES[7], "Verify the TikTok Pixel / Shop ad events are firing",
        "Without correct event tracking your ROAS numbers (and therefore every kill/scale "
        "decision downstream) are measuring the wrong thing.",
        "ads"),
    PlaybookStep("ads-launch", PHASES[7], "Launch a small first test campaign",
        "Small per-ad-set budgets, spread across a few hooks/creators — not one big bet. "
        "Watch 3-second view rate → CTR → add-to-cart → ROAS, in that order.",
        "ads"),
    PlaybookStep("log-daily", PHASES[7], "Log spend/revenue every day the test runs",
        "The 48-hour kill timer only works if the data is actually there daily — "
        "skipping a day breaks the consecutive-day math, not just your convenience.",
        "ads", command="log-test <id> --spend X --revenue Y", auto=_has_live_test),
    PlaybookStep("decide", PHASES[7], "Let `validate` make the kill/scale call — don't override it",
        "Below break-even for 48 straight hours is KILL even if you feel optimistic. The "
        "discipline IS the product here; hope is not a strategy with real ad dollars.",
        "ads", command="validate <id> && log-result <id> --decision kill|scale",
        auto=_has_concluded_result),

    # ── 8. Creator / affiliate outreach ─────────────────────────────────────
    PlaybookStep("affiliate-rate", PHASES[8], "Set your affiliate commission rate",
        "15–25% is a common starting range in TikTok Shop's affiliate settings — check "
        "current norms in your category; rates that are too low get ignored by creators.",
        "outreach"),
    PlaybookStep("creator-outreach", PHASES[8], "Open collaboration / invite creators",
        "The dashboard's Creators page lists the marketplaces (TikTok Affiliate Center, "
        "Creator Marketplace, Insense, Billo, Collabstr, and more) and which TEST-ready "
        "products to pitch right now.",
        "outreach", command="packet <id>"),
    PlaybookStep("send-samples", PHASES[8], "Send free samples to your best responders",
        "The relationship stays human — this is the one place automation is deliberately "
        "NOT built. Iterate on whoever actually converts.",
        "outreach"),

    # ── 9. Scale the winner ─────────────────────────────────────────────────
    PlaybookStep("scale-steps", PHASES[9], "Raise budget in steps, not all at once",
        "~20–30% increases while ROAS holds above break-even, re-checking `validate` "
        "after each raise — a SCALE verdict is not a blank check.",
        "ads", auto=_has_scale_result),
    PlaybookStep("scale-angles", PHASES[9], "Diversify creative angles before you scale hard",
        "Reliance on one ad is fragile — fatigue kills a single-creative scale fast. Run "
        "another `creative` batch with new hooks once you're spending real budget.",
        "creative"),
    PlaybookStep("scale-supply", PHASES[9], "Confirm your supplier can handle the new volume",
        "Reorder lead time and MOQ matter a lot more at scale than at test size — a "
        "stockout mid-scale burns the momentum you just paid to build.",
        "sourcing"),

    # ── 10. Etsy POD (parallel, lower-risk stream) ──────────────────────────
    PlaybookStep("pod-shop", PHASES[10], "Create your Etsy shop + connect a POD provider",
        "Printify, Printful, or Gelato are the common choices — connect one to Etsy "
        "before designing anything.",
        "product"),
    PlaybookStep("pod-plan", PHASES[10], "Size your listing cadence with the POD planner",
        "Target profit ÷ profit-per-sale ÷ your real sales-per-listing = listings needed, "
        "then capped by your actual hours per week. The default sales-rate is a cold-start "
        "guess — re-run this with YOUR measured number after 30 days.",
        "product", command="pod --target 1000 --profit 8"),
    PlaybookStep("pod-publish", PHASES[10], "Publish your first batch and track for 30 days",
        "Then re-plan with the real sales-per-listing you observed, not the default.",
        "product"),

    # ── 11. Financial hygiene & compliance (ongoing) ────────────────────────
    PlaybookStep("recon-monthly", PHASES[11], "Reconcile payouts against your books monthly",
        "TikTok Shop and Etsy payouts rarely match gross sales 1:1 once fees, refunds, "
        "and holds are netted out — reconcile monthly or the numbers you're deciding on "
        "are wrong.",
        "financial"),
    PlaybookStep("tax-reserve", PHASES[11], "Set aside a tax reserve from every payout",
        "The exact percentage depends on your structure, jurisdiction, and total income — "
        "ask your accountant for YOUR number, then automate the transfer so it isn't "
        "spendable.",
        "financial"),
    PlaybookStep("account-health", PHASES[11], "Check account health regularly",
        "A low Shop Performance Score throttles reach regardless of how good your "
        "products are — `health` models the inputs so you can see it coming.",
        "ops", command="health --ship-days 4 --refund-rate 0.03"),
    PlaybookStep("monthly-report", PHASES[11], "Run the monthly recalibration report",
        "Which sub-scores actually predicted your winners vs your losers. Suggestions "
        "only — you approve any weight change with `recalibrate --apply`, never automatic.",
        "ops", command="report-monthly"),

    # ── 12. Systemize (hero) ────────────────────────────────────────────────
    PlaybookStep("sop-docs", PHASES[12], "Write down your SOPs",
        "Sourcing checklist, testing checklist, creative brief template — so the process "
        "survives a bad week and doesn't live only in your head.",
        "ops"),
    PlaybookStep("reinvest-split", PHASES[12], "Decide a reinvestment vs. draw split",
        "Pick the percentage of profit that gets reinvested into testing/scaling vs. paid "
        "out, before a big win makes that decision emotionally instead of on purpose.",
        "financial"),
    PlaybookStep("revisit-runbook", PHASES[12], "Revisit the operating runbook monthly",
        "docs/OPERATING.md — the loop matures as you do; what was manual at step 1 may "
        "be worth tightening once it's proven itself for weeks, per the iron rule: never "
        "automate what you haven't run by hand first.",
        "ops"),
]


@dataclass
class PhaseProgress:
    name: str
    steps: list[tuple[PlaybookStep, bool]]

    @property
    def done_count(self) -> int:
        return sum(1 for _, done in self.steps if done)

    @property
    def total(self) -> int:
        return len(self.steps)


def progress(db: Database) -> list[PhaseProgress]:
    manual = db.playbook_state()
    by_phase: dict[str, list[tuple[PlaybookStep, bool]]] = {}
    for step in STEPS:
        by_phase.setdefault(step.phase, []).append((step, step.is_done(db, manual)))
    return [PhaseProgress(name, by_phase[name]) for name in PHASES if name in by_phase]


def overall(db: Database) -> tuple[int, int]:
    phases = progress(db)
    return sum(p.done_count for p in phases), sum(p.total for p in phases)


def current_phase(db: Database) -> Optional[PhaseProgress]:
    """The first phase that isn't fully checked off — where the operator actually is."""
    for p in progress(db):
        if p.done_count < p.total:
            return p
    return None


def render_playbook(db: Database) -> str:
    phases = progress(db)
    done, total = overall(db)
    lines = [f"# Zero-to-hero playbook — {done}/{total} steps complete", ""]
    where = current_phase(db)
    if where:
        lines.append(f"**You are here:** {where.name} ({where.done_count}/{where.total})")
    else:
        lines.append("**Every step checked.** Ongoing operations still apply (phases 11-12).")
    lines.append("")
    for p in phases:
        lines.append(f"## {p.name}  ({p.done_count}/{p.total})")
        lines.append("")
        for step, done_flag in p.steps:
            mark = "x" if done_flag else " "
            src = "auto" if step.auto else "manual"
            cmd = f"  \n      `{step.command}`" if step.command else ""
            lines.append(f"- [{mark}] **{step.title}** ({src}) — {step.detail}{cmd}")
        lines.append("")
    lines.append(
        "> Manual steps: check them off with "
        "`python -m tt_engine.cli playbook-check <step_id>` once done. "
        "Auto steps flip themselves the moment the DB shows the work."
    )
    return "\n".join(lines)
