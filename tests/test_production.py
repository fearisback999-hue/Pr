"""The production runbook: the keyframe-first Seedance pipeline, encoded from the
practitioner workflow. Invariants under test — the three image rules (iPhone 15 Pro,
flaws on person AND scene, never 'photorealism'); one room per ad; clean spoken
lines; the persona threads through; disclosure and 'plans-not-spends' stay on."""

from tt_engine.creative import (
    actor_image_prompt,
    build_pack,
    build_runbook,
    load_persona,
    scene_frame_prompt,
    scene_video_prompt,
)
from tt_engine.creative import realism
from tt_engine.creative.production import _spoken
from tt_engine.db import models
from tt_engine.psychology import analyze


def _product(pid="P-DOGCALMVEST"):
    return models.Product(id=pid, name="Dog Calming Vest", category="pet")


def _pack(product):
    psych = analyze(product.name, ["my rescue finally slept"], "pet")
    return build_pack(product, psych, n_hooks=8, n_concepts=8, n_scripts=5)


# ── image prompts: the three practitioner rules ─────────────────────────────────
def test_actor_prompt_follows_the_three_rules():
    ip = actor_image_prompt(load_persona())
    assert ip.kind == "actor"
    assert "iPhone 15 Pro" in ip.prompt
    assert "flaws to BOTH" in ip.prompt              # person AND scenery
    assert "photorealism" in ip.negative             # banned, not requested
    assert "photorealism" not in ip.prompt
    # The persona's face and forbidden list anchor the actor.
    p = load_persona()
    assert p.master_description.split(",")[0] in ip.prompt
    assert "never changes" in ip.prompt


def test_scene_frame_attaches_reference_and_product_when_shown():
    p = load_persona()
    with_prod = scene_frame_prompt(_product(), "shows the vest on the dog",
                                   persona=p, needs_product=True)
    assert "iPhone 15 Pro" in with_prod.prompt
    assert "SAME actor" in with_prod.prompt
    assert "product photo" in with_prod.attach
    assert "photorealism" in with_prod.negative

    no_prod = scene_frame_prompt(_product(), "talks to camera",
                                 persona=p, needs_product=False)
    assert "product photo" not in no_prod.attach
    assert "actor reference image" in no_prod.attach


def test_scene_frame_stays_in_personas_rooms():
    p = load_persona()
    for i in range(8):
        ip = scene_frame_prompt(_product(), "a beat", persona=p, index=i)
        env = realism.SETTINGS
        assert any(env[s]["environment"] in ip.prompt for s in p.settings)


def test_scene_video_is_frame_first_with_dialogue_and_no_drift():
    vp = scene_video_prompt(_product(), "velcros the vest on", dialogue="watch this",
                            persona=load_persona())
    assert "Animate the attached starting frame" in vp
    assert 'says, naturally: "watch this"' in vp
    assert "IDENTICAL to the starting frame" in vp
    # No dialogue → no spoken-line clause.
    silent = scene_video_prompt(_product(), "shows the seams", dialogue="")
    assert "says, naturally" not in silent


# ── spoken-line hygiene ─────────────────────────────────────────────────────────
def test_spoken_strips_stage_directions():
    assert _spoken("Why is everyone obsessed (creator holds it up, close on face)") \
        == "Why is everyone obsessed"
    assert _spoken("Tap the cart.") == "Tap the cart."


# ── the runbook ─────────────────────────────────────────────────────────────────
def test_runbook_one_room_per_ad():
    product = _product()
    rb = build_runbook(product, _pack(product), n_ads=3)
    p = load_persona()
    envs = {s["environment"] for s in realism.SETTINGS.values()}
    for ad in rb.ads:
        # Every scene frame in one ad names the SAME room.
        rooms_in_ad = [next(e for e in envs if e in sc.frame.prompt)
                       for sc in ad.scenes]
        assert len(set(rooms_in_ad)) == 1


def test_runbook_beats_map_to_talk_demo_talk():
    product = _product()
    rb = build_runbook(product, _pack(product), n_ads=1)
    scenes = rb.ads[0].scenes
    assert [s.label for s in scenes] == ["hook (0–3s)", "demo", "CTA (final)"]
    assert scenes[0].on_camera and scenes[2].on_camera      # hook + CTA are spoken
    assert not scenes[1].on_camera and scenes[1].shows_product  # demo shows product
    # Spoken lines carry no stage directions.
    assert "(" not in scenes[0].dialogue
    assert scenes[1].dialogue == ""


def test_runbook_renders_full_pipeline_and_guardrails():
    product = _product()
    rb = build_runbook(product, _pack(product), n_ads=2)
    text = rb.render()
    for marker in ("Step 1 — Generate the actor", "first-frame image",
                   "Animate (Seedance", "video-to-voice", "text-to-voice",
                   "CapCut", "Maya"):
        assert marker in text
    # The non-negotiables stay on the page.
    assert "AI-generated" in text
    assert "never spends" in text or "never fabricates" in text
    assert "export-creatives" in text or "refuses assets" in text


def test_runbook_without_persona_still_works(tmp_path):
    """No creator bible → generic actor, runbook still renders (graceful)."""
    product = _product()
    pack = _pack(product)
    rb = build_runbook(product, pack, persona=None, n_ads=1)
    # build_runbook auto-loads the shipped bible; force the no-bible path directly.
    from tt_engine.creative.realism import actor_image_prompt as aip
    ip = aip(persona=None)
    assert "iPhone 15 Pro" in ip.prompt
    assert ip.kind == "actor"
