from tt_engine.creative import (
    FORMATS,
    HOOK_TYPES,
    HiggsfieldClient,
    build_kit,
    generate_hooks,
    generate_scripts,
    review_text,
)
from tt_engine.db import models
from tt_engine.psychology import analyze


def _psych():
    return analyze(
        "Scalp Massager Pro",
        ["this melts my tension away, obsessed", "the tingles are insane!"],
        "beauty",
    )


def test_offline_hooks_count_types_and_length():
    hooks = generate_hooks("Scalp Massager Pro", _psych(), n=20)
    assert len(hooks) == 20
    assert all(h.type in HOOK_TYPES for h in hooks)
    # Each hook is <= 10 words (thumb-stopping constraint, Part 7).
    assert all(len(h.text.split()) <= 10 for h in hooks)
    # All four hook types are represented.
    assert {h.type for h in hooks} == set(HOOK_TYPES)


def test_offline_scripts_have_three_beats():
    psych = _psych()
    hooks = generate_hooks("Scalp Massager Pro", psych, n=20)
    scripts = generate_scripts("Scalp Massager Pro", psych, hooks, n=10)
    assert len(scripts) == 10
    for s in scripts:
        assert s.first_3s and s.middle and s.cta and s.emotion


def test_compliance_flags_fabricated_and_medical_claims():
    bad = review_text("100% guaranteed to cure your anxiety — verified buyer")
    assert not bad.ok
    assert any("cure" in i or "guarantee" in i for i in bad.issues)
    clean = review_text("Melts tension after a long day — try it tonight")
    assert clean.ok
    assert clean.requires_disclosure  # AI content still needs disclosure


def test_build_kit_offline_is_compliant_and_briefable():
    product = models.Product(id="P", name="Scalp Massager Pro", category="beauty")
    kit = build_kit(product, _psych(), variations=24)
    assert len(kit.hooks) == 20
    assert len(kit.scripts) == 10
    assert kit.compliant  # templated offline copy carries no risky claims
    text = kit.brief_text()
    assert "Psychological spine" in text
    assert "Hooks" in text


def test_higgsfield_plan_offline():
    product = models.Product(id="P", name="Scalp Massager Pro", category="beauty")
    kit = build_kit(product, _psych(), variations=24)
    hf = HiggsfieldClient(api_key="")  # offline
    assert not hf.available
    creatives = hf.push(kit)  # offline push returns the plan
    assert len(creatives) == 24
    assert all(c.status == "briefed" for c in creatives)
    assert {c.format for c in creatives}.issubset(set(FORMATS))
