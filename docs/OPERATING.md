# Operating manual — Phase 1 & Phase 2

Plain-language runbook for the one operator this engine is built for. Run everything
by hand before trusting any automation (the iron rule, Part 0).

Every command takes `--db path.db` (defaults to `TT_DB_PATH`). Start with
`python -m tt_engine.cli seed` if you just want to poke at sample data first.

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

### Creative pipeline (Higgsfield via MCP)

```bash
python -m tt_engine.cli creative P-CLOUD                       # dry-run plan (free)
python -m tt_engine.cli creative P-CLOUD --confirm             # actually generate ($)
python -m tt_engine.cli creative P-CLOUD --brief reports/out/brief.md
python -m tt_engine.cli export-creatives P-CLOUD --out reports/out/creatives.json
```

Rules wired in, none optional:

- **Gated on TEST verdict.** A WATCH or KILL product is refused (`--force` overrides,
  loudly). Finding ≠ producing; don't spend creative budget on an unproven product.
- **`--confirm` required to spend money.** With `HIGGSFIELD_MCP_URL` set but no
  `--confirm`, the command refuses. Without the URL it dry-runs: plans the batch across
  the five formats (UGC-Reaction, HyperMotion-Reveal, ASMR, POV-BeforeAfter, Unboxing)
  and persists them as `briefed`.
- **AIGC disclosure travels in asset metadata.** `export-creatives` refuses to export
  any creative missing it and tells you which ones.
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
