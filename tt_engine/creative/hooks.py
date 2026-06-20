"""20 hooks across four types (Part 7). Each ≤10 words, written to stop a thumb in the
first frame. LLM-generated when available; deterministic templates otherwise."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..llm import LLMClient, LLMUnavailable
from ..psychology import PsychProfile

HOOK_TYPES = ("curiosity", "problem", "shock", "transformation")

_SYSTEM = (
    "You write scroll-stopping TikTok Shop ad hooks. Each hook is <= 10 words, punchy, and "
    "designed to stop a thumb in the first frame. Lead with the product's single psychological "
    "trigger. Never fabricate testimonials or claim results the product does not deliver."
)

_SCHEMA = {
    "type": "object",
    "properties": {
        "hooks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "type": {"type": "string", "enum": list(HOOK_TYPES)},
                },
                "required": ["text", "type"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["hooks"],
    "additionalProperties": False,
}


@dataclass
class Hook:
    text: str
    type: str  # one of HOOK_TYPES


_TEMPLATES = {
    "curiosity": [
        "Why is everyone obsessed with the {name}?",
        "Nobody told me the {name} did this",
        "The {name} hack TikTok is hiding",
        "I didn't believe the {name} until now",
        "POV: you just found the {name}",
    ],
    "problem": [
        "Still dealing with {pain}? Watch this",
        "Fix {pain} in seconds with the {name}",
        "If {pain} ruins your day, you need this",
        "Tired of {pain}? The {name} changed it",
        "Stop ignoring {pain} — try the {name}",
    ],
    "shock": [
        "Wait… the {name} actually does THAT?",
        "This {name} clip broke my brain",
        "You won't believe what the {name} does",
        "Okay the {name} is kind of insane",
        "I was NOT ready for the {name}",
    ],
    "transformation": [
        "From {pain} to relief with one {name}",
        "Watch the {name} change this instantly",
        "Before vs after using the {name}",
        "30 seconds with the {name} = obsessed",
        "The {name} gave me my evenings back",
    ],
}


def _truncate_10(text: str) -> str:
    words = text.split()
    return text if len(words) <= 10 else " ".join(words[:10])


def generate_hooks(
    product_name: str,
    psych: PsychProfile,
    n: int = 20,
    llm: Optional[LLMClient] = None,
) -> list[Hook]:
    llm = llm or LLMClient()
    if llm.available:
        try:
            user = (
                f"Product: {product_name}\n"
                f"Psychological spine: {psych.spine}\n"
                f"Primary trigger: {psych.emotional_trigger}\n"
                f"Pain point: {psych.pain_point}\n\n"
                f"Write exactly {n} hooks, balanced across the four types "
                f"({', '.join(HOOK_TYPES)}). Each <= 10 words."
            )
            data = llm.complete_json(_SYSTEM, user, _SCHEMA, max_tokens=2500)
            hooks = [
                Hook(text=_truncate_10(h["text"]), type=h["type"])
                for h in data.get("hooks", [])
                if h.get("text") and h.get("type") in HOOK_TYPES
            ]
            if hooks:
                return hooks[:n]
        except LLMUnavailable:
            pass
    return _offline_hooks(product_name, psych, n)


def _offline_hooks(product_name: str, psych: PsychProfile, n: int) -> list[Hook]:
    # short pain phrase for templates
    pain = psych.pain_point.split(",")[0].split(" they ")[0].strip().lower()
    if len(pain.split()) > 4:
        pain = " ".join(pain.split()[:4])
    short_name = product_name.split("(")[0].strip()
    hooks: list[Hook] = []
    per_type = max(1, n // len(HOOK_TYPES))
    for htype in HOOK_TYPES:
        for tmpl in _TEMPLATES[htype][:per_type]:
            hooks.append(Hook(text=_truncate_10(tmpl.format(name=short_name, pain=pain)), type=htype))
    # top up to n by cycling
    i = 0
    flat = [(t, tmpl) for t in HOOK_TYPES for tmpl in _TEMPLATES[t]]
    while len(hooks) < n and i < len(flat):
        t, tmpl = flat[i]
        h = Hook(text=_truncate_10(tmpl.format(name=short_name, pain=pain)), type=t)
        if h.text not in {x.text for x in hooks}:
            hooks.append(h)
        i += 1
    return hooks[:n]
