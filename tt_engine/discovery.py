"""How finding products actually works — and how to scout niche-with-demand products.

The honest mechanics, because it's the thing operators most often misunderstand:

  The engine does NOT browse TikTok/Amazon to DISCOVER products. It never scrapes a
  platform that prohibits it (the founding guardrail). What it does is FILTER and
  SCORE a pool of candidates you give it — killing commodity-saturated, thin-margin,
  branded, and restricted products, and rewarding real demand (momentum) + a
  defensible niche (differentiation). "Niche but has demand" is exactly what the
  filter surfaces — from candidates you supply.

Where the candidate pool comes from, two honest routes:
  1. A DATA FEED — Kalodata / FastMoss / EchoTik list trending products with velocity
     data. Import it (`import-csv`) or wire the API; the engine scores the lot.
  2. Your own SCOUTING — you spot products on free surfaces, log what you observe,
     and let the gates tell you which are real. This module guides that route.

Scouting is human work; the engine can't do it for you. What it CAN do is make it
disciplined — you bring candidates, it kills the commodity traps and surfaces the
defensible ones with real demand.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Source:
    name: str
    free: bool
    how: str


# Free (or free-tier) surfaces to scout — no scraping, just looking where sellers look.
SOURCES: tuple[Source, ...] = (
    Source("TikTok Creative Center → Top Ads / Top Products", True,
           "TikTok's OWN free tool: filter Top Products by category, region, and time "
           "window. See what's actually converting in ads right now — the cleanest "
           "free demand signal there is."),
    Source("TikTok Shop app → category Best Sellers + '#TikTokMadeMeBuyIt'", True,
           "browse Best Sellers within a NICHE category (not the front page); scan the "
           "hashtag for products with repeat 'where can I buy?' comments."),
    Source("Amazon → Movers & Shakers / Best Sellers by niche sub-category", True,
           "cross-platform demand check: a product rising in a niche Amazon "
           "sub-category AND showing up on TikTok is a strong two-signal find."),
    Source("Kalodata / FastMoss (free trial / limited tier)", False,
           "the velocity data the engine scores best — units/day, sellers, ad counts. "
           "Export a CSV and `import-csv` it; even a trial gives you a real candidate list."),
    Source("Niche communities (subreddits, hobby forums, Facebook groups)", True,
           "hunt for repeated PAIN POINTS and 'I wish something existed that…'. This is "
           "how you find a defensible niche BEFORE it's saturated on TikTok."),
)

# What "niche" actually means — so it doesn't collapse into random mashups.
NICHE_PRINCIPLE: tuple[str, ...] = (
    "A niche is a real AUDIENCE with a real shared NEED — not a random combination "
    "of demographics. 'Sourdough bakers' is a niche. 'Single-mom dog-lovers who play "
    "guitar' is not — it's three unrelated traits stapled together, with no shared "
    "need and nowhere those people actually gather.",
    "The test: can you name WHERE this audience already congregates — a subreddit, a "
    "hashtag, a Facebook group, a shelf in a store? If yes, it's a niche. If you have "
    "to invent the group to justify the product, it's a guess, not a niche.",
    "Go one level deep, not three. 'Guitarists' → too broad; 'gigging guitarists who "
    "hate strap slippage' → a real, nameable need. 'Left-handed vegan gigging "
    "guitarists' → over-specified, tiny, and probably imaginary.",
    "The product solves the need; the audience is why it spreads. If you can't say "
    "the need in one plain sentence, it's random.",
)

# The niche-with-demand bar (researched) — what a real find must show.
CRITERIA: tuple[str, ...] = (
    "DEMAND is real (3 signals, not one viral video): repeat creators posting it, "
    "repeat 'where can I buy?' comments, and multi-day consistency.",
    "NICHE / defensible: a specific audience or use-case, NOT a generic me-too item. "
    "Ask 'why would they buy MINE?' — material, design, a bundle, an angle.",
    "NOT saturated: roughly < 50 recent sellers and < 500 reviews, and the field "
    "isn't all the same offer.",
    "IMPULSE priced $10–45 and demonstrable in 15–60s on camera.",
    "MARGIN holds: ≥ 45% at a real US/fast landed cost (the engine's hard gate).",
    "SOURCEABLE fast: a US warehouse or a proven fast route (see the sourcing guide).",
)


# What you actually SEE scrolling TikTok Shop — and the honest read on each. These
# are the high-volume lanes everyone tests; most are near-commodity, so the money is
# in the DEFENSIBLE ANGLE within the lane, not the lane itself.
@dataclass(frozen=True)
class ScrollType:
    name: str
    read: str
    angle: str
    ai_fit: str


SCROLL_TYPES: tuple[ScrollType, ...] = (
    ScrollType(
        "Comfortable / simplistic clothing (basics, loungewear, wide-leg, sets)",
        "huge and PROVEN, but saturated — a plain tee competes with everyone",
        "win on a SPECIFIC fit/fabric/aesthetic + honest sizing, sold via the fit-check "
        "format. The garment (your real photos) is the product; the angle is the vibe.",
        "STRONG — garment-swap try-on; faceless chest-down mode lands reliably"),
    ScrollType(
        "Blue-light / trendy glasses",
        "very saturated and near-commodity — the engine's commodity gate will often "
        "(correctly) flag the generic version",
        "only worth it with a real edge: a distinct frame style, a niche audience "
        "(gamers, nurses, night-shift), or a bundle. Otherwise skip — margins get "
        "raced to zero.",
        "PARTIAL — worn on camera (try-on), but claims about eye strain are OFF-limits"),
    ScrollType(
        "Meme / statement / novelty tees (identity + humour)",
        "POD-friendly (low inventory risk), defensible via the DESIGN/identity niche, "
        "healthy margin — but design-dependent and can be a flash trend",
        "the JOKE or identity IS the product. Win a specific community; rotate designs "
        "fast; Etsy POD + TikTok is the natural pairing (see the POD planner).",
        "STRONG — wear it and let the design read; the reaction is the hook"),
    ScrollType(
        "Novelty / 'one satisfying job' gadgets (mini shavers, quirky tools)",
        "demonstrable and impulse, but commodity-prone with real quality/refund risk",
        "win with a genuinely satisfying real-time demo + FAST US shipping (returns "
        "kill these). Differentiate on the specific job, not price.",
        "STRONG — hands-on function demo; faceless/POV works great"),
)


def render() -> str:
    lines = [
        "# How finding products works — and how to scout",
        "",
        "## The honest mechanics",
        "The engine doesn't browse TikTok to DISCOVER products — it never scrapes a "
        "platform (the founding guardrail). It FILTERS and SCORES candidates YOU bring: "
        "it kills commodity-saturated, thin-margin, branded, and restricted items, and "
        "rewards real demand (momentum) + a defensible niche (differentiation). So "
        "'niche but has demand' is what the filter surfaces — you supply the candidates, "
        "it tells you which are real.",
        "",
        "Two ways to get candidates: a DATA FEED (Kalodata/FastMoss/EchoTik → "
        "`import-csv`) or your own SCOUTING (below).",
        "",
        "## Where to scout (free surfaces — no scraping, just looking)",
        "",
    ]
    for s in SOURCES:
        tag = "free" if s.free else "paid / free-tier"
        lines += [f"### {s.name}  ({tag})", f"- {s.how}", ""]
    lines += ["## What you keep seeing while scrolling (the honest read)", "",
              "The lanes everyone tests. Most are near-commodity — the money is in the "
              "DEFENSIBLE ANGLE within the lane, not the lane itself:", ""]
    for s in SCROLL_TYPES:
        lines += [f"### {s.name}",
                  f"- **The read:** {s.read}",
                  f"- **Your angle:** {s.angle}",
                  f"- **AI-creator fit:** {s.ai_fit}", ""]
    lines += ["## What 'niche' means (so it's not random)", "",
              "Niche means a real audience with a real need — not a mashup of "
              "demographics. Get this right first, or the finds are noise:", ""]
    lines += [f"- {n}" for n in NICHE_PRINCIPLE]
    lines += ["", "## What a real 'niche with demand' find must show", ""]
    lines += [f"- {c}" for c in CRITERIA]
    lines += [
        "",
        "## Turn a find into a scored candidate (let the gates judge it)",
        "",
        "1. `add --name \"...\" --category <cat> --id P-YOURID` — log the product.",
        "2. `add-metric P-YOURID --units N --price P` — log what you observe, ideally "
        "over a few days (momentum needs a series, not one day).",
        "3. `add-supplier P-YOURID --cost X --ship-cost Y --ship-days N --us-warehouse` "
        "— a real US/fast quote (economics won't score without it).",
        "4. `scorecard P-YOURID` — the gates + score tell you: commodity trap, or a "
        "defensible niche with demand. `select` then ranks your finds by expected "
        "dollars.",
        "",
        "Scouting is human work — the engine can't do it for you. But it kills the "
        "commodity traps hard, so the finds that survive are worth your money.",
    ]
    return "\n".join(lines) + "\n"
