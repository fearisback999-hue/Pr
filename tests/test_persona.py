"""The creator bible: parsing, validation, and the anti-drift wiring into the
realism layer. Invariants: the shipped bible parses production-ready; the master
description opens the casting block verbatim; one outfit per product batch; the
persona never leaves her own rooms; a missing bible degrades gracefully."""

from tt_engine.creative import load_persona, validate_persona
from tt_engine.creative import realism
from tt_engine.creative.realism import SETTINGS, enhance_prompt, prompts_for_scripts
from tt_engine.db import models


def _product(pid="P-DOGCALMVEST"):
    return models.Product(id=pid, name="Dog Calming Vest", category="pet")


def _maya():
    p = load_persona()
    assert p is not None, "the shipped bible must always parse"
    return p


# ── parsing ─────────────────────────────────────────────────────────────────────
def test_shipped_bible_parses_complete_and_production_ready():
    p = _maya()
    assert p.name == "Maya"
    assert len(p.master_description) > 100          # a face, not a stub
    assert len(p.outfits) >= 2
    assert all(s in SETTINGS for s in p.settings)   # her rooms are engine bundles
    assert len(p.speech_quirks) >= 2
    assert p.forbidden                              # the never-changes list exists
    assert p.voice_reference
    assert validate_persona(p) == []                # zero production warnings


def test_wrapped_markdown_lines_parse_whole():
    """Values that wrap across lines (jewelry, the third quirk) must not truncate."""
    p = _maya()
    assert "never gains pieces" in p.jewelry
    assert any("so… yeah" in q for q in p.speech_quirks)


def test_missing_bible_degrades_gracefully(tmp_path):
    assert load_persona(str(tmp_path / "nope.md")) is None
    warnings = validate_persona(None)
    assert any("CREATOR.md" in w for w in warnings)


def test_bible_without_a_face_is_no_bible(tmp_path):
    f = tmp_path / "thin.md"
    f.write_text("## identity\n- name: Ghost\n")   # no master-description
    assert load_persona(str(f)) is None


# ── casting + outfit determinism ────────────────────────────────────────────────
def test_casting_spec_carries_master_forbidden_and_soul():
    p = _maya()
    spec = p.casting_spec("SOUL-42")
    assert "Maya, the store's recurring persona (Soul ID SOUL-42)" in spec
    assert p.master_description in spec             # verbatim — the anti-drift anchor
    assert "NEVER CHANGES" in spec and "mole" in spec


def test_outfit_is_stable_per_product_batch():
    p = _maya()
    assert p.outfit_for("P-X") == p.outfit_for("P-X")     # one outfit per batch
    outfits = {p.outfit_for(f"P-{i}") for i in range(12)}
    assert len(outfits) > 1                               # the closet rotates BETWEEN products
    assert all("jewelry:" in o for o in outfits)          # jewelry pinned everywhere


# ── realism wiring ──────────────────────────────────────────────────────────────
def test_enhanced_prompt_carries_the_full_persona():
    p = _maya()
    rp = enhance_prompt(_product(), "demo scene", persona=p, soul_id="SOUL-42")
    assert p.master_description in rp.prompt              # verbatim, every prompt
    assert "WARDROBE (exact" in rp.prompt
    assert rp.layers["wardrobe"] == p.outfit_for("P-DOGCALMVEST")
    assert rp.layers["setting"] in p.settings             # never leaves her rooms
    assert rp.layers["speech"] in p.speech_quirks         # her quirks, not the pool
    assert "Soul ID SOUL-42" in rp.prompt


def test_persona_setting_pool_is_respected_across_indices():
    p = _maya()
    for i in range(10):
        rp = enhance_prompt(_product(), "demo scene", index=i, persona=p)
        assert rp.layers["setting"] in p.settings


def test_without_persona_generic_path_is_unchanged():
    rp = enhance_prompt(_product(), "demo scene", soul_id="")
    assert "wardrobe" not in rp.layers
    assert rp.layers["casting"] in realism.CASTING
    assert rp.layers["speech"] in realism.SPEECH


def test_prompts_for_scripts_autoloads_the_bible():
    """build_pack's path: the batch carries Maya without anyone passing her."""
    from tt_engine.creative import build_pack
    from tt_engine.psychology import analyze
    product = _product()
    psych = analyze("Dog Calming Vest", ["my rescue finally slept"], "pet")
    pack = build_pack(product, psych, n_hooks=8, n_concepts=8, n_scripts=3)
    p = _maya()
    for rp in pack.realism_prompts:
        assert "Maya" in rp.prompt
        assert rp.layers["wardrobe"] == p.outfit_for(product.id)  # whole batch, one outfit
        assert rp.layers["setting"] in p.settings
