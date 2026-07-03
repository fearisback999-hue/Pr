"""Scorecard verdicts (KILL/WATCH/TEST) and the show-your-work rendering."""

from tt_engine import pipeline, seed
from tt_engine.db import Database
from tt_engine.reports.scorecard import render_scorecard, verdict


def _db(tmp_path):
    return Database(str(tmp_path / "sc.db"))


def test_verdict_mapping():
    assert verdict(gates_passed=False, total=95.0) == "KILL"   # gates absolute
    assert verdict(gates_passed=True, total=85.0) == "TEST"
    assert verdict(gates_passed=True, total=79.9) == "WATCH"


def test_scorecard_for_attack_ready_product_shows_all_the_work(tmp_path):
    with _db(tmp_path) as db:
        seed.seed_sample(db)
        pipeline.daily(db)
        sr = pipeline.score_stored(db, "P-SCALPMASSAGER")
        text = render_scorecard(sr)
        assert "**Verdict:** **TEST**" in text
        # Every category appears with points, and the input data is shown.
        for cat in ("viral demo", "market demand", "competition timing",
                    "economics", "content potential", "brand potential"):
            assert cat in text
        assert "units/day" in text                    # momentum math
        assert "sellers" in text and "/100" in text   # saturation inputs + index
        assert "break-even ROAS" in text              # economics math
        assert "max allowable CAC" in text
        assert "days of runway" in text               # window estimate


def test_scorecard_kill_verdict_for_gated_product(tmp_path):
    with _db(tmp_path) as db:
        seed.seed_sample(db)
        pipeline.daily(db)
        sr = pipeline.score_stored(db, "P-BRANDPLUSH")  # branded → hard gate
        text = render_scorecard(sr)
        assert "**Verdict:** **KILL**" in text
        assert "branded / trademarked" in text
        assert "never overrides" in text  # momentum can't override a gate


def test_scorecard_refuses_economics_without_landed_cost(tmp_path):
    with _db(tmp_path) as db:
        pipeline.daily(db)  # no suppliers seeded
        sr = pipeline.score_stored(db, "P-SCALPMASSAGER")
        text = render_scorecard(sr)
        assert "**Verdict:** **KILL**" in text
        assert "NOT SCORED" in text and "no real landed cost" in text
