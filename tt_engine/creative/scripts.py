"""10 UGC scripts (Part 7). Each has a first-3-seconds hook beat, a middle
(demonstration / visible result), and a CTA — annotated with the emotion it targets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..llm import LLMClient, LLMUnavailable
from ..psychology import PsychProfile
from .hooks import Hook

_SYSTEM = (
    "You write short UGC ad scripts for TikTok Shop. Each script has three beats: "
    "(1) first 3 seconds — the hook, (2) middle — show the product working / a visible result, "
    "(3) CTA. Keep it natural, like one creator talking to camera. Never fabricate testimonials "
    "or imply a result the product cannot deliver. Annotate the single emotion each script targets."
)

_SCHEMA = {
    "type": "object",
    "properties": {
        "scripts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "hook": {"type": "string"},
                    "first_3s": {"type": "string"},
                    "middle": {"type": "string"},
                    "cta": {"type": "string"},
                    "emotion": {"type": "string"},
                },
                "required": ["hook", "first_3s", "middle", "cta", "emotion"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["scripts"],
    "additionalProperties": False,
}


@dataclass
class UGCScript:
    hook: str
    first_3s: str        # hook beat
    middle: str          # demonstration / visible result
    cta: str
    emotion: str         # the single emotion this script targets


def generate_scripts(
    product_name: str,
    psych: PsychProfile,
    hooks: list[Hook],
    n: int = 10,
    llm: Optional[LLMClient] = None,
) -> list[UGCScript]:
    llm = llm or LLMClient()
    if llm.available:
        try:
            hook_list = "\n".join(f"- {h.text}" for h in hooks[:n])
            user = (
                f"Product: {product_name}\n"
                f"Psychological spine: {psych.spine}\n"
                f"Pain point: {psych.pain_point}\nDesire: {psych.desire}\n\n"
                f"Hooks to build from:\n{hook_list}\n\n"
                f"Write exactly {n} UGC scripts."
            )
            data = llm.complete_json(_SYSTEM, user, _SCHEMA, max_tokens=4000)
            scripts = [
                UGCScript(
                    hook=s["hook"], first_3s=s["first_3s"], middle=s["middle"],
                    cta=s["cta"], emotion=s["emotion"],
                )
                for s in data.get("scripts", [])
                if all(k in s for k in ("hook", "first_3s", "middle", "cta", "emotion"))
            ]
            if scripts:
                return scripts[:n]
        except LLMUnavailable:
            pass
    return _offline_scripts(product_name, psych, hooks, n)


def _offline_scripts(
    product_name: str, psych: PsychProfile, hooks: list[Hook], n: int
) -> list[UGCScript]:
    short_name = product_name.split("(")[0].strip()
    desire = psych.desire
    ctas = [
        "Tap the orange cart before it sells out.",
        "Grab yours from the link — limited stock.",
        "Get it now while it's still in stock.",
    ]
    scripts: list[UGCScript] = []
    pool = hooks or [Hook(text=f"You need the {short_name}", type="curiosity")]
    for i in range(n):
        h = pool[i % len(pool)]
        scripts.append(UGCScript(
            hook=h.text,
            first_3s=f"{h.text} (creator holds up the {short_name}, close on their face)",
            middle=(
                f"Quick demo: show the {short_name} actually working — {desire}. "
                f"Real-time, no cuts, so it reads as genuine."
            ),
            cta=ctas[i % len(ctas)],
            emotion=psych.emotional_trigger,
        ))
    return scripts[:n]
