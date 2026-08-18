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


def test_nav_shows_named_sections_and_only_the_current_section_pages():
    """Two-tier nav: four named sections up top, and the second row shows only the
    pages inside the section you're in — so every page has a visible home."""
    html = render.page("T", "<p>x</p>", "/")
    for label in ("Engine", "Studio", "Money", "Start"):
        assert f">{label}</a>" in html, f"missing section tab {label}"
    # "/" lives in Engine, so Engine's pages show and Studio's do not.
    assert "/catalog" in html and "/audit" in html
    assert "/restyle" not in html.split("<main>")[0]

    studio = render.page("T", "<p>x</p>", "/restyle")
    assert "/restyle" in studio.split("<main>")[0]
    assert "Make the videos" in studio          # the section tagline


def test_helpers_render():
    assert "class=toc" in render.toc([("a", "1"), ("b", "2"), ("c", "3")])
    assert render.toc([("a", "1")]) == ""      # <3 sections → no toc
    assert "class=empty" in render.empty_state("📥", "nothing", "<a>go</a>")
    assert "cmdline" in render.cmd_code("python -m tt_engine.cli audit")


# ── actor lanes: one account = one audience, many products ───────────────────

def test_actor_lane_routes_products_to_the_right_actor():
    """The answer to 'does every character need a niche': an account needs a coherent
    AUDIENCE, not one product. Many products per actor, all inside their lane."""
    from tt_engine.creative.persona import actor_for_product, load_personas
    roster = load_personas()
    assert roster, "shipped bibles should load"
    maya = actor_for_product(roster, "home")
    assert maya and maya.name == "Maya"
    # Same actor carries MULTIPLE categories — that's the point of a lane.
    assert actor_for_product(roster, "beauty").name == "Maya"
    assert actor_for_product(roster, "wellness").name == "Maya"
    # A different world routes elsewhere.
    assert actor_for_product(roster, "electronics").name == "Jordan"


def test_uncovered_categories_are_reported_not_silently_assigned():
    """A product with no matching lane must surface as a decision, never get handed
    to whichever actor happens to be free — that's the mixed-account failure."""
    from tt_engine.creative.persona import actor_for_product, lane_report, load_personas
    roster = load_personas()
    assert actor_for_product(roster, "firearms") is None
    rep = lane_report(roster, ["home", "apparel", "electronics"])
    assert "apparel" in rep["uncovered"]
    assert "home" not in rep["uncovered"]


def test_actors_page_explains_the_lane_rule(tmp_path):
    from tt_engine.web.server import page_actors
    db = _seeded(tmp_path)
    html = page_actors(db, "")
    assert "many products" in html.lower()
    assert "lane" in html.lower()
    # Every seeded category IS covered by the shipped roster, so no gap panel here.
    assert "Product types with no actor" not in html
    db.close()


def test_actors_page_flags_a_genuinely_uncovered_category(tmp_path):
    """A product nobody's lane covers must surface as a decision to make."""
    from tt_engine.web.server import page_actors
    db = Database(str(tmp_path / "gap.db"))
    db.upsert_product(models.Product(id="G1", name="Cordless Drill", category="tools"))
    html = page_actors(db, "")
    assert "Product types with no actor" in html
    assert "tools" in html
    db.close()


def test_prohibited_categories_never_ask_for_an_actor(tmp_path):
    """The seed's vape product is prohibited — it must not show up as a lane gap
    ('you need an actor for vape' would be absurd)."""
    from tt_engine.web.server import page_actors
    db = _seeded(tmp_path)
    html = page_actors(db, "")
    gap = html.split("Product types with no actor")[-1] if "Product types with no actor" in html else ""
    assert "restricted" not in gap
    db.close()


# ── real faces ────────────────────────────────────────────────────────────────

def test_avatar_uses_a_real_photo_when_present_and_initials_when_not(tmp_path):
    from tt_engine.creative.persona import Persona
    from tt_engine.web.render import avatar
    photo = tmp_path / "face.png"
    photo.write_bytes(b"\x89PNG\r\n\x1a\n")
    with_face = Persona(name="Maya", master_description="m", avatar=str(photo))
    assert "<img" in avatar(with_face) and "/face?actor=maya" in avatar(with_face)
    without = Persona(name="Ada Lovelace", master_description="m")
    out = avatar(without)
    assert "<img" not in out and ">AL<" in out   # initials fallback, never a fake face


def test_avatar_is_discovered_beside_the_bible(tmp_path):
    """MAYA.md + MAYA.jpg — no config needed."""
    from tt_engine.creative.persona import load_persona
    bible = tmp_path / "TESTER.md"
    bible.write_text("## identity\n- name: Tester\n\n## master-description\n\nA person.\n",
                     encoding="utf-8")
    assert load_persona(str(bible)).avatar == ""
    (tmp_path / "TESTER.jpg").write_bytes(b"\xff\xd8\xff")
    assert load_persona(str(bible)).avatar.endswith("TESTER.jpg")


def test_handle_strips_the_bible_parenthetical():
    from tt_engine.creative.persona import Persona
    p = Persona(name="Maya", master_description="m",
                account="@maya.tries (her own account — NOT the brand)")
    assert p.handle == "@maya.tries"


# ── "How it works" explainer ─────────────────────────────────────────────────

def test_how_page_explains_the_four_steps_in_plain_words(tmp_path):
    from tt_engine.web.server import page_how
    db = _seeded(tmp_path)
    html = page_how(db)
    for probe in ["How the engine works", "Get the facts", "deal-breakers",
                  "Score what", "Test with real money"]:   # apostrophe is HTML-escaped
        assert probe in html, f"missing: {probe}"
    # It must state the limits, not just the mechanics.
    assert "never do" in html
    assert "market decides" in html
    db.close()


def test_how_page_numbers_come_from_the_real_config(tmp_path):
    """The explainer must not hardcode thresholds — if a gate changes, the page
    changes with it, or it becomes a lie."""
    from tt_engine.economics.calculator import MARGIN_FLOOR
    from tt_engine.validation import KILL_HOURS
    from tt_engine.web.server import page_how
    db = _seeded(tmp_path)
    html = page_how(db)
    assert f"{MARGIN_FLOOR*100:.0f}%" in html
    assert f"{KILL_HOURS:.0f}-hour" in html
    db.close()


def test_how_page_gate_count_matches_the_list(tmp_path):
    """The summary card said 'Five' while six were listed — an easy, embarrassing drift."""
    import re
    from tt_engine.web.server import page_how
    db = _seeded(tmp_path)
    html = page_how(db)
    listed = html.count("class=gatex")
    words = {5: "Five", 6: "Six", 7: "Seven"}
    assert f"{words[listed]} things that kill" in html, \
        f"{listed} gates listed but the card says otherwise"
    db.close()
