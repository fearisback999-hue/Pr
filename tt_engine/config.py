"""Central configuration. Reads from environment (and an optional .env file) with
sensible offline-friendly defaults so the whole engine runs with zero setup."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path = ROOT / ".env") -> None:
    """Minimal .env loader (no dependency on python-dotenv). Existing env wins."""
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_dotenv()


def _get(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


@dataclass(frozen=True)
class Config:
    # Storage
    db_path: str = field(default_factory=lambda: _get("TT_DB_PATH", str(ROOT / "tt_engine.db")))

    # Detection / scoring
    primary_feed: str = field(default_factory=lambda: _get("TT_PRIMARY_FEED", "mock"))
    score_threshold: float = field(
        default_factory=lambda: float(_get("TT_SCORE_THRESHOLD", "80") or 80)
    )

    # LLM (Part 4 / 7). Defaults chosen per the Claude API guidance: opus 4.8 + high effort.
    anthropic_api_key: str = field(default_factory=lambda: _get("ANTHROPIC_API_KEY"))
    llm_model: str = field(default_factory=lambda: _get("TT_LLM_MODEL", "claude-opus-4-8"))
    llm_effort: str = field(default_factory=lambda: _get("TT_LLM_EFFORT", "high"))

    # Feed credentials (Part 2)
    kalodata_api_key: str = field(default_factory=lambda: _get("KALODATA_API_KEY"))
    echotik_api_key: str = field(default_factory=lambda: _get("ECHOTIK_API_KEY"))
    pipiads_api_key: str = field(default_factory=lambda: _get("PIPIADS_API_KEY"))

    # Sourcing (Part 6)
    cj_api_key: str = field(default_factory=lambda: _get("CJ_DROPSHIPPING_API_KEY"))
    zendrop_api_key: str = field(default_factory=lambda: _get("ZENDROP_API_KEY"))

    # Creative (Part 7)
    higgsfield_api_key: str = field(default_factory=lambda: _get("HIGGSFIELD_API_KEY"))
    higgsfield_soul_id: str = field(default_factory=lambda: _get("HIGGSFIELD_SOUL_ID"))
    # Phase 2: Higgsfield via MCP (streamable-HTTP endpoint). Unset → dry-run planning.
    higgsfield_mcp_url: str = field(default_factory=lambda: _get("HIGGSFIELD_MCP_URL"))
    higgsfield_mcp_tool: str = field(
        default_factory=lambda: _get("HIGGSFIELD_MCP_TOOL", "generate_video")
    )

    @property
    def llm_available(self) -> bool:
        """True only if we have both a key and the SDK importable."""
        if not self.anthropic_api_key:
            return False
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return False
        return True


CONFIG = Config()
"""Process-wide singleton. Import this, or call Config() for a fresh read."""
