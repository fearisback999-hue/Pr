"""The dashboard assistant: grounded in live DB state, honest about its mode, never
inventing numbers offline, and answering through the LLM when one is injected."""

from tt_engine import pipeline, seed
from tt_engine.assistant import KNOWLEDGE, answer, build_context
from tt_engine.db import Database
from tt_engine.llm import LLMClient


def _db(tmp_path):
    return Database(str(tmp_path / "assist.db"))


def _seeded(tmp_path):
    db = Database(str(tmp_path / "assist.db"))
    seed.seed_sample(db)
    pipeline.daily(db)
    return db


def test_context_contains_live_state_and_knowledge(tmp_path):
    db = _seeded(tmp_path)
    ctx = build_context(db)
    assert "P-SOURDOUGHLAME" in ctx                 # live board
    assert "[TEST]" in ctx and "[KILL]" in ctx       # verdicts included
    assert "Playbook:" in ctx                        # playbook progress
    assert "48 straight hours" in ctx                # kill/scale knowledge
    assert "6% referral" in ctx                      # fee knowledge
    db.close()


def test_offline_routes_fee_questions_to_fee_knowledge(tmp_path):
    with _db(tmp_path) as db:
        r = answer(db, "how much profit do I actually keep after fees?")
        assert r.mode == "offline"
        assert "fees" in r.sections
        assert "6% referral" in r.text
        assert "Offline mode" in r.text              # labels itself honestly


def test_offline_leads_with_named_product_live_state(tmp_path):
    db = _seeded(tmp_path)
    r = answer(db, "is P-PIMPLEPATCH worth testing?")
    assert "P-PIMPLEPATCH" in r.text
    assert "KILL" in r.text                          # its real verdict, not a vibe
    assert "commodity-saturated" in r.text           # the real gate failure
    db.close()


def test_offline_what_next_uses_the_live_guide(tmp_path):
    db = _seeded(tmp_path)
    r = answer(db, "what should I do next?")
    assert "next actions" in r.text.lower()
    assert "tt_engine.cli" in r.text                 # concrete commands, not vibes
    db.close()


def test_unmatched_question_falls_back_to_commands(tmp_path):
    with _db(tmp_path) as db:
        r = answer(db, "zzz qqq unrelated gibberish")
        assert r.sections == ["commands"]


def test_llm_mode_uses_injected_client(tmp_path):
    class FakeResp:
        stop_reason = "end_turn"
        content = [type("B", (), {"type": "text", "text": "Test P-SOURDOUGHLAME first."})()]

    class FakeMessages:
        def create(self, **kwargs):
            # The context must actually be handed to the model.
            joined = str(kwargs)
            assert "LIVE STATE" in joined and "QUESTION" in joined
            return FakeResp()

    class FakeSDK:
        messages = FakeMessages()

    db = _seeded(tmp_path)
    llm = LLMClient(client=FakeSDK())
    r = answer(db, "which product first?", llm=llm)
    assert r.mode == "llm"
    assert "P-SOURDOUGHLAME" in r.text
    db.close()


def test_knowledge_sections_stay_honest():
    joined = " ".join(KNOWLEDGE.values())
    assert "most tests lose" in joined or "reverify" in joined   # caveats survive
    assert "will not scrape" in joined                            # the guardrail is stated
