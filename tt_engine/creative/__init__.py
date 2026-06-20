"""Part 7 — Creative Engine. When a candidate scores 80+, the engine auto-builds the
creative kit and (when configured) pushes it into Higgsfield.

  hooks      — 20 hooks across 4 types, each ≤10 words, written to stop a thumb
  scripts    — 10 UGC scripts (3s hook beat / demonstration / CTA), annotated by emotion
  compliance — the guardrail that keeps the shop alive (FTC + TikTok AI-disclosure)
  brief      — assemble product + psychology spine + hooks into a Higgsfield brief
  higgsfield — API adapter (Hermes Agent, AI Hook Generator, batch, export)
"""

from .hooks import Hook, generate_hooks, HOOK_TYPES
from .scripts import UGCScript, generate_scripts
from .compliance import ComplianceReport, review_text, DISCLOSURE
from .brief import CreativeKit, build_kit, FORMATS
from .higgsfield import HiggsfieldClient

__all__ = [
    "Hook", "generate_hooks", "HOOK_TYPES",
    "UGCScript", "generate_scripts",
    "ComplianceReport", "review_text", "DISCLOSURE",
    "CreativeKit", "build_kit", "FORMATS",
    "HiggsfieldClient",
]
