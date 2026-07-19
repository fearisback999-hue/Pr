"""Slideshow carousels: the cheap-volume format. Invariants — the face-covered
mirror-selfie anchors slide 1; personless styles carry no wardrobe (incoherence is
a tell); one room per post; the agency '550/day' number is reality-checked to a
sane single-store cadence; disclosure and no-outcome-claims stay on."""

from tt_engine.creative import build_slideshows, load_persona
from tt_engine.creative import realism
from tt_engine.creative.slideshow import POSTS_PER_DAY, STYLES
from tt_engine.db import models
from tt_engine.psychology import analyze


def _plan(n=2, pid="P-COWHIDESTRAP", name="Cowhide Guitar Strap", cat="accessories"):
    product = models.Product(id=pid, name=name, category=cat)
    psych = analyze(name, ["love the leather, quality feels amazing"], cat)
    return build_slideshows(product, psych, n=n)


def test_slide_one_is_the_face_covered_mirror_selfie():
    plan = _plan()
    for post in plan.posts:
        first = post.slides[0]
        assert first.role == "hook"
        assert "phone covering the face" in first.style
        assert "face hidden by the phone" in first.image.prompt
        # No actor reference needed when the face is hidden.
        assert "actor reference" not in first.image.attach


def test_slide_arc_and_one_room_per_post():
    plan = _plan()
    envs = {k: v["environment"] for k, v in realism.SETTINGS.items()}
    p = load_persona()
    for post in plan.posts:
        assert [s.role for s in post.slides] == ["hook", "context", "demo",
                                                 "detail", "cta"]
        assert post.setting in p.settings              # her rooms only
        for s in post.slides:
            assert envs[post.setting] in s.image.prompt  # same room, every slide


def test_personless_styles_carry_no_wardrobe():
    plan = _plan(n=4)
    for post in plan.posts:
        for s in post.slides:
            if "flat-lay" in s.style or "close-up" in s.style:
                assert "Wearing" not in s.image.prompt
                assert "no person in frame" in s.image.prompt
                assert "actor reference" not in s.image.attach
            elif "phone covering the face" not in s.style:
                assert "actor reference image" in s.image.attach


def test_image_rules_inherited():
    plan = _plan()
    for post in plan.posts:
        for s in post.slides:
            assert "iPhone 15 Pro" in s.image.prompt
            assert "photorealism" in s.image.negative
            assert "photorealism" not in s.image.prompt


def test_render_reality_checks_the_agency_number_and_keeps_guardrails():
    text = _plan().render()
    assert "550/day" in text and "spam" in text        # the number is contextualized
    assert f"~{POSTS_PER_DAY} slideshows/day" in text  # the sane cadence stated
    assert "AI-generated" in text                      # disclosure on top
    assert "outcome" in text and "real footage" in text
    assert "Maya" in text


def test_overlays_and_captions_present_and_deterministic():
    a, b = _plan(), _plan()
    assert a.render() == b.render()                    # deterministic offline
    for post in a.posts:
        assert post.slides[0].overlay == post.hook     # hook text on slide 1
        assert post.caption
        assert "AI-generated" in post.caption          # label travels with the post


def test_ai_plan_weekly_mix_includes_slideshows():
    from tt_engine.creative import build_creator_plan
    from tt_engine.economics import compute_economics
    product = models.Product(id="P-X", name="Thing", category="accessories")
    plan = build_creator_plan(product, compute_economics(39.99, 9.0, 3.0))
    assert any("slideshow" in m for m in plan.weekly_mix)
