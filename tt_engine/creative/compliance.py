"""The compliance guardrail (Part 7) — this keeps the shop alive.

AI-generated UGC-style content is standard and fine. What is NOT fine: fabricated
testimonials and false claims (deceptive advertising under FTC rules and against TikTok
policy). Follow TikTok's AI-content disclosure. Use Soul ID personas you have rights to.
Never generate a result the product does not deliver.

This module scans generated copy for risky patterns and surfaces the required disclosure.
It is a guardrail, not legal advice — when a hook trips a flag, rewrite it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

DISCLOSURE = (
    "AI-generated / AI-assisted content. Disclose per TikTok's AI-content policy and FTC "
    "guidance. Use a Soul ID persona you hold rights to — do not depict a real, identifiable "
    "person without permission."
)

# Absolute / medical / fabricated-claim patterns that read as deceptive advertising.
_CLAIM_PATTERNS = [
    (r"\bcure[sd]?\b", "medical 'cure' claim"),
    (r"\b(fda|clinically|doctor)\s+(approved|proven|recommend(ed)?)\b", "unsubstantiated authority claim"),
    (r"\bguarantee(d|s)?\b", "absolute 'guarantee' claim"),
    (r"\b100%\b", "absolute '100%' claim"),
    (r"\bmiracle\b", "'miracle' claim"),
    (r"\bcures?\s+(anxiety|depression|cancer|disease)\b", "medical condition claim"),
    (r"\blose\s+\d+\s*(lbs|pounds|kg)\b", "specific weight-loss claim"),
    (r"\bpermanent(ly)?\b", "'permanent' result claim"),
]

# Patterns that imply a fabricated testimonial (a claimed real person's specific result).
_TESTIMONIAL_PATTERNS = [
    (r"\breal customer\b", "implies a real testimonial — must be genuine"),
    (r"\b\d+,?\d*\s+(people|customers|women|men)\s+(can't be wrong|agree|love)\b",
     "fabricated social-proof count"),
    (r"\bverified buyer\b", "implies a verified review — must be genuine"),
]


@dataclass
class ComplianceReport:
    text: str
    issues: list[str] = field(default_factory=list)
    requires_disclosure: bool = True

    @property
    def ok(self) -> bool:
        return not self.issues

    @property
    def summary(self) -> str:
        if self.ok:
            return "compliant (still add AI-content disclosure)"
        return "REWRITE: " + "; ".join(self.issues)


def review_text(text: str) -> ComplianceReport:
    issues: list[str] = []
    low = text.lower()
    for pattern, label in _CLAIM_PATTERNS + _TESTIMONIAL_PATTERNS:
        if re.search(pattern, low):
            issues.append(label)
    return ComplianceReport(text=text, issues=issues, requires_disclosure=True)


def review_batch(texts: list[str]) -> list[ComplianceReport]:
    return [review_text(t) for t in texts]
