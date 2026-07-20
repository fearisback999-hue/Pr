"""Category creative styles: clothing must not film like gadgets. Invariants —
aliases land (clothing→apparel, gadget→electronics); hooks/videos/slideshows differ
by category; apparel's product-is-outfit rule overrides the pinned wardrobe;
outcome categories keep their real-footage proof rules; unknown categories degrade
to a sane default; the Styles tab renders every type with live products."""

from tt_engine.creative import style_for, all_styles
from tt_engine.creative.category_styles import DEFAULT
from tt_engine.creative.hooks import generate_hooks
from tt_engine.creative.realism import SETTINGS, enhance_prompt, scene_video_prompt
from tt_engine.creative.slideshow import build_slideshows
from tt_engine.db import models
from tt_engine.psychology import analyze


def _p(cat, pid="P-C", name="Linen Wrap Top"):
    return models.Product(id=pid, name=name, category=cat)


def _psych(name="Linen Wrap Top", cat="apparel"):
    return analyze(name, ["fits perfectly, love the fabric"], cat)


# ── registry ────────────────────────────────────────────────────────────────────
def test_aliases_land_on_the_right_style():
    assert style_for("clothing").key == "apparel"
    assert style_for("gadget").key == "electronics"
    assert style_for("GADGETS").key == "electronics"
    assert style_for("skincare").key == "beauty"
    assert style_for("dog").key == "pet"
    assert style_for("supplement").key == "wellness"
    assert style_for("unheard-of-niche") is DEFAULT
    assert style_for("") is DEFAULT


def test_every_style_is_complete_and_rooms_are_real():
    for st in all_styles():
        assert st.demo_grammar and st.proof and st.hook_templates
        assert all(s in SETTINGS for s in st.setting_bias)
        assert all(len(tmpl.format(name="X", pain="Y").split()) <= 10
                   for _, tmpl in st.hook_templates)


def test_outcome_categories_pin_real_footage_proof():
    assert "real" in style_for("pet").proof.lower()          # animal reactions
    assert "real customer footage" in style_for("beauty").proof
    assert "zero health" in style_for("wellness").proof.lower()


# ── hooks differ per category ───────────────────────────────────────────────────
def test_hooks_lead_with_category_native_angles():
    apparel = generate_hooks("Linen Wrap Top", _psych(), n=20, category="clothing")
    gadget = generate_hooks("Linen Wrap Top", _psych(), n=20, category="gadget")
    assert any("fit check" in h.text.lower() or "sizing" in h.text.lower()
               for h in apparel[:6])
    assert any("settings" in h.text.lower() or "unboxing" in h.text.lower()
               for h in gadget[:6])
    # The two categories' openings genuinely differ.
    assert [h.text for h in apparel[:6]] != [h.text for h in gadget[:6]]
    # And the generic contract still holds: n hooks, all four types, ≤10 words.
    for hooks in (apparel, gadget):
        assert len(hooks) == 20
        assert {h.type for h in hooks} == {"curiosity", "problem", "shock",
                                           "transformation"}
        assert all(len(h.text.split()) <= 10 for h in hooks)


def test_unknown_category_hooks_fall_back_to_generic():
    generic = generate_hooks("Widget", _psych("Widget", "x"), n=20, category="")
    assert len(generic) == 20                                # unchanged behavior


# ── videos differ per category ──────────────────────────────────────────────────
def test_video_prompts_carry_the_category_demo_grammar():
    top = enhance_prompt(_p("clothing"), "she shows the top")
    gadget = enhance_prompt(_p("gadget", name="Mini Label Printer"), "she demos it")
    assert "try-on" in top.prompt and "mirror" in top.prompt
    assert "hands-on function demo" in gadget.prompt
    assert top.layers["category_demo"] != gadget.layers["category_demo"]
    # Category camera replaces the generic demo grip.
    assert "full-body mirror shot" in top.layers["camera_demo"]
    assert "both hands" in gadget.layers["camera_demo"]


def test_apparel_wardrobe_rule_product_is_the_outfit():
    from tt_engine.creative import load_persona
    rp = enhance_prompt(_p("clothing"), "try-on scene", persona=load_persona())
    assert "the product IS the outfit" in rp.layers["wardrobe"]
    assert "Linen Wrap Top itself" in rp.prompt
    # Persona jewelry continuity survives the override.
    assert "jewelry" in rp.layers["wardrobe"]
    # Non-apparel keeps the pinned persona outfit.
    other = enhance_prompt(_p("hobby", name="Scoring Lame"), "demo")
    assert "IS the outfit" not in other.layers.get("wardrobe", "")


def test_category_setting_bias_intersects_persona_rooms():
    for i in range(6):
        rp = enhance_prompt(_p("gadget", name="Mini Label Printer"), "demo", index=i)
        # electronics bias: desk-office / kitchen-evening — both persona rooms.
        assert rp.layers["setting"] in ("desk-office", "kitchen-evening")


def test_seedance_animate_prompt_carries_the_grammar():
    vp = scene_video_prompt(_p("clothing"), "she turns in the mirror")
    assert "Demo grammar (Clothing & apparel)" in vp


# ── slideshows differ per category ──────────────────────────────────────────────
def test_slideshow_demo_slide_uses_the_category_lead():
    apparel = build_slideshows(_p("clothing"), _psych(), n=1)
    hobby = build_slideshows(_p("hobby", name="Scoring Lame"),
                             _psych("Scoring Lame", "hobby"), n=1)
    a_demo = next(s for s in apparel.posts[0].slides if s.role == "demo")
    h_demo = next(s for s in hobby.posts[0].slides if s.role == "demo")
    assert "mirror try-on" in a_demo.style
    assert "workbench" in h_demo.style
    assert a_demo.style != h_demo.style


# ── the dashboard tab ───────────────────────────────────────────────────────────
def test_styles_page_lists_every_category_with_live_products(tmp_path):
    import http.client
    import threading

    from tt_engine import pipeline, seed
    from tt_engine.db import Database
    from tt_engine.web import make_server

    db_path = str(tmp_path / "styles.db")
    with Database(db_path) as db:
        seed.seed_sample(db)
        pipeline.daily(db)
    srv = make_server(db_path, host="127.0.0.1", port=0)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        conn = http.client.HTTPConnection(*srv.server_address, timeout=10)
        conn.request("GET", "/styles")
        resp = conn.getresponse()
        body = resp.read().decode()
        conn.close()
        assert resp.status == 200
        import html as _html
        for label in ("Clothing & apparel", "Gadgets & tech", "Beauty & skincare",
                      "Pet products", "Home & kitchen", "Hobby & craft tools",
                      "Accessories & carry", "Toys & games", "Wellness & routine"):
            assert _html.escape(label) in body
        assert "P-COWHIDESTRAP" in body            # live product under accessories
        assert "P-DOGCALMVEST" in body             # live product under pet
        assert "Demo grammar" in body
        assert "AIGC label stays on" in body       # the invariant, on-page
        assert 'href="/styles"' in body            # it's a real nav tab
    finally:
        srv.shutdown()
        srv.server_close()
