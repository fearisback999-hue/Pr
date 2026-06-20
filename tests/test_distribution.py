from tt_engine.distribution import (
    OUTREACH_PRINCIPLES,
    CreatorProspect,
    build_seeding_plan,
    rank_creators,
    score_creator,
)


def _p(handle, followers, niche, eng):
    return CreatorProspect(handle=handle, followers=followers, niche=niche, engagement_rate=eng)


def test_niche_fit_and_reach_drive_score():
    on_niche = score_creator(_p("a", 200_000, "beauty", 0.08), "beauty")
    off_niche = score_creator(_p("b", 200_000, "gaming", 0.08), "beauty")
    assert on_niche.score > off_niche.score
    assert on_niche.fit == 1.0
    assert off_niche.fit < 1.0


def test_rank_and_seeding_plan_size():
    prospects = [
        _p("big_fit", 400_000, "beauty", 0.09),
        _p("small_off", 5_000, "tech", 0.02),
        _p("mid_fit", 80_000, "beauty", 0.06),
    ]
    ranked = rank_creators(prospects, "beauty")
    assert ranked[0].prospect.handle == "big_fit"

    plan = build_seeding_plan("P", prospects, "beauty", samples=2)
    assert plan.samples_to_send == 2
    assert len(plan.targets) == 2
    # The relationship stays human — principles are surfaced, copy is not generated.
    assert plan.principles == OUTREACH_PRINCIPLES
    assert any("yourself" in p for p in plan.principles)


def test_seeding_plan_caps_at_available_creators():
    plan = build_seeding_plan("P", [_p("only", 10_000, "beauty", 0.05)], "beauty", samples=10)
    assert plan.samples_to_send == 1
