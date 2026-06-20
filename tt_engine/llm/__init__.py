"""Claude API access for the enrichment stages (Part 4 psychology, Part 7 hooks/scripts).

Everything here degrades gracefully: when no ANTHROPIC_API_KEY / SDK is present, the
client reports `available == False` and callers fall back to deterministic offline logic
so the engine still runs end-to-end.
"""

from .client import LLMClient, LLMUnavailable

__all__ = ["LLMClient", "LLMUnavailable"]
