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


def create_variants(db: Database, product_id: str, actor_slugs=None,
                    prompt: str = "", shot_mode: str = "") -> list[int]:
    """Demographic testing the legitimate way: one editable spec per actor for the
    SAME product, so you can A/B the same concept across different faces (young/old,
    etc.) using YOUR OWN roster — not by cloning anyone's video. Each variant seeds
    its own persona-appropriate prompt unless you pass a shared one. Returns the new
    spec ids (empty if the product is unknown)."""
    from .persona import load_personas
    if db.get_product(product_id) is None:
        return []
    if actor_slugs:
        slugs = [s.strip() for s in actor_slugs if s and s.strip()]
    else:
        slugs = [p.slug for p in load_personas()]
    out: list[int] = []
    for slug in slugs:
        sid = create_spec(db, product_id, actor_slug=slug, prompt=prompt,
                          shot_mode=shot_mode)
        if sid is not None:
            out.append(sid)
    return out


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


class AlreadyGenerated(RuntimeError):
    """This spec already has a creative in flight or landed. Generating again would
    pay twice and overwrite the first job's id — the receipt you need to recover it."""


def generate_from_spec(db: Database, spec_id: int, confirm: bool = False, mcp=None):
    """Generate the ONE video this spec describes — from the actor + product + the
    PROMPT you already edited and reviewed. Closes the loop: you fix the spec, approve
    it, then generate exactly that. Same guardrails as every generation:

      • must be APPROVED first (you reviewed it — no generating an unreviewed draft)
      • the briefed plan is saved before the money gate (never lost)
      • with a key configured, nothing generates without confirm=True
      • the AIGC disclosure is written into the asset metadata
      • an unwired SDK fails cleanly (GenerationNotWired), never a raw crash
    """
    from . import spend
    from .compliance import DISCLOSURE
    from .mcp_client import (
        ConfirmationRequired,
        GenerationNotWired,
        GenerationResult,
        HiggsfieldMCP,
    )
    from ..config import CONFIG

    spec = db.video_spec(spec_id)
    if spec is None:
        raise ValueError(f"no video spec #{spec_id}")
    if spec["status"] not in ("approved", "generated"):
        raise ValueError(
            f"spec #{spec_id} is '{spec['status']}' — review and `draft approve "
            f"{spec_id}` first. You only ever generate a spec you've looked at.")
    product = db.get_product(spec["product_id"])
    if product is None:
        raise ValueError(f"spec #{spec_id}: product '{spec['product_id']}' is gone — "
                         "fix the PRODUCT part before generating.")
    persona = resolve_actor(spec["actor_slug"])
    prompt = assemble(product, persona, spec["prompt"], spec["shot_mode"])
    soul = (CONFIG.higgsfield_soul_id or (persona.slug if persona else "")) or ""

    # The creative id is derived from the spec id, so a second generate OVERWRITES the
    # first — paying twice and destroying the job id needed to collect what the first
    # payment already bought. Refuse while a job is in flight or already landed.
    existing = next((c for c in db.all_creatives() if c.id == f"SPEC-{spec_id}"), None)
    if existing is not None and existing.status in ("generating", "ready", "exported",
                                                    "posted"):
        raise AlreadyGenerated(
            f"spec #{spec_id} already has a creative at status '{existing.status}'"
            + (f" (job {existing.meta['job_id']})" if existing.meta.get("job_id") else "")
            + ". Generating again would pay a second time and overwrite the first job's "
            "id. If it never landed, run `creative-recover` to collect what you already "
            "paid for. To make a genuinely different video, create a new spec.")

    creative = models.Creative(
        id=f"SPEC-{spec_id}", product_id=product.id, format="Spec",
        hook=spec["prompt"][:80], hook_type="spec", soul_id=soul, asset_url=None,
        status="briefed",
        meta={"aigc_disclosure": DISCLOSURE, "prompt": prompt,
              "actor": spec["actor_slug"], "shot_mode": spec["shot_mode"]},
    )
    db.upsert_creative(creative)                        # persist the plan FIRST (free)

    mcp = mcp or HiggsfieldMCP()
    if mcp.available and not confirm:
        raise ConfirmationRequired(
            f"spec #{spec_id} is ready and Higgsfield is configured. Generation spends "
            "credits — re-run with --confirm to actually generate this video.\n"
            f"  SPEND IF CONFIRMED: {spend.estimate(1).render()}")

    if not mcp.available:
        return GenerationResult(
            creatives=[creative], dry_run=True,
            notes=[f"spec #{spec_id} planned (dry-run) — the assembled prompt is saved. "
                   "Set HIGGSFIELD_API_KEY (+ higgsfield-client) to generate for real, "
                   "or run it from a Claude Code session with the Higgsfield MCP."])

    spend.guard(1)                                      # ceiling applies to one clip too

    # Live path: one job. The assembled prompt lives on creative.meta["prompt"] — an
    # SDK wiring reads it there. Until then submit() raises → clean GenerationNotWired.
    try:
        job_id = mcp.submit(None, creative)             # type: ignore[arg-type]
    except NotImplementedError as e:
        raise GenerationNotWired(
            f"spec #{spec_id}: Higgsfield is configured but submit/poll isn't wired — "
            "the assembled prompt is saved as 'briefed'. Wire HiggsfieldMCP.submit/poll "
            f"(it reads creative.meta['prompt']), or generate from a connected MCP. ({e})"
        ) from e
    creative.status, creative.meta["job_id"] = "generating", job_id
    db.upsert_creative(creative)
    db.update_video_spec(spec_id, status="generated")
    return GenerationResult(creatives=[creative], dry_run=False,
                            notes=[f"spec #{spec_id} submitted (job {job_id})."])


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
