"""Part 7 — Creative Engine. When a candidate scores 80+, the engine auto-builds the
creative kit and (when configured) pushes it into Higgsfield.

  hooks      — 20 hooks across 4 types, each ≤10 words, written to stop a thumb
  scripts    — 10 UGC scripts (3s hook beat / demonstration / CTA), annotated by emotion
  compliance — the guardrail that keeps the shop alive (FTC + TikTok AI-disclosure)
  brief      — assemble product + psychology spine + hooks into a Higgsfield brief
  higgsfield — API adapter (Hermes Agent, AI Hook Generator, batch, export)
"""

from .ai_creator import FitResult, ai_fit, build_creator_plan
from .brief import FORMATS, CreativeKit, build_kit
from .persona import Persona, load_persona, validate_persona
from .compliance import DISCLOSURE, ComplianceReport, review_text
from .concepts import CreativePack, UGCConcept, build_pack
from .production import ProductionRunbook, build_runbook
from .slideshow import SlideshowPlan, SlideshowPost, build_slideshows
from .realism import (
    ARTIFACT_CHECKLIST,
    ImagePrompt,
    RealismPrompt,
    actor_image_prompt,
    enhance_prompt,
    prompts_for_scripts,
    render_qa_checklist,
    scene_frame_prompt,
    scene_video_prompt,
)
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
    "CreativePack", "build_pack", "UGCConcept",
    "FitResult", "ai_fit", "build_creator_plan",
    "Persona", "load_persona", "validate_persona",
    "RealismPrompt", "enhance_prompt", "prompts_for_scripts", "render_qa_checklist",
    "ARTIFACT_CHECKLIST",
    "ImagePrompt", "actor_image_prompt", "scene_frame_prompt", "scene_video_prompt",
    "ProductionRunbook", "build_runbook",
    "SlideshowPlan", "SlideshowPost", "build_slideshows",
    "HiggsfieldClient",
    "HiggsfieldMCP", "generate_batch", "export_creatives", "soul_consistency",
    "GenerationResult", "ExportResult", "ConfirmationRequired",
]
