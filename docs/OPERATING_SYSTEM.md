# ENGINE OS — The Complete Operating System

The full redesign of the TikTok Shop dropshipping operation, grounded in the code that
actually runs in this repo. Every threshold cited here is the one the engine enforces;
every command named is real. Evidence labels used throughout: **[EVIDENCE]** = sourced
research or implemented+tested code · **[INFERENCE]** = reasoned from evidence ·
**[SPECULATION]** = plausible, unverified.

Companion docs: `THESIS.md` (why), `OPERATING.md` (daily runbook), `playbook` command
(zero-to-hero checklist). This document is the strategy + SOP layer.

---

## 1. Executive summary

You already own the hard part: a working detection→scoring→economics→creative→test→
feedback pipeline with hard gates, a 48-hour kill timer, a true-fee-stack profit
optimizer, lifecycle staging, a confidence meter, and a dashboard. What this document
adds is the **operating system around the code**: the research workflow and source
rankings, the creator and ads playbooks, SOPs, decision trees, compliance checklists,
and the build-order/ROI map.

Three design principles carried through everything:

1. **Learn fast, kill fast, scale only on agreement.** A product scales only when
   multiple independent signals agree (score ≥80 + gates + lifecycle actionable +
   confidence ≥ medium + live ROAS above the TRUE break-even). Any single kill signal
   kills.
2. **TikTok Shop analytics is partial truth.** It reports GMV, orders, traffic,
   affiliate attribution, settlement — it does not compute your net profit. Profit truth
   lives in this engine (`optimize`, `log-test`, `report-monthly`) reconciled monthly
   against settlement statements. **[EVIDENCE — researched 2026-07; the engine models
   what TikTok won't]**
3. **Automate computation, never judgment or spend.** Scoring, math, copy drafts,
   reports: automated. Orders, ad budgets, creator relationships, kill decisions:
   human, with the engine advising. This is the founding guardrail and it's why the
   account survives.

---

## 2. System architecture

```
                              ┌─────────────────────────────────────────────┐
                              │                DATA IN (manual/API only)     │
                              │  Kalodata CSV · FastMoss CSV · manual add    │
                              │  TikTok Creative Center (browse) · quotes    │
                              └──────────────────┬──────────────────────────┘
                                                 ▼
        ┌────────────────────────────── SQLite (single file) ─────────────────────────────┐
        │ products · daily_metrics · suppliers · scores · creatives · tests · results ·   │
        │ playbook_state · import_log                                                     │
        └───────┬──────────────────────────────────────────────────────────────┬─────────┘
                ▼                                                              ▼
   DETECTION (auto)                                              ECONOMICS (auto, refuses guesses)
   momentum (spike-capped) · saturation ·                        landed cost → margin → break-even
   lifecycle (6 stages) · window estimate                        → TRUE fee stack (optimize)
                └───────────────┬──────────────────────────────────────┘
                                ▼
                   SCORING (auto) — 100pts, 6 categories
                   HARD GATES: margin<45% · returns≥10% · branded ·
                   restricted · commodity-saturated(≥65)  → KILL
                   + CONFIDENCE (data trust, reasons stated)
                                ▼
              ┌────────── VERDICT: TEST / WATCH / KILL ──────────┐
              ▼ (TEST only)                                      ▼ (all)
   CREATIVE (auto-draft, human-select)                DASHBOARD + ASSISTANT (read-only)
   psych spine → 50 hooks · concepts ·                board · search · scorecards ·
   scripts · landing copy · creator brief             next-actions · alerts · playbook
              ▼
   HUMAN: launch listing + ads + creator outreach     ← the engine NEVER does these
              ▼
   TEST TELEMETRY (manual daily: log-test)
   validate → 48h kill timer · scale check
              ▼
   OUTCOME (log-result) → FEEDBACK LOOP (monthly recalibration, suggestions only)
```

**Manual vs automated — the boundary table:**

| Stage | Automated | Human | Why |
|---|---|---|---|
| Data ingestion | CSV parse, validation, dedupe | Export/observe | ToS-legal sources only |
| Detection/scoring | Fully | — | Pure math, shows work |
| Economics | Computation | Enter the REAL quote | Engine refuses placeholder costs |
| Creative | Draft generation, compliance sweep | Select, shoot, approve | Volume cheap; judgment isn't |
| Generation spend | — | `--confirm` every time | Money |
| Listings/ads/orders | — | Fully human (official integrations for fulfillment) | Founding guardrail |
| Kill/scale calls | Recommendation + timer math | Final call (but don't override kills) | Discipline is the product |
| Recalibration | Fit + suggestion | `--apply` | A self-tuning loop unsupervised tunes to noise |

---

## 3. Product scoring model

The implemented model: **100 points, 6 categories, hard gates first, lifecycle +
confidence alongside.** Your requested 20 metrics map onto it as follows — several are
deliberately *merged* (they're the same signal) and several are deliberately *outputs
of testing, not inputs* (pretending to know CVR before testing is how people lie to
themselves). **[EVIDENCE — implemented + 204 tests]**

| Requested metric | Where it lives | Formula (implemented) | Weight | Normalization |
|---|---|---|---|---|
| Demand Score | Market Demand | log₁₀(velocity_7d)/log₁₀(500)·8 + WoW/0.5·5 + trend·3 + consistency·2 + urgency·2 | 20 | each component clamped 0–1 × subweight |
| Competition Score | Competition Timing (saturation⁻¹) | 1−(sat_index/100), sat = 0.4·sellers/60 + 0.35·promos/100 + 0.25·ads/50 | 6 of 15 | ceilings→0–1 |
| Saturation Risk | **HARD GATE** + lifecycle | sat ≥ 65 → disqualified; lifecycle stages the trajectory | gate | absolute |
| Novelty Score | Differentiation | 1−(0.6·commodity_prior⊕review_signal + 0.4·price_race) | 4 of 15 | 0–1 |
| Virality Score | Viral Demo | clarity(8)+curiosity(4)+visible_result(5)+emotion(3); emotion/curiosity from review corpus | 20 | 0–1 × subweight |
| Impulse Score | Economics (price band) | $15–50→1.0, shoulders to $5/$100→0 | 2 of 20 | piecewise linear |
| Margin Score | Economics + **GATE** | (margin−0.40)/0.30; gate at 45% | 7 of 20 | 40%→0, 70%→1 |
| Refund Risk | **GATE** + Economics | category prior + 0.08·complaint_density; ≥10% → disqualified | gate + 6 of 20 | prior-anchored |
| Shipping Risk | Supplier score | ship_days vs 5-day target, US warehouse bonus | supplier rank | 0–100 |
| Supplier Reliability | Supplier score | rating, response_hrs, MOQ, sample status | supplier rank | 0–100 |
| Creator Availability | **manual input** | not computable from feed data — check Affiliate Center count for the niche | — | — |
| UGC Potential | Content Potential | category ugc_fit prior, override with real signal | 4 of 15 | 0–1 |
| Hook Potential | Viral Demo (curiosity) + psych spine | one sharp trigger > five vague ones | in 20 | 0–1 |
| Scale Potential | Brand Potential + window | repeat/consumable(4)+line_extension(3)+identity(3); window_days | 10 | 0–1 |
| Compliance Risk | **GATES** (branded/restricted) + creative sweep | binary gates; regex sweep on all copy | gate | absolute |
| Expected ROAS | **break-even, not expected** | TRUE break-even = price ÷ true_profit (`optimize`) | derived | the bar ads must beat |
| Expected CPA | max CAC | = true profit/unit; spend more and you lose | derived | $ |
| Expected CVR | **OUTPUT of testing** | logged via `log-test`; 3–6% organic / 0.3–0.6% paid benchmarks **[EVIDENCE-researched]** | — | — |
| Expected AOV | offer structure | `optimize` sweep picks the AOV-maximizing viable bundle | derived | $ |
| Expected MER | **OUTPUT** | blended revenue ÷ blended spend from logged actuals | — | tracked |

**Tradeoffs encoded:** momentum weighted highest *but* gated (a hot commodity is still
dead); differentiation beats raw low-competition (a quiet commodity floods on first
success); pre-test "expected" conversion metrics are refused as inputs — the engine
gives you the *bar* (break-even) and testing gives you the *number*. Weights live in
`weights.json` and recalibrate from YOUR outcomes (`recalibrate`, ≥20 labeled tests).

---

## 4. Research workflow

**Sources ranked by signal quality for finding winners** (quality = leading-ness ×
specificity × legality of access):

| Rank | Source | Signal | Access | Role |
|---|---|---|---|---|
| 1 | Kalodata / FastMoss | actual TikTok Shop velocity + seller counts | paid, CSV export | PRIMARY — only true leading signal |
| 2 | TikTok Creative Center (Top Ads) | what's being spent on NOW | free, browse | creative + early demand read |
| 3 | TikTok Shop tab + #TikTokMadeMeBuyIt | live merchandising | free, browse | hypothesis generation |
| 4 | Amazon Movers & Shakers | 24h rank velocity, cross-platform demand | free, browse | confirmation + pre-TikTok discovery |
| 5 | Google Trends | upstream search demand | free, CSV export | trend slope input |
| 6 | CJ/AliExpress/Alibaba order counts | supply-side volume | free, browse | saturation cross-check (>1k AliExpress orders = late) |
| 7 | Facebook Ads Library | competitor ad count/age | free, search | saturation check (>15–20 active advertisers = crowded) |
| 8 | Pinterest Trends | 2–6mo early aesthetic trends | free | seasonal/aesthetic lead |
| 9 | Reddit niche subs | problem language, pain points | free, browse | psychology corpus, NOT demand |
| 10 | YouTube Shorts / IG Reels | trend echo (lags TikTok) | browse | confirmation only |
| 11 | X/Twitter | weak for products | browse | ignore mostly |
| 12 | Shopify store inspection | competitor offers/AOV structure | manual | offer design input |
| 13 | USPTO TESS trademark search | IP kill-check | free | **mandatory before listing** |

**The weekly workflow (90 min, Monday):**

1. Export Kalodata/FastMoss CSV — filters: 7d growth >100%, sellers <15, price $15–50,
   your content-capable categories. → `import-csv`
2. 20 min in Creative Center Top Ads + Shop tab: note 3–5 products you *see* working →
   `add` + start `add-metric` daily observations.
3. `daily` → `next` → for anything TEST/near: cross-checks — Google Trends slope,
   FB Ads Library advertiser count, AliExpress order counts, USPTO word-mark search.
4. Get 2 real quotes (CJ + HyperSKU, US warehouse) → `add-supplier` → `scorecard` →
   `optimize` → `analyze`.
5. Anything surviving all of it: order the sample. That's the go/no-go tree (§11).

---

## 5. Creative system

Strategy in one line: **one psychological trigger per product, demonstrated in the
first 3 seconds, at UGC polish level — never ad polish.** [EVIDENCE: overproduced
content underperforms; the engine's `psych` pass extracts the single trigger]

The engine generates raw material (`creative-pack <id>`: 50 hooks, 50 UGC concepts,
20 paid + 20 organic scripts, CTAs, captions, hashtags, storyboards, B-roll,
thumbnails, all compliance-swept). Your job is selection and production.

**25 canonical hook templates** (the pack's four types; {X}=product, {P}=pain):
curiosity — "Why is everyone obsessed with {X}?" · "Nobody told me {X} did this" ·
"The {X} everyone keeps gatekeeping" · "I tested {X} so you don't have to" · "So THIS
is why {X} sold out" · "What {X} does at 0:07 is wild";
problem — "Still dealing with {P}? Watch this" · "Your {P} isn't normal. Watch" ·
"{P} had me until I tried this" · "The real reason {P} keeps happening" · "3 signs {P}
is costing you" · "How I finally stopped {P}";
shock — "Wait… {X} actually does THAT?" · "No edits. Just {X}. Watch" · "I was NOT
ready for {X}" · "Did {X} just do that live?" · "The {X} result nobody warned me
about" · "Filming this {X} demo with zero cuts";
transformation — "Before vs after {X}" · "Day 1 vs day 7 with {X}" · "Watch {X} change
this instantly" · "One week with {X}. Look" · "Proof {X} actually works" · "My routine
before vs after {X}" · "Small purchase. Big difference. {X}".

**20 demo structures:** real-time demo no cuts · before/after split · speed-run
(problem→solved <15s) · first-reaction · unboxing-silent · side-by-side vs generic ·
3-things-I-didn't-expect · reply-to-hater demo · day-in-life insert · ASMR use ·
stress test · wrong-way/right-way · gift reaction · duet-bait challenge · storytime
over B-roll · POV discovery · 0-to-result timer on screen · "I bought so you don't
have to" · repeat-buyer restock · creator-vs-creator same product.

**UGC brief template (×20 = one per script in the pack):** hook line (verbatim) →
emotion target → scene list (5, from `storyboard`) → what must be REAL (no fabricated
claims — compliance list attached) → AI-disclosure requirement → format/length →
CTA (paid vs organic variant) → usage rights granted → deliverable count.

**10 ad angles per product** (generated by `analyze`): problem-first · identity ·
trigger-led · contrast · UGC reaction · authority-adjacent (no fake authority) ·
economic (cost-per-use) · seasonal · gift · objection-preemption.

**Testing matrix:** 3 hooks × 2 formats × 2 CTAs = 12 variants max per wave; one
variable isolated per comparison; $10–20/ad-set/day; kill at <1% CTR after ~2k
impressions **[INFERENCE from engine thresholds]**; winner → next wave varies the
*other* dimension.

**Fatigue detection:** frequency >2.5, CTR −30% from peak over 3 days, rising CPM at
flat CTR → rotate hooks (same winning demo core). **[INFERENCE — standard signals; the
engine's per-creative CTR tracking in `tests` supports the read]**

---

## 6. Creator system

**Sourcing (ranked):** TikTok Shop Affiliate Center open collab (free, volume) →
targeted invites to creators already posting your niche (search hashtags, sort by
recent, 5k–100k followers) → marketplaces when scaling (Collabstr no-minimum →
Billo ~$99+/video → Twirl ~$325 → Insense ~$500/mo — real prices on the Creators
dashboard page). **[EVIDENCE — researched 2026-07]**

**Commissions [EVIDENCE]:** open collab 10–15%; targeted 18–25%; top performers to
50%. Category reality: beauty 10–25%, fashion/home 8–18%, electronics 3–8%. Rates
lock 30 days once a creator picks up. Your `optimize` output tells you the max
affordable commission (true-stack margin must stay >0 at the floor).

**Outreach script (targeted invite):** "Hey {name} — loved your {specific video}.
We make {product, one line}. {Commission}% commission + free sample, no exclusivity,
no scripts — you make what you'd make. Want me to send one?" Short, specific,
no-obligation. Follow up once after 4 days. Never automate the relationship.

**Sample workflow:** 30–50 invites → sample the 10 best responders → track: sample
sent → posted? (14-day check) → GMV attributed (native affiliate attribution) →
re-supply + raise commission for converters; stop sampling non-posters.

**Creator scorecard (0–100):** posted within 14d (30) · attributed GMV/sample cost
(40) · content reusable as Spark Ad? (20) · audience-niche match (10). Scale
criterion: any creator >3× sample cost in attributed GMV → negotiate ongoing rate +
Spark Ad rights. Micro (5–50k) for volume/authenticity; macro only after a proven
winner needs reach. International: match creator country to your shipping country;
US-only until fulfillment is proven. Contract checklist: usage rights (organic +
paid + duration), FTC disclosure obligation, no-claims list, payment terms, content
approval rights.

---

## 7. Ads system

**Structure [INFERENCE — standard 2026 practice, adjust to observed]:** 1 testing
campaign (ABO, 3–5 ad sets, broad targeting, $10–20/day each) + 1 scaling campaign
(CBO, winners only). Broad > interest targeting in 2026 — creative IS the targeting.
Spark Ads from creator posts > dark ads (social proof persists).

**Rules (the engine enforces the money ones):**
- Learning phase: don't touch an ad set before ~50 conversions or 3 days unless a
  kill rule fires. **[INFERENCE]**
- KILL (engine, `validate`): below TRUE break-even ROAS 48 straight hours → kill (no
  overrides — hope is not a strategy) · CTR <1% and not improving · refunds >5%.
- SCALE (engine, all must hold): CTR ≥1.5% · ROAS >1.15× break-even · stable refunds
  · one clear winning creative. Then +20–30% budget steps every 2–3 days, re-`validate`
  after each. Duplicate-and-raise rather than editing the learning-phase winner.
  **[part engine / part INFERENCE]**
- Judge everything against the **TRUE break-even** from `optimize` (e.g. 1.88, not
  the 6%-only 1.40) — the single most common silent loss.
- Dayparting: don't until >$100/day spend; then check hourly splits. **[SPECULATION —
  low priority]**
- Account health: never run traffic to SLAs you can't hit; ad account bans propagate
  to Shop health. One product per ad account is paranoia you don't need; one BM with
  backup admin is prudence you do. **[INFERENCE]**
- Attribution: TikTok overcounts vs settlement — reconcile weekly against `log-test`
  actuals and monthly against settlement (SOP §11). **[EVIDENCE — platform analytics
  ≠ profit truth]**

---

## 8. Landing page system

The engine writes the copy (`landing <id>`) with the honesty rules baked in; this is
the conversion checklist around it:

trust — real policy stated plainly (the [YOUR POLICY HERE] block), sample-tested
claim only if true · social proof — REAL reviews only, into the marked slots; a fake
testimonial is an FTC violation and the generator refuses · urgency — only true
scarcity (real stock counts, real end dates; fake countdowns are the listed
anti-pattern) · bundles — the ★ structure from `optimize` (2-pack at 1.75× was the
margin-optimal example) · pricing — charm pricing inside the $15–50 band; anchor with
the crossed-out 3-pack · video — autoplay demo above the fold, GIF fallback of THE
3-second payoff moment · mobile — 90%+ of TikTok traffic; thumb-reach CTA, one-screen
value prop, <2.5s LCP · friction — express checkout on top, ≤3 form fields visible,
shipping cost visible before checkout (surprise shipping = abandonment + chargebacks)
· A/B — one variable at a time, headline first (5 variants generated), then hero
media, then offer structure; ≥300 sessions/variant before calling it.
**[INFERENCE — standard CRO; engine supplies the tested copy skeleton]**

---

## 9. Analytics system

**The truth table — native vs yours:**

| Metric | TikTok Shop native | This engine | Third-party |
|---|---|---|---|
| GMV / orders / traffic / content-type split | ✅ | — | — |
| Affiliate attribution | ✅ | creator scorecard (manual roll-up) | — |
| Settlement (fees netted) | ✅ (lagging) | reconcile monthly | — |
| Ad spend | Ads Manager | `log-test` daily | — |
| COGS / landed cost | ❌ | `add-supplier` (refuses guesses) | — |
| Refund cost impact | partial | return-rate priors + complaint signal + `optimize` drag line | — |
| **True fee stack / contribution margin** | ❌ | `optimize` (referral+payment+affiliate) | — |
| Break-even ROAS / max CAC | ❌ | `scorecard` + `optimize` | — |
| MER / blended | ❌ | logged actuals vs true break-even | spreadsheet |
| SKU-level profit | ❌ | scorecard economics × logged volume | Dashboardly-class tools optional |
| Cohort LTV / retention | ❌ | ❌ (needs order-level export — Phase 3) | yes |
| Creative-level ROI | partial | `tests` table per creative | — |

Contribution margin per order = revenue − COGS − ship − referral − payment −
affiliate − ad spend/order − refund drag. `optimize` computes everything except your
actual ad spend per order (that's MER from logs). **The operating rule: TikTok tells
you what sold; only your own ledger tells you what you kept.**

---

## 10. Automation system (agents)

The engine's stance: **agents compute and draft; humans approve and spend.** Status
of your 14 requested agents:

| Agent | Status | Inputs → outputs | Human checkpoint | Failure mode guarded |
|---|---|---|---|---|
| Trend monitor | ⚠ semi: CSV import + your eyes; NO scrapers (ToS) | vendor CSV → daily_metrics | you export | stale data → `confidence` flags short history |
| Product scorer | ✅ `daily` | metrics → scores+gates | none needed (read-only) | placeholder costs → refused |
| Supplier comparer | ✅ rank + ★ | supplier rows → ranked | you enter quotes | fake quotes → engine refuses estimates |
| Competitor ad watcher | ❌ scraper; do manually via Creative Center/Ads Library weekly | — | you | ban risk avoided |
| Hook generator | ✅ `creative-pack` | psych spine → 50 hooks | you select | claims → compliance sweep |
| UGC script generator | ✅ | spine+hooks → 40 scripts | you select/shoot | fabricated testimony → swept |
| Ad variant generator | ✅ pack + Higgsfield path | brief → variants | `--confirm` (spends) | unlabeled AI → export blocks missing disclosure |
| Creator brief generator | ✅ `packet` | product+psych → brief | you send | over-promising → compliance list attached |
| Performance analyzer | ✅ `validate` | test logs → decision | you execute | missed logging → timer math degrades visibly |
| Kill/scale recommender | ✅ 48h timer + scale check | logs+breakeven → verdict | you act (don't override kills) | optimism → hard timer |
| Daily reporter | ✅ `next` / dashboard | DB → actions | — | — |
| Weekly reporter | ✅ `weekly` | DB → report+packets | — | — |
| Policy risk flagger | ✅ gates + sweep + playbook | copy/products → flags | rewrite | regex misses nuance → treat as floor not ceiling |
| Saturation predictor | ✅ lifecycle + window | series → stage+runway | — | single-source → confidence caps trust |

Claude-in-the-loop (`ANTHROPIC_API_KEY`): psychology, hooks/scripts quality, the
dashboard Assistant — all grounded, all with deterministic fallbacks.

---

## 11. SOP library

Each SOP: trigger → steps → exit. Commands are literal.

**SOP-1 Product research (weekly, 90m):** §4 workflow → exit: 0–3 candidates with
scorecards ≥75.
**SOP-2 Validation (per candidate, 30m):** `scorecard` → `optimize` → `analyze` →
USPTO word-mark → FB Ads Library count (<15 advertisers) → AliExpress orders (<1k) →
exit: TEST verdict + all cross-checks pass, else drop with one-line reason in notes.
**SOP-3 Supplier sourcing (per TEST, 45m):** CJ quote + HyperSKU quote (US warehouse)
→ `add-supplier` both → ★ wins unless notes veto → exit: sample ordered.
**SOP-4 Sample (on arrival, 30m):** function test on camera (that footage = first
creative) · quality vs listing photos · weight/size vs quote → exit: pass = launch
prep; fail = requote or drop. Never skip: refund spirals start here.
**SOP-5 Creator outreach (parallel, 60m/wk):** §6 — 30–50 invites, 10 samples, 14-day
tracker → exit: ≥3 posting creators or re-target the invite list.
**SOP-6 Creative testing:** `creative-pack` → select 12 (§5 matrix) → shoot/generate
(`--confirm` if Higgsfield) → `export-creatives` (disclosure-gated) → exit: uploaded
wave.
**SOP-7 Ad launch (per product, 30m):** §7 structure · budget = test budget/14 days ·
pixel verified BEFORE spend (EMQ ≥6) → exit: live + day-1 `log-test` entry.
**SOP-8 Daily (10m, non-negotiable):** `log-test` per live product → `validate` → act
on KILL immediately → `next` → exit: zero unlogged live days.
**SOP-9 Scaling:** all §7 scale conditions → +20–30%, 2–3 day steps, re-`validate` ·
creator re-supply · supplier depth check (MOQ/lead time) · consider FBT → exit: new
plateau or kill.
**SOP-10 Refund handling (48h SLA):** approve fast (account health > $15) · tag reason
· complaint language feeds the corpus (`psych --file`) → exit: <2-day handling time,
reasons logged.
**SOP-11 Reporting:** weekly — actuals vs true break-even per product, creator
scorecard, `weekly` report · monthly — settlement reconciliation vs ledger,
`report-monthly`, `recalibrate` (dry), review gate near-misses → exit: numbers agree
or discrepancy explained.
**SOP-12 Monthly optimization:** kill the watchlist stragglers (>21 days WATCH with
flat momentum) · re-quote suppliers on winners · refresh creative on fatigue signals ·
playbook phase review → exit: pipeline has ≥3 fresh candidates.

**Decision tree — product go/no-go:**
```
Score ≥80? ─no→ ≥70 + early_trend + confidence high? ─no→ DROP
   │yes                                   │yes → WATCH (daily metrics, re-score)
Gates all clear? ─no→ DROP (never argue with a gate)
   │yes
Cross-checks pass (USPTO, <15 advertisers, <1k AliE orders)? ─no→ DROP
   │yes
TRUE-stack margin ≥45% at real quote? ─no→ requote once, else DROP
   │yes
Sample passes on camera? ─no→ DROP
   │yes → LAUNCH (SOP-6→7)
```

**Decision tree — live test:**
```
Daily log entered? ─no→ enter it (SOP-8) — timer math is broken without it
ROAS < TRUE break-even for 48h? ─yes→ KILL today. log-result. No overrides.
CTR <1% & not improving after $50+? ─yes→ KILL
Refunds >5%? ─yes→ KILL + corpus the complaints
All scale conditions? ─yes→ SCALE (SOP-9)
else → WATCH: iterate creative (new hooks, same winning demo), keep logging
```

---

## 12. Compliance & risk

**FTC:** every creator post with a free sample or commission = clear disclosure
(#ad / built-in toggle); *your* obligation contractually, not just theirs · no
fabricated reviews/testimonials (the generators refuse; don't defeat them) · claims
must be substantiated — the regex sweep catches cure/guarantee/100%/miracle/weight-loss
patterns; treat it as a floor.
**IP:** USPTO word-mark search before EVERY listing (SOP-2) · no character/brand
merch (branded gate) · design patents exist on "generic-looking" products —
**[INFERENCE]** reverse-image search the supplier photo; if one brand dominates
results, assume protected.
**Music:** commercial content = TikTok Commercial Music Library only; a licensed-sound
takedown can kill a winning Spark Ad — brief creators explicitly.
**AI content:** disclosure required for fully/substantially AI-generated content incl.
AI backgrounds on real products; ads have a dedicated checkbox; the engine's export
refuses undisclosed assets. **[EVIDENCE — TikTok policy, sourced in playbook]**
**Privacy:** Pixel/Events API → privacy policy must say so; no third-party retargeting
data uploads (2026 rule).
**Shipping/returns:** promise only the SLA your supplier hits (2d in-transit/6d
delivered dropship rule) · 30-day returns default · approve refunds <100 fast — a $15
refund is cheaper than an account-health hit.
**Chargebacks:** accurate photos (sample-verified), visible shipping cost, tracking
uploaded same-day, answer messages <24h — chargebacks mostly measure surprise.
**Platform:** the restricted-category gate + prohibited list (playbook `tt-restricted`)
· Account Health Rating is enforcement, SPS is reach — watch both (`health`).

---

## 13. Prioritized action plan

**Build first (already built → operate):** the engine is ahead of this plan — your
constraint is DATA and REPS, not code. Priority: (1) Kalodata/FastMoss subscription +
first real CSV import — everything downstream is dry until then. (2) Seller account +
playbook phase 0–1 completion. (3) First 3 SOP-2 validations on real data.

**Highest ROI per hour:** daily `log-test` + `validate` (10 min, protects every ad
dollar) > weekly research SOP-1 (90 min, fills the funnel) > creator open-collab
setup (evergreen free traffic) > creative iteration on winners > everything else.

**Easiest to automate next (Phase 3, code exists to extend):** cron `daily` +
dashboard alerts → Kalodata API adapter when subscribed → order-level settlement
import for LTV/cohorts.

**Must stay human:** kill/scale execution · creator relationships · sample judgment ·
anything that spends · policy gray areas.

**Biggest risks (ranked):** 1. skipping daily logs → timer blind → slow bleed ·
2. judging ads vs the 6%-only break-even instead of TRUE → profitable-looking losses ·
3. falling in love past a gate · 4. one-creative dependence → fatigue cliff ·
5. slow shipping → SPS throttle → everything gets harder · 6. scaling on TikTok's
attribution without settlement reconciliation.

**Beginner mistakes the system already blocks:** chasing peaked products (lifecycle),
commodity traps (gate), placeholder margins (refusal), fake urgency/testimonials
(generator + sweep), overriding kills (timer), unlabeled AI (export block).

---

## 14. Implementation roadmap

**Days 1–7:** playbook phases 0–2 (entity, accounts, capital plan) · data subscription
· first import · first `daily`.
**Days 8–21:** 3–5 SOP-2 validations · 2 samples ordered · creator open-collab live ·
first creative pack shot.
**Days 22–45:** first live test (SOP-7/8) · kill or scale by the tree · second product
overlapping · weekly SOPs running.
**Days 46–90:** 3+ tests concluded → `log-result` each → first `report-monthly` with
real attribution · winner → FBT + Spark Ads from creator posts · `recalibrate` dry-run
review.
**Success criteria at 90 days:** ≥6 real tests, ≥1 net-profitable product at TRUE
stack, zero unlogged live days, zero gate overrides. (That beats ~90% of starters —
[EVIDENCE: <10% survive year one].)

---

## 15. Open questions / assumptions

**Assumptions [labeled]:** US market · TikTok Shop native checkout (not external
Shopify LP — §8 applies to product-page + any external LP hybrid) · solo operator
· $2–5k starting capital (else redo `capital`) · payment rate 3% until your
settlement says otherwise · single data source until a second feed cross-confirms
(confidence caps at 90% deliberately).

**Open questions for you:** actual capital? hours/week? content: your face, faceless,
or creator-only (changes the organic-margin path on the $1M math)? category
shortlist (pet/hobby/accessories priors are loaded — where can YOU produce content
credibly)? Kalodata or FastMoss budget tier?

**Known limits [honest]:** no order-level LTV/cohorts until settlement import exists
(Phase 3) · Creator Availability isn't computable from feed data (manual Affiliate
Center check) · Expected CVR/CPA are testing outputs by design · the sample feed
demonstrates, only real data finds.
