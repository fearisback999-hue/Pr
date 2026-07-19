"""The creator bible, parsed: ONE persona per store, specified in a markdown file
that humans edit and the engine reads.

Research-backed design (verified 2026-07-19, sources in docs/research/
AI_VIDEO_REALISM.md):
  • character drift is the #1 consistency failure — the fix is a MASTER DESCRIPTION
    repeated verbatim at the top of every prompt, same order every time
  • outfit drift is the #2 failure — the fix is ITEMIZED outfit strings ("oversized
    cream knit sweater, gold hoops") repeated exactly, one outfit per product batch
  • scene coherence — the persona lives in a small, fixed set of rooms; her videos
    never wander into settings she doesn't own
  • speech identity — recurring phrases and a stated disfluency style make the same
    "person" sound the same across clips

The file format is ordinary markdown (`## section` + `- key: value` bullets), so
the operator edits it like a doc and the engine parses what it needs. A missing
file degrades gracefully — the engine falls back to its generic casting pool.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..config import CONFIG


@dataclass
class Persona:
    name: str
    master_description: str                 # opens EVERY prompt, verbatim
    outfits: dict[str, str] = field(default_factory=dict)   # slot -> itemized string
    jewelry: str = ""
    settings: list[str] = field(default_factory=list)       # engine scene-bundle keys
    speech_quirks: list[str] = field(default_factory=list)
    voice_description: str = ""
    voice_reference: str = ""               # canonical clip fed to native-audio gen
    forbidden: list[str] = field(default_factory=list)      # must-never-change list
    source_path: str = ""

    def casting_spec(self, soul_id: str = "") -> str:
        """The casting block for a prompt: Soul ID (when set) + the master
        description, verbatim — the research-backed anti-drift anchor."""
        head = (f"{self.name}, the store's recurring persona"
                + (f" (Soul ID {soul_id})" if soul_id else "")
                + f": {self.master_description}")
        if self.forbidden:
            head += " NEVER CHANGES: " + "; ".join(self.forbidden) + "."
        return head

    def outfit_for(self, key: str) -> str:
        """Deterministic outfit per product batch: every clip in one batch wears the
        SAME itemized outfit (outfit drift is the #2 consistency failure). Different
        products/posts may rotate the closet."""
        if not self.outfits:
            return ""
        slots = sorted(self.outfits)
        import hashlib
        h = int(hashlib.sha256(f"outfit:{key}".encode()).hexdigest(), 16)
        slot = slots[h % len(slots)]
        outfit = self.outfits[slot]
        if self.jewelry:
            outfit += f"; jewelry: {self.jewelry}"
        return outfit

    @property
    def summary(self) -> str:
        return (f"{self.name} — {len(self.outfits)} outfit(s), "
                f"{len(self.settings)} home setting(s), "
                f"{len(self.speech_quirks)} speech quirk(s)"
                + (f" · voice ref {self.voice_reference}" if self.voice_reference else ""))


_SECTION_RE = re.compile(r"^##\s+(.+?)\s*$")
_BULLET_RE = re.compile(r"^-\s+(?:\*\*)?([^:*]+?)(?:\*\*)?\s*:\s*(.+?)\s*$")
_ITEM_RE = re.compile(r"^-\s+(?!\[)(.+?)\s*$")   # plain list item (not a checkbox)


def _parse_sections(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current = ""
    for raw in text.splitlines():
        m = _SECTION_RE.match(raw)
        if m:
            current = m.group(1).strip().lower()
            sections.setdefault(current, [])
        elif current:
            sections[current].append(raw.rstrip())
    # Markdown wraps: an indented line that isn't itself a bullet continues the
    # bullet above it — merge so wrapped values parse whole.
    for name, lines in sections.items():
        merged: list[str] = []
        for line in lines:
            if (merged and line.startswith("  ") and line.strip()
                    and not line.strip().startswith("-")
                    and merged[-1].strip().startswith("-")):
                merged[-1] += " " + line.strip()
            else:
                merged.append(line)
        sections[name] = merged
    return sections


def load_persona(path: Optional[str] = None) -> Optional[Persona]:
    """Parse the creator bible. Returns None when the file doesn't exist — the
    engine must keep working (with generic casting) before the operator writes one."""
    p = Path(path or CONFIG.persona_path)
    if not p.exists():
        return None
    sections = _parse_sections(p.read_text())

    def kv(section: str) -> dict[str, str]:
        out = {}
        for line in sections.get(section, []):
            m = _BULLET_RE.match(line.strip())
            if m:
                out[m.group(1).strip().lower()] = m.group(2).strip()
        return out

    def items(section: str) -> list[str]:
        out = []
        for line in sections.get(section, []):
            m = _ITEM_RE.match(line.strip())
            if m and ":" not in m.group(1)[:20]:
                out.append(m.group(1).strip())
        return out

    identity = kv("identity")
    master = " ".join(l.strip() for l in sections.get("master-description", [])
                      if l.strip() and not l.strip().startswith(("<!--", "(")))
    wardrobe = kv("wardrobe")
    outfits = {k: v for k, v in wardrobe.items() if k.startswith("outfit")}
    speech = kv("speech")
    quirks = [q.strip() for q in speech.get("quirks", "").split(";") if q.strip()]
    voice = kv("voice")
    appearance = kv("appearance")
    forbidden = [f.strip() for f in appearance.get("forbidden", "").split(";")
                 if f.strip()]

    name = identity.get("name", "")
    if not name or not master:
        return None                          # a bible without a face is no bible
    return Persona(
        name=name, master_description=master, outfits=outfits,
        jewelry=wardrobe.get("jewelry", ""), settings=items("settings"),
        speech_quirks=quirks, voice_description=voice.get("description", ""),
        voice_reference=voice.get("reference", ""), forbidden=forbidden,
        source_path=str(p),
    )


def validate_persona(persona: Optional[Persona]) -> list[str]:
    """Operator-facing warnings: what's missing before the bible is production-ready."""
    if persona is None:
        return ["no creator bible found — create docs/persona/CREATOR.md "
                "(the shipped file is a complete, editable template)"]
    warnings = []
    if len(persona.outfits) < 2:
        warnings.append("fewer than 2 itemized outfits — outfit drift is the #2 "
                        "consistency failure; itemize at least 2")
    if not persona.settings:
        warnings.append("no home settings listed — scene coherence needs a fixed "
                        "set of rooms the persona owns")
    else:
        from .realism import SETTINGS
        unknown = [s for s in persona.settings if s not in SETTINGS]
        if unknown:
            warnings.append(f"unknown setting(s) {unknown} — must be engine scene "
                            f"bundles: {', '.join(sorted(SETTINGS))}")
    if not persona.speech_quirks:
        warnings.append("no speech quirks — the persona will sound like anyone; "
                        "list 2–3 recurring phrases/disfluencies")
    if not persona.forbidden:
        warnings.append("no forbidden-variations list — state what must NEVER "
                        "change (marks, teeth, hair) or drift will creep in")
    if not persona.voice_reference:
        warnings.append("no canonical voice reference clip — pin one ≤15s clip and "
                        "feed it to every native-audio generation")
    return warnings
