from tt_engine.db import Database, models


def _db(tmp_path):
    return Database(str(tmp_path / "t.db"))


def test_product_metric_roundtrip(tmp_path):
    with _db(tmp_path) as db:
        db.upsert_product(models.Product(id="P", name="Thing", category="home"))
        db.upsert_metric(models.DailyMetric(
            product_id="P", date="2026-06-01", units=10, gmv=100.0, price=10.0,
            sellers=5, promo_videos=3, ads=2, avg_ad_age=8.0,
        ))
        assert db.get_product("P").name == "Thing"
        metrics = db.metrics_for("P")
        assert len(metrics) == 1 and metrics[0].units == 10


def test_upsert_is_idempotent(tmp_path):
    with _db(tmp_path) as db:
        p = models.Product(id="P", name="A", category="home")
        db.upsert_product(p)
        p.name = "B"
        db.upsert_product(p)
        assert db.get_product("P").name == "B"
        assert len(db.all_products()) == 1


def test_board_ranked_descending(tmp_path):
    with _db(tmp_path) as db:
        for pid, total, gates in [("A", 85, True), ("B", 70, True), ("C", 90, False)]:
            db.upsert_product(models.Product(id=pid, name=pid, category="home"))
            db.upsert_score(models.Score(
                product_id=pid, date="2026-06-01", viral_demo=0, market_demand=0,
                competition_timing=0, economics=0, content_potential=0, brand_potential=0,
                total=total, gates_passed=gates, gate_failures=[], window_days=10,
            ))
        board = db.board()
        assert [s.product_id for s in board] == ["C", "A", "B"]
        gated_only = db.board(gated_only=True)
        assert "C" not in [s.product_id for s in gated_only]


def test_tests_and_results_for_product(tmp_path):
    with _db(tmp_path) as db:
        db.upsert_product(models.Product(id="P", name="P", category="home"))
        db.upsert_creative(models.Creative(id="P-C0", product_id="P", format="UGC", hook="hi"))
        db.upsert_test(models.Test(id="T0", creative_id="P-C0", date="2026-06-01",
                                   spend=20, impressions=1000, ctr=0.02, roas=2.0))
        db.upsert_result(models.Result(product_id="P", date="2026-06-02",
                                       net_margin=0.1, refund_rate=0.03, roas=2.0, decision="scale"))
        assert len(db.tests_for_product("P")) == 1
        assert db.latest_result("P").decision == "scale"
