"""Organic marketing: how to get views for free, in the app.

Everything the operator asked for about organic — the researched playbook (2026-07,
sources at the bottom), not vibes. Organic is the engine's cheapest lever: a labeled
AI persona posting native-feeling content that the algorithm rewards for watch time,
not ad spend. This module states what actually moves reach in 2026 and turns it into
a checklist.

The honest frame carried from the rest of the engine: the algorithm rewards
COMPLETION and genuine engagement, which no bot can fake — so the work is real
content, posted like a human (see account_safety), with the AIGC label on. There's
no growth hack that substitutes for a hook people watch to the end.
"""

from __future__ import annotations

from dataclasses import dataclass

# Researched benchmarks (2026-07 — re-verify, the algorithm shifts).
COMPLETION_TARGET = 0.70     # ~70% average completion is the 2026 reach threshold
HOOK_SECONDS = 3            # the first 3s decide whether it gets shown at all
POSTS_PER_WEEK = (4, 6)     # 4–6/week…
RAMP_WEEKS = 8             # …for 8+ weeks before expecting real traction


@dataclass
class Signal:
    name: str
    weight: str
    how: str


# The five signals the 2026 algorithm weights most — and how to earn each.
ALGO_SIGNALS: tuple[Signal, ...] = (
    Signal("Completion rate", "highest",
           f"aim for ~{COMPLETION_TARGET*100:.0f}% average completion — keep clips "
           "SHORT (a tight 8–15s often beats 30s), and make the last second worth "
           "reaching (a payoff, a loop, a 'wait for it')"),
    Signal("Watch time", "high",
           "a strong hook in the first 3s, then no dead air — cut the setup, start "
           "mid-action"),
    Signal("Shares", "high",
           "make it worth sending to a friend: genuinely useful, funny, or "
           "'you need this' — shares outrun likes for reach"),
    Signal("Comments", "high",
           "leave a small open question or a mild 'wrong' opinion people correct; "
           "reply to every early comment as the persona (that's a human action you do)"),
    Signal("Repeat views", "medium",
           "loops and 'blink and you missed it' details pull rewatches — design the "
           "cut so the end flows back into the start"),
)

# The plays that actually work for a small/new account in 2026.
PLAYS: tuple[str, ...] = (
    "Small accounts have the edge: TikTok serves on QUALITY, not follower count — a "
    "zero-follower clip can pop if the first 3s land. Reported: small accounts grow "
    "faster than large ones.",
    "Post what people SEARCH (TikTok SEO): say the keyword out loud, put it in the "
    "caption and on-screen text. TikTok is a search engine now — 'best [thing] for "
    "[problem]' beats a clever caption.",
    "Series beat standalone: Part 1 / Part 2 / Part 3 and named playlists drive "
    "follow-through most standalone videos can't. Turn one product into a 5-part arc "
    "(the problem, the unbox, the demo, the objection, the result).",
    "Consistency is the price of entry: 4–6 posts/week for 8+ weeks before judging "
    "traction. Most quit at week 2 — that's the whole edge.",
    "Educational / entertaining / BTS / storytelling out-reach straight ads: 'here's "
    "why this exists', 'watch me try it', 'the mistake everyone makes'.",
    "Reply-to-comment videos are the highest-trust format and free content: answer a "
    "real question with a new clip (also un-bottable, so it lifts a clean account).",
    "Hook menu — the first line does the work: 'POV:…', 'Nobody tells you…', 'I "
    "tested…so you don't have to', 'Stop [mistake] if you [goal]', 'The [thing] "
    "everyone's gatekeeping'. The engine's hook packs are built from these.",
    "Trending sounds/formats give a reach boost — but only bend a trend to YOUR "
    "product; a trend that doesn't sell is just a view that doesn't convert.",
)


def render() -> str:
    lines = [
        "# Organic marketing — how to get views for free",
        "",
        "The cheapest lever you have. The 2026 algorithm rewards COMPLETION and real "
        "engagement — things no bot fakes — so the work is native-feeling content "
        "posted like a human, AIGC label on. No hack replaces a hook people finish.",
        "",
        "## The 5 signals the algorithm weights (earn each)", "",
    ]
    for s in ALGO_SIGNALS:
        lines.append(f"- **{s.name}** ({s.weight}) — {s.how}")
    lines += ["", "## The plays that work for a small account", ""]
    lines += [f"- {p}" for p in PLAYS]
    lines += [
        "", "## Cadence & the honest timeline", "",
        f"- {POSTS_PER_WEEK[0]}–{POSTS_PER_WEEK[1]} posts/week for {RAMP_WEEKS}+ weeks "
        "before you judge whether it's working. Traction is rarely week one.",
        "- Mix the engine's formats: persona video (`production`), photo-mode "
        "carousels (`slideshows`), and reply-to-comment clips; space them like a "
        "person (see `account-safety` for the safe cadence).",
        "- If a clip flops, it's almost always the first 3 seconds or the completion "
        "rate — not the product. Re-hook and re-post; don't panic-pivot the product.",
        "",
        "The AIGC label stays on every post. Organic reach is earned by watch time; "
        "the engine makes the content, YOU post it from the app.",
    ]
    return "\n".join(lines) + "\n"


SOURCES = (
    "https://www.socialinsider.io/blog/organic-tiktok-growth/",
    "https://12amagency.com/blog/what-is-tiktok-organic-marketing/",
    "https://www.stackmatix.com/blog/tiktok-marketing-strategy-2026",
    "https://multilogin.com/blog/mobile/how-to-grow-your-tiktok-account/",
    "https://www.ourkidthings.com/tiktok-growth-strategies-that-actually-work-in-2026/",
)
