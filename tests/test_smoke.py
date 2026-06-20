"""End-to-end smoke test: seed → daily → weekly on a temp DB, fully offline."""

from tt_engine import pipeline, seed
from tt_engine.db import Database
from tt_engine.feedback import recalibrate


def _db(tmp_path):
    return Database(str(tmp_path / "smoke.db"))


def test_seed_and_daily_pipeline(tmp_path):
    with _db(tmp_path) as db:
        n = seed.seed_sample(db)
        assert n >= 5
        result = pipeline.daily(db)
        ids = {s.record.product.id for s in result.scored}
        assert "P-SCALPMASSAGER" in ids

        by_id = {s.record.product.id: s for s in result.scored}

        # The clean beauty product should be an attack-ready candidate.
        scalp = by_id["P-SCALPMASSAGER"].breakdown.score
        assert scalp.gates_passed
        assert scalp.total >= 80
        assert any(c.record.product.id == "P-SCALPMASSAGER" for c in result.new_candidates)

        # Each problem archetype trips its intended gate (or fails to trigger).
        assert not by_id["P-BRANDPLUSH"].breakdown.score.gates_passed     # branded
        assert not by_id["P-VAPEKIT"].breakdown.score.gates_passed        # restricted
        assert not by_id["P-CHEAPCABLE"].breakdown.score.gates_passed     # thin margin
        # Cheap cable triggers on momentum but is blocked — momentum can't override economics.
        assert by_id["P-CHEAPCABLE"].trigger.triggered
        assert not by_id["P-CHEAPCABLE"].breakdown.recommended


def test_weekly_report_has_attack_packet(tmp_path):
    with _db(tmp_path) as db:
        seed.seed_sample(db)
        report = pipeline.weekly(db, push_creative=True)
        assert report.packets, "expected at least one attack-ready packet"
        top = report.packets[0]
        # Packet carries the full 70%: economics, psychology spine, supplier, creative kit.
        assert top.economics.gross_margin > 0.45
        assert top.psych.spine
        assert top.supplier is not None
        assert top.kit is not None and top.planned_creatives > 0
        # Creatives were persisted.
        assert db.creatives_for(top.product.id)


def test_recalibration_needs_sample_then_shifts_weights(tmp_path):
    with _db(tmp_path) as db:
        seed.seed_sample(db)
        # Without enough labeled outcomes, recalibration declines to move weights.
        before = recalibrate(db, apply=False)
        assert not before.applied

        # With synthetic outcomes where economics/market_demand predict winners,
        # recalibration runs and upweights those categories.
        seed.seed_demo_outcomes(db)
        after = recalibrate(db, apply=False)
        assert after.sample_size >= 20
        assert after.new_weights
        assert after.correlations["economics"] > 0
