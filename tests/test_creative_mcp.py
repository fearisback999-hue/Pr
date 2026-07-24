"""Phase 2 Higgsfield generation: dry-run, confirmation guardrail, AIGC disclosure,
Soul ID consistency, and the export block.

Also pins the July-2026 research fix: this project no longer speaks a fabricated,
unauthenticated JSON-RPC "MCP" protocol over raw urllib (that was never real — Higgsfield's
actual hosted MCP is OAuth-only, and scripted access goes through the official
higgsfield_client SDK). submit()/poll() are honest NotImplementedError stubs until wired
against a real account, matching this repo's own convention for unverified integrations
(see KalodataFeed.fetch(), HiggsfieldClient.push())."""

import pytest

from tt_engine import pipeline, seed
from tt_engine.config import CONFIG
from tt_engine.creative import (
    ConfirmationRequired,
    HiggsfieldMCP,
    build_kit,
    export_creatives,
    generate_batch,
    soul_consistency,
)
from tt_engine.creative.brief import FORMATS
from tt_engine.db import Database, models
from tt_engine.psychology import analyze


def _db(tmp_path):
    return Database(str(tmp_path / "mcp.db"))


def _kit(soul_id="SOUL-STORE-1"):
    product = models.Product(id="P-X", name="Scalp Massager Pro", category="beauty")
    psych = analyze(product.name, ["obsessed, melts my tension!"], "beauty")
    return build_kit(product, psych, variations=10, soul_id=soul_id)


class FakeMCP(HiggsfieldMCP):
    """In-memory double: forces the live path without a real key/SDK, and every
    submitted job completes on first poll."""
    def __init__(self):
        super().__init__(api_key="fake-key-for-tests")
        self.submitted = []

    @property
    def available(self):
        return True

    def submit(self, kit, c):
        self.submitted.append(c.id)
        return f"job-{c.id}"

    def poll(self, job_id):
        return "ready", f"https://assets.test/{job_id}.mp4"


def test_dry_run_plans_batch_with_disclosure_metadata(tmp_path):
    with _db(tmp_path) as db:
        db.upsert_product(models.Product(id="P-X", name="Scalp Massager Pro", category="beauty"))
        result = generate_batch(db, _kit(), mcp=HiggsfieldMCP())  # no key/SDK configured
        assert result.dry_run
        assert len(result.creatives) == 10
        stored = db.creatives_for("P-X")
        assert len(stored) == 10
        for c in stored:
            assert c.status == "briefed"
            assert c.meta["aigc_disclosure"]          # non-negotiable
            assert c.meta["format_tag"] == c.format   # format tags saved
            assert c.format in FORMATS


def test_confirmation_required_when_mcp_configured(tmp_path):
    with _db(tmp_path) as db:
        db.upsert_product(models.Product(id="P-X", name="Scalp Massager Pro", category="beauty"))
        with pytest.raises(ConfirmationRequired, match="spends money"):
            generate_batch(db, _kit(), confirm=False, mcp=FakeMCP())


def test_confirmed_generation_polls_to_ready(tmp_path):
    with _db(tmp_path) as db:
        db.upsert_product(models.Product(id="P-X", name="Scalp Massager Pro", category="beauty"))
        mcp = FakeMCP()
        result = generate_batch(db, _kit(), confirm=True, mcp=mcp, poll_interval=0)
        assert not result.dry_run
        assert len(mcp.submitted) == 10
        for c in db.creatives_for("P-X"):
            assert c.status == "ready"
            assert c.asset_url.endswith(".mp4")
            assert c.meta["job_id"].startswith("job-")
            assert c.meta["aigc_disclosure"]


def test_briefed_plan_persists_before_the_confirm_gate(tmp_path):
    """With a key configured (available) but no confirm, generation must still SAVE
    the briefed plan before raising — so build-creative advances the pipeline instead
    of getting stuck re-proposing forever."""
    from tt_engine.creative import ConfirmationRequired
    with _db(tmp_path) as db:
        db.upsert_product(models.Product(id="P-X", name="Scalp Massager Pro", category="beauty"))
        with pytest.raises(ConfirmationRequired):
            generate_batch(db, _kit(), confirm=False, mcp=FakeMCP())
        stored = db.creatives_for("P-X")
        assert len(stored) == 10                        # plan saved despite the raise
        assert all(c.status == "briefed" for c in stored)


def test_unwired_sdk_raises_clean_generation_not_wired(tmp_path):
    """A real key + the honest NotImplementedError stub → a clean GenerationNotWired,
    not a raw crash; the briefed plan is preserved."""
    from tt_engine.creative import GenerationNotWired
    from tt_engine.creative.mcp_client import HiggsfieldMCP
    with _db(tmp_path) as db:
        db.upsert_product(models.Product(id="P-X", name="Scalp Massager Pro", category="beauty"))
        # Force 'available' without a real SDK by subclassing.
        class _AvailMCP(HiggsfieldMCP):
            available = property(lambda self: True)
        with pytest.raises(GenerationNotWired):
            generate_batch(db, _kit(), confirm=True, mcp=_AvailMCP(api_key="fake"))
        assert all(c.status == "briefed" for c in db.creatives_for("P-X"))


def test_soul_id_consistency_one_persona_per_store(tmp_path):
    with _db(tmp_path) as db:
        db.upsert_product(models.Product(id="P-X", name="X", category="beauty"))
        db.upsert_creative(models.Creative(
            id="OLD-1", product_id="P-X", format="UGC-Reaction", hook="h",
            soul_id="SOUL-OTHER"))
        warnings = soul_consistency(db, "SOUL-STORE-1")
        assert warnings and "mismatch" in warnings[0]
        assert soul_consistency(db, "SOUL-OTHER") == []       # matching persona: clean
        assert "no Soul ID configured" in soul_consistency(db, "")[0]


def test_export_blocks_creatives_missing_disclosure(tmp_path):
    with _db(tmp_path) as db:
        db.upsert_product(models.Product(id="P-X", name="X", category="beauty"))
        db.upsert_creative(models.Creative(
            id="OK-1", product_id="P-X", format="ASMR", hook="h", status="ready",
            meta={"aigc_disclosure": "AI-generated content."}))
        db.upsert_creative(models.Creative(
            id="BAD-1", product_id="P-X", format="ASMR", hook="h", status="ready",
            meta={}))  # slipped through without disclosure
        db.upsert_creative(models.Creative(
            id="PLAN-1", product_id="P-X", format="ASMR", hook="h", status="briefed",
            meta={"aigc_disclosure": "AI-generated content."}))  # never generated
        out = tmp_path / "manifest.json"
        result = export_creatives(db, "P-X", str(out))
        assert [c.id for c in result.exported] == ["OK-1"]
        assert [c.id for c in result.blocked] == ["BAD-1"]
        assert [c.id for c in result.not_ready] == ["PLAN-1"]  # a plan is not an asset
        assert "BLOCKED" in result.summary and "AIGC disclosure" in result.summary
        assert out.exists()
        # Exported creative flipped to 'exported'; blocked + not-ready untouched.
        stored = {c.id: c for c in db.creatives_for("P-X")}
        assert stored["OK-1"].status == "exported"
        assert stored["BAD-1"].status == "ready"
        assert stored["PLAN-1"].status == "briefed"


def test_produce_creatives_gated_on_test_verdict(tmp_path):
    with _db(tmp_path) as db:
        seed.seed_sample(db)
        pipeline.daily(db)
        # Gated product (branded) → refused without --force.
        with pytest.raises(ValueError, match="not at TEST verdict"):
            pipeline.produce_creatives(db, "P-BRANDPLUSH")
        # TEST-verdict product → dry-run plan flows through.
        kit, result = pipeline.produce_creatives(db, "P-SOURDOUGHLAME",
                                                 mcp=HiggsfieldMCP())
        assert result.dry_run and len(result.creatives) == 30
        assert kit.psych.spine  # psychology paragraph feeds the brief
        assert "Psychological spine" in kit.brief_text()


def test_unconfigured_client_is_unavailable_and_never_calls_out():
    """With no key and no SDK, HiggsfieldMCP must be unavailable — this is what routes
    generate_batch() to the dry-run path instead of attempting any network call."""
    assert HiggsfieldMCP(api_key="").available is False
    assert HiggsfieldMCP().available is False  # ambient CONFIG in this sandbox: no key


def test_submit_and_poll_are_honest_stubs_not_fake_network_calls():
    """The old code POSTed an invented JSON-RPC payload to a URL with zero auth — a
    silent-wrong-protocol bug. It's gone: calling submit()/poll() directly (bypassing the
    dry-run gate) must fail loudly and explain what to wire, never pretend to succeed."""
    mcp = HiggsfieldMCP(api_key="whatever-key")
    kit = _kit()
    fake_creative = models.Creative(id="C1", product_id="P-X", format="ASMR", hook="h")
    with pytest.raises(NotImplementedError, match="higgsfield_client"):
        mcp.submit(kit, fake_creative)
    with pytest.raises(NotImplementedError, match="higgsfield_client"):
        mcp.poll("job-123")


def test_available_requires_both_key_and_sdk_like_llm_available():
    """Mirrors CONFIG.llm_available's shape exactly: a key alone isn't enough without the
    SDK importable, since this sandbox never has higgsfield_client installed."""
    assert CONFIG.higgsfield_available is False  # no key in this test environment
    mcp = HiggsfieldMCP(api_key="some-key")
    # Even with an explicit key passed to the instance, the class still requires the
    # ambient CONFIG to report available (key + importable SDK) — no key alone shortcuts it.
    assert mcp.available is False
