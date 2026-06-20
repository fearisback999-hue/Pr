from tt_engine import pipeline, seed
from tt_engine.db import Database
from tt_engine.reports.opportunity import render_winners, window_band


def _db(tmp_path):
    return Database(str(tmp_path / "f.db"))


def test_find_winners_ranks_attack_ready(tmp_path):
    with _db(tmp_path) as db:
        seed.seed_sample(db)
        result = pipeline.find_winners(db, top=5)
        assert result.source == "mock"
        assert len(result.winners) >= 2  # enriched sample feed has multiple winners
        # Ranked best-first, and every winner is attack-ready (≥80, gates clear).
        totals = [p.breakdown.score.total for p in result.winners]
        assert totals == sorted(totals, reverse=True)
        for p in result.winners:
            assert p.breakdown.score.gates_passed
            assert p.breakdown.score.total >= 80
            assert p.kit is None  # find skips creative production (that's the next step)
            assert p.psych.spine  # but does carry the 'why it wins' context


def test_find_respects_top_limit(tmp_path):
    with _db(tmp_path) as db:
        seed.seed_sample(db)
        result = pipeline.find_winners(db, top=1)
        assert len(result.winners) == 1


def test_near_misses_explain_the_block(tmp_path):
    with _db(tmp_path) as db:
        seed.seed_sample(db)
        result = pipeline.find_winners(db)
        blocked = {b.score.product_id for b in result.near_misses}
        assert "P-BRANDPLUSH" in blocked  # branded gate
        assert "P-VAPEKIT" in blocked     # restricted gate


def test_window_band_urgency():
    assert "closing" in window_band(3)
    assert "act now" in window_band(15)
    assert "early" in window_band(45)
    assert window_band(None) == "—"


def test_render_winners_flags_sample_source(tmp_path):
    with _db(tmp_path) as db:
        seed.seed_sample(db)
        result = pipeline.find_winners(db)
        text = render_winners(result.winners, result.near_misses, result.source, result.date)
        assert "sample feed" in text  # honest about not being a real market find
        assert "Best winning products" in text
