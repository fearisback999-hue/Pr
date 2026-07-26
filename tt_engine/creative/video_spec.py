"""Composable video specs: every generation is THREE separately-editable parts —
the ACTOR, the PRODUCT, and the PROMPT (plus a shot mode). Edit any one without
disturbing the others, review the assembled result, and fix it BEFORE you generate —
so a bad prompt is corrected on the page, not after burning credits.

The operator's ask, exactly: "three sections per generation — the prompt, the actor,
and the product, all separately editable. If I want to change the prompt, I change
the prompt without restarting the whole video." A spec is a cheap, editable draft;
generation stays the separate confirmed (spend) step, so nothing is wasted on a
draft you're still fixing.
"""

from __future__ import annotations

from typing import Optional

from ..db import Database, models
from .persona import Persona, load_persona, persona_by_slug
from .realism import enhance_prompt, shot_mode_spec


def resolve_actor(actor_slug: str) -> Optional[Persona]:
    """The ACTOR part → a roster persona. Empty falls back to the default bible."""
    if actor_slug:
        return persona_by_slug(actor_slug)
    return load_persona()


def default_prompt(product: models.Product, persona: Optional[Persona],
                   shot_mode: str = "full") -> str:
    """Seed the PROMPT part with a sensible naturalism prompt the operator then edits.
    It's a starting point, not a cage — the whole point is that it's editable."""
    scene = f"a natural, single-take demo of the {product.name.split('(')[0].strip()}"
    rp = enhance_prompt(product, scene, persona=persona)
    return rp.prompt


def assemble(product: models.Product, persona: Optional[Persona], prompt: str,
             shot_mode: str = "full") -> str:
    """Weave the three parts into the exact text a generation would receive — the
    preview you approve. Actor + product are prepended to the editable prompt."""
    spec = shot_mode_spec(shot_mode)
    if persona:
        actor = (persona.casting_spec() if spec["face"]
                 else f"{persona.name} (face NOT shown this mode); "
                      f"identity via wardrobe: {persona.outfit_for(product.id)}")
    else:
        actor = "an ordinary-looking person (no roster actor set)"
    mode_note = "" if spec["face"] else f" FRAMING: {spec['framing']}."
    return (f"ACTOR: {actor}.{mode_note} "
            f"PRODUCT: {product.name} ({product.category}) — shown honestly, matched "
            f"from your real product photo. {prompt}")


def create_spec(db: Database, product_id: str, actor_slug: str = "",
                prompt: str = "", shot_mode: str = "") -> Optional[int]:
    """New draft. Seeds the prompt from the actor+product if none is given, and
    inherits the store's shot-mode default when unset."""
    product = db.get_product(product_id)
    if product is None:
        return None
    shot_mode = shot_mode or db.get_setting("shot_mode", "full")
    persona = resolve_actor(actor_slug)
    if not actor_slug and persona:
        actor_slug = persona.slug
    if not prompt:
        prompt = default_prompt(product, persona, shot_mode)
    return db.create_video_spec(product_id, actor_slug, prompt, shot_mode)


def render_spec(db: Database, spec: dict) -> str:
    """The three editable parts, the assembled preview, and the review contract."""
    product = db.get_product(spec["product_id"])
    persona = resolve_actor(spec["actor_slug"])
    pname = product.name if product else spec["product_id"]
    actor_line = (f"{persona.name} ({persona.account or 'no account set'})"
                  if persona else f"'{spec['actor_slug']}' — NOT in the roster")
    lines = [
        f"# Video spec #{spec['id']} — {pname}  [{spec['status']}]",
        "",
        "Three separately-editable parts. Edit any one; the others stay put. Nothing "
        "is generated yet — no credits spent.",
        "",
        f"## 1. ACTOR   (edit: `draft set {spec['id']} --actor <slug>`)",
        f"   {actor_line}",
        f"## 2. PRODUCT (edit: `draft set {spec['id']} --product <id>`)",
        f"   {pname} ({product.category if product else '?'})",
        f"## 3. PROMPT  (edit: `draft set {spec['id']} --prompt \"...\"`)",
        f"   {spec['prompt']}",
        f"## shot mode: {spec['shot_mode']}   (edit: `draft set {spec['id']} --mode <mode>`)",
        "",
        "## Assembled preview (what a generation would receive)",
        "```",
        assemble(product, persona, spec["prompt"], spec["shot_mode"]) if product
        else "(product missing — fix the PRODUCT part)",
        "```",
        "",
    ]
    warns = []
    if product is None:
        warns.append("PRODUCT not found — fix it before generating.")
    if persona is None:
        warns.append(f"ACTOR '{spec['actor_slug']}' isn't in the roster (`personas`) "
                     "— pick a real actor slug.")
    if warns:
        lines += ["⚠ " + w for w in warns] + [""]
    lines += [
        f"Fix any part above, then `draft approve {spec['id']}` when it's right. "
        "Generation is the separate confirmed step that spends credits — so you only "
        "ever pay for a spec you've already reviewed."
    ]
    return "\n".join(lines) + "\n"


def render_spec_list(db: Database, specs: list[dict]) -> str:
    if not specs:
        return "No video specs yet. Create one: `draft new <product-id> [--actor <slug>]`\n"
    lines = ["# Video specs (composable drafts)", ""]
    for s in specs:
        lines.append(f"  #{s['id']:<4} {s['product_id']:<16} actor={s['actor_slug'] or '(default)':<10} "
                     f"mode={s['shot_mode']:<10} [{s['status']}]")
    lines.append("")
    lines.append("`draft show <id>` to review/edit the three parts before generating.")
    return "\n".join(lines) + "\n"
