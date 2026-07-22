"""Account health / shadowban guidance. Invariants — the honest answer (labeled AI
is fine; automated ACCOUNT operation is the risk); the cadence ramp warms new
accounts and caps volume; the framing stays compliance, never evasion; the guide and
assistant surface it."""

from tt_engine import account_safety
from tt_engine.account_safety import (
    RULES,
    SAFE_POSTS_PER_DAY,
    cadence_advice,
    ramp_cap,
    render,
)


def test_the_honest_answer_is_stated():
    text = render()
    assert "LABELED AI content" in text
    assert "automated account operation" in text.lower()
    assert "plans, YOU post" in text or "it plans, YOU post" in text
    # It never sells evasion.
    low = text.lower()
    assert "evasion" in low and "not evasion" in low
    assert "undetectable" not in low
    assert "avoid detection" not in low


def test_the_first_rule_is_human_posting_not_auto_posters():
    top = RULES[0]
    assert "HUMAN posts" in top.rule
    assert "auto-poster" in top.rule.lower()
    assert "unofficial" in top.why.lower()


def test_disclosure_rule_is_present():
    assert any("AIGC label" in r.rule for r in RULES)


def test_ramp_warms_new_accounts_then_caps():
    assert ramp_cap(2) == 2          # first week: gentle
    assert ramp_cap(20) == 3         # first month: moderate
    assert ramp_cap(90) == SAFE_POSTS_PER_DAY
    assert ramp_cap(2) < ramp_cap(90)


def test_cadence_flags_blasting_and_fresh_accounts():
    risky = cadence_advice(account_age_days=3, planned_per_day=6)
    assert not risky.ok
    assert any("exceeds" in w for w in risky.warnings)
    assert any("first week" in w for w in risky.warnings)

    fine = cadence_advice(account_age_days=90, planned_per_day=3)
    assert fine.ok and not fine.warnings


def test_reduced_reach_playbook_diagnoses_not_evades():
    steps = " ".join(account_safety.REDUCED_REACH_PLAYBOOK).lower()
    assert "account status" in steps or "strikes" in steps
    assert "pause posting" in steps
    assert "content quality" in steps          # sometimes it's the hook, not a ban
    # No "make it look human to dodge the filter" framing.
    assert "dodge" not in steps and "evade" not in steps


def test_slideshow_plan_carries_the_post_from_app_rule():
    from tt_engine.creative import build_slideshows
    from tt_engine.db import models
    from tt_engine.psychology import analyze
    product = models.Product(id="P-X", name="Thing", category="accessories")
    plan = build_slideshows(product, analyze("Thing", ["nice"], "accessories"), n=1)
    assert any("POST FROM THE APP" in n for n in plan.notes)


def test_assistant_routes_shadowban_questions(tmp_path):
    from tt_engine import pipeline, seed
    from tt_engine.assistant import answer
    from tt_engine.db import Database
    with Database(str(tmp_path / "a.db")) as db:
        seed.seed_sample(db)
        pipeline.daily(db)
        out = answer(db, "will tiktok shadowban us if it's run by a bot")
    low = out.text.lower()
    assert "label" in low
    assert "automated account" in low or "auto-post" in low
    assert "never touches your account" in low or "you post" in low
