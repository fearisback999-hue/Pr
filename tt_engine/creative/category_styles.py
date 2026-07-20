"""Category creative styles: clothing doesn't sell like gadgets — and shooting them
the same way is itself an AI tell.

Real try-on videos, gadget demos, pet clips, and home-reset videos have completely
different visual grammar (what the camera does, what the hands do, where it's shot,
what the first frame promises). This registry gives every product type its own:

  hooks          — category-native angles the generic pool can't produce
  demo grammar   — what the middle beat of the video actually shows
  demo camera    — how real people film THIS kind of product
  interaction    — how the product is handled on camera
  setting bias   — which of the persona's rooms this category lives in
  slideshow lead — the slide style that carries the carousel's demo slide
  proof          — what honest proof looks like (outcome categories stay real-footage)
  wardrobe rule  — apparel's special case: the product IS the outfit

`style_for()` maps loose names (clothing→apparel, gadget→electronics) so operator
vocabulary and DB categories both land on the right style. Unknown categories get a
sane default — the engine never crashes on a new niche, it just loses the flavor.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Hook templates are (type, template) with {name}/{pain} slots, each ≤10 words —
# same contract as the generic pool in hooks.py.
Hooks = tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class CategoryStyle:
    key: str
    label: str
    hook_templates: Hooks
    demo_grammar: str
    camera_demo: str
    interaction: str
    setting_bias: tuple[str, ...]
    slideshow_lead: str
    proof: str
    wardrobe_rule: str = ""          # "product-is-outfit" for apparel

    @property
    def summary(self) -> str:
        return f"{self.label}: {self.demo_grammar}"


STYLES: dict[str, CategoryStyle] = {}


def _register(style: CategoryStyle, *aliases: str) -> None:
    STYLES[style.key] = style
    for a in aliases:
        _ALIASES[a] = style.key


_ALIASES: dict[str, str] = {}


_register(CategoryStyle(
    key="apparel", label="Clothing & apparel",
    hook_templates=(
        ("curiosity", "The {name} fit check you asked for"),
        ("curiosity", "Honest sizing on the {name}"),
        ("transformation", "Styling the {name} three ways"),
        ("shock", "The {name} fabric in real light"),
        ("problem", "Nothing ever fits right? Watch the {name}"),
        ("transformation", "Same outfit, then the {name}. Look"),
    ),
    demo_grammar="a try-on: full-body in the mirror, turn once, fabric moving, "
                 "tug the hem, honest fit commentary — never a static mannequin shot",
    camera_demo="phone propped for a full-body mirror shot, then handheld close on "
                "the fabric and stitching",
    interaction="worn, not held: adjusted at the shoulder, pocket checked, sleeve "
                "pushed up — the small things people do in real clothes",
    setting_bias=("bedroom-morning", "entryway"),
    slideshow_lead="mirror try-on, phone covering the face, full outfit visible",
    proof="fit and fabric ARE the proof — show them moving; sizing honesty beats hype",
    wardrobe_rule="product-is-outfit",
), "clothing", "clothes", "fashion")

_register(CategoryStyle(
    key="electronics", label="Gadgets & tech",
    hook_templates=(
        ("curiosity", "Settings your {name} is hiding"),
        ("curiosity", "Unboxing the {name} nobody shut up about"),
        ("shock", "The {name} feature nobody mentions"),
        ("problem", "{pain}? The {name} setup takes a minute"),
        ("transformation", "A week with the {name}. Verdict"),
        ("shock", "Okay, the {name} at full power"),
    ),
    demo_grammar="hands-on function demo: press the thing, show the response in "
                 "real time, one continuous take — function over vibes",
    camera_demo="over-the-shoulder POV of both hands using it, close and slightly "
                "too tight, screen or mechanism clearly visible",
    interaction="operated like an owned device: deliberate button presses, a "
                "settings flick, set down mid-use to talk",
    setting_bias=("desk-office", "kitchen-evening"),
    slideshow_lead="close-up of the device mid-function, cable clutter at the edge",
    proof="the function demo IS the proof — real-time, no cuts on the money moment",
), "gadget", "gadgets", "tech", "electronic")

_register(CategoryStyle(
    key="beauty", label="Beauty & skincare",
    hook_templates=(
        ("curiosity", "The {name} texture up close"),
        ("curiosity", "My shelf before the {name}"),
        ("problem", "{pain}? Here's my honest routine"),
        ("curiosity", "How the {name} actually applies"),
        ("shock", "The {name} ingredient list, read aloud"),
        ("curiosity", "AM routine feat. the {name}"),
    ),
    demo_grammar="application ritual: texture close-up, the actual apply motion, "
                 "where it sits in the routine — NEVER a before/after claim",
    camera_demo="propped at the vanity/mirror, close on hands and texture, "
                "natural window light only",
    interaction="opened and applied like a daily staple: cap set down off-frame, "
                "texture rubbed between fingers first",
    setting_bias=("bedroom-morning",),
    slideshow_lead="texture macro on the back of the hand, imperfect focus",
    proof="OUTCOME CLAIMS STAY OFF — results proof must be real customer footage; "
          "the persona shows texture, application, and routine only",
), "skincare", "cosmetics", "makeup")

_register(CategoryStyle(
    key="pet", label="Pet products",
    hook_templates=(
        ("curiosity", "My dog's reaction to the {name}"),
        ("problem", "{pain}? Vet suggested trying this"),
        ("curiosity", "Unboxing the {name} with my dog"),
        ("curiosity", "Fitting the {name} the right way"),
        ("shock", "The {name} sizing nobody explains"),
        ("curiosity", "What's actually inside the {name}"),
    ),
    demo_grammar="unboxing, fitting, and explaining — the ANIMAL's reaction is the "
                 "sale and that footage must be real (affiliate/customer clips)",
    camera_demo="handheld low to the floor at pet level, or propped while both "
                "hands fit the product",
    interaction="handled like pet gear: straps checked, sizing shown against a "
                "hand, treat pocket demonstrated",
    setting_bias=("entryway", "kitchen-evening"),
    slideshow_lead="the product staged with leash/bowl clutter at pet level",
    proof="the persona may unbox, fit, and explain — REAL animal reaction footage "
          "carries the conversion; never generate a pet 'reacting'",
), "pets", "dog", "cat")

_register(CategoryStyle(
    key="home", label="Home & kitchen",
    hook_templates=(
        ("problem", "My {pain} corner, finally handled"),
        ("curiosity", "The {name} everyone's kitchen is missing"),
        ("transformation", "Sunday reset feat. the {name}"),
        ("shock", "The {name} did this in one pass"),
        ("curiosity", "Rating my {name} after 30 days"),
        ("problem", "Renters: the {name} needs no drilling"),
    ),
    demo_grammar="the reset: start from the real mess, use it in real time, end at "
                 "the honestly-better state — satisfaction pacing, no time-lapse fakery",
    camera_demo="propped on the counter for the wide, handheld for the working "
                "close-up, same light throughout",
    interaction="used mid-chore: wet hands, a towel over the shoulder, the drawer "
                "that doesn't quite close",
    setting_bias=("kitchen-evening", "entryway"),
    slideshow_lead="flat-lay in the real kitchen clutter, no staging",
    proof="the visible task IS the proof — film the whole pass, no cuts",
), "kitchen", "decor", "household")

_register(CategoryStyle(
    key="hobby", label="Hobby & craft tools",
    hook_templates=(
        ("curiosity", "The {name} serious hobbyists gatekeep"),
        ("curiosity", "Watch the {name} do one pass"),
        ("shock", "The {name} sound is so satisfying"),
        ("problem", "{pain}? Your tool is the problem"),
        ("transformation", "First try with the {name} vs now"),
        ("curiosity", "What's in my kit: the {name}"),
    ),
    demo_grammar="process ASMR: the tool doing its one job in real time, close on "
                 "the workpiece, the sound left in — skill plus tool, no shortcuts",
    camera_demo="top-down on the work surface, phone propped, hands in frame the "
                "whole take",
    interaction="handled like a favorite tool: grip adjusted, blade/edge checked, "
                "workpiece turned between passes",
    setting_bias=("desk-office", "kitchen-evening"),
    slideshow_lead="top-down of the tool on the workbench mid-project",
    proof="the process shot IS the proof — one continuous pass beats ten cuts",
), "craft", "crafts", "tools", "diy")

_register(CategoryStyle(
    key="accessories", label="Accessories & carry",
    hook_templates=(
        ("curiosity", "The {name} detail nobody noticed"),
        ("curiosity", "What fits in the {name}"),
        ("transformation", "Outfit, then the {name} on"),
        ("shock", "The {name} stitching up close"),
        ("problem", "Cheap ones break. The {name} won't"),
        ("curiosity", "Six months with the {name}. Look"),
    ),
    demo_grammar="on-body styling: put it on, rotate it in the light, pair it with "
                 "the outfit, show the wear points honestly",
    camera_demo="handheld close orbit of the detail, then a propped half-body shot "
                "wearing it",
    interaction="worn and touched: strap adjusted, clasp worked once, leather "
                "flexed to show the grain",
    setting_bias=("bedroom-morning", "entryway"),
    slideshow_lead="detail macro of the material/stitching in window light",
    proof="material honesty converts here — flaws in the grain read as real leather",
), "accessory", "jewelry", "bags")

_register(CategoryStyle(
    key="toys", label="Toys & games",
    hook_templates=(
        ("curiosity", "The {name} that ended screen time"),
        ("curiosity", "Gift idea: the {name}, wrapped"),
        ("shock", "The {name} kept them busy HOURS"),
        ("problem", "Rainy day? The {name} delivers"),
        ("curiosity", "Setting up the {name} in real time"),
        ("transformation", "Boredom, then the {name}"),
    ),
    demo_grammar="play in motion: the toy actually doing its thing on the floor or "
                 "table, real physics, real pace — child reactions stay real footage",
    camera_demo="handheld at table height following the action, a bit wobbly",
    interaction="played with, not presented: wound up, launched, rebuilt after it "
                "topples",
    setting_bias=("kitchen-evening", "entryway"),
    slideshow_lead="mid-play action shot, pieces scattered honestly",
    proof="the toy in motion IS the proof; kid reactions must be real footage",
), "toy", "games", "kids")

_register(CategoryStyle(
    key="wellness", label="Wellness & routine",
    hook_templates=(
        ("curiosity", "Where the {name} fits my day"),
        ("curiosity", "The {name} habit, week one"),
        ("problem", "{pain}? Here's my honest setup"),
        ("curiosity", "What's actually in the {name}"),
        ("curiosity", "My wind-down feat. the {name}"),
        ("shock", "Reading the {name} label out loud"),
    ),
    demo_grammar="routine placement: where it lives, when it's used, what the habit "
                 "looks like — NEVER a health outcome claim, ever",
    camera_demo="propped for the routine wide, casual and unhurried",
    interaction="used as a habit: set by the kettle, packed in the bag, checked "
                "off the morning list",
    setting_bias=("bedroom-morning", "kitchen-evening"),
    slideshow_lead="the product in the real routine spot, morning light",
    proof="STRICTEST category: zero health/outcome claims anywhere — routine and "
          "ingredients only; results talk is a compliance sweep failure",
), "supplement", "fitness", "health")

DEFAULT = CategoryStyle(
    key="general", label="General",
    hook_templates=(),
    demo_grammar="show the product doing its one job in real time, in the "
                 "persona's own space, one continuous take",
    camera_demo="",
    interaction="",
    setting_bias=(),
    slideshow_lead="",
    proof="the live demo is the proof — no claims the footage doesn't show",
)


def style_for(category: str) -> CategoryStyle:
    c = (category or "").strip().lower()
    if c in STYLES:
        return STYLES[c]
    if c in _ALIASES:
        return STYLES[_ALIASES[c]]
    return DEFAULT


def all_styles() -> list[CategoryStyle]:
    return list(STYLES.values())
