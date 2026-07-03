"""The Phase-1 manual operating loop, end to end through the real CLI entry point:
add → add-supplier → add-metric ×N → scorecard → log-test → validate → log-result →
report-monthly. One operator, by hand — exactly how the engine is meant to be run first."""

from tt_engine.cli import main
from tt_engine.db import Database


def _run(db_path, *argv):
    return main(["--db", str(db_path), *argv])


def test_manual_loop_end_to_end(tmp_path, capsys):
    db_path = tmp_path / "cli.db"

    # 1. Add a hand-found product + a real landed-cost quote.
    assert _run(db_path, "add", "--name", "Cloud Slippers", "--category", "home",
                "--id", "P-CLOUD") == 0
    assert _run(db_path, "add-supplier", "P-CLOUD", "--cost", "4.50",
                "--ship-cost", "1.00") == 0

    # 2. Log a ramping daily series (momentum needs a time series).
    for i, units in enumerate([40, 45, 50, 60, 80, 110, 150, 200, 260, 330,
                               400, 480, 560, 650]):
        assert _run(db_path, "add-metric", "P-CLOUD", "--units", str(units),
                    "--price", "24.99", "--date", f"2026-06-{i+1:02d}",
                    "--sellers", str(5 + i), "--promo-videos", str(10 + 2 * i),
                    "--ads", str(3 + i // 2), "--avg-ad-age", "6") == 0

    # 3. Scorecard renders with a verdict and the math shown.
    out = tmp_path / "card.md"
    assert _run(db_path, "scorecard", "P-CLOUD", "--out", str(out)) == 0
    card = out.read_text()
    assert "**Verdict:**" in card and "break-even ROAS" in card

    # 4. Log two bad test days → the 48h timer flags KILL in validate.
    assert _run(db_path, "log-test", "P-CLOUD", "--spend", "40", "--revenue", "30",
                "--date", "2026-06-14") == 0
    assert _run(db_path, "log-test", "P-CLOUD", "--spend", "40", "--revenue", "35",
                "--date", "2026-06-15") == 0
    capsys.readouterr()
    assert _run(db_path, "validate", "P-CLOUD") == 0
    text = capsys.readouterr().out
    assert "[KILL]" in text and "48h" in text

    # 5. Record the outcome; the monthly report picks it up.
    assert _run(db_path, "log-result", "P-CLOUD", "--decision", "kill",
                "--roas", "0.8", "--date", "2026-06-15") == 0
    assert _run(db_path, "report-monthly", "--month", "2026-06") == 0
    monthly = capsys.readouterr().out
    assert "1 concluded test(s)" in monthly and "Suggestions only" in monthly

    # The manual placeholder creative exists and carries the test rows.
    with Database(str(db_path)) as db:
        assert db.tests_for_product("P-CLOUD")


def test_import_csv_cli(tmp_path, capsys):
    db_path = tmp_path / "cli2.db"
    csv_path = tmp_path / "kalo.csv"
    csv_path.write_text(
        "Product Name,Date,Sales Volume,Revenue\n"
        "Neck Fan,2026-07-01,150,\"$2,998.50\"\n"
    )
    assert _run(db_path, "import-csv", str(csv_path), "--source", "kalodata") == 0
    out = capsys.readouterr().out
    assert "1 product(s), 1 metric row(s), 0 skipped" in out


def test_creative_cli_refuses_below_test_verdict(tmp_path, capsys):
    db_path = tmp_path / "cli3.db"
    assert _run(db_path, "add", "--name", "Meh Product", "--category", "electronics",
                "--id", "P-MEH") == 0
    assert _run(db_path, "add-supplier", "P-MEH", "--cost", "9.0") == 0
    assert _run(db_path, "add-metric", "P-MEH", "--units", "5", "--price", "19.99") == 0
    capsys.readouterr()
    assert _run(db_path, "creative", "P-MEH") == 1  # WATCH at best — refused
    assert "not at TEST verdict" in capsys.readouterr().out
