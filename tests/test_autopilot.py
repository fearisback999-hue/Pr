"""Autopilot: the approval-gated automation loop. Invariants under test — nothing
executes without approval; external (spend) stages can never be flipped to auto;
manual stages refuse approval and clear themselves when state advances; rejection
sticks until the world moves; the audit trail records everything."""

from datetime import date

import pytest

from tt_engine import autopilot, pipeline, seed
from tt_engine.autopilot import EXTERNAL_STAGES, INTERNAL_STAGES, kind_for
from tt_engine.db import Database


@pytest.fixture()
def db(tmp_path):
    with Database(str(tmp_path / "ap.db")) as db:
        seed.seed_sample(db)
        pipeline.daily(db)
        yield db


def _pending(db, stage=None, pid=None):
    items = db.autopilot_actions(status="pending")
    return [i for i in items
            if (stage is None or i["stage"] == stage)
            and (pid is None or i["product_id"] == pid)]


# ── proposing ───────────────────────────────────────────────────────────────────
def test_run_proposes_but_executes_nothing_by_default(db):
    report = autopilot.run(db)
    assert report.proposed
    assert report.auto_executed == []                  # every step asks first
    assert _pending(db, stage="build-creative")        # TEST products queued (internal)
    assert _pending(db, stage="gated")                 # blocked products visible (manual)
    # Proposing changed no product state: no creatives were built.
    assert all(not db.creatives_for(i["product_id"])
               for i in _pending(db, stage="build-creative"))


def test_run_is_idempotent(db):
    autopilot.run(db)
    n = len(_pending(db))
    report2 = autopilot.run(db)
    assert report2.proposed == []                      # nothing double-queued
    assert len(_pending(db)) == n


# ── approving ───────────────────────────────────────────────────────────────────
def test_approve_executes_internal_step_and_queue_advances(db):
    autopilot.run(db)
    item = _pending(db, stage="build-creative", pid="P-SOURDOUGHLAME")[0]
    result = autopilot.approve(db, item["id"])
    assert "briefed" in result or "planned" in result
    assert db.creatives_for("P-SOURDOUGHLAME")         # the work actually happened
    assert db.autopilot_action(item["id"])["status"] == "executed"

    # Next run: the stale stage is superseded, the NEXT stage is proposed.
    report = autopilot.run(db)
    assert not _pending(db, stage="build-creative", pid="P-SOURDOUGHLAME")
    new = _pending(db, pid="P-SOURDOUGHLAME")
    assert new and new[0]["stage"] != "build-creative"


def test_approve_refuses_manual_steps_with_instructions(db):
    autopilot.run(db)
    item = _pending(db, stage="gated")[0]
    with pytest.raises(ValueError, match="off-engine"):
        autopilot.approve(db, item["id"])
    assert db.autopilot_action(item["id"])["status"] == "pending"   # untouched


def test_approve_refuses_double_execution(db):
    autopilot.run(db)
    item = _pending(db, stage="build-creative")[0]
    autopilot.approve(db, item["id"])
    with pytest.raises(ValueError, match="already"):
        autopilot.approve(db, item["id"])


def test_reject_sticks_until_the_world_moves(db):
    autopilot.run(db)
    item = _pending(db, stage="build-creative", pid="P-SOURDOUGHLAME")[0]
    autopilot.reject(db, item["id"], "not this week")
    report = autopilot.run(db)
    # No nagging: the same (product, stage) is not re-proposed.
    assert not _pending(db, stage="build-creative", pid="P-SOURDOUGHLAME")


# ── policy: earned automation, with a hard floor ────────────────────────────────
def test_policy_auto_executes_internal_stage_on_sight(db):
    # Make every product need a re-score (scores dated yesterday).
    db.conn.execute("UPDATE scores SET date='2026-01-01'")
    db.conn.commit()
    autopilot.set_policy(db, "needs-score", "auto")
    report = autopilot.run(db)
    assert report.auto_executed                        # executed without approval
    assert all("[auto]" in i["result"] for i in report.auto_executed)
    today = date.today().isoformat()
    for i in report.auto_executed:
        assert db.latest_score(i["product_id"]).date == today


def test_external_stages_can_never_be_auto(db):
    for stage in EXTERNAL_STAGES:
        with pytest.raises(ValueError, match="never"):
            autopilot.set_policy(db, stage, "auto")


def test_manual_stages_cannot_be_automated(db):
    with pytest.raises(ValueError, match="off-engine"):
        autopilot.set_policy(db, "launch", "auto")


def test_kind_classification_is_exhaustive_and_conservative():
    assert kind_for("generate") == "external"          # money = external, forever
    for s in INTERNAL_STAGES:
        assert kind_for(s) == "internal"
    # Anything unknown defaults to manual — the safe direction.
    assert kind_for("some-future-stage") == "manual"


# ── the record decision executor ────────────────────────────────────────────────
def test_kill_and_scale_record_results(db):
    from tt_engine.autopilot import _EXECUTORS
    msg = _EXECUTORS["kill-now"](db, "P-SOURDOUGHLAME")
    assert "KILL recorded" in msg
    assert db.latest_result("P-SOURDOUGHLAME").decision == "kill"


def test_render_queue_states_the_policy_floor(db):
    autopilot.run(db)
    text = autopilot.render_queue(db)
    assert "Awaiting your approval" in text
    assert "SPENDS MONEY" in text or "always require approval" in text
    assert "generate" in text                          # the external stage is named
