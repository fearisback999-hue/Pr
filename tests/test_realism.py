"""Naturalism prompt layer: phone-real craft with the disclosure line hard-wired.
The module must make labeled AI content feel native — and must NOT be usable as a
disclosure-evasion tool."""

from tt_engine.creative import (
    ARTIFACT_CHECKLIST,
    build_pack,
    enhance_prompt,
    prompts_for_scripts,
    render_qa_checklist,
)
from tt_engine.creative import realism
from tt_engine.db import models
from tt_engine.psychology import analyze


def _product():
    return models.Product(id="P-DOGCALMVEST", name="Dog Calming Vest", category="pet")


def _psych():
    return analyze("Dog Calming Vest", ["my rescue finally slept, obsessed"], "pet")


def test_prompt_composes_every_naturalism_layer():
    rp = enhance_prompt(_product(), "They put the vest on the dog during a thunderstorm.")
    for layer in ("camera", "lighting", "skin", "motion", "behavior",
                  "environment", "audio", "lens", "interaction"):
        assert layer in rp.layers and rp.layers[layer]
        assert rp.layers[layer] in rp.prompt
    assert "9:16" in rp.prompt
    assert "NOT cinematic" in rp.prompt


def test_negative_prompt_bans_the_plastic_look():
    rp = enhance_prompt(_product(), "demo scene")
    for banned in ("studio lighting", "airbrushed skin", "floating product",
                   "robotic motion", "CGI texture"):
        assert banned in rp.negative


def test_disclosure_is_wired_into_every_rendered_prompt():
    """The line the module holds: naturalism is craft, not disclosure evasion."""
    rp = enhance_prompt(_product(), "demo scene")
    rendered = rp.render()
    assert "label as AI-generated" in rendered
    # And the module's own guidance never sells 'undetectable':
    import inspect
    source = inspect.getsource(realism)
    assert "undetectable" not in source.lower()
    assert "requires disclosure" in source or "refuses assets missing" in source


def test_prompts_are_deterministic_per_product_and_scene():
    a = enhance_prompt(_product(), "same scene", index=2)
    b = enhance_prompt(_product(), "same scene", index=2)
    assert a.prompt == b.prompt
    c = enhance_prompt(_product(), "same scene", index=3)
    assert c.prompt != a.prompt          # variety across indices


def test_prompts_for_scripts_uses_script_beats():
    pack_scripts_needed = 3
    product, psych = _product(), _psych()
    pack = build_pack(product, psych, n_hooks=8, n_concepts=8,
                      n_scripts=pack_scripts_needed)
    rps = prompts_for_scripts(product, pack.paid_scripts, n=3)
    assert len(rps) == 3
    for rp, script in zip(rps, pack.paid_scripts):
        assert script.cta in rp.scene    # the actual beat drives the scene


def test_qa_checklist_covers_the_classic_artifacts():
    text = render_qa_checklist()
    joined = " ".join(ARTIFACT_CHECKLIST)
    for artifact in ("five fingers", "blinking", "floats", "lip-sync"):
        assert artifact in joined
    assert "disclosure" in text          # policy item present and non-negotiable
    assert "export-creatives" in text


def test_pack_render_includes_naturalism_prompts_and_checklist():
    pack = build_pack(_product(), _psych(), n_hooks=8, n_concepts=8, n_scripts=5)
    assert len(pack.realism_prompts) == 5
    text = pack.render()
    assert "naturalism-enhanced" in text
    assert "Pre-export QA" in text
    assert "craft and honesty are compatible" in text


# ── v2: coherence, budget, beats, persona continuity ────────────────────────


def test_setting_is_coherent_not_independently_sampled():
    """Light, clutter, sound, and behavior must all come from ONE setting bundle —
    'golden-hour car window' + 'bedroom laundry' is itself an AI tell."""
    for idx in range(8):
        rp = enhance_prompt(_product(), "demo scene", index=idx)
        s = realism.SETTINGS[rp.layers["setting"]]
        assert rp.layers["lighting"] == s["lighting"]
        assert rp.layers["environment"] == s["environment"]
        assert rp.layers["audio"] == s["audio"]
        assert rp.layers["behavior"] in s["behaviors"]


def test_explicit_setting_override_is_respected():
    rp = enhance_prompt(_product(), "demo scene", setting="car-parked")
    assert rp.layers["setting"] == "car-parked"
    assert "parked car interior" in rp.prompt


def test_imperfections_are_budgeted_to_exactly_two():
    """Stacking every artifact reads as a filter; real phone clips have 2–3 tells."""
    for idx in range(8):
        rp = enhance_prompt(_product(), "demo scene", index=idx)
        t1, t2 = rp.layers["lens"].split("; ")
        assert t1 in realism.TEXTURES and t2 in realism.TEXTURES
        assert t1 != t2
        assert "exactly these two" in rp.prompt
        # No third texture sneaks into the prompt outside the budget line.
        others = [t for t in realism.TEXTURES if t not in (t1, t2)]
        assert not any(t in rp.prompt for t in others)


def test_beats_produce_a_timeline_with_per_beat_cameras():
    rp = enhance_prompt(
        _product(), "full scene", index=1,
        hook_beat="POV: your dog during a storm.",
        demo_beat="They velcro the vest on and the dog settles.",
        cta_beat="Link's below if your dog needs this.",
    )
    assert "TIMELINE — 0–3s" in rp.prompt
    assert rp.layers["camera_demo"] in rp.prompt        # demo gets its own grip
    assert rp.layers["camera"] != rp.layers["camera_demo"]
    assert "final 3s" in rp.prompt
    # Single-beat calls stay simple — no fake timeline.
    plain = enhance_prompt(_product(), "just one beat", index=1)
    assert "TIMELINE" not in plain.prompt
    assert "SCENE (camera:" in plain.prompt


def test_speech_disfluency_and_continuity_are_directed():
    rp = enhance_prompt(_product(), "demo scene")
    assert rp.layers["speech"] in realism.SPEECH
    assert "CONTINUITY: same room, same light, same outfit" in rp.prompt


def test_soul_id_keeps_the_store_persona_stable():
    rp = enhance_prompt(_product(), "demo scene", soul_id="SOUL-42")
    assert "Soul ID SOUL-42" in rp.prompt
    assert "recurring persona" in rp.layers["casting"]
    # Without a Soul ID, a consistent casting spec still anchors the look.
    anon = enhance_prompt(_product(), "demo scene", soul_id="")
    assert anon.layers["casting"] in realism.CASTING


def test_prompts_for_scripts_carry_beats_and_soul():
    product, psych = _product(), _psych()
    pack = build_pack(product, psych, n_hooks=8, n_concepts=8, n_scripts=3)
    rps = prompts_for_scripts(product, pack.paid_scripts, n=3, soul_id="SOUL-42")
    for rp, script in zip(rps, pack.paid_scripts):
        assert "TIMELINE — 0–3s" in rp.prompt
        assert script.first_3s in rp.prompt              # hook beat lands at 0–3s
        assert "Soul ID SOUL-42" in rp.prompt


def test_qa_checklist_v2_covers_phone_check_and_continuity():
    joined = " ".join(ARTIFACT_CHECKLIST)
    assert "ON A PHONE" in joined                        # judge it where it will live
    assert "disfluency" in joined
    assert "continuity" in joined or "same room" in joined
