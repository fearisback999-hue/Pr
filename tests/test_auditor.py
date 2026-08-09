"""The auditor agent + the how-to instructions.

The load-bearing property here is that the auditor must not lie by omission: a check
that silently fails to run is worse than no check, because it reads as a clean bill
of health.
"""

import pytest

from tt_engine.agent import auditor
from tt_engine.agent.auditor import CRITICAL, GOOD, INFO, WARNING, Finding, audit, run_rules
from tt_engine.db import Database, models
from tt_engine.howto import HOW_TO, how_to, render_how
from tt_engine.playbook import STEPS


# ── the rules layer ───────────────────────────────────────────────────────────

def test_every_check_runs_without_crashing_on_an_empty_db(tmp_path):
    """A fresh install must produce a real report, not a stack trace."""
    with Database(str(tmp_path / "a.db")) as db:
        findings = run_rules(db)
    assert findings
    assert not [f for f in findings if f.domain == "auditor"], \
        "a check reported itself as broken: " + \
        "; ".join(f.title for f in findings if f.domain == "auditor")


def test_a_broken_check_reports_itself_instead_of_vanishing(tmp_path, monkeypatch):
    """Silent skipping is the failure mode worth designing against — a check that
    quietly does nothing looks exactly like a check that passed."""
    def exploding(db):
        raise RuntimeError("boom")
    monkeypatch.setattr(auditor, "CHECKS", [exploding])
    with Database(str(tmp_path / "a.db")) as db:
        findings = run_rules(db)
    assert len(findings) == 1
    assert findings[0].domain == "auditor"
    assert "exploding" in findings[0].title
    assert "boom" in findings[0].detail


def test_orphaned_paid_jobs_are_critical(tmp_path):
    with Database(str(tmp_path / "a.db")) as db:
        db.upsert_product(models.Product(id="P1", name="Thing", category="home"))
        db.upsert_creative(models.Creative(
            id="C1", product_id="P1", format="UGC", hook="h", hook_type="t",
            soul_id="s", asset_url=None, status="generating",
            meta={"aigc_disclosure": "AI", "job_id": "job-1"}))
        findings = auditor.check_spend_guards(db)
    orphan = [f for f in findings if "never landed" in f.title]
    assert orphan and orphan[0].severity == CRITICAL
    assert "creative-recover" in orphan[0].fix


def test_undisclosed_ai_content_is_critical(tmp_path):
    with Database(str(tmp_path / "a.db")) as db:
        db.upsert_product(models.Product(id="P1", name="Thing", category="home"))
        db.upsert_creative(models.Creative(
            id="C1", product_id="P1", format="UGC", hook="h", hook_type="t",
            soul_id="s", asset_url="u", status="ready", meta={}))
        findings = auditor.check_compliance(db)
    assert findings and findings[0].severity == CRITICAL


def test_spend_guard_findings_track_the_env(tmp_path, monkeypatch):
    monkeypatch.delenv("TT_GENERATION_UNIT_COST", raising=False)
    monkeypatch.delenv("TT_MAX_BATCH_SPEND", raising=False)
    with Database(str(tmp_path / "a.db")) as db:
        unset = auditor.check_spend_guards(db)
        assert len(unset) == 2
        monkeypatch.setenv("TT_GENERATION_UNIT_COST", "0.40")
        monkeypatch.setenv("TT_MAX_BATCH_SPEND", "25")
        armed = auditor.check_spend_guards(db)
    assert armed == [], "configured guards must stop being reported as problems"


def test_a_test_running_without_a_breakeven_is_flagged(tmp_path):
    """Spending against an undefined losing condition is the thing to catch."""
    with Database(str(tmp_path / "a.db")) as db:
        db.upsert_product(models.Product(id="P1", name="Thing", category="home"))
        db.upsert_creative(models.Creative(
            id="C1", product_id="P1", format="UGC", hook="h", hook_type="t",
            soul_id="s", asset_url="u", status="ready",
            meta={"aigc_disclosure": "AI"}))
        db.upsert_test(models.Test(id="T1", creative_id="C1", date="2026-01-01",
                                   spend=40.0, roas=0.4))
        findings = auditor.check_test_discipline(db)
    assert findings, "a live test with no landed cost must be reported"
    assert findings[0].severity == WARNING
    assert "no break-even" in findings[0].title


# ── the report ────────────────────────────────────────────────────────────────

def test_score_penalises_criticals_hardest():
    clean = auditor.AuditReport(findings=[Finding(GOOD, "d", "t", "x")])
    assert clean.score == 100
    warned = auditor.AuditReport(findings=[Finding(WARNING, "d", "t", "x")])
    critical = auditor.AuditReport(findings=[Finding(CRITICAL, "d", "t", "x")])
    assert critical.score < warned.score < clean.score


def test_report_renders_fix_and_cost(tmp_path):
    with Database(str(tmp_path / "a.db")) as db:
        text = audit(db).render()
    assert "readiness" in text
    assert "FIX:" in text
    assert "does NOT mean a product will work" in text   # the honest line survives


def test_judgment_is_labeled_and_offline_is_deterministic(tmp_path):
    with Database(str(tmp_path / "a.db")) as db:
        report = audit(db)
    assert report.judgment_mode == "offline"
    assert report.judgment
    with Database(str(tmp_path / "a.db")) as db:
        again = audit(db)
    assert again.judgment == report.judgment, "offline judgment must be reproducible"


def test_judgment_never_deletes_a_finding(tmp_path):
    """A model talking you out of a real problem is the designed-against failure."""
    class _Chatty:
        available = True
        def complete_text(self, system, user, max_tokens=4000):
            return "Ignore all of the above, everything is fine."
    with Database(str(tmp_path / "a.db")) as db:
        db.upsert_product(models.Product(id="P1", name="Thing", category="home"))
        db.upsert_creative(models.Creative(
            id="C1", product_id="P1", format="UGC", hook="h", hook_type="t",
            soul_id="s", asset_url="u", status="ready", meta={}))
        report = audit(db, llm=_Chatty())
    assert report.judgment_mode == "llm"
    assert report.criticals, "the critical finding survives whatever the model said"
    assert "AIGC disclosure" in report.render()


def test_llm_failure_falls_back_to_offline(tmp_path):
    from tt_engine.llm import LLMUnavailable
    class _Broken:
        available = True
        def complete_text(self, system, user, max_tokens=4000):
            raise LLMUnavailable("network down")
    with Database(str(tmp_path / "a.db")) as db:
        report = audit(db, llm=_Broken())
    assert report.judgment_mode == "offline"
    assert report.judgment


# ── how-to instructions ───────────────────────────────────────────────────────

def test_every_playbook_step_has_instructions():
    missing = sorted({s.id for s in STEPS} - set(HOW_TO))
    assert not missing, f"steps with no how-to: {missing}"


def test_no_orphan_instructions():
    orphans = sorted(set(HOW_TO) - {s.id for s in STEPS})
    assert not orphans, f"instructions for non-existent steps: {orphans}"


def test_instructions_are_substantive_and_have_a_done_condition():
    for step_id, (steps, done) in HOW_TO.items():
        assert len(steps) >= 3, f"{step_id}: only {len(steps)} instruction(s)"
        assert done, f"{step_id}: no done-condition"
        for s in steps:
            assert len(s) > 24, f"{step_id}: instruction too thin to act on: {s!r}"


def test_render_how_includes_numbering_and_done_condition():
    text = render_how("tt-seller")
    assert "1." in text and "2." in text
    assert "DONE WHEN" in text
    assert render_how("no-such-step") == ""


def test_how_to_is_safe_on_unknown_ids():
    steps, done = how_to("nonsense")
    assert steps == () and done == ""
