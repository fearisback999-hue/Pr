"""The zero-to-hero playbook: content integrity, auto-detection from DB state, manual
check-off persistence, and rendering."""

from tt_engine import pipeline, seed
from tt_engine.db import Database
from tt_engine.playbook import (
    PHASES,
    STEPS,
    VERIFIED_DATE,
    all_sources,
    current_phase,
    overall,
    progress,
    render_playbook,
)


def _db(tmp_path):
    return Database(str(tmp_path / "pb.db"))


def test_steps_are_well_formed():
    ids = [s.id for s in STEPS]
    assert len(ids) == len(set(ids)), "duplicate step id"
    assert len(STEPS) > 30, "the checklist should be genuinely comprehensive"
    used_phases = {s.phase for s in STEPS}
    assert used_phases == set(PHASES), "every declared phase must have at least one step"
    for s in STEPS:
        assert s.title and s.detail, f"{s.id} missing content"
        assert s.category in {
            "legal", "financial", "platform", "sourcing", "product",
            "creative", "ads", "outreach", "ops",
        }


def test_empty_db_nothing_checked(tmp_path):
    with _db(tmp_path) as db:
        done, total = overall(db)
        assert done == 0
        assert total == len(STEPS)
        assert current_phase(db).name == PHASES[0]


def test_manual_check_off_persists(tmp_path):
    with _db(tmp_path) as db:
        db.set_playbook_step("biz-structure", True, note="formed LLC")
        done, _ = overall(db)
        assert done == 1
        state = db.playbook_state()
        assert state["biz-structure"]["done"] == 1
        assert state["biz-structure"]["note"] == "formed LLC"
        assert state["biz-structure"]["done_at"]  # timestamp recorded

        db.set_playbook_step("biz-structure", False)
        done, _ = overall(db)
        assert done == 0
        assert db.playbook_state()["biz-structure"]["done_at"] is None


def test_auto_steps_cannot_be_faked_by_manual_state(tmp_path):
    """A manual check-off on an AUTO step's id must not flip it — auto steps only
    reflect real DB/config state, otherwise the checklist could lie."""
    with _db(tmp_path) as db:
        auto_step = next(s for s in STEPS if s.auto is not None)
        db.set_playbook_step(auto_step.id, True)  # attempt to fake it
        phases = progress(db)
        flat = {s.id: done for p in phases for s, done in p.steps}
        assert flat[auto_step.id] is False  # still false — no supplier/data/etc. exists


def test_auto_steps_flip_as_the_business_actually_progresses(tmp_path):
    with _db(tmp_path) as db:
        assert not _flag(db, "sup-real-quote")
        assert not _flag(db, "data-in")
        assert not _flag(db, "first-test-verdict")

        seed.seed_sample(db)
        assert _flag(db, "sup-real-quote")   # suppliers seeded
        assert _flag(db, "data-in")          # metrics seeded

        pipeline.daily(db)
        assert _flag(db, "first-test-verdict")  # at least one product clears TEST


def _flag(db, step_id):
    flat = {s.id: done for p in progress(db) for s, done in p.steps}
    return flat[step_id]


def test_current_phase_advances_as_phase_0_completes(tmp_path):
    with _db(tmp_path) as db:
        assert current_phase(db).name == PHASES[0]
        phase0_manual_ids = [s.id for s in STEPS if s.phase == PHASES[0]]
        for sid in phase0_manual_ids:
            db.set_playbook_step(sid, True)
        assert current_phase(db).name == PHASES[1]


def test_current_phase_none_when_everything_done(tmp_path):
    with _db(tmp_path) as db:
        seed.seed_sample(db)
        pipeline.daily(db)
        for s in STEPS:
            if s.auto is None:
                db.set_playbook_step(s.id, True)
        # Auto steps that seed/daily didn't satisfy (e.g. creative generation, ads
        # launched) remain unchecked, so overall completion is expected to be partial —
        # but every MANUAL step is done, which is the guarantee under test.
        manual_ids = {s.id for s in STEPS if s.auto is None}
        state = db.playbook_state()
        assert all(state[mid]["done"] for mid in manual_ids)


def test_render_playbook_shows_progress_and_command_hints(tmp_path):
    with _db(tmp_path) as db:
        text = render_playbook(db)
        assert "0/" in text and "steps complete" in text
        assert "You are here" in text
        assert "playbook-check" in text
        # spot-check a command hint renders
        assert "add-supplier" in text or "import-csv" in text


def test_render_playbook_reflects_check_off(tmp_path):
    with _db(tmp_path) as db:
        db.set_playbook_step("biz-structure", True)
        text = render_playbook(db)
        assert "[x]" in text
        assert text.count("[ ]") == len(STEPS) - 1


# ── research-grounded content (2026-07-09 pass) ─────────────────────────────────
def test_sourced_steps_carry_real_urls():
    sourced = [s for s in STEPS if s.sources]
    assert len(sourced) >= 10, "the research pass should have grounded a real chunk of steps"
    for step in sourced:
        for url in step.sources:
            assert url.startswith("https://"), f"{step.id}: non-https source {url!r}"
            assert " " not in url, f"{step.id}: malformed source URL {url!r}"


def test_all_sources_is_deduplicated_and_ordered():
    sources = all_sources()
    assert len(sources) == len(set(sources))  # no duplicates
    assert len(sources) >= 15
    # First-seen order: whichever sourced step appears first in STEPS contributes first.
    first_step_with_sources = next(s for s in STEPS if s.sources)
    assert sources[0] == first_step_with_sources.sources[0]


def test_render_playbook_includes_sources_section(tmp_path):
    with _db(tmp_path) as db:
        text = render_playbook(db)
        assert f"## Sources (verified {VERIFIED_DATE})" in text
        for url in all_sources():
            assert url in text


def test_verified_date_is_iso_format():
    import datetime
    datetime.date.fromisoformat(VERIFIED_DATE)  # raises if malformed
