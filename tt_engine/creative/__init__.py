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
from .category_styles import CategoryStyle, all_styles, style_for
from .persona import (
    Persona,
    load_persona,
    load_personas,
    persona_by_slug,
    validate_persona,
)
from .video_spec import (
    assemble,
    create_spec,
    default_prompt,
    render_spec,
    render_spec_list,
    resolve_actor,
)
from .compliance import DISCLOSURE, ComplianceReport, review_text
from .concepts import CreativePack, UGCConcept, build_pack
from .clothing import FitCheckRunbook, build_fit_check
from .production import ProductionRunbook, build_runbook
from .slideshow import SlideshowPlan, SlideshowPost, build_slideshows
from .realism import (
    ARTIFACT_CHECKLIST,
    ImagePrompt,
    RealismPrompt,
    actor_image_prompt,
    enhance_prompt,
    garment_swap_prompt,
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
    GenerationNotWired,
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
    "Persona", "load_persona", "load_personas", "persona_by_slug", "validate_persona",
    "create_spec", "render_spec", "render_spec_list", "assemble", "resolve_actor",
    "default_prompt",
    "CategoryStyle", "style_for", "all_styles",
    "RealismPrompt", "enhance_prompt", "prompts_for_scripts", "render_qa_checklist",
    "ARTIFACT_CHECKLIST",
    "ImagePrompt", "actor_image_prompt", "scene_frame_prompt", "scene_video_prompt",
    "garment_swap_prompt",
    "ProductionRunbook", "build_runbook",
    "FitCheckRunbook", "build_fit_check",
    "SlideshowPlan", "SlideshowPost", "build_slideshows",
    "HiggsfieldClient",
    "HiggsfieldMCP", "generate_batch", "export_creatives", "soul_consistency",
    "GenerationResult", "ExportResult", "ConfirmationRequired", "GenerationNotWired",
]
