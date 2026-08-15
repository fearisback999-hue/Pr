"""Video restyle: your own footage as the base, everything else generated.

Two properties carry the module: the base must be YOUR footage, and the product is
never restylable. Both are enforcement, not advice.
"""

import pytest

from tt_engine.creative import restyle as rs
from tt_engine.db import Database, models


def _video(tmp_path, name="clip.mp4", size=1000):
    p = tmp_path / name
    p.write_bytes(b"\x00" * size)
    return p


def _db(tmp_path):
    db = Database(str(tmp_path / "r.db"))
    db.upsert_product(models.Product(id="P1", name="Pull Up Bar", category="fitness"))
    return db


# ── the ownership gate ────────────────────────────────────────────────────────

def test_restyle_refuses_without_ownership_attestation(tmp_path):
    """Restyling a competitor's ad is the cloning workflow this project declines.
    Swapping the actor does not make their footage yours."""
    db = _db(tmp_path)
    with pytest.raises(rs.NotYourFootage) as e:
        rs.create_restyle(db, "P1", _video(tmp_path), {"wall": "sage"})
    assert "YOURS" in str(e.value)
    assert "copyrighted" in str(e.value)
    assert db.restyle_jobs() == [], "nothing may be stored on a refused job"
    db.close()


def test_restyle_accepts_with_attestation(tmp_path):
    db = _db(tmp_path)
    jid = rs.create_restyle(db, "P1", _video(tmp_path), {"wall": "sage green"},
                            i_own_this_footage=True)
    job = rs.load(db, jid)
    assert job.changes == {"wall": "sage green"}
    assert job.status == "draft"
    db.close()


# ── the product is never restylable ───────────────────────────────────────────

@pytest.mark.parametrize("target", ["product", "item", "packaging", "label"])
def test_the_product_can_never_be_restyled(tmp_path, target):
    """Changing the product misrepresents what the buyer receives."""
    db = _db(tmp_path)
    with pytest.raises(rs.ProductIsNotRestylable) as e:
        rs.create_restyle(db, "P1", _video(tmp_path), {target: "make it chrome"},
                          i_own_this_footage=True)
    assert "misrepresentation" in str(e.value)
    db.close()


def test_unknown_targets_are_refused_not_ignored(tmp_path):
    db = _db(tmp_path)
    with pytest.raises(ValueError, match="unknown restyle target"):
        rs.create_restyle(db, "P1", _video(tmp_path), {"nonsense": "x"},
                          i_own_this_footage=True)
    db.close()


def test_empty_change_set_is_refused(tmp_path):
    db = _db(tmp_path)
    with pytest.raises(ValueError, match="nothing to change"):
        rs.create_restyle(db, "P1", _video(tmp_path), {}, i_own_this_footage=True)
    db.close()


def test_a_target_with_no_instruction_is_refused(tmp_path):
    db = _db(tmp_path)
    with pytest.raises(ValueError, match="no instruction"):
        rs.create_restyle(db, "P1", _video(tmp_path), {"wall": "  "},
                          i_own_this_footage=True)
    db.close()


# ── the base file ─────────────────────────────────────────────────────────────

def test_missing_and_wrong_type_base_files_are_refused(tmp_path):
    db = _db(tmp_path)
    with pytest.raises(FileNotFoundError):
        rs.create_restyle(db, "P1", tmp_path / "nope.mp4", {"wall": "x"},
                          i_own_this_footage=True)
    txt = tmp_path / "notes.txt"
    txt.write_text("not a video")
    with pytest.raises(ValueError, match="not a video container"):
        rs.create_restyle(db, "P1", txt, {"wall": "x"}, i_own_this_footage=True)
    db.close()


def test_empty_and_oversized_base_files_are_refused(tmp_path):
    db = _db(tmp_path)
    empty = _video(tmp_path, "empty.mp4", 0)
    with pytest.raises(ValueError, match="empty"):
        rs.create_restyle(db, "P1", empty, {"wall": "x"}, i_own_this_footage=True)
    big = _video(tmp_path, "big.mp4", int(rs.MAX_BASE_MB * 1e6) + 10)
    with pytest.raises(ValueError, match="over the"):
        rs.create_restyle(db, "P1", big, {"wall": "x"}, i_own_this_footage=True)
    db.close()


def test_unknown_product_is_refused(tmp_path):
    db = _db(tmp_path)
    with pytest.raises(ValueError, match="no product"):
        rs.create_restyle(db, "NOPE", _video(tmp_path), {"wall": "x"},
                          i_own_this_footage=True)
    db.close()


# ── the prompt ────────────────────────────────────────────────────────────────

def test_prompt_leads_with_preservation_and_names_the_changes(tmp_path):
    db = _db(tmp_path)
    jid = rs.create_restyle(db, "P1", _video(tmp_path),
                            {"wall": "sage green", "room": "sunlit doorway"},
                            i_own_this_footage=True)
    text = rs.build_prompt(rs.load(db, jid))
    assert text.index("PRESERVE EXACTLY") < text.index("CHANGE:")
    assert "pixel-faithful" in text
    assert "sage green" in text and "sunlit doorway" in text
    assert "fail rather than approximate" in text
    # The handheld imperfections are the realism — must not be cleaned up.
    assert "do not stabilise" in text
    db.close()


def test_prompt_folds_in_the_roster_persona(tmp_path):
    db = _db(tmp_path)
    jid = rs.create_restyle(db, "P1", _video(tmp_path), {"wall": "x"},
                            actor_slug="maya", i_own_this_footage=True)
    text = rs.build_prompt(rs.load(db, jid))
    assert "person on camera" in text
    db.close()


# ── generation guardrails ─────────────────────────────────────────────────────

def test_generation_requires_approval_first(tmp_path):
    db = _db(tmp_path)
    jid = rs.create_restyle(db, "P1", _video(tmp_path), {"wall": "x"},
                            i_own_this_footage=True)
    with pytest.raises(ValueError, match="review the assembled prompt"):
        rs.generate_restyle(db, jid, confirm=True)
    db.close()


def test_generation_dry_runs_without_a_key_and_stamps_disclosure(tmp_path):
    db = _db(tmp_path)
    jid = rs.create_restyle(db, "P1", _video(tmp_path), {"wall": "x"},
                            i_own_this_footage=True)
    db.update_restyle_job(jid, status="approved")
    res = rs.generate_restyle(db, jid)
    assert res.dry_run
    c = res.creatives[0]
    assert c.meta["aigc_disclosure"]
    assert c.meta["substantially_altered"] is True   # TikTok's own wording
    assert c.meta["base_video"]
    db.close()


def test_a_moved_base_file_is_caught_before_spending(tmp_path):
    db = _db(tmp_path)
    v = _video(tmp_path)
    jid = rs.create_restyle(db, "P1", v, {"wall": "x"}, i_own_this_footage=True)
    db.update_restyle_job(jid, status="approved")
    v.unlink()
    with pytest.raises(FileNotFoundError):
        rs.generate_restyle(db, jid, confirm=True)
    db.close()


# ── the upload path ───────────────────────────────────────────────────────────

def test_multipart_parser_reads_fields_and_the_file():
    from tt_engine.web.server import parse_multipart
    body = (b'--X\r\nContent-Disposition: form-data; name="product_id"\r\n\r\nP1\r\n'
            b'--X\r\nContent-Disposition: form-data; name="video"; filename="a.mp4"\r\n'
            b'Content-Type: video/mp4\r\n\r\nDATA\r\n--X--\r\n')
    form = parse_multipart(body, "multipart/form-data; boundary=X")
    assert form["product_id"] == "P1"
    assert form["__file__"] == ("a.mp4", b"DATA")


def test_uploads_cannot_escape_the_upload_directory(tmp_path):
    """A crafted filename must not be able to write outside the directory."""
    from tt_engine.web.server import save_upload
    path = save_upload("../../../etc/passwd", b"x", str(tmp_path))
    assert path.startswith(str(tmp_path))
    assert "etc" not in path.rsplit("/", 1)[1] or ".." not in path


def test_uploads_never_silently_overwrite(tmp_path):
    from tt_engine.web.server import save_upload
    a = save_upload("clip.mp4", b"first", str(tmp_path))
    b = save_upload("clip.mp4", b"second", str(tmp_path))
    assert a != b, "a second upload must not clobber the first base clip"


def test_restyle_page_states_both_hard_rules(tmp_path):
    from tt_engine.web.server import page_restyle
    db = _db(tmp_path)
    html = page_restyle(db)
    assert "must be yours" in html.lower()
    assert "never restylable" in html.lower()
    db.close()


def test_restyle_is_in_the_nav():
    from tt_engine.web.render import _NAV
    assert ("Restyle", "/restyle") in _NAV
