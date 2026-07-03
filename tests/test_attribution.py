"""Phase 2 feedback loop: per-test sub-score attribution + the monthly report."""

from tt_engine import seed
from tt_engine.db import Database, models
from tt_engine.feedback import attribute, render_monthly
from tt_engine.scoring import load_weights


def _db(tmp_path):
    return Database(str(tmp_path / "attr.db"))


def _score(pid, date, econ, market):
    """A score row where economics/market_demand are set and the rest are middling."""
    return models.Score(
        product_id=pid, date=date, viral_demo=10.0, market_demand=market,
        competition_timing=8.0, economics=econ, content_potential=8.0,
        brand_potential=5.0, total=10 + market + 8 + econ + 8 + 5,
        gates_passed=True, gate_failures=[], window_days=20,
    )


def test_attribution_classifies_hits_and_misses(tmp_path):
    w = load_weights()
    hi_econ = 0.8 * w["economics"]     # ≥60% of weight → "predicted a winner"
    lo_econ = 0.2 * w["economics"]
    with _db(tmp_path) as db:
        # Winner with HIGH economics → economics called it (hit).
        db.upsert_product(models.Product(id="W1", name="w1", category="home"))
        db.upsert_score(_score("W1", "2026-07-01", hi_econ, 15.0))
        db.upsert_result(models.Result(product_id="W1", date="2026-07-02", decision="scale"))
        # Loser with HIGH economics → economics was wrong (miss).
        db.upsert_product(models.Product(id="L1", name="l1", category="home"))
        db.upsert_score(_score("L1", "2026-07-01", hi_econ, 15.0))
        db.upsert_result(models.Result(product_id="L1", date="2026-07-03", decision="kill"))
        # Loser with LOW economics → economics called it (hit).
        db.upsert_product(models.Product(id="L2", name="l2", category="home"))
        db.upsert_score(_score("L2", "2026-07-01", lo_econ, 15.0))
        db.upsert_result(models.Result(product_id="L2", date="2026-07-04", decision="kill"))

        report = attribute(db)
        assert report.sample_size == 3
        rows = {r.product_id: r for r in report.rows}
        assert rows["W1"].correct["economics"] is True
        assert rows["L1"].correct["economics"] is False
        assert rows["L2"].correct["economics"] is True
        assert report.hit_rate["economics"] == 2 / 3


def test_attribution_month_filter(tmp_path):
    with _db(tmp_path) as db:
        db.upsert_product(models.Product(id="A", name="a", category="home"))
        db.upsert_score(_score("A", "2026-06-30", 15.0, 15.0))
        db.upsert_result(models.Result(product_id="A", date="2026-06-30", decision="scale"))
        db.upsert_product(models.Product(id="B", name="b", category="home"))
        db.upsert_score(_score("B", "2026-07-01", 15.0, 15.0))
        db.upsert_result(models.Result(product_id="B", date="2026-07-01", decision="kill"))
        assert attribute(db, month="2026-06").sample_size == 1
        assert attribute(db, month="2026-07").sample_size == 1
        assert attribute(db).sample_size == 2


def test_monthly_report_is_suggestions_only(tmp_path):
    with _db(tmp_path) as db:
        seed.seed_demo_outcomes(db)  # ≥20 labeled outcomes → the fit runs
        text = render_monthly(db)
        assert "Suggestions only" in text
        assert "recalibrate --apply" in text            # manual approval path
        assert "Which sub-scores predicted the outcome" in text
        assert "| Category | Hit rate |" in text
        assert "Suggested |" in text                    # weight suggestion table


def test_monthly_report_with_no_outcomes_says_so(tmp_path):
    with _db(tmp_path) as db:
        text = render_monthly(db, month="2026-07")
        assert "No concluded tests" in text
        assert "log-result" in text  # tells the operator the next step
