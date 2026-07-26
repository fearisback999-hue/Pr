"""Account health: staying within TikTok's ToS so an AI-content shop keeps its reach.

The operator's real question: "will TikTok shadowban us for being run by a bot?"
The honest answer, encoded here so the engine states it plainly:

  TikTok does NOT restrict reach for AI-generated content that's LABELED (our AIGC
  disclosure). What gets accounts reach-restricted or banned is automated account
  OPERATION and inauthentic behaviour — auto-posting through unofficial APIs, bought
  engagement, engagement pods, inhuman cadence, aggressive follow/unfollow, device
  farms. Content automation (disclosed) is fine; ACCOUNT automation is the risk.

This engine is built so the risky parts stay human: it PLANS, you post from the app;
the autopilot never publishes; generation needs confirmation; nothing here ever
touches your TikTok account. So the tool itself won't get you flagged — this module
keeps the human operation inside the lines too.

This is compliance guidance, not evasion. Every rule is "operate legitimately," not
"dodge detection." "Shadowban" is an unofficial term for reduced/restricted reach.
Guidance reflects TikTok's published Community Guidelines / spam & inauthentic-
behaviour policies as of 2026-07 — re-verify; platform rules move.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Human-plausible posting cadence per ACCOUNT (not across a whole store's accounts).
# Bursts of dozens/day or scheduled-to-the-second posting read as automation.
SAFE_POSTS_PER_DAY = 4
# New accounts start with low trust; ramp, don't blast. (day-range, max posts/day)
WARMUP_RAMP = ((7, 2), (30, 3))     # ≤7d: ≤2/day; ≤30d: ≤3/day; then SAFE_POSTS_PER_DAY


@dataclass
class Rule:
    rule: str
    why: str


# The account-health checklist. Each rule is legitimate operation; the WHY names the
# real enforcement signal it avoids.
RULES: tuple[Rule, ...] = (
    Rule("The engine plans; a HUMAN posts from the TikTok app (or an officially "
         "sanctioned scheduler — TikTok's own, or an approved Marketing Partner). "
         "Never a gray-market auto-poster.",
         "Automated posting through unofficial APIs is the clearest 'bot' signal and "
         "a direct ToS violation — it actions accounts far more than AI content does."),
    Rule("Keep the AIGC label ON every post (the engine already refuses to export "
         "assets without it).",
         "TikTok requires disclosing realistic AI-generated content; undisclosed "
         "synthetic media is the policy line you must not cross."),
    Rule(f"Human cadence: ~1–{SAFE_POSTS_PER_DAY} posts/day per account, spread "
         "through the day — not a burst, not scheduled to the same second.",
         "Inhuman volume and metronomic timing are automation signals; normal "
         "creators post a handful of times a day."),
    Rule("Warm up a new account: a few posts the first week, watch and comment like "
         "a person, ramp slowly.",
         "Fresh accounts posting aggressively read as throwaway bot accounts and "
         "start with low trust and reach."),
    Rule("One consistent persona per account; a DEDICATED account per avatar.",
         "A stable creator identity reads authentic — the opposite of a spam signal. "
         "It's also why the clothing section posts from the persona's own account."),
    Rule("Vary the content: different hooks, angles, settings, categories — never "
         "re-post near-identical clips.",
         "Duplicate/repetitive content is a spam trigger; the engine's 50-hook "
         "variety and per-category styles exist partly for this."),
    Rule("No bought followers or engagement, no engagement pods, no aggressive "
         "follow/unfollow loops.",
         "Inauthentic engagement is explicitly against Community Guidelines and a "
         "common cause of reduced reach."),
    Rule("No hashtag stuffing or banned/flagged tags; keep links clean and relevant.",
         "Spammy or flagged hashtags and links throttle distribution."),
    Rule("One account per device/identity where you can; avoid many accounts on one "
         "IP or device.",
         "Coordinated-account and device-farm patterns are classic inauthentic-"
         "behaviour flags."),
    Rule("Engage for real: reply to comments as the persona.",
         "Genuine interaction lifts reach honestly and is un-bottable — a human "
         "action the engine deliberately leaves to you."),
)

# Running MULTIPLE accounts (a roster of distinct personas) — the legitimate way.
# You don't need to "beat" a limit: multiple accounts are allowed. What gets clusters
# of accounts banned is HIDING the coordination with evasion tooling — the opposite
# of safe.
MULTI_ACCOUNT: tuple[Rule, ...] = (
    Rule("Multiple accounts are ALLOWED — you don't need to get around anything. "
         "TikTok lets you run several and switch between them; a roster of distinct "
         "persona-accounts for different niches is legitimate.",
         "the risk was never 'more than one account' — it's coordinated accounts "
         "concealed to look independent."),
    Rule("Make each account a GENUINELY distinct creator: different persona, voice, "
         "look, niche, and content. That real distinctness IS the legitimacy.",
         "near-identical content across accounts, or one persona spread thin, reads "
         "as a spam network; distinct creators read as distinct creators."),
    Rule("Do NOT use a VPN, antidetect browser, or device farm to mask that one "
         "operator runs the roster. The engine will not set this up.",
         "spoofing to hide coordination is the single clearest coordinated-inauthentic-"
         "behavior fingerprint — it gets whole clusters banned at once, and "
         "ban-evasion is explicitly against ToS."),
    Rule("Want hard separation? Use separate REAL devices / logins, not spoofing "
         "software.",
         "genuine separation is fine; faked separation is the flag."),
    Rule("Never cross-bot your own accounts (liking/commenting/following between "
         "them) or buy engagement to prop them up.",
         "inter-account engagement rings are a textbook takedown trigger."),
    Rule("Add an account only when you can actually FEED it 1–3 human-paced posts/day. "
         "Grow the roster one persona at a time.",
         "ten thin, half-dead accounts perform worse and look more automated than one "
         "genuinely active one."),
)

# What to do if reach collapses — DIAGNOSE, don't evade.
REDUCED_REACH_PLAYBOOK: tuple[str, ...] = (
    "Check the app's account status / Community Guideline strikes; appeal anything "
    "wrongful.",
    "Pause posting 24–48h — don't panic-post more, that amplifies the spam signal.",
    "Delete any post that was flagged or removed.",
    "Confirm every live post has the AIGC label and no banned hashtags.",
    "Post ONE genuinely original, human-feeling clip (a reply-to-comment, a "
    "face-covered mirror selfie) to re-establish normal behaviour.",
    "If reach stays low with a clean account, it's probably content quality (low "
    "watch time), not a ban — fix the hook, not the account.",
)


@dataclass
class CadenceAdvice:
    account_age_days: int
    planned_per_day: int
    cap: int
    ok: bool
    warnings: list[str] = field(default_factory=list)


def ramp_cap(account_age_days: int) -> int:
    """Max human-plausible posts/day for an account of this age."""
    for max_age, cap in WARMUP_RAMP:
        if account_age_days <= max_age:
            return cap
    return SAFE_POSTS_PER_DAY


def cadence_advice(account_age_days: int, planned_per_day: int) -> CadenceAdvice:
    cap = ramp_cap(account_age_days)
    warnings: list[str] = []
    if planned_per_day > cap:
        warnings.append(
            f"{planned_per_day} posts/day exceeds the ~{cap}/day human cap for a "
            f"{account_age_days}-day-old account — spread them out or spread them "
            "across more persona accounts (never blast one account).")
    if account_age_days <= 7 and planned_per_day > WARMUP_RAMP[0][1]:
        warnings.append("this account is still in its first week — warm it up (watch, "
                        "comment, a couple posts) before ramping volume.")
    return CadenceAdvice(account_age_days=account_age_days, planned_per_day=planned_per_day,
                         cap=cap, ok=not warnings, warnings=warnings)


def render() -> str:
    lines = [
        "# Account health — will a bot get us shadowbanned?",
        "",
        "**Short answer: not for LABELED AI content — but yes for automated account "
        "operation.** TikTok restricts reach for auto-posting via unofficial tools, "
        "bought/faked engagement, inhuman cadence, and coordinated accounts — not for "
        "AI videos that carry the disclosure. This engine never touches your account: "
        "it plans, YOU post. Keep the human operation inside these lines.",
        "",
        "## The rules (legitimate operation, not evasion)",
        "",
    ]
    for r in RULES:
        lines += [f"- **{r.rule}**", f"  - why: {r.why}"]
    lines += ["", "## Running MANY accounts (a persona roster) — the legitimate way", "",
              "You don't need to get past a limit: multiple accounts are ALLOWED. The "
              "way to run a roster safely is to genuinely BE several distinct creators, "
              "not to hide with a VPN/antidetect browser (that's what gets clusters "
              "banned).", ""]
    for r in MULTI_ACCOUNT:
        lines += [f"- **{r.rule}**", f"  - why: {r.why}"]
    lines += ["", "## If reach suddenly drops", ""]
    lines += [f"- {step}" for step in REDUCED_REACH_PLAYBOOK]
    lines += ["", f"Safe cadence: ~1–{SAFE_POSTS_PER_DAY} posts/day per established "
              "account; warm new accounts up first. 'Shadowban' is an unofficial term "
              "for reduced reach — rules per TikTok's published policies (2026-07, "
              "re-verify)."]
    return "\n".join(lines) + "\n"
