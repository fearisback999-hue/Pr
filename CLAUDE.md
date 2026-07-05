# CLAUDE.md

Guidance for Claude Code (and any AI assistant) working in this repository.

## What this is

A detection-first product research and launch engine for TikTok Shop
(`tt-shop-intelligence` / `tt_engine`). It ingests product velocity data, detects
sales acceleration ("momentum") before saturation sets in, scores candidates on a
100-point weighted rubric with hard disqualifying gates, and — for products that
clear the bar — assembles a full "attack packet" (economics, psychology, supplier
scoring, creative kit, distribution plan).

**Read `docs/THESIS.md` (Part 0) before making design decisions.** It states five
"honest" operating truths (data is rented, no system predicts winners, the product
is only ~30% of the outcome, etc.) and every major architectural choice traces back
to one of them. `docs/OPERATING.md` is the day-to-day runbook (Phase 1 manual loop,
Phase 2 psychology/creative/feedback) — read it to understand *why* a CLI command
behaves the way it does before changing that behavior.

Runtime is **stdlib-only**. `anthropic` (LLM) and `requests` (live feeds) are
optional extras — every module has a deterministic offline fallback so the engine
always runs with zero API keys (see "Offline-first" convention below).

## Architecture — the pipeline

```
data feeds → detection → scoring → enrichment → output
Kalodata/EchoTik/CSV   momentum      100-pt      economics    opportunity report
(+ mock feed)          saturation    6 subscores psychology   + attack packets
                       trigger       hard gates  sourcing
                       window est.               creative kit
```

A product surfaces only if it scores **≥ `TT_SCORE_THRESHOLD` (default 80) AND
clears every hard gate**. Gates never yield to a high score — see `scoring/gates.py`.

### Module map (`tt_engine/`)

| Module | Responsibility | Brief part |
|---|---|---|
| `config.py` | `CONFIG` singleton: env vars + `.env`, all tunables | — |
| `db/` | SQLite schema (`schema.sql`) + `models.py` dataclasses + `database.py` wrapper | 12 |
| `feeds/` | Data-feed adapters: `mock_feed`, `csv_import`, `kalodata`/`echotik` (stubs) | 2 |
| `detection/` | Momentum, saturation, trigger, window estimate, cross-confirm | 2 |
| `scoring/` | 100-pt algorithm (`algorithm.py`), 6 subscores, hard gates (`gates.py`) | 3 |
| `psychology/` | LLM pass over reviews/comments → emotional trigger, spine | 4 |
| `economics/` | Landed cost, margin, break-even ROAS, max CAC, offer math | 5 |
| `sourcing/` | Supplier scoring/ranking | 6 |
| `creative/` | Hooks, scripts, brief, compliance, Higgsfield (MCP client) | 7 |
| `distribution/` | Affiliate / creator outreach funnel | 8 |
| `validation/` | 30-day plan, kill/scale decision logic (incl. 48h timer) | 9 |
| `account/` | Shop Performance Score proxy + throttle warnings | 10 |
| `capital/` | Payout float, runway, affordable-test math | 11 |
| `feedback/` | Outcome ingestion + weight recalibration (suggest-only) | 13 |
| `reports/` | Opportunity report, attack packets, Appendix-A CSV export | — |
| `llm/` | `LLMClient` — thin Anthropic SDK wrapper with offline fallback | — |
| `pipeline.py` | Orchestrates all stages: `ingest → score → daily/weekly → find_winners → build_attack_packet → produce_creatives` | — |
| `cli.py` | All CLI subcommands (`seed`, `daily`, `find`, `scorecard`, `validate`, `creative`, `recalibrate`, ...) | — |

`scripts/` holds cron wrappers (`daily_cron.py`, `weekly_cron.py`) — Phase 3,
intentionally not wired into anything automatic yet. `tests/` mirrors the module
layout, one file per part plus `test_smoke.py` (end-to-end) and
`test_cli_workflow.py`.

## Development workflow

```bash
pip install -e ".[dev,llm,feeds]"     # editable install with test/optional deps

python -m pytest -q                    # run the full suite (109 tests, all offline)
python -m pytest tests/test_scoring.py -q   # single file

ruff check .                           # lint (line-length 110, see pyproject.toml)
ruff check --fix .                     # autofix import order etc.

python -m tt_engine.cli seed           # sample data, no keys needed
python -m tt_engine.cli find --top 5   # exercise the full pipeline end-to-end
```

There is no CI config in this repo (no `.github/workflows`) — running
`pytest` and `ruff check .` locally before considering work done is the
substitute for a build gate.

Everything runs offline and deterministically by default (mock feed +
deterministic LLM/economics fallbacks). Nothing needs `ANTHROPIC_API_KEY` or any
feed key to develop or test.

## Conventions to follow

- **Offline-first, fail loud when wiring live integrations.** Every external
  integration (feeds, LLM, Higgsfield) has a working offline path. Stub adapters
  (`feeds/kalodata.py`, `feeds/echotik.py`) raise `NotImplementedError`/`RuntimeError`
  with an actionable message rather than silently returning fake data — don't make
  a stub adapter fail silently or return made-up numbers.
- **Hard gates are absolute.** `scoring/gates.py` disqualifies regardless of total
  score (margin floor, return-risk, branded/trademark, restricted category, no
  verifiable landed cost). Never add a code path where a high score bypasses a
  gate — that defeats the point of the brief (Part 3).
- **Never guess a landed cost.** If no supplier is on file, economics comes back
  `landed_known=False`, the Economics sub-score is withheld (0), and the margin
  gate fails as "unverifiable." Don't add a default/placeholder cost anywhere —
  this is deliberate (see `pipeline.economics_for` and `docs/OPERATING.md` §2).
- **Money-spending / external-action commands require explicit confirmation.**
  `creative` only generates (spends) with `--confirm`; `recalibrate` only persists
  weights with `--apply`. Dry-run/plan is always the default. Follow this pattern
  for any new command that spends money, calls a paid API, or mutates external
  state.
- **Dataclasses, not ORMs.** `db/models.py` are thin dataclasses mirroring the
  SQL schema; `db/database.py` is a stdlib `sqlite3` wrapper with explicit
  upsert/query methods. Don't introduce an ORM or ad hoc dict-based records.
- **`from __future__ import annotations`** at the top of every module, `Optional[X]`
  style typing (not `X | None`) throughout, targeting Python 3.10+.
- **Comment sparingly, and tie comments to the brief.** Existing comments explain
  *why* (often citing a Part number from `docs/THESIS.md`), not *what*. Match that
  style rather than narrating obvious code.
- **Config only through `CONFIG`.** `tt_engine/config.py`'s `Config` dataclass +
  `CONFIG` singleton is the single source of truth for env-derived settings
  (`TT_*`, API keys). Don't read `os.environ` directly elsewhere.
- **Ruff**: line-length 110 (deliberate, for data-heavy dataclasses/f-strings),
  rules `E, F, W, I`, `E741` ignored (short names like `s`, `m` are fine in this
  numeric/score-heavy code).
- **Tests are offline and use `tmp_path` for a throwaway SQLite DB** (see
  `tests/test_smoke.py`). New tests should follow the same pattern — no network
  calls, no shared state between tests.

## Deliberately not built (don't add prematurely)

Per `docs/OPERATING.md`, these are intentional gaps, not oversights — check with
the user/issue before implementing them wholesale:

- Scrapers (CSV import + official APIs only — scraping violates platform ToS).
- Any automatic spending, ordering, publishing, or outreach (everything needs
  `--confirm`/`--apply`).
- Auto-generation of creative purely on hitting TEST verdict (a human runs
  `creative` explicitly).
- Cron/scheduled auto-refresh wired into the pipeline (stages are separately
  callable; wiring cron is meant to come later, see `scripts/`).
- Auto-applied weight recalibration (the monthly report only suggests changes).

## Where to look for examples

- Adding a CLI command → `cli.py` (`cmd_*` functions + `argparse` subparsers at
  the bottom of the file).
- Adding a data feed → `feeds/base.py` (`DataFeed`/`FeedRecord` contract) plus
  `feeds/kalodata.py` as the documented stub template.
- Adding a sub-score → `scoring/subscores.py` + register in `scoring/algorithm.py`'s
  `SUBSCORES`/`DEFAULT_WEIGHTS`.
- LLM-backed feature → `llm/client.py`'s `LLMClient` (`complete_text` /
  `complete_json`), always with a deterministic fallback when `not llm.available`.
