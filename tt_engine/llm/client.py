"""Thin wrapper over the Anthropic SDK.

Defaults follow the Claude API guidance: model `claude-opus-4-8`, adaptive thinking for
the generative calls, and modest max_tokens (well under the streaming guard) for these
short enrichment tasks. Structured extraction uses `output_config.format` (JSON schema).
"""

from __future__ import annotations

import json
from typing import Any

from ..config import CONFIG


class LLMUnavailable(RuntimeError):
    """Raised when an LLM call is attempted but no key/SDK is configured, or it errored."""


class LLMClient:
    def __init__(self, config=CONFIG, client=None):
        """`client` lets callers inject a pre-built SDK client (e.g. AnthropicBedrock /
        AnthropicVertex, or a fake in tests). When None, build the first-party client iff
        a key + SDK are available; otherwise stay offline (`available == False`)."""
        self.config = config
        self._client = client
        if client is None and config.llm_available:
            import anthropic  # imported lazily; presence already checked by config

            self._client = anthropic.Anthropic(api_key=config.anthropic_api_key)

    @property
    def available(self) -> bool:
        return self._client is not None

    # ── text generation (hooks, scripts) ───────────────────────────────────────
    def complete_text(self, system: str, user: str, max_tokens: int = 4000) -> str:
        if not self.available:
            raise LLMUnavailable("no Claude API key/SDK configured")
        try:
            resp = self._client.messages.create(
                model=self.config.llm_model,
                max_tokens=max_tokens,
                system=system,
                thinking={"type": "adaptive"},
                output_config={"effort": self.config.llm_effort},
                messages=[{"role": "user", "content": user}],
            )
        except Exception as exc:  # network, auth, rate-limit, etc. — fall back gracefully
            raise LLMUnavailable(str(exc)) from exc
        if resp.stop_reason == "refusal":
            raise LLMUnavailable("model refused the request")
        return _first_text(resp)

    # ── structured extraction (psychology, content-fit) ────────────────────────
    def complete_json(
        self, system: str, user: str, schema: dict[str, Any], max_tokens: int = 3000
    ) -> dict[str, Any]:
        if not self.available:
            raise LLMUnavailable("no Claude API key/SDK configured")
        try:
            resp = self._client.messages.create(
                model=self.config.llm_model,
                max_tokens=max_tokens,
                system=system,
                output_config={"format": {"type": "json_schema", "schema": schema}},
                messages=[{"role": "user", "content": user}],
            )
        except Exception as exc:
            raise LLMUnavailable(str(exc)) from exc
        if resp.stop_reason == "refusal":
            raise LLMUnavailable("model refused the request")
        text = _first_text(resp)
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMUnavailable(f"non-JSON response: {exc}") from exc


def _first_text(resp) -> str:
    return next((b.text for b in resp.content if getattr(b, "type", None) == "text"), "")
