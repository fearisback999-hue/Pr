"""Bulk paste intake — the fast way to get real products into the engine.

This exists INSTEAD of a scraper. The rule it upholds: parse what the operator
pasted, never invent a value, never silently drop a line.
"""

import pytest

from tt_engine.db import Database
from tt_engine.paste import PasteResult, parse_line, paste_products, product_id


def _db(tmp_path):
    return Database(str(tmp_path / "p.db"))


# ── parsing messy real-world lines ────────────────────────────────────────────

@pytest.mark.parametrize("raw,name,price,cat", [
    ("Doorway Pull Up Bar $34.99 fitness", "Doorway Pull Up Bar", 34.99, "fitness"),
    ("2. Scalp Massager — $12.99 (beauty)", "Scalp Massager", 12.99, "beauty"),
    ("Blue Light Glasses  19.99", "Blue Light Glasses", 19.99, "uncategorized"),
    ("Meme Graphic Tee | $24.99 | apparel", "Meme Graphic Tee", 24.99, "apparel"),
    ("• Mini Handheld Fan $9.99", "Mini Handheld Fan", 9.99, "uncategorized"),
])
def test_parses_the_shapes_people_actually_paste(raw, name, price, cat):
    p = parse_line(raw)
    assert p is not None, f"failed to parse: {raw}"
    assert p.name == name
    assert p.price == pytest.approx(price)
    assert p.category == cat


def test_category_tag_is_stripped_from_the_name():
    """Leaving the tag in corrupts the name AND makes the same product parse to two
    different ids depending on whether you typed the tag."""
    with_tag = parse_line("Doorway Pull Up Bar $34.99 fitness")
    without = parse_line("Doorway Pull Up Bar $34.99")
    assert with_tag.name == without.name
    assert product_id(with_tag.name) == product_id(without.name)


def test_a_line_with_no_name_is_rejected():
    assert parse_line("12345") is None
    assert parse_line("$9.99") is None
    assert parse_line("   ") is None
    assert parse_line("--") is None


def test_a_price_is_never_invented():
    p = parse_line("Cordless Drill")
    assert p is not None and p.price is None


def test_bare_four_digit_numbers_are_not_treated_as_prices():
    """'Widget 2026' is a year, not $2,026 — guessing here would poison the margin
    gate with a fake price."""
    p = parse_line("Retro Lamp 2026")
    assert p is not None and p.price is None


# ── saving ────────────────────────────────────────────────────────────────────

def test_paste_creates_products_and_reports_skips(tmp_path):
    db = _db(tmp_path)
    res = paste_products(db, """
Doorway Pull Up Bar $34.99 fitness
Scalp Massager $12.99 beauty
12345
""")
    assert len(res.added) == 2
    assert len(res.skipped) == 1
    assert "couldn't find a product name" in res.skipped[0][1]
    names = {p.name for p in db.all_products()}
    assert "Doorway Pull Up Bar" in names
    db.close()


def test_duplicates_within_one_paste_are_reported_not_doubled(tmp_path):
    db = _db(tmp_path)
    res = paste_products(db, "Pull Up Bar $34.99\nPull Up Bar $34.99")
    assert len(res.added) == 1
    assert "duplicate" in res.skipped[0][1]
    db.close()


def test_price_is_stored_so_the_margin_gate_has_something_real(tmp_path):
    db = _db(tmp_path)
    paste_products(db, "Scalp Massager $12.99 beauty")
    pid = product_id("Scalp Massager")
    metrics = db.metrics_for(pid)
    assert metrics and metrics[-1].price == pytest.approx(12.99)
    db.close()


def test_summary_says_candidates_not_winners(tmp_path):
    db = _db(tmp_path)
    text = paste_products(db, "Scalp Massager $12.99").summary
    assert "CANDIDATES, not winners" in text
    assert "supplier quote" in text
    db.close()


def test_empty_paste_is_harmless(tmp_path):
    db = _db(tmp_path)
    res = paste_products(db, "\n\n   \n")
    assert res.added == [] and res.skipped == []
    db.close()


# ── the web surface ───────────────────────────────────────────────────────────

def test_search_page_offers_the_paste_box(tmp_path):
    from tt_engine.web.server import page_search
    db = _db(tmp_path)
    html = page_search(db, {})
    assert "pastebox" in html
    assert "action='/paste'" in html
    db.close()


def test_search_page_reports_what_was_added(tmp_path):
    from tt_engine.web.server import page_search
    db = _db(tmp_path)
    html = page_search(db, {"added": ["3"], "skipped": ["1"]})
    assert "Added 3 product(s)" in html
    assert "1 line(s)" in html
    db.close()
