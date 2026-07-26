"""Product options: a menu of researched STARTING DIRECTIONS to validate — not
guaranteed winners, and not a substitute for real data.

The honest deal (reinforced after the loan conversation): nobody, including this
engine, can hand you a guaranteed winner. What this module gives you is a spread of
product ARCHETYPES that fit the model — demonstrable on camera, defensible (not
commodity), impulse-priced, AI-creator-friendly, healthy margin — each with why it
fits, how it demos, the honest watch-out, and exactly how to VALIDATE it with real
data before you spend a dollar on inventory. Options, not one product at a time.

Validation gate (researched 2026-07, sources at the bottom) — a direction only
becomes a candidate when it clears these with REAL data:
  • demand is real: 3 signals, not viral views — repeat creators, repeat "where can
    I buy?" comments, and multi-day consistency
  • not saturated: roughly < 50 recent sellers/listings and < 500 reviews, and the
    field isn't all the same angle
  • margin holds: ≥ 25–40% after product + shipping + fees, with room for creators/ads
  • demonstrable in 15–60s, TikTok-Shop-approved, reliably stockable
The engine's gates + scoring enforce the same thing once you import Kalodata/FastMoss
data — these ideas are where to POINT that engine, not its output.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProductIdea:
    name: str
    category: str                 # maps to a creative category style
    price_band: str
    why_fits: str
    demo: str
    ai_creator: str               # how the labeled AI persona carries it (honest)
    watch_out: str

    @property
    def line(self) -> str:
        return f"{self.name} ({self.category}, {self.price_band})"


# Curated to fit the model: niche/defensible, demonstrable, impulse-priced, and
# honest about where the AI persona can and can't carry the sale.
IDEAS: tuple[ProductIdea, ...] = (
    ProductIdea(
        "Precision hobby/craft tools (sourdough lame, leather edge-slicker, "
        "carving gouge)", "hobby", "$18–40",
        "defensible skill niche, low returns, buyers are passionate and search for it",
        "process ASMR — the tool doing its one job in one continuous take, sound left in",
        "STRONG — a handling product; the persona's hands do the whole demo, no faked "
        "outcome needed",
        "small audiences; you win on depth, not reach — pair with real hobbyist affiliates"),
    ProductIdea(
        "Material-story accessories (full-grain leather straps, waxed-canvas EDC, "
        "cowhide goods)", "accessories", "$25–45",
        "material honesty converts; flaws in real leather grain read as authentic",
        "close orbit of the stitching/grain in window light, then worn on-body",
        "STRONG — in-hand + on-body; the persona shows the object, which IS the proof",
        "photograph the real grain — a generated 'leather' that looks too perfect is a tell"),
    ProductIdea(
        "Satisfying organization systems (modular cable trays, packing cubes with a "
        "twist, drawer inserts)", "home", "$15–35",
        "solves a visible problem; the before→after reset is inherently watchable",
        "the real mess → the reset in real time, no time-lapse fakery",
        "STRONG — the task is the proof; film the whole pass",
        "commodity risk is high here — you need a genuine design twist, not a generic bin"),
    ProductIdea(
        "Problem-specific pet gear (calming vest, slow-feeder, de-shed glove)", "pet",
        "$20–40",
        "emotional, high-intent buyers; a real pain the owner is actively solving",
        "unbox + fit + explain on camera; the animal's reaction is the closer",
        "PARTIAL — the persona unboxes/fits/explains, but the animal reaction MUST be "
        "real affiliate/customer footage (never generate a pet 'reacting')",
        "sizing = returns; publish a real fit guide, and the outcome proof can't be faked"),
    ProductIdea(
        "Defensible-fit basics apparel (one silhouette done unusually well)", "apparel",
        "$25–45",
        "fit-check format is proven; a specific aesthetic is a moat generic tees lack",
        "garment-swap try-on (upload your real product photos) — walk in, turn, fabric moves",
        "STRONG for styling/try-on via the garment swap; sizing honesty replaces hype",
        "apparel returns run ~12% — a real sizing chart is non-negotiable"),
    ProductIdea(
        "Sensory/desk 'quiet luxury' items (heavy knurled pen, machined fidget, "
        "linen desk mat)", "accessories", "$20–40",
        "aspirational and tactile; photographs and unboxes beautifully",
        "close-up detail + a slow in-hand rotation; the weight and finish sell it",
        "STRONG — pure object demo; no outcome claim to fake",
        "aesthetic-driven → your creative bar is high; the persona look must be dialed"),
    ProductIdea(
        "Routine props, NOT supplements (sunrise alarm, specific insulated bottle, "
        "silk sleep mask)", "wellness", "$20–40",
        "rides the wellness wave without the health-claim compliance minefield",
        "where it lives, when it's used — the habit, shown honestly",
        "STRONG for the routine/placement; NO health or outcome claims, ever",
        "STRICT compliance: any 'it fixed my sleep' line is a claim-sweep failure"),
    ProductIdea(
        "Niche audio/comfort gear (open-ear clips, a specific earbud tip system)",
        "electronics", "$25–40",
        "buyers trust side-by-side sound/comfort demos that answer objections upfront",
        "hands-on function demo — the fit and the sound test in one take",
        "STRONG for the demo; the persona operates it like an owned device",
        "tech buyers are savvy and the category is competitive — you need a real edge"),
    ProductIdea(
        "Kitchen 'one satisfying job' tools (herb stripper, one-press gadget, "
        "specific prep tool)", "home", "$12–30",
        "fast visible result, impulse price, endlessly demonstrable",
        "the tool doing the one job in real time on a real, slightly-messy counter",
        "STRONG — the visible result is the proof, no cuts",
        "the most commodity-prone bucket — differentiate or the gate will (correctly) kill it"),
    ProductIdea(
        "Aesthetic problem-solvers (cord-hiding decor, a genuinely nicer version of "
        "an ugly necessity)", "home", "$18–38",
        "'I didn't know I needed this' + it photographs well = share-driven reach",
        "the ugly before → the tasteful after, in a real room",
        "STRONG — object + room do the talking; face-covered slideshow works great here",
        "must be genuinely better-looking, not just cheaper — that's the whole moat"),
)


def render() -> str:
    lines = [
        "# Product options — directions to validate (not guaranteed winners)",
        "",
        "A spread of archetypes that fit the model: demonstrable, defensible (not "
        "commodity), impulse-priced ($10–45), AI-creator-friendly, healthy margin. "
        "Pick 2–3 that fit you, then VALIDATE with real data before buying inventory.",
        "",
    ]
    for i, idea in enumerate(IDEAS, 1):
        lines += [
            f"## {i}. {idea.name}",
            f"- **Type / price:** {idea.category} · {idea.price_band}",
            f"- **Why it fits:** {idea.why_fits}",
            f"- **How it demos:** {idea.demo}",
            f"- **AI-creator fit:** {idea.ai_creator}",
            f"- **Watch out:** {idea.watch_out}",
            "",
        ]
    lines += [
        "## Before you spend a dollar — validate with REAL data", "",
        "- **Demand (3 signals, not viral views):** repeat creators posting it, repeat "
        "\"where can I buy?\" comments, and multi-day consistency.",
        "- **Not saturated:** roughly < 50 recent sellers and < 500 reviews, and the "
        "field isn't all the same angle/offer.",
        "- **Margin holds:** ≥ 25–40% after product + shipping + fees, with room for "
        "creators/ads.",
        "- **Then run it through the engine:** `import-csv` your Kalodata/FastMoss "
        "export → `daily` → `scorecard <id>`. The gates + score enforce all of this; "
        "`select` ranks the survivors by expected dollars.",
        "",
        "These are where to POINT the engine — not its output. The engine's real job "
        "is to tell you which of YOUR candidates clears the bar, on real numbers.",
    ]
    return "\n".join(lines) + "\n"


SOURCES = (
    "https://winninghunter.com/blog/best-products-to-sell-on-tiktok-shops",
    "https://eva.guru/blog/tiktok-shop-product-categories-that-sell-best/",
    "https://www.minea.com/dropshipping-winning-products/find-dropshipping-products/how-to-find-trending-products-on-tiktok",
    "https://starterx.co/blog/tiktok-shop-product-research/",
    "https://tiktokshopprofitcalculator.com/guides/best-products-to-sell",
)
