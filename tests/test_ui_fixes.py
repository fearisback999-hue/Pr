"""Regression tests for the dashboard bug-fix + polish pass.

Each test pins a specific reported bug so it can't silently come back.
"""

import pytest

from tt_engine.db import Database, models
from tt_engine.web import render, server as S


def _seeded(tmp_path):
    from tt_engine.seed import seed_sample, seed_demo_outcomes
    db = Database(str(tmp_path / "ui.db"))
    seed_sample(db)
    seed_demo_outcomes(db)
    return db


# ── Bug 3: UTF-8 encoding (Windows mojibake) ──────────────────────────────────

def test_persona_reads_are_utf8_everywhere():
    """Every file read/write in the package must pin encoding='utf-8'; the default
    is cp1252 on Windows, which mangles em-dashes into 'â€\"'."""
    import pathlib, re
    offenders = []
    for f in pathlib.Path("tt_engine").rglob("*.py"):
        src = f.read_text(encoding="utf-8")
        for m in re.finditer(r"\.(read_text|write_text)\(", src):
            # crude: check the call has encoding= within the next 120 chars
            tail = src[m.end():m.end() + 120]
            head = src[m.start()-1:m.end()]
            if "encoding=" not in tail and "encoding=" not in src[m.start():m.start()+200]:
                offenders.append(f"{f}: {head}")
    assert not offenders, "unqualified file I/O (Windows encoding bug): " + "; ".join(offenders)


def test_actors_page_has_no_mojibake(tmp_path):
    from tt_engine.web.server import page_actors
    db = _seeded(tmp_path)
    html = page_actors(db, "")
    assert "â€" not in html, "mojibake in personas — a non-utf-8 read snuck back in"
    db.close()


# ── Bug 6: prohibited products excluded from catalog ranking ──────────────────

def test_prohibited_products_are_excluded_from_rank(tmp_path):
    from tt_engine.sourcing import catalog as cat
    db = _seeded(tmp_path)
    ranked = [p.product.name for p in cat.rank(db, top=99)]
    assert not any("Vape" in n for n in ranked), "a prohibited product was ranked"
    banned = cat.prohibited_products(db)
    assert any("Vape" in p.name for p, _ in banned), "vape must appear in the excluded list"
    db.close()


def test_is_prohibited_detects_flag_and_keywords():
    from tt_engine.sourcing.catalog import is_prohibited
    assert is_prohibited(models.Product(id="a", name="X", category="home",
                                        restricted=True))[0]
    assert is_prohibited(models.Product(id="b", name="Disposable Vape", category="misc"))[0]
    assert is_prohibited(models.Product(id="c", name="CBD Gummies", category="wellness"))[0]
    assert not is_prohibited(models.Product(id="d", name="Phone Stand", category="tech"))[0]


def test_catalog_page_shows_the_exclusion_transparently(tmp_path):
    db = _seeded(tmp_path)
    html = S.page_catalog(db)
    assert "Excluded — prohibited category" in html
    assert "cannot be listed" in html
    db.close()


# ── Bug 7: search category dropdown + price reconciliation ────────────────────

def test_search_category_is_a_real_dropdown_of_existing_values(tmp_path):
    db = _seeded(tmp_path)
    html = S.page_search(db, {})
    assert "<select name=category>" in html
    # the categories actually present must be options
    assert ">home<" in html
    db.close()


def test_search_falls_back_to_supplier_price_like_catalog(tmp_path):
    """A product with a supplier but no metrics showed '—'; Catalog showed a price.
    Search now shows the same supplier-derived target, marked '~'."""
    db = Database(str(tmp_path / "s.db"))
    db.upsert_product(models.Product(id="X1", name="Widget", category="home"))
    db.upsert_supplier(models.Supplier(ref="s1", product_id="X1", name="CJ", cost=3.0,
                                       ship_cost=1.0, ship_days=5, moq=1, us_warehouse=True))
    html = S.page_search(db, {})
    assert "~$14.00" in html    # (3+1) * 3.5
    db.close()


# ── Bug 8: overview collapses identical steps ─────────────────────────────────

def test_overview_collapses_identical_steps(tmp_path):
    db = _seeded(tmp_path)
    html = S.page_overview(db)
    # 30 demo products all need data — must be ONE summary row, not 12 identical ones
    assert "products</b>" in html
    assert html.count("Only 0 day(s) of metrics") <= 1
    db.close()


# ── Part 2: shared enhancement layer present ──────────────────────────────────

def test_shell_ships_the_js_and_toast_layer():
    html = render.page("T", "<p>x</p>", "/")
    assert "<script>" in html and "copybtn" in html
    assert "id=toast" in html


def test_nav_groups_render_with_labels():
    html = render.page("T", "<p>x</p>", "/")
    for label in ("operate", "build", "learn"):
        assert f"title='{label}'" in html


def test_helpers_render():
    assert "class=toc" in render.toc([("a", "1"), ("b", "2"), ("c", "3")])
    assert render.toc([("a", "1")]) == ""      # <3 sections → no toc
    assert "class=empty" in render.empty_state("📥", "nothing", "<a>go</a>")
    assert "cmdline" in render.cmd_code("python -m tt_engine.cli audit")
