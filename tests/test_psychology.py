from tt_engine.psychology import analyze, emotion_signal


def test_emotion_signal_scales_with_intensity():
    strong = ["OMG insane, obsessed, cannot believe it!", "the tingles are amazing!"]
    weak = ["it's fine", "does the job"]
    cs_strong, em_strong = emotion_signal(strong)
    cs_weak, em_weak = emotion_signal(weak)
    assert em_strong > em_weak
    assert cs_strong > cs_weak
    assert 0 <= em_strong <= 0.95


def test_emotion_signal_none_for_empty():
    assert emotion_signal([]) is None


def test_offline_analyze_produces_a_spine():
    reviews = [
        "this melts my tension headaches away, so relaxing",
        "helps me fall asleep, wish I found it sooner",
    ]
    profile = analyze("Scalp Massager", reviews, "beauty")
    assert profile.source == "offline"  # no LLM configured in tests
    assert profile.spine
    assert profile.emotional_trigger
    # A relief-themed corpus should surface a relief trigger.
    assert "relief" in profile.emotional_trigger.lower()


def test_offline_analyze_handles_empty_reviews():
    profile = analyze("Mystery Gadget", [], "electronics")
    assert profile.spine
    assert profile.source == "offline"
