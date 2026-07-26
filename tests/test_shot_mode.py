"""Shot-mode fallback ladder: shoot AROUND the AI's weak spots when faces struggle.
Invariants — faceless crops the face out (no face reference, voiceover not lip-sync),
face_light hides it, the garment swap still uses the REAL product, the toggle
persists, and it flows through fit-check + general runbook. Label stays on in all modes."""

from tt_engine.creative import (
    build_fit_check,
    build_pack,
    build_runbook,
    garment_swap_prompt,
    load_persona,
)
from tt_engine.creative.realism import (
    SHOT_MODES,
    scene_frame_prompt,
    scene_video_prompt,
    shot_mode_spec,
)
from tt_engine.db import Database, models
from tt_engine.psychology import analyze


def _shorts():
    return models.Product(id="P-SHORTS", name="Breathable Lounge Shorts",
                          category="clothing")


def _pack(product, cat="apparel"):
    return build_pack(product, analyze(product.name, ["fits great"], cat),
                      n_hooks=8, n_concepts=8, n_scripts=3)


# ── the ladder itself ───────────────────────────────────────────────────────────
def test_ladder_has_three_tiers_face_to_faceless():
    assert SHOT_MODES == ("full", "face_light", "faceless")
    assert shot_mode_spec("full")["face"] is True
    assert shot_mode_spec("face_light")["face"] is False
    assert shot_mode_spec("faceless")["face"] is False
    assert shot_mode_spec("faceless")["talks"] is False       # no lip-sync
    # Unknown mode degrades to full, never crashes.
    assert shot_mode_spec("nonsense")["face"] is True


# ── garment swap respects the mode (the clothing example) ───────────────────────
def test_faceless_garment_swap_crops_the_face_and_drops_the_reference():
    full = garment_swap_prompt(_shorts(), persona=load_persona(), shot_mode="full")
    faceless = garment_swap_prompt(_shorts(), persona=load_persona(),
                                   shot_mode="faceless", garment_angles=("front", "back"))
    assert "face EXACTLY" in full.prompt and "model reference image" in full.attach
    assert "No face in frame" in faceless.prompt
    assert "CROP ABOVE THE CHIN" in faceless.prompt
    assert "model reference image" not in faceless.attach      # no face to match
    # The REAL garment is still swapped in — the whole point isn't lost.
    assert "EXACT garment from the attached clothing photo" in faceless.prompt
    assert "clothing photo(s): front, back" in faceless.attach


def test_faceless_video_is_voiceover_not_lip_sync():
    full = scene_video_prompt(_shorts(), "turn in the mirror", dialogue="fit check",
                              shot_mode="full")
    faceless = scene_video_prompt(_shorts(), "turn in the mirror", dialogue="fit check",
                                  shot_mode="faceless")
    assert "says, naturally" in full                           # on-camera lip-sync
    assert "VOICEOVER (not on camera)" in faceless
    assert "says, naturally" not in faceless
    assert "NO face enters the frame" in faceless


def test_faceless_scene_frame_crops_face():
    ff = scene_frame_prompt(_shorts(), "using it", shot_mode="faceless",
                            needs_product=True)
    assert "NO face in frame" in ff.prompt
    assert "actor reference image" not in ff.attach


# ── the fit-check runbook end to end ────────────────────────────────────────────
def test_fit_check_faceless_beats_and_render():
    product = _shorts()
    rb = build_fit_check(product, _pack(product).hooks, n_clips=1, shot_mode="faceless")
    assert rb.shot_mode == "faceless"
    labels = [lbl for lbl, _ in rb.clips[0].beats]
    assert any("reveal" in l for l in labels)                  # not "walk in" (face)
    text = rb.render()
    assert "Faceless" in text
    assert "crops the face out" in text
    assert "AI-generated" in text                              # label still on


def test_full_mode_is_unchanged_default():
    product = _shorts()
    rb = build_fit_check(product, _pack(product).hooks, n_clips=1)   # default full
    assert rb.shot_mode == "full"
    assert "walk into mirror frame" in rb.clips[0].beats[0][1]
    assert "face EXACTLY" in rb.clips[0].garment_frame.prompt


def test_general_runbook_faceless_makes_all_scenes_facefree():
    product = models.Product(id="P-TOOL", name="Herb Stripper", category="home")
    rb = build_runbook(product, _pack(product, "home"), n_ads=1, shot_mode="faceless")
    from tt_engine.creative import ProductionRunbook
    assert isinstance(rb, ProductionRunbook)
    for scene in rb.ads[0].scenes:
        assert not scene.on_camera                            # nobody talks to camera
        assert "NO face in frame" in scene.frame.prompt


# ── the persisted toggle ────────────────────────────────────────────────────────
def test_setting_persists_and_defaults_full(tmp_path):
    with Database(str(tmp_path / "s.db")) as db:
        assert db.get_setting("shot_mode", "full") == "full"
        db.set_setting("shot_mode", "faceless")
        assert db.get_setting("shot_mode", "full") == "faceless"


def test_dashboard_toggle_switches_mode(tmp_path):
    import http.client
    import threading

    from tt_engine import pipeline, seed
    from tt_engine.web import make_server

    db_path = str(tmp_path / "w.db")
    with Database(db_path) as db:
        seed.seed_sample(db)
        pipeline.daily(db)
    srv = make_server(db_path, host="127.0.0.1", port=0)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        addr = srv.server_address
        conn = http.client.HTTPConnection(*addr, timeout=10)
        conn.request("GET", "/advertising")
        body = conn.getresponse().read().decode()
        conn.close()
        assert "Shot mode" in body and "Faceless" in body

        conn = http.client.HTTPConnection(*addr, timeout=10)
        conn.request("GET", "/shot-mode?set=faceless")
        resp = conn.getresponse(); resp.read(); conn.close()
        assert resp.status == 303                              # toggle + redirect
        with Database(db_path) as db:
            assert db.get_setting("shot_mode") == "faceless"
    finally:
        srv.shutdown()
        srv.server_close()
