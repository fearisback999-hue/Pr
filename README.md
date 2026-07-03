# TikTok Shop Product Intelligence Engine

A detection-first operating system for finding, validating, launching, and scaling
ecommerce products on TikTok Shop. Built to the **Master Build Brief** — read
[`docs/THESIS.md`](docs/THESIS.md) (Part 0) before changing anything; it shapes every
design decision here.

> **The honest framing:** No system predicts winners. This one *shifts odds and
> compresses time* — it detects steep sales acceleration while competition is still
> low, scores the opportunity, and assembles the attack packet so you can move before
> the window closes. The data feeds are rented (anyone can buy them). The durable edge
> is **detection speed, creative throughput, fast fulfillment, and a scoring model
> tuned to your own results** (Part 13).

---

## What it does (the pipeline)

```
   data feeds            detection            scoring            enrichment           output
 ┌────────────┐      ┌──────────────┐    ┌─────────────┐    ┌──────────────┐    ┌──────────────┐
 │ Kalodata   │      │ momentum     │    │ 100-pt algo │    │ economics    │    │ opportunity  │
 │ EchoTik    │ ───▶ │ saturation   │──▶ │ 6 subscores │──▶ │ psychology   │──▶ │ report +     │
 │ (+ mock)   │      │ trigger      │    │ hard gates  │    │ sourcing     │    │ attack       │
 └────────────┘      │ window est.  │    └─────────────┘    │ creative kit │    │ packets      │
                     └──────────────┘                       └──────────────┘    └──────────────┘
```

A product surfaces only if it scores **≥ 80/100 AND clears every hard gate**
(margin floor, return-risk, no trademark, allowed category). For each survivor the
engine emits a **window estimate** ("good product, ~18 days of runway") and, when
configured, auto-builds the Higgsfield creative kit.

## Quick start

> Operating the engine day-to-day? Read **[`docs/OPERATING.md`](docs/OPERATING.md)** —
> the plain-language Phase 1/Phase 2 runbook.

```bash
# 1. Seed a realistic sample dataset (no API keys needed — uses the mock feed)
python -m tt_engine.cli seed

# — or bring real data in by hand (Phase 1: no scrapers, CSV + manual entry only) —
python -m tt_engine.cli import-csv exports/kalodata.csv --source kalodata
python -m tt_engine.cli add --name "Cloud Slippers" --category home --id P-CLOUD
python -m tt_engine.cli add-metric P-CLOUD --units 120 --price 24.99
python -m tt_engine.cli add-supplier P-CLOUD --cost 4.50 --ship-cost 1.00  # REQUIRED to score economics

# 2. ⭐ Find the best winning products to move on now — ranked, with the "why"
python -m tt_engine.cli find --top 5

# (or) run the daily detection + scoring pass, then read one product's full scorecard
python -m tt_engine.cli daily
python -m tt_engine.cli scorecard P-CLOUD          # every sub-score + verdict KILL/WATCH/TEST

# 3. Run a live test: log spend/revenue daily; the 48h below-break-even timer flags KILL
python -m tt_engine.cli log-test P-CLOUD --spend 40 --revenue 30
python -m tt_engine.cli validate P-CLOUD
python -m tt_engine.cli log-result P-CLOUD --decision kill   # concluded → feeds Part 13

# Phase 2 — psychology, creative (Higgsfield MCP), feedback
python -m tt_engine.cli psych P-CLOUD --file comments.txt
python -m tt_engine.cli creative P-CLOUD                     # dry-run plan; --confirm to spend
python -m tt_engine.cli export-creatives P-CLOUD             # blocks assets missing AIGC disclosure
python -m tt_engine.cli report-monthly --month 2026-07       # recalibration suggestions only

# Reports & ops
python -m tt_engine.cli weekly --out reports/out
python -m tt_engine.cli board
python -m tt_engine.cli export --out reports/out/board.csv
python -m tt_engine.cli capital --capital 5000 --test-budget 300 --daily-ad 50 --daily-cogs 30
python -m tt_engine.cli health --ship-days 4 --refund-rate 0.03
```

Everything above runs **offline** with deterministic logic. Wire in real data and the
Claude API by filling `.env` (see `.env.example`) and implementing the feed adapters'
`fetch()` methods.

## Finding *real* winners (the honest part)

`find` ranks the best attack-ready products from whatever feed it's given. Out of the box
that's the **sample feed** — so the results are illustrative, not real market finds (the
command says so in its banner). The engine doesn't conjure winners; it detects
acceleration in real velocity data. To find actual TikTok Shop winners:

1. Get a velocity source — **Kalodata** (Enterprise API) and/or **EchoTik** (cheaper,
   Growth-Velocity alerts). The data is *rented*: it's not your moat, your detection speed
   and feedback loop are (Part 0). **No API budget?** Export CSVs by hand from the vendor
   UI and `import-csv` them — same detection, scoring, and gates, zero integration work.
2. Put the key in `.env` and set `TT_PRIMARY_FEED=kalodata` (or `echotik`).
3. Implement the adapter's `fetch()` — `tt_engine/feeds/kalodata.py` has a commented
   template; map the vendor's daily series onto `units / gmv / price / sellers /
   promo_videos / ads / avg_ad_age`. That's the only glue needed; detection, scoring,
   gates, and `find` work unchanged.
4. Stack a **second** source and cross-confirm (`detection.cross_confirm`) before trusting
   a trigger — one rented feed can lag or be wrong.

What the engine guarantees is *discipline*, not magic: it only surfaces products with real
acceleration, low-but-rising saturation, runway left on the clock, healthy margins after
the 6% fee, and no compliance/return landmines — then ranks them by how good the bet is.
Most products you test will still lose money; that's structural (Appendix D).

## Build order (Part 14 — do not build it all at once)

| Phase | Status | What |
|---|---|---|
| **1 — Detection core** | ✅ built | one velocity source, momentum + saturation detector, ranked list with window estimates |
| **2 — Enrichment** | ✅ built | supplier-API economics, return-risk + psychology LLM passes |
| **3 — Creative** | ✅ built | Higgsfield brief / hooks / scripts / compliance pipeline (adapter stubbed) |
| **4 — Creator outreach** | ✅ built | affiliate funnel + outreach logistics (relationship stays human) |
| **5 — Feedback loop** | ✅ built | pipe your own results back in, recalibrate the Part-3 weights |

> ⚠️ **The builder's trap (Part 12):** building the engine *feels* like progress while
> it quietly lets you avoid the part that teaches you the business — talking to
> customers, eating losing tests, doing outreach. Run the store. The engine is the
> asset; the profitable brand is the low-probability upside on top.

## Layout

```
tt_engine/
  config.py          # env + tunables
  db/                # SQLite schema + models (Part 12 tables)
  feeds/             # data-feed adapters (mock + Kalodata/EchoTik stubs)   — Part 2
  detection/         # momentum, saturation, trigger, window, cross-confirm — Part 2
  scoring/           # 100-pt algorithm, 6 subscores, hard gates            — Part 3
  psychology/        # LLM pass over reviews/comments                       — Part 4
  economics/         # landed cost, margin, break-even ROAS, max CAC, offer — Part 5
  sourcing/          # supplier scoring                                     — Part 6
  creative/          # hooks, scripts, brief, compliance, Higgsfield        — Part 7
  distribution/      # affiliate / creator outreach funnel                  — Part 8
  validation/        # 30-day framework, kill/scale thresholds              — Part 9
  account/           # Shop Performance Score proxy + throttle warnings     — Part 10
  capital/           # payout float, runway, # of tests you can afford      — Part 11
  feedback/          # outcome ingestion + weight recalibration             — Part 13
  reports/           # opportunity report, attack packets, Appendix-A CSV
  llm/               # Claude API client (offline fallback)
  pipeline.py        # orchestration
  cli.py             # seed/daily/weekly/board/score/packet/validate/
                     #   recalibrate/plan/export/capital/health
scripts/             # cron wrappers
tests/               # 109 tests across every part + end-to-end smoke + CLI workflow
docs/THESIS.md       # Part 0 — the operating thesis (read first)
docs/OPERATING.md    # the Phase 1/2 runbook — how to actually run this daily
```

## Realistic expectations (Appendix D — reread when excited)

This engine improves your odds and saves time. It does **not** guarantee profit, and
most products you test will lose money. That is structural, not a bug: test many, most
fail, a few winners pay for the failures. The near-certain payoff is the skill and the
system. The profitable brand is the upside — won on execution, fulfillment, creative,
and capital far more than on which product you picked.
