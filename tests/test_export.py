import csv

from tt_engine import pipeline, seed
from tt_engine.db import Database
from tt_engine.reports.spreadsheet import COLUMNS, board_rows, export_csv


def _db(tmp_path):
    return Database(str(tmp_path / "e.db"))


def test_board_rows_match_appendix_a_columns(tmp_path):
    with _db(tmp_path) as db:
        seed.seed_sample(db)
        pipeline.daily(db)
        rows = board_rows(db)
        assert rows
        # Every Appendix-A column is present on every row.
        for r in rows:
            assert set(r.keys()) == set(COLUMNS)
        # Sorted by total descending; the top row is an attack-ready winner.
        totals = [r["total"] for r in rows]
        assert totals == sorted(totals, reverse=True)
        assert rows[0]["verdict"] == "ATTACK"
        assert rows[0]["gates_passed"] == "Y"
        # Clean winners surface as ATTACK rows.
        attack_names = {r["name"] for r in rows if r["verdict"] == "ATTACK"}
        assert "Scalp Massager Pro" in attack_names


def test_gated_products_marked_n(tmp_path):
    with _db(tmp_path) as db:
        seed.seed_sample(db)
        pipeline.daily(db)
        rows = {r["name"]: r for r in board_rows(db)}
        # The licensed plush trips the branded gate.
        assert rows["Stitch Plush (licensed)"]["gates_passed"] == "N"
        assert rows["Stitch Plush (licensed)"]["verdict"] == "GATED"


def test_export_csv_writes_file(tmp_path):
    with _db(tmp_path) as db:
        seed.seed_sample(db)
        pipeline.daily(db)
        out = tmp_path / "board.csv"
        n = export_csv(db, str(out))
        assert n >= 5 and out.exists()
        with out.open() as f:
            reader = csv.DictReader(f)
            assert reader.fieldnames == COLUMNS
            written = list(reader)
        assert len(written) == n
