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
    for raw in path.read_text(encoding="utf-8").splitlines():
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

    # Creative (Part 7). Verified July 2026 (Higgsfield's own docs/changelog — reverify
    # before relying on this, vendor APIs move fast):
    #   • Scripted/headless generation (what this engine calls) goes through the
    #     `higgsfield-client` Python SDK against the Higgsfield Cloud API, authenticated
    #     via HTTP Basic auth built from the HF_KEY env var (or HF_API_KEY + HF_API_SECRET).
    #     The SDK reads those exact env-var names itself; set HIGGSFIELD_API_KEY below for
    #     this project's own gating AND set HF_KEY to the same value in .env for the SDK.
    #   • Higgsfield ALSO ships an official interactive MCP server at
    #     https://mcp.higgsfield.ai/mcp (launched 2026-04-30) — but it authenticates via
    #     browser OAuth, not an API key, so it's built for an interactive MCP client (e.g.
    #     this engine running inside a Claude Code session) rather than an unattended
    #     script. If you're operating from such a session, you can just ask the agent to
    #     run the batch directly through its connected Higgsfield MCP tools
    #     (`generate_video` for the batch, `create_character` for Soul ID,
    #     `get_status`/`subscribe` to poll) — that sidesteps HIGGSFIELD_API_KEY entirely.
    higgsfield_api_key: str = field(default_factory=lambda: _get("HIGGSFIELD_API_KEY"))
    higgsfield_soul_id: str = field(default_factory=lambda: _get("HIGGSFIELD_SOUL_ID"))
    # Posting from the app — the OFFICIAL TikTok Content Posting API (developers.tiktok.com):
    # OAuth-authorised by the account owner, sanctioned, NOT a gray-market auto-poster.
    # A client key/secret plus a per-account OAuth access token. Posting still requires
    # explicit per-post confirmation; this only enables the sanctioned upload path.
    tiktok_client_key: str = field(default_factory=lambda: _get("TIKTOK_CLIENT_KEY"))
    tiktok_client_secret: str = field(default_factory=lambda: _get("TIKTOK_CLIENT_SECRET"))
    tiktok_access_token: str = field(default_factory=lambda: _get("TIKTOK_ACCESS_TOKEN"))
    # The creator bible: ONE persona per store, specified in a markdown file the
    # engine parses (casting, wardrobe, settings, speech). See docs/persona/CREATOR.md.
    persona_path: str = field(
        default_factory=lambda: _get("TT_PERSONA_PATH",
                                     str(ROOT / "docs" / "persona" / "CREATOR.md"))
    )
    # Informational only — never dialed by this code. The real, verified endpoint for the
    # interactive-agent path above; printed as guidance, not POSTed to programmatically.
    higgsfield_mcp_url: str = field(
        default_factory=lambda: _get("HIGGSFIELD_MCP_URL", "https://mcp.higgsfield.ai/mcp")
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

    @property
    def higgsfield_available(self) -> bool:
        """True only if we have both a key and the official SDK importable — mirrors
        llm_available. False means: plan the batch, never attempt to generate for real."""
        if not self.higgsfield_api_key:
            return False
        try:
            import higgsfield_client  # noqa: F401
        except ImportError:
            return False
        return True

    @property
    def tiktok_posting_available(self) -> bool:
        """True only when the official Content Posting API is fully configured (client
        credentials + a per-account OAuth token). False means: the engine can prepare
        the post but not upload it — you post by hand, or wire the official API."""
        return bool(self.tiktok_client_key and self.tiktok_client_secret
                    and self.tiktok_access_token)


CONFIG = Config()
"""Process-wide singleton. Import this, or call Config() for a fresh read."""
