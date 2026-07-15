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
