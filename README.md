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

```bash
# 1. Seed a realistic sample dataset (no API keys needed — uses the mock feed)
python -m tt_engine.cli seed

# 2. Run the daily detection + scoring pass
python -m tt_engine.cli daily

# 3. Generate the weekly opportunity report with attack packets
python -m tt_engine.cli weekly --out reports/out

# Inspect the ranked board
python -m tt_engine.cli board

# Export the Appendix-A scoring spreadsheet (CSV)
python -m tt_engine.cli export --out reports/out/board.csv

# Part 11 — capital & cash-flow tracking (payout float, runway, # of tests you can afford)
python -m tt_engine.cli capital --capital 5000 --test-budget 300 --daily-ad 50 --daily-cogs 30

# Part 10 — account-health / Shop Performance proxy (a low score throttles reach)
python -m tt_engine.cli health --ship-days 4 --refund-rate 0.03
```

Everything above runs **offline** with deterministic logic. Wire in real data and the
Claude API by filling `.env` (see `.env.example`) and implementing the feed adapters'
`fetch()` methods.

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
tests/               # 73 tests across every part + end-to-end smoke
docs/THESIS.md       # Part 0 — the operating thesis (read first)
```

## Realistic expectations (Appendix D — reread when excited)

This engine improves your odds and saves time. It does **not** guarantee profit, and
most products you test will lose money. That is structural, not a bug: test many, most
fail, a few winners pay for the failures. The near-certain payoff is the skill and the
system. The profitable brand is the upside — won on execution, fulfillment, creative,
and capital far more than on which product you picked.
