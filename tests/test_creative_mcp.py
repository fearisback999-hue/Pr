"""Phase 2 Higgsfield MCP pipeline: dry-run, confirmation guardrail, AIGC disclosure,
Soul ID consistency, and the export block."""

import pytest

from tt_engine import pipeline, seed
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
    """In-memory MCP double: every submitted job completes on first poll."""
    def __init__(self):
        super().__init__(url="http://fake-mcp.test/mcp")
        self.submitted = []

    def submit(self, kit, c):
        self.submitted.append(c.id)
        return f"job-{c.id}"

    def poll(self, job_id):
        return "ready", f"https://assets.test/{job_id}.mp4"


def test_dry_run_plans_batch_with_disclosure_metadata(tmp_path):
    with _db(tmp_path) as db:
        db.upsert_product(models.Product(id="P-X", name="Scalp Massager Pro", category="beauty"))
        result = generate_batch(db, _kit(), mcp=HiggsfieldMCP(url=""))  # unconfigured
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
        kit, result = pipeline.produce_creatives(db, "P-SCALPMASSAGER",
                                                 mcp=HiggsfieldMCP(url=""))
        assert result.dry_run and len(result.creatives) == 30
        assert kit.psych.spine  # psychology paragraph feeds the brief
        assert "Psychological spine" in kit.brief_text()
