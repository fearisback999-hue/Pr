"""Landing-page copy generator: description, benefits, FAQ, guarantee, comparison,
headlines, urgency, social-proof SLOTS, and SEO metadata — composed from the product's
computed psychology and economics, compliance-swept line by line.

Two honesty rules baked in:
  • Social proof is a SLOT, never generated copy — fabricated testimonials are deceptive
    advertising (FTC + TikTok policy, same rule the compliance module enforces). The
    template marks exactly where YOUR real reviews go.
  • Urgency/scarcity copy states only what you can make true (a real stock count, a real
    end date). Fake countdowns are listed as the anti-pattern, not offered as copy.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..creative.compliance import ComplianceReport, review_text
from ..db import models
from ..economics import Economics
from ..psychology import PsychProfile


@dataclass
class LandingPage:
    product: models.Product
    headlines: list[str]
    description: str
    benefits: list[tuple[str, str]]          # (benefit, supporting detail)
    faq: list[tuple[str, str]]
    guarantee: str
    comparison: list[tuple[str, str, str]]   # (axis, generic, this)
    urgency: list[str]
    social_proof_slots: list[str]
    seo_title: str
    seo_description: str
    compliance: list[ComplianceReport] = field(default_factory=list)

    @property
    def flagged(self) -> list[ComplianceReport]:
        return [c for c in self.compliance if not c.ok]

    def render(self) -> str:
        lines = [
            f"# Landing page copy — {self.product.name}",
            "",
            "## Headline variations (test these)",
            "",
            *[f"{i}. {h}" for i, h in enumerate(self.headlines, 1)],
            "",
            "## Product description",
            "",
            self.description,
            "",
            "## Benefits",
            "",
        ]
        for benefit, detail in self.benefits:
            lines += [f"**{benefit}**  ", detail, ""]
        lines += ["## FAQ", ""]
        for q, a in self.faq:
            lines += [f"**Q: {q}**  ", f"A: {a}", ""]
        lines += [
            "## Guarantee block", "", self.guarantee, "",
            "## Comparison table", "",
            "| | Generic alternative | This |", "|---|---|---|",
            *[f"| {axis} | {generic} | {ours} |" for axis, generic, ours in self.comparison],
            "",
            "## Urgency / scarcity (only what you can make TRUE)", "",
            *[f"- {u}" for u in self.urgency],
            "- ❌ anti-pattern: fake countdown timers and invented \"only 3 left\" — "
            "deceptive, and platforms enforce against it",
            "",
            "## Social proof — SLOTS for real reviews (never fabricate)", "",
            *[f"- {s}" for s in self.social_proof_slots],
            "",
            "## SEO metadata", "",
            f"- title ({len(self.seo_title)} chars): {self.seo_title}",
            f"- description ({len(self.seo_description)} chars): {self.seo_description}",
        ]
        if self.flagged:
            lines += ["", "## ⚠️ Compliance flags — rewrite before publishing", ""]
            lines += [f"- {c.summary} → \"{c.text}\"" for c in self.flagged]
        else:
            lines += ["", "_Compliance sweep: clean._"]
        return "\n".join(lines) + "\n"


def build_landing_page(
    product: models.Product, psych: PsychProfile, economics: Economics,
    us_warehouse: bool = False,
) -> LandingPage:
    short = product.name.split("(")[0].strip()
    pain = psych.pain_point.rstrip(".")
    desire = psych.desire.rstrip(".")

    headlines = [
        f"{short} — {desire.capitalize()}",
        f"Finally: an answer to {pain}",
        f"The {short} everyone's asking about",
        f"Stop settling. {desire.capitalize()}.",
        f"{short}: small change, visible difference",
    ]

    description = (
        f"{short} exists for one reason: {pain}. Instead of another workaround, it "
        f"delivers {desire} — simply, and fast enough that you notice. Built for people "
        f"who care about {psych.identity_appeal.rstrip('.')}, it earns its spot in your "
        "routine the first time you use it."
    )

    benefits = [
        (f"Solves the actual problem", f"Targets {pain} directly instead of masking it."),
        (f"You feel it fast", f"{desire.capitalize()} — the payoff is immediate enough "
                              "to notice on day one."),
        ("Made for your routine", f"Fits how you already live; {psych.impulse_factor.rstrip('.')}."),
        ("No learning curve", "Open it, use it, done. If a product needs a manual, "
                              "it isn't this one."),
    ]

    ship_line = ("Ships from a US warehouse — arrives in days, not weeks."
                 if us_warehouse else
                 "Ships tracked; the exact window is stated at checkout — we only promise "
                 "what we hit.")
    faq = [
        (f"Does it really help with {pain}?",
         f"That's its whole job. The demo video shows it working in real time — "
         "no cuts, no tricks."),
        ("How fast is shipping?", ship_line),
        ("What if it's not for me?",
         "Returns are accepted within the window stated below — no interrogation."),
        ("Is the quality actually good?",
         "We sample-tested it ourselves before listing it. If a batch slips, we pull it."),
        ("Is there a warranty?",
         "See the policy block below — what's written there is exactly what we honor."),
        ("Why not just buy the cheap version?",
         "You can — the comparison table below is honest about the differences."),
    ]

    guarantee = (
        "**[YOUR POLICY HERE]** — state the return window you actually honor "
        "(TikTok Shop offers 14/30/45/90-day settings; 30 is the default most categories "
        "use) and who pays return shipping. A guarantee you can't honor is a refund "
        "spiral plus an account-health hit; a clear one converts."
    )

    comparison = [
        ("Built for the problem", "generic, one-size-fits-all", f"designed around {pain}"),
        ("Quality control", "whatever ships", "sample-tested before listing"),
        ("Support", "silence", "real replies within the stated window"),
        ("Returns", "good luck", "the policy above, honored"),
    ]

    urgency = [
        "state the REAL stock count when it's genuinely low (pull it from your supplier "
        "dashboard, update it, and remove it when restocked)",
        "run genuine time-boxed launch pricing: a real end date, price actually goes up "
        "after, and you say so plainly",
        f"lean on the trend itself: the honest fact that demand is moving now (that's "
        f"why {short} surfaced in the engine) is urgency enough",
    ]

    social_proof_slots = [
        "[SLOT] paste 2–3 REAL buyer reviews verbatim once you have them (screenshot or "
        "text + first name) — never write these yourself",
        "[SLOT] embed your best-performing organic TikTok once one exists (real view "
        "count is the proof)",
        "[SLOT] creator quotes from your affiliate program — with their permission, "
        "linked to their video",
    ]

    seo_title = f"{short} | {desire.capitalize()}"[:60]
    seo_description = (
        f"{short}: {desire}. Fast shipping, honest returns, sample-tested. "
        f"See the real-time demo."
    )[:155]

    page = LandingPage(
        product=product, headlines=headlines, description=description,
        benefits=benefits, faq=faq, guarantee=guarantee, comparison=comparison,
        urgency=urgency, social_proof_slots=social_proof_slots,
        seo_title=seo_title, seo_description=seo_description,
    )
    texts = (headlines + [description] + [b for b, _ in benefits]
             + [d for _, d in benefits] + [a for _, a in faq] + urgency)
    page.compliance = [review_text(t) for t in texts]
    return page
