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
    account: str = ""                       # the dedicated account this actor posts from
    source_path: str = ""

    @property
    def slug(self) -> str:
        """A stable short id (lowercased name, filename-safe) used to reference this
        actor in generation specs and on accounts."""
        return re.sub(r"[^a-z0-9]+", "-", self.name.lower()).strip("-")

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
    sections = _parse_sections(p.read_text(encoding="utf-8"))

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
        account=identity.get("account", ""), source_path=str(p),
    )


def load_personas(directory: Optional[str] = None) -> list[Persona]:
    """The ROSTER — every creator bible in the persona directory, one actor each.
    Ten or twelve actors, each on its own account, is the scale model: more accounts
    spread the posting cadence (shadowban-safe) and multiply shots at reach."""
    root = Path(directory) if directory else Path(CONFIG.persona_path).parent
    if not root.exists():
        one = load_persona()
        return [one] if one else []
    out: list[Persona] = []
    for f in sorted(root.glob("*.md")):
        p = load_persona(str(f))
        if p is not None:
            out.append(p)
    return out


def persona_by_slug(slug: str, directory: Optional[str] = None) -> Optional[Persona]:
    """Look up one actor from the roster by slug (or name)."""
    want = re.sub(r"[^a-z0-9]+", "-", slug.lower()).strip("-")
    for p in load_personas(directory):
        if p.slug == want or p.name.lower() == slug.lower():
            return p
    return None


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def bible_template(name: str, account: str = "") -> str:
    """A ready-to-edit creator bible for a new character. Every field is a placeholder
    the operator fills in — look, rooms, voice — the one place a character is defined."""
    handle = account or f"@{_slugify(name).replace('-', '')}"
    return f"""# Creator bible — "{name}"

The single source of truth for this character. Edit the values below; the engine
parses this file into every prompt and the Actors tab. Keep the `## section`
headings and `- key: value` bullets. Validate with
`python -m tt_engine.cli persona --path docs/persona/{_slugify(name)}.md`.

## identity

- name: {name}
- age: <age>
- pronouns: <she/her | he/him | they/them>
- account: {handle} (their OWN dedicated creator account — NOT the brand)
- vibe: <one line: who they are on camera>

## master-description

<ONE paragraph describing their face and body, repeated verbatim at the top of every
prompt. Be specific and give them a small imperfection: e.g. "A 26-year-old with
wavy auburn hair, fair freckled skin, green eyes, a small gap in the front teeth,
slim build, relaxed posture — reads as a real creator filming in their own space.">

## appearance

- face: <shape, any marks, makeup or none>
- hair: <colour, length, texture — never salon-perfect>
- skin: <tone, visible texture>
- build: <build, approx height>
- forbidden: <the things that must NEVER change, semicolon-separated: e.g. the gap in
  the teeth never closes; hair never changes colour; no tattoos ever appear>

## wardrobe

- outfit-home: <itemized: e.g. oversized grey hoodie, black joggers, white socks>
- outfit-desk: <itemized second outfit>
- outfit-out: <itemized third outfit>
- jewelry: <pieces that never change mid-clip: e.g. small silver studs>

## settings

<the rooms this character owns — pick from the engine's scene bundles; their videos
never leave these. One per line:>
- bedroom-morning
- kitchen-evening
- desk-office

## speech

- pace: <how they talk>
- quirks: <recurring phrases / one disfluency; semicolon-separated: e.g. opens with
  "okay so—"; one mid-sentence correction; ends on "anyway">
- never: influencer over-energy, superlatives, reading-off-a-script cadence

## voice

- description: <the voice: e.g. warm mezzo, slight vocal fry, small laugh>
- reference: assets/voice/{_slugify(name)}-ref.wav

(ONE voice, forever. Record or generate a single ≤15s clip and pin it: feed it as
the reference to every generation — via Seedance native audio, or lip-synced on with
ElevenLabs video-to-voice. A shifting voice is as obvious as a shifting face.)

## values

- shows the thing working, honestly; never claims a result it can't show
- outcome proof comes from real customer/affiliate footage, and says so
- every post carries the AIGC label — openly an AI creator

## soul-id-training

- [ ] 20–25 photos of the SAME generated face, even lighting, varied angles
- [ ] at least one full-height photo; nothing cropping the face
- [ ] set the Soul ID once trained; the engine threads it into every prompt

## workflow

Keyframe-first: generate the actor once, then per scene a first-frame image → animate
→ ONE pinned voice → assemble; QA on a phone; AIGC label non-negotiable.
"""


def create_bible(name: str, account: str = "", directory: Optional[str] = None) -> Path:
    """Write a new character bible file (refuses to overwrite an existing one)."""
    root = Path(directory) if directory else Path(CONFIG.persona_path).parent
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{_slugify(name).upper().replace('-', '_')}.md"
    if path.exists():
        raise FileExistsError(f"{path} already exists — edit it instead of recreating.")
    path.write_text(bible_template(name, account), encoding="utf-8")
    return path


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
