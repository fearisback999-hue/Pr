"""Part 7 — Creative Engine. When a candidate scores 80+, the engine auto-builds the
creative kit and (when configured) pushes it into Higgsfield.

  hooks      — 20 hooks across 4 types, each ≤10 words, written to stop a thumb
  scripts    — 10 UGC scripts (3s hook beat / demonstration / CTA), annotated by emotion
  compliance — the guardrail that keeps the shop alive (FTC + TikTok AI-disclosure)
  brief      — assemble product + psychology spine + hooks into a Higgsfield brief
  higgsfield — API adapter (Hermes Agent, AI Hook Generator, batch, export)
"""

from .brief import FORMATS, CreativeKit, build_kit
from .compliance import DISCLOSURE, ComplianceReport, review_text
from .higgsfield import HiggsfieldClient
from .hooks import HOOK_TYPES, Hook, generate_hooks
from .mcp_client import (
    ConfirmationRequired,
    ExportResult,
    GenerationResult,
    HiggsfieldMCP,
    export_creatives,
    generate_batch,
    soul_consistency,
)
from .scripts import UGCScript, generate_scripts

__all__ = [
    "Hook", "generate_hooks", "HOOK_TYPES",
    "UGCScript", "generate_scripts",
    "ComplianceReport", "review_text", "DISCLOSURE",
    "CreativeKit", "build_kit", "FORMATS",
    "HiggsfieldClient",
    "HiggsfieldMCP", "generate_batch", "export_creatives", "soul_consistency",
    "GenerationResult", "ExportResult", "ConfirmationRequired",
]
