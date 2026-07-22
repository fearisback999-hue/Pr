"""Clothing fit-check runbook: the apparel try-on method. Invariants — apparel
routes to the fit-check (not the generic hook/demo/CTA runbook); the garment is
SWAPPED from the operator's real photos with front/back angles; the model reads
aspirational but stays the pinned persona; the dedicated-account strategy is stated;
break-even is computed from REAL margin (never parroted); disclosure stays on."""

import math

import pytest

from tt_engine.creative import (
    build_fit_check,
    build_pack,
    build_runbook,
    garment_swap_prompt,
    load_persona,
    style_for,
)
from tt_engine.creative.clothing import (
    CLIPS_PER_MONTH,
    GEN_PLAN_COST,
    FitCheckRunbook,
)
from tt_engine.db import models
from tt_engine.economics import compute_economics, unknown_economics
from tt_engine.psychology import analyze


def _jeans():
    return models.Product(id="P-JEANS", name="High-Waist Wide-Leg Jeans",
                          category="clothing")


def _pack(product):
    psych = analyze(product.name, ["fits perfectly, love the denim"], "apparel")
    return build_pack(product, psych, n_hooks=8, n_concepts=8, n_scripts=5)


# ── the apparel style carries the new fields ────────────────────────────────────
def test_apparel_style_flags_garment_swap_and_dedicated_account():
    st = style_for("clothing")
    assert st.garment_swap is True
    assert "creator-style account" in st.dedicated_account
    assert "not" in st.dedicated_account.lower()          # not the brand account
    assert st.avatar_note and "objectifying" in st.avatar_note   # tasteful bar stated
    # A non-apparel category doesn't get garment swap.
    assert style_for("gadget").garment_swap is False


# ── garment swap prompt ─────────────────────────────────────────────────────────
def test_garment_swap_references_real_clothing_and_angles():
    ip = garment_swap_prompt(_jeans(), persona=load_persona(),
                             garment_angles=("front", "back"))
    assert ip.kind == "garment-swap"
    assert "EXACT garment from the attached clothing photo" in ip.prompt
    assert "do not redesign it" in ip.prompt
    assert "front, back" in ip.prompt
    assert "clothing photo(s): front, back" in ip.attach
    assert "model reference image" in ip.attach
    # iPhone realism rules still hold.
    assert "iPhone 15 Pro" in ip.prompt
    assert "photorealism" in ip.negative
    # Face stays pinned to the persona.
    assert "same person, no drift" in ip.prompt


# ── routing: apparel → fit-check ────────────────────────────────────────────────
def test_build_runbook_routes_clothing_to_fit_check():
    product = _jeans()
    rb = build_runbook(product, _pack(product), n_ads=2,
                       economics=compute_economics(44.99, 11.0, 3.0))
    assert isinstance(rb, FitCheckRunbook)
    assert len(rb.clips) == 2
    # Non-apparel still gets the generic ProductionRunbook.
    from tt_engine.creative import ProductionRunbook
    gp = models.Product(id="P-G", name="Mini Label Printer", category="gadget")
    gr = build_runbook(gp, _pack(gp), n_ads=1)
    assert isinstance(gr, ProductionRunbook)


def test_fit_check_clips_have_the_eight_second_arc():
    product = _jeans()
    rb = build_fit_check(product, _pack(product).hooks, persona=load_persona(),
                         economics=compute_economics(44.99, 11.0, 3.0), n_clips=2)
    for clip in rb.clips:
        labels = [lbl for lbl, _ in clip.beats]
        assert any("walk in" in l for l in labels)
        assert any("turn" in l for l in labels)
        assert any("detail" in l for l in labels)
        assert any("CTA" in l for l in labels)
        assert "front, back" in clip.garment_frame.prompt


# ── break-even is REAL, never parroted ──────────────────────────────────────────
def test_breakeven_computed_from_true_margin():
    product = _jeans()
    econ = compute_economics(44.99, 11.0, 3.0)   # ~$27 true profit/unit
    rb = build_fit_check(product, _pack(product).hooks, economics=econ, n_clips=1)
    from tt_engine.economics.optimizer import DEFAULT_PAYMENT_RATE, true_economics
    te = true_economics(44.99, 11.0, 3.0, DEFAULT_PAYMENT_RATE, 0.0)
    expected = math.ceil(GEN_PLAN_COST / te.true_profit)
    assert f"~{expected} sale" in rb.breakeven_note
    assert "2–3" not in rb.breakeven_note        # not parroted


def test_breakeven_refuses_without_landed_cost():
    product = _jeans()
    rb = build_fit_check(product, _pack(product).hooks,
                         economics=unknown_economics(44.99), n_clips=1)
    assert "add a real supplier cost" in rb.breakeven_note
    assert "guess" in rb.breakeven_note
    # And with no economics at all.
    rb2 = build_fit_check(product, _pack(product).hooks, economics=None, n_clips=1)
    assert "add a real supplier cost" in rb2.breakeven_note


def test_breakeven_flags_negative_margin():
    product = _jeans()
    # Sell below cost → negative true margin.
    rb = build_fit_check(product, _pack(product).hooks,
                         economics=compute_economics(12.0, 11.0, 3.0), n_clips=1)
    assert "loses money per sale" in rb.breakeven_note


# ── render: strategy + guardrails on the page ───────────────────────────────────
def test_render_states_account_strategy_economics_and_disclosure():
    product = _jeans()
    rb = build_fit_check(product, _pack(product).hooks,
                         economics=compute_economics(44.99, 11.0, 3.0), n_clips=1)
    text = rb.render()
    assert "creator-style account" in text and "NOT the brand" in text
    assert f"${GEN_PLAN_COST:.0f}/mo" in text
    assert f"~{CLIPS_PER_MONTH} clips" in text
    assert "AI-generated" in text                 # disclosure
    assert "sizing honesty" in text or "fit/sizing honesty" in text.lower() \
        or "Fit/sizing honesty" in text
    assert "Maya" in text                          # the pinned persona
