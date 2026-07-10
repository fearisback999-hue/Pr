# Operating manual — Phase 1 & Phase 2

Plain-language runbook for the one operator this engine is built for. Run everything
by hand before trusting any automation (the iron rule, Part 0).

Every command takes `--db path.db` (defaults to `TT_DB_PATH`). Start with
`python -m tt_engine.cli seed` if you just want to poke at sample data first.

**Brand new to this?** Run `python -m tt_engine.cli playbook` (or open `/playbook` in
the dashboard) first — it's the zero-to-hero checklist for the whole business, not just
the product-scoring part: entity/tax setup, TikTok Shop + Etsy platform accounts,
capital planning, sourcing, the engine's own loop, paid traffic, creator outreach,
scaling, and ongoing compliance, in order. Steps the engine can see (a supplier on
file, a TEST-verdict product, a live test logged) check themselves off automatically;
everything that happens outside the database (opening a bank account, verifying a
seller account) you check off yourself with `playbook-check <step_id>`. Legal/tax items
describe what to go figure out, not legal or tax advice — verify specifics with a
professional and the current platform terms, since both change.

Concrete numbers in the playbook (fees, thresholds, SLAs, return windows) come from live
web research done 2026-07-09 against primary sources where possible — TikTok Seller
Center's own policy essays, Etsy Help, IRS.gov, plus vendor pricing pages for suppliers/
POD/UGC platforms. Every fact-bearing step shows its source link, and the full list is
at the bottom of `playbook` output / the dashboard's Playbook page. These are snapshots:
re-verify anything money- or compliance-critical before relying on it, since platforms
change fee schedules and policy without much notice — this is exactly why the
Economics module refuses to score without a real, current landed-cost quote instead of
a remembered one.

---

## The dashboard — everything on one site

```bash
python -m tt_engine.cli serve                  # → http://127.0.0.1:8787
python -m tt_engine.cli serve --host 0.0.0.0   # reach it from other devices on your LAN
```

Six sections, all live from the DB:

- **Overview** — KPIs, the ranked board with KILL/WATCH/TEST chips, and *What to do
  next*: every product's single next action with the exact command, most urgent first
  (a KILL-timer breach shows 🔴 at the top). The same list is `cli next` in a terminal.
  Also shows where you are in the business playbook with a link through.
- **Playbook** — the zero-to-hero checklist (see above), with a progress bar per phase.
  Manual steps toggle with a click (safe — it only records that YOU did something off-
  engine; it can never spend money or place an order). Auto steps show a plain checkmark
  with no toggle, because faking them would just lie to you about the DB's real state.
- **Product page** — the full scorecard rendered (sub-scores, momentum/saturation
  inputs, economics math), the next step, creatives, and test telemetry.
- **Advertising** — Higgsfield/MCP configuration status (what's set, what's missing,
  what each key does), creative batches per product with AIGC-disclosure state, and
  live ad tests vs break-even with the 48h kill timer. The dashboard **never spends
  money** — generation stays a deliberate `creative <id> --confirm` in the terminal.
- **Budget** — the TikTok capital/cash-flow calculator (payout float, runway, tests
  you can afford) and the **Etsy POD listings planner** (how many listings, at what
  weekly pace, for your profit target — all assumptions editable in the form). Plus
  actual ad spend logged in the last 7 days.
- **Creators** — the UGC/affiliate marketplaces (TikTok Affiliate Center, Creator
  Marketplace, Insense, Billo, Collabstr, Twirl, Fiverr, Upwork) and which TEST-ready
  products to pitch, with the `packet` command that builds the outreach materials.

---

## Phase 1 — the manual loop (daily, ~20 minutes)

### 1. Get data in (pick any mix)

```bash
# Export a CSV by hand from Kalodata or FastMoss, then:
python -m tt_engine.cli import-csv exports/kalodata_2026-07-03.csv --source kalodata

# Column named something weird? Remap it once:
python -m tt_engine.cli import-csv f.csv --map "Sales Volume=units" --map "Shop #=sellers"

# Found something by hand? Add it, then log a metric row per day you observe it:
python -m tt_engine.cli add --name "Cloud Slippers" --category home --id P-CLOUD
python -m tt_engine.cli add-metric P-CLOUD --units 120 --price 24.99 --sellers 8 --ads 5
```

Momentum needs a time series — one row per product per day. Two weeks of rows makes
the 7d-vs-30d math meaningful; fewer and the score treats missing history conservatively.

### 2. Add the real landed cost (not optional)

```bash
python -m tt_engine.cli add-supplier P-CLOUD --cost 4.50 --ship-cost 1.00 --ship-days 6
```

**The engine refuses to score Economics without this.** No supplier quote on file =
Economics 0/20 + the margin gate fails as "unverifiable" = verdict KILL. That is
deliberate: a guessed margin gates real money. Get the quote, then score.

### 3. Score and read the verdict

```bash
python -m tt_engine.cli daily                      # detect + score everything
python -m tt_engine.cli scorecard P-CLOUD          # one product, all the work shown
python -m tt_engine.cli scorecard P-CLOUD --out reports/out/P-CLOUD.md
```

The scorecard shows every sub-score, the raw inputs behind each, gate results, and one
of three verdicts:

- **KILL** — failed a hard gate (margin < 45%, return-risk, trademark/IP, restricted
  category, or unverifiable landed cost). Total score is irrelevant; momentum never
  overrides a gate.
- **WATCH** — gates clear, total < 80. Keep logging metrics; re-score daily.
- **TEST** — gates clear, total ≥ 80. Worth a live ad test; the window estimate tells
  you how many days of runway you likely have.

### 4. Run the live test and log it daily

```bash
python -m tt_engine.cli log-test P-CLOUD --spend 40 --revenue 30      # once a day
python -m tt_engine.cli validate P-CLOUD                              # kill/scale call
```

`validate` applies the kill/scale rules **including the 48-hour timer**: spend-weighted
daily ROAS below break-even for 2 consecutive calendar days = KILL, even if the trend
is improving. Above target with a clear creative winner = SCALE candidate. Everything
else = keep watching. The math is printed with the decision.

### 5. Close the loop when the test concludes

```bash
python -m tt_engine.cli log-result P-CLOUD --decision kill --roas 0.8
```

This is what feeds Phase 2's recalibration. Log every conclusion, including the losers —
*especially* the losers.

---

## Phase 2 — psychology, creative, feedback

### Psychology pass (feeds the creative brief)

Paste the product's top comments/reviews into a text file, one per line:

```bash
python -m tt_engine.cli psych P-CLOUD --file comments.txt
```

Output: emotional trigger, pain point, desire, identity appeal, impulse factor, and the
one-paragraph spine. With `ANTHROPIC_API_KEY` set it's an LLM pass; without, a
deterministic keyword fallback (it says which one it used). The comments are stored on
the product, so the creative brief automatically uses them.

### Creative pipeline (Higgsfield)

```bash
python -m tt_engine.cli creative P-CLOUD                       # dry-run plan (free)
python -m tt_engine.cli creative P-CLOUD --confirm             # actually generate ($)
python -m tt_engine.cli creative P-CLOUD --brief reports/out/brief.md
python -m tt_engine.cli export-creatives P-CLOUD --out reports/out/creatives.json
```

Two real ways to make `--confirm` actually generate (verified July 2026 — reverify,
vendor APIs move fast):

1. **Scripted** — set `HIGGSFIELD_API_KEY` in `.env`, also set `HF_KEY` to the same value
   (the official `higgsfield-client` SDK reads that exact name itself), and
   `pip install higgsfield-client`. Wire the exact SDK call in
   `HiggsfieldMCP.submit()`/`.poll()` — the request/response shape isn't published
   outside the SDK, so this engine won't guess at it; the integration-point comments on
   those two methods show what's confirmed vs. what you verify against your own account.
2. **Interactive** — if you're operating this engine from inside a Claude Code session
   with the Higgsfield MCP connected (hosted at `https://mcp.higgsfield.ai/mcp`, browser
   OAuth, **not** an API key — confirmed tools include `generate_video`,
   `create_character` for Soul ID, `get_status`/`subscribe` to poll), just ask the agent
   to generate the batch directly from the brief. No `.env` entry needed for this path.

Without either configured, `creative` always dry-runs: plans the batch across the five
formats (UGC-Reaction, HyperMotion-Reveal, ASMR, POV-BeforeAfter, Unboxing) and persists
them as `briefed`.

Rules wired in, none optional:

- **Gated on TEST verdict.** A WATCH or KILL product is refused (`--force` overrides,
  loudly). Finding ≠ producing; don't spend creative budget on an unproven product.
- **`--confirm` required to spend money**, on either path above.
- **AIGC disclosure travels in asset metadata.** `export-creatives` refuses to export
  any creative missing it and tells you which ones. (TikTok's own disclosure rule, per
  its Seller Center policy: label content that's fully AI-generated or significantly
  AI-altered — including an AI-generated background behind a real product; minor edits
  like color grading don't require it.)
- **One Soul ID persona per store** (`HIGGSFIELD_SOUL_ID`). A mismatch against
  creatives already in the DB is flagged before anything generates.

### Feedback loop (monthly, ~10 minutes)

```bash
python -m tt_engine.cli report-monthly --month 2026-07 --out reports/out/2026-07.md
```

For every concluded test, the report shows which sub-scores called the outcome and
which were wrong (✓/✗ per category), per-category hit-rates, and the suggested weight
adjustments from the correlation fit. **Suggestions only** — nothing is applied until
you run `recalibrate --apply` yourself.

---

## Accuracy: what the scorer now checks that it didn't before

- **One viral day is not a trend.** A single 7-day-window day above 3× the window
  median is capped before velocity/WoW are computed (`[spike capped]` shows in the
  momentum summary). A genuine multi-day ramp passes through untouched.
- **Steady beats spiky.** `trend_consistency` (0–1, last 14 days vs their own trend
  line) is a scored component of Market Demand — steady growth predicts a real wave,
  a spiky average predicts a one-video flash.
- **Complaints predict refunds.** The review corpus is scanned for complaint language
  ("broke", "refund", "flimsy", "doesn't work"…); a complaint-dense corpus adds up to
  +8pts of expected return rate — enough to trip the 10% return-risk hard gate.
- **Impulse price band.** $15–50 scores full marks in Economics; below ~$10 you can't
  buy the customer profitably, above ~$70 the scroll-buy reflex dies.
- **Niche over commodity — the big one.** Generic me-too products (pimple patches,
  tumblers, phone stands) are traps: competition floods in the moment they work and
  there's no defensible edge. Two mechanisms reject them: (1) a **commodity-saturation
  hard gate** — a crowded category (saturation index ≥ 65, the common research rule of
  thumb) is disqualified regardless of momentum or margins, so a flooded product with
  *great* economics still gets KILLED; and (2) a **differentiation** sub-score in
  Competition Timing that pulls generic commodities below the 80 bar even while their
  current competition is still low, computed from the category's inherent commodity-ness,
  price position (a $6 race-to-the-bottom price is a tell), and commoditization language
  in the reviews ("everyone sells this", "prices all over"). The winners that surface
  instead are defensible niche demand — a hobby tool, a problem-specific pet product, an
  aesthetic accessory — where the window is actually yours to own.

---

## What was deliberately NOT built, and why

- **Scrapers.** CSV import + official APIs only. Scraping platforms that prohibit it
  risks the account and the data quality; you export by hand for now.
- **Automatic spending, ordering, publishing, outreach.** Every external action needs
  your explicit confirmation (`--confirm`, `--apply`). The engine plans; you act.
- **Auto-generation on TEST verdict.** The `creative` command must be run by you — a
  score crossing 80 does not silently trigger spend.
- **Cron / scheduled refresh (Phase 3).** Until you've run the daily loop by hand for
  weeks, automating it just scales mistakes. The stages are already separately callable,
  so wiring a cron later is trivial — see `scripts/`.
- **Auto-discovery feed and affiliate tracker (Phase 3).** Extension points exist
  (`feeds/` adapters, `distribution/`), intentionally unwired.
- **Auto-applied weight recalibration.** The monthly report suggests; you approve.
  A feedback loop you don't supervise will happily tune itself to noise.
