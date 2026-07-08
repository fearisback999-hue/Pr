"""The operator guide: every DB state maps to the right next action."""

from datetime import date, timedelta

from tt_engine import pipeline, seed
from tt_engine.db import Database, models
from tt_engine.guide import all_steps, next_step, render_guide


def _db(tmp_path):
    return Database(str(tmp_path / "guide.db"))


def _add_metrics(db, pid, days=14, base=40, growth=1.12, price=24.99,
                 sellers=6, promos=12, ads=4):
    today = date.today()
    u = base
    for i in range(days):
        u *= growth
        db.upsert_metric(models.DailyMetric(
            product_id=pid, date=(today - timedelta(days=days - 1 - i)).isoformat(),
            units=int(u), gmv=u * price, price=price, sellers=sellers,
            promo_videos=promos, ads=ads, avg_ad_age=6.0))


def test_stage_progression(tmp_path):
    with _db(tmp_path) as db:
        pid = "P-G"
        db.upsert_product(models.Product(id=pid, name="Guide Product", category="beauty",
                                         reviews=["obsessed!", "melts tension"]))
        p = db.get_product(pid)

        assert next_step(db, p).stage == "needs-data"          # < 7 days of metrics

        _add_metrics(db, pid)
        assert next_step(db, p).stage == "needs-supplier"      # no landed cost

        db.upsert_supplier(models.Supplier(ref="S", product_id=pid, cost=5.0,
                                           ship_cost=1.0, ship_days=5))
        assert next_step(db, p).stage == "needs-score"         # not scored today

        sr = pipeline.score_stored(db, pid)
        db.upsert_score(sr.breakdown.score)
        step = next_step(db, p)
        assert step.stage in ("build-creative", "watch")       # depends on the score
        if step.stage == "build-creative":                     # TEST path continues:
            db.upsert_creative(models.Creative(
                id="C1", product_id=pid, format="ASMR", hook="h",
                meta={"aigc_disclosure": "x"}))
            assert next_step(db, p).stage in ("configure-mcp", "generate")

            for c in db.creatives_for(pid):
                c.status = "ready"
                db.upsert_creative(c)
            assert next_step(db, p).stage == "export"

            for c in db.creatives_for(pid):
                c.status = "exported"
                db.upsert_creative(c)
            assert next_step(db, p).stage == "launch"


def test_kill_now_when_timer_tripped(tmp_path):
    with _db(tmp_path) as db:
        pid = "P-K"
        db.upsert_product(models.Product(id=pid, name="Kill Me", category="beauty"))
        _add_metrics(db, pid)
        db.upsert_supplier(models.Supplier(ref="SK", product_id=pid, cost=5.0,
                                           ship_cost=1.0, ship_days=5))
        sr = pipeline.score_stored(db, pid)
        db.upsert_score(sr.breakdown.score)
        db.upsert_creative(models.Creative(id="CK", product_id=pid, format="Manual", hook="m"))
        today = date.today()
        for i, roas in enumerate([0.8, 0.7]):
            d = (today - timedelta(days=1 - i)).isoformat()
            db.upsert_test(models.Test(id=f"T{i}", creative_id="CK", date=d,
                                       spend=40.0, roas=roas))
        step = next_step(db, db.get_product(pid))
        assert step.stage == "kill-now"
        assert step.urgency == 3
        assert "log-result" in step.command


def test_concluded_products_rest(tmp_path):
    with _db(tmp_path) as db:
        pid = "P-DONE"
        db.upsert_product(models.Product(id=pid, name="Done", category="home"))
        _add_metrics(db, pid)
        db.upsert_supplier(models.Supplier(ref="SD", product_id=pid, cost=5.0,
                                           ship_cost=1.0, ship_days=5))
        sr = pipeline.score_stored(db, pid)
        db.upsert_score(sr.breakdown.score)
        db.upsert_result(models.Result(product_id=pid, date=date.today().isoformat(),
                                       decision="kill"))
        assert next_step(db, db.get_product(pid)).stage == "concluded-kill"


def test_render_guide_orders_by_urgency(tmp_path):
    with _db(tmp_path) as db:
        seed.seed_sample(db)
        pipeline.daily(db)
        steps = all_steps(db)
        urgencies = [s.urgency for s in steps]
        assert urgencies == sorted(urgencies, reverse=True)
        text = render_guide(db, limit=5)
        assert "What to do next" in text
        assert "$ python -m tt_engine.cli" in text


def test_render_guide_empty_db(tmp_path):
    with _db(tmp_path) as db:
        assert "Nothing in the pipeline" in render_guide(db)
