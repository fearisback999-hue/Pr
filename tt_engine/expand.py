"""Find products FROM products — seed expansion.

One good find should not be one product. The person who bought it has a whole
basket you can see from where you're standing: the thing that goes WITH it, the
better version of it, the thing that runs out, the thing they reach for in the
same moment.

This turns a single seed into a list of leads along five real axes:

  ACCESSORY   what it needs to work well      pull-up bar  → grip pads
  UPGRADE     the better version of it        pull-up bar  → wall-mounted rack
  COMPANION   used in the same moment/place   pull-up bar  → resistance bands
  CONSUMABLE  the part that runs out          coffee press → filters
  ALTERNATIVE same problem, different fix     pull-up bar  → doorway rings

Why these five and not "similar products": a similar product competes with your
seed for the same sale. These five are things the SAME BUYER buys IN ADDITION,
which is what actually compounds — same audience, same actor, same account, so
they stay inside the lane the roster already routes by.

THE LIMIT, stated once and enforced everywhere: this produces LEADS, not
products. It knows what tends to go with what; it knows nothing about whether
anyone is buying it right now. Every suggestion still has to survive the same
3-signal demand check and the same six gates as anything you found by scrolling.
An expansion that skipped those would just be a faster way to buy bad products.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .db import Database, models

AXES = {
    "accessory":  "what it needs to work well",
    "upgrade":    "the better version, for people who liked it",
    "companion":  "used in the same moment or the same room",
    "consumable": "the part that runs out and gets rebought",
    "alternative": "same problem, a different fix",
}

# Deterministic seeds per category. Not a product database — a THINKING PROMPT
# per axis, so the offline path gives real leads instead of "similar item 1".
# Kept coarse on purpose: the operator names the specific product, the engine
# only points at where to look.
_CATEGORY_AXES: dict[str, dict[str, list[str]]] = {
    "fitness": {
        "accessory": ["grip pads / gloves", "door frame protector", "resistance band set"],
        "upgrade": ["wall-mounted version", "adjustable / heavier-duty model"],
        "companion": ["exercise mat", "recovery roller", "workout timer"],
        "consumable": ["chalk / grip spray", "replacement bands"],
        "alternative": ["suspension straps", "gymnastic rings"],
    },
    "beauty": {
        "accessory": ["storage / travel case", "cleaning brush", "applicator"],
        "upgrade": ["heated or electric version", "pro-size / salon version"],
        "companion": ["the product it is used with (oil, serum, mask)",
                      "satin pillowcase / hair wrap"],
        "consumable": ["refill", "replacement heads / pads"],
        "alternative": ["the manual version if yours is electric (or vice versa)"],
    },
    "home": {
        "accessory": ["mounting / adhesive kit", "matching organiser"],
        "upgrade": ["larger or multi-pack version", "premium material version"],
        "companion": ["what sits next to it on the shelf or counter"],
        "consumable": ["refill / cartridge / liner"],
        "alternative": ["the no-install version", "the portable version"],
    },
    "pet": {
        "accessory": ["replacement cover", "sizing extender"],
        "upgrade": ["orthopedic / heavy-duty version"],
        "companion": ["grooming tool", "treat pouch", "calming spray"],
        "consumable": ["refill pads", "treats"],
        "alternative": ["the wearable version", "the crate/mat version"],
    },
    "electronics": {
        "accessory": ["case / stand / mount", "cable + adapter"],
        "upgrade": ["higher-capacity or faster model"],
        "companion": ["what it plugs into or sits beside on the desk"],
        "consumable": ["replacement tips / batteries / filters"],
        "alternative": ["the wireless version", "the compact travel version"],
    },
    "apparel": {
        "accessory": ["matching bottoms / layering piece"],
        "upgrade": ["heavier fabric or premium-weight version"],
        "companion": ["the rest of the outfit in the same aesthetic"],
        "consumable": ["care kit (defuzzer, wash)"],
        "alternative": ["the cropped / oversized / long-sleeve cut"],
    },
    "wellness": {
        "accessory": ["carry case", "replacement attachment"],
        "upgrade": ["heated or rechargeable version"],
        "companion": ["what they use in the same routine (mat, oil, eye mask)"],
        "consumable": ["refill / replacement pads"],
        "alternative": ["the manual, no-battery version"],
    },
    "accessories": {
        "accessory": ["protective case", "replacement strap / clasp"],
        "upgrade": ["premium material version"],
        "companion": ["what it is worn or carried with"],
        "consumable": ["cleaning kit"],
        "alternative": ["the minimalist version", "the oversized version"],
    },
    "hobby": {
        "accessory": ["storage case", "starter attachment set"],
        "upgrade": ["pro-grade version"],
        "companion": ["what the same hobby needs next"],
        "consumable": ["blades / refills / material"],
        "alternative": ["the beginner kit version"],
    },
    "toys": {
        "accessory": ["carry bag", "expansion pack"],
        "upgrade": ["the larger / multiplayer version"],
        "companion": ["what gets played with alongside it"],
        "consumable": ["batteries / refill parts"],
        "alternative": ["the travel-size version"],
    },
}

# Anything not in the map still gets a usable frame.
_GENERIC = {
    "accessory": ["what it needs to work properly"],
    "upgrade": ["the premium or larger version"],
    "companion": ["what the same person uses alongside it"],
    "consumable": ["the part that runs out"],
    "alternative": ["a different solution to the same problem"],
}


@dataclass
class Lead:
    axis: str
    prompt: str                 # what to go look for
    why: str                    # why this buyer wants it
    seed_name: str
    category: str

    def render(self) -> str:
        return f"  [{self.axis:11s}] {self.prompt}\n               → {self.why}"


@dataclass
class Expansion:
    seed: models.Product
    leads: list[Lead] = field(default_factory=list)
    mode: str = "offline"
    actor: Optional[str] = None

    def render(self) -> str:
        lines = [f"# Leads from: {self.seed.name}", ""]
        lines.append(
            f"Category {self.seed.category}"
            + (f" · these stay on {self.actor}'s account" if self.actor
               else f" · no actor covers '{self.seed.category}' yet — decide whose "
                    "lane this belongs to before you build content for it"))
        lines.append("")
        by_axis: dict[str, list[Lead]] = {}
        for l in self.leads:
            by_axis.setdefault(l.axis, []).append(l)
        for axis, items in by_axis.items():
            lines.append(f"{axis.upper()} — {AXES.get(axis, '')}")
            lines += [l.render() for l in items]
            lines.append("")
        lines.append("These are LEADS, not products. Each one still has to pass the "
                     "same checks as anything you found by scrolling:")
        lines.append("  1. multiple creators posting it, real 'where can I buy' comments")
        lines.append("  2. a real supplier cost")
        lines.append("  3. the six gates, then a score of 80+")
        lines.append("")
        lines.append("Go look each one up, then `paste` the ones that look real.")
        return "\n".join(lines)


_LLM_SYSTEM = """You expand ONE seed product into adjacent product LEADS for a
TikTok Shop seller.

For each axis you are given, name 2 SPECIFIC, concrete products a real supplier
would list — not categories. "Silicone grip pads for pull-up bars" not "fitness
accessories".

Hard rules:
- The same PERSON who bought the seed must plausibly buy it. Not "also fitness".
- Impulse price range (roughly $10–35 retail). No large or fragile items.
- No branded/trademarked products. No vape, alcohol, weapons, CBD, supplements.
- You do NOT know whether anything sells. Never claim demand, never say
  "trending", "viral", or "hot". These are things to go check.

Reply as plain lines, one per lead, exactly:
axis | product name | why this buyer wants it
No preamble, no numbering, no extra commentary."""


# Natural per-axis reasons. A generic "needs <axis description>" reads like a
# template and gets skimmed; a specific sentence gets acted on.
_WHY = {
    "accessory":  "they need it to use {seed} properly — often bought in the same order",
    "upgrade":    "they already liked {seed}; this is what they buy next",
    "companion":  "reached for in the same moment as {seed}",
    "consumable": "runs out, so they buy it again — repeat revenue, not one-off",
    "alternative": "solves the same problem as {seed} a different way, for people it didn't suit",
}


def _offline_leads(product: models.Product, axes: dict) -> list[Lead]:
    seed = product.name.lower()
    out: list[Lead] = []
    for axis, prompts in axes.items():
        for prompt in prompts:
            out.append(Lead(
                axis=axis, prompt=prompt, seed_name=product.name,
                category=product.category,
                why=_WHY[axis].format(seed=seed)))
    return out


def expand(db: Database, product_id: str, llm=None) -> Optional[Expansion]:
    """Turn one product into adjacent leads. Works offline; uses Claude for
    specific product names when a key is configured."""
    product = db.get_product(product_id)
    if product is None:
        return None

    axes = _CATEGORY_AXES.get(product.category.lower(), _GENERIC)

    # Which actor's account these would live on — expansion should stay in one lane.
    actor_name = None
    try:
        from .creative.persona import actor_for_product, load_personas
        actor = actor_for_product(load_personas(), product.category)
        actor_name = actor.name if actor else None
    except Exception:
        actor_name = None

    exp = Expansion(seed=product, actor=actor_name)

    from .llm import LLMClient, LLMUnavailable
    client = llm if llm is not None else LLMClient()
    if getattr(client, "available", False):
        user = (f"SEED PRODUCT: {product.name} (category: {product.category})\n"
                f"AXES: {', '.join(f'{a} = {d}' for a, d in AXES.items())}")
        try:
            text = client.complete_text(_LLM_SYSTEM, user)
            for line in text.splitlines():
                parts = [p.strip() for p in line.split("|")]
                if len(parts) != 3:
                    continue
                axis, name, why = parts
                axis = axis.lower().strip()
                if axis not in AXES or not name:
                    continue
                exp.leads.append(Lead(axis=axis, prompt=name, why=why,
                                      seed_name=product.name,
                                      category=product.category))
            if exp.leads:
                exp.mode = "llm"
                return exp
        except LLMUnavailable:
            pass          # fall through to the deterministic frame

    exp.leads = _offline_leads(product, axes)
    return exp


def expand_all(db: Database, limit: int = 5) -> list[Expansion]:
    """Expand the highest-scoring products you already have. A winner is the best
    seed there is — you already know that audience buys."""
    scored = []
    for p in db.all_products():
        s = db.latest_score(p.id)
        scored.append((s.total if s else -1, p.id))
    scored.sort(reverse=True)
    out = []
    for _, pid in scored[:limit]:
        e = expand(db, pid)
        if e:
            out.append(e)
    return out
