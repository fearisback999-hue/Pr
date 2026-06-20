"""Mock-based tests for the Claude API integration — exercises the real request shape and
response parsing without a key (only the offline fallbacks are covered elsewhere)."""

import pytest

from tt_engine.llm import LLMClient, LLMUnavailable
from tt_engine.psychology import analyze


class _Block:
    def __init__(self, type_, text):
        self.type = type_
        self.text = text


class _Resp:
    def __init__(self, blocks, stop_reason="end_turn"):
        self.content = blocks
        self.stop_reason = stop_reason


class _FakeMessages:
    def __init__(self, resp, capture):
        self._resp = resp
        self.capture = capture

    def create(self, **kwargs):
        self.capture.update(kwargs)
        if isinstance(self._resp, Exception):
            raise self._resp
        return self._resp


class _FakeAnthropic:
    def __init__(self, resp, capture):
        self.messages = _FakeMessages(resp, capture)


def _client(resp):
    capture: dict = {}
    return LLMClient(client=_FakeAnthropic(resp, capture)), capture


def test_complete_text_request_shape_and_parse():
    # Adaptive thinking emits a (empty) thinking block before the text block.
    resp = _Resp([_Block("thinking", ""), _Block("text", "  here are the hooks  ")])
    client, capture = _client(resp)
    assert client.available
    out = client.complete_text("sys", "user")
    assert out == "  here are the hooks  "
    # Request follows the Claude API guidance: opus 4.8 + adaptive thinking + effort.
    assert capture["model"] == "claude-opus-4-8"
    assert capture["thinking"] == {"type": "adaptive"}
    assert capture["output_config"] == {"effort": "high"}
    assert capture["messages"] == [{"role": "user", "content": "user"}]
    assert capture["system"] == "sys"


def test_complete_json_uses_structured_output_and_parses():
    resp = _Resp([_Block("text", '{"emotional_trigger": "relief", "ok": true}')])
    client, capture = _client(resp)
    data = client.complete_json("sys", "user", {"type": "object"})
    assert data["emotional_trigger"] == "relief"
    assert capture["output_config"] == {"format": {"type": "json_schema", "schema": {"type": "object"}}}
    # JSON extraction must not set a thinking param (keeps it simple/cheap).
    assert "thinking" not in capture


def test_refusal_raises_unavailable():
    resp = _Resp([], stop_reason="refusal")
    client, _ = _client(resp)
    with pytest.raises(LLMUnavailable):
        client.complete_text("sys", "user")


def test_non_json_response_raises_unavailable():
    client, _ = _client(_Resp([_Block("text", "not json at all")]))
    with pytest.raises(LLMUnavailable):
        client.complete_json("sys", "user", {"type": "object"})


def test_api_exception_becomes_unavailable():
    client, _ = _client(RuntimeError("rate limited"))
    with pytest.raises(LLMUnavailable):
        client.complete_text("sys", "user")


def test_unavailable_client_raises():
    client = LLMClient(client=None)
    # No key/SDK in the test env → offline.
    if not client.available:
        with pytest.raises(LLMUnavailable):
            client.complete_text("sys", "user")


def test_psychology_uses_llm_when_available():
    """analyze() should route through the injected LLM and report source='llm'."""
    payload = (
        '{"emotional_trigger": "relief", "pain_point": "stress", "desire": "calm", '
        '"identity_appeal": "self-care", "impulse_factor": "cheap + instant", '
        '"spine": "It moves on relief."}'
    )
    client, _ = _client(_Resp([_Block("text", payload)]))
    profile = analyze("Scalp Massager", ["melts my tension"], "beauty", llm=client)
    assert profile.source == "llm"
    assert profile.spine == "It moves on relief."
    assert profile.emotional_trigger == "relief"


def test_psychology_falls_back_when_llm_errors():
    client, _ = _client(RuntimeError("boom"))
    profile = analyze("Scalp Massager", ["melts my tension"], "beauty", llm=client)
    assert profile.source == "offline"  # graceful degradation
    assert profile.spine
