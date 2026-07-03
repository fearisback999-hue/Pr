"""Assemble the creative kit: product + psychology spine + hooks + scripts → a brief ready
for Higgsfield's Hermes Agent. Plans the batch (20–100 variations across formats), pins a
recurring Soul ID persona, and runs every line through the compliance guardrail."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..config import CONFIG
from ..db import models
from ..llm import LLMClient
from ..psychology import PsychProfile
from .compliance import ComplianceReport, review_text
from .hooks import Hook, generate_hooks
from .scripts import UGCScript, generate_scripts

# Formats to vary across (Part 7 / Phase 2 spec): UGC reaction, Hyper Motion reveal,
# ASMR, POV before/after, unboxing.
FORMATS = ("UGC-Reaction", "HyperMotion-Reveal", "ASMR", "POV-BeforeAfter", "Unboxing")


@dataclass
class CreativeKit:
    product: models.Product
    psych: PsychProfile
    hooks: list[Hook]
    scripts: list[UGCScript]
    soul_id: str
    formats: tuple[str, ...]
    variations: int                       # planned batch size (20–100)
    compliance: list[ComplianceReport] = field(default_factory=list)

    @property
    def compliant(self) -> bool:
        return all(c.ok for c in self.compliance)

    @property
    def flagged(self) -> list[ComplianceReport]:
        return [c for c in self.compliance if not c.ok]

    def brief_text(self) -> str:
        """The brief you'd hand to Hermes Agent (Click-to-Ad)."""
        lines = [
            f"# Creative brief — {self.product.name}",
            "",
            "## Psychological spine (lead every ad with this)",
            self.psych.spine,
            "",
            f"## Recurring persona (Soul ID): {self.soul_id or '<set HIGGSFIELD_SOUL_ID>'}",
            "All ads should feel like one creator's account — same face/voice across variations.",
            "",
            f"## Formats ({self.variations} variations total): {', '.join(self.formats)}",
            "",
            "## Hooks",
        ]
        lines += [f"- [{h.type}] {h.text}" for h in self.hooks]
        lines += ["", "## UGC scripts"]
        for i, s in enumerate(self.scripts, 1):
            lines += [
                f"### Script {i} — targets: {s.emotion}",
                f"- 0–3s (hook): {s.first_3s}",
                f"- middle (demo/result): {s.middle}",
                f"- CTA: {s.cta}",
            ]
        if self.flagged:
            lines += ["", "## ⚠️ Compliance — rewrite before generating"]
            lines += [f"- {c.summary}  →  \"{c.text}\"" for c in self.flagged]
        return "\n".join(lines)


def build_kit(
    product: models.Product,
    psych: PsychProfile,
    variations: int = 30,
    soul_id: Optional[str] = None,
    formats: tuple[str, ...] = FORMATS,
    llm: Optional[LLMClient] = None,
) -> CreativeKit:
    llm = llm or LLMClient()
    hooks = generate_hooks(product.name, psych, n=20, llm=llm)
    scripts = generate_scripts(product.name, psych, hooks, n=10, llm=llm)

    # Compliance sweep over every hook and script beat (full set kept; brief shows flags).
    reports: list[ComplianceReport] = [review_text(h.text) for h in hooks]
    for s in scripts:
        reports += [review_text(s.first_3s), review_text(s.middle), review_text(s.cta)]

    return CreativeKit(
        product=product, psych=psych, hooks=hooks, scripts=scripts,
        soul_id=soul_id or CONFIG.higgsfield_soul_id,
        formats=formats, variations=variations, compliance=reports,
    )
