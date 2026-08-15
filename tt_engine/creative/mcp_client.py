"""Higgsfield batch generation (Phase 2).

The flow when a product hits TEST verdict: creative brief (product + psychology paragraph
+ hooks) → batch generation across the five formats → poll for completion → save assets
to `creatives` with format tags and AIGC-disclosure metadata.

Three guardrails, none optional:
  1. Generation costs money → it never runs without an explicit confirm=True from the
     operator (CLI `creative <id> --confirm`). Without it you get the dry-run plan.
  2. Every asset carries the AIGC disclosure in its metadata; the export path refuses
     to export any creative missing it.
  3. One Soul ID persona per store — a mismatch against creatives already in the DB is
     surfaced before anything generates.

Two real integration paths exist for Higgsfield (verified July 2026 — see config.py for
the detail and sources; reverify before trusting, vendor APIs move fast):
  • This module targets the SCRIPTED path: the official `higgsfield-client` SDK against
    the Higgsfield Cloud API, gated on CONFIG.higgsfield_available (an API key + the SDK
    installed). Unset/not installed → dry-run: the batch is planned and persisted as
    'briefed' so the rest of the engine works end-to-end offline.
  • If you're running this from an interactive MCP client instead (e.g. this engine
    operated from inside a Claude Code session with the Higgsfield MCP connected), the
    simpler path is asking the agent to generate the batch directly through its own
    connected tools — that authenticates via browser OAuth and needs no key in .env at
    all. See CONFIG.higgsfield_mcp_url for that endpoint.

submit()/poll() below are the extension points: even with a key configured, they raise
NotImplementedError until wired to the SDK's actual call shape — the SDK's exact request/
response fields aren't published outside the SDK itself, and this project refuses to
guess at an integration it hasn't verified against a real account (the same rule as the
Kalodata/EchoTik feed stubs and Economics' no-placeholder-cost rule).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Optional

from ..config import CONFIG
from ..db import Database, models
from .brief import CreativeKit
from . import spend
from .compliance import DISCLOSURE
from .higgsfield import HiggsfieldClient


class ConfirmationRequired(RuntimeError):
    """Raised when generation is attempted without explicit operator confirmation."""


class PartialBatch(RuntimeError):
    """Submission failed midway: some jobs are already submitted and PAID FOR.
    Carries the instruction to recover them rather than letting the spend vanish."""


class GenerationNotWired(RuntimeError):
    """Raised when generation is confirmed and a key IS configured, but the
    higgsfield_client SDK integration point (submit/poll) isn't wired yet — so the
    engine can plan but not actually generate. A clean, catchable signal instead of a
    raw NotImplementedError crashing the caller (CLI / autopilot)."""


@dataclass
class GenerationResult:
    creatives: list[models.Creative]
    dry_run: bool
    soul_warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        mode = "DRY-RUN (no key/SDK configured — plan persisted as 'briefed')" if self.dry_run \
            else "generated via Higgsfield"
        by_status: dict[str, int] = {}
        for c in self.creatives:
            by_status[c.status] = by_status.get(c.status, 0) + 1
        counts = ", ".join(f"{n} {s}" for s, n in sorted(by_status.items()))
        lines = [f"{len(self.creatives)} creative(s) — {mode} — {counts}"]
        lines += [f"⚠️  {w}" for w in self.soul_warnings]
        lines += self.notes
        return "\n".join(lines)


def soul_consistency(db: Database, soul_id: Optional[str]) -> list[str]:
    """One persona per store: flag any existing creatives carrying a different Soul ID."""
    if not soul_id:
        return ["no Soul ID configured (HIGGSFIELD_SOUL_ID) — set ONE persona for the "
                "whole store and reuse it across every ad"]
    others = {c.soul_id for c in db.all_creatives() if c.soul_id and c.soul_id != soul_id}
    if others:
        return [f"Soul ID mismatch: store persona is '{soul_id}' but existing creatives "
                f"use {sorted(others)} — one persona per store; do not mix faces"]
    return []


def _asset_meta(c: models.Creative) -> dict:
    """Metadata every generated asset must carry — the AIGC disclosure is non-negotiable."""
    return {
        "aigc_disclosure": DISCLOSURE,
        "format_tag": c.format,
        "hook_type": c.hook_type,
        "soul_id": c.soul_id,
    }


class HiggsfieldMCP:
    """Gate + extension point for scripted Higgsfield generation via the official SDK.

    `available` mirrors CONFIG.higgsfield_available (key + SDK both present) by default.
    Test doubles/subclasses can override the property directly to force a path without
    needing a real key or the SDK installed — see FakeMCP in tests/test_creative_mcp.py.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key if api_key is not None else CONFIG.higgsfield_api_key

    @property
    def available(self) -> bool:
        return bool(self.api_key) and CONFIG.higgsfield_available

    def submit(self, kit: CreativeKit, c: models.Creative) -> str:
        """Submit one generation job; returns the job id.

        ── Integration point ───────────────────────────────────────────────────
        # import higgsfield_client
        # controller = higgsfield_client.submit(
        #     model="soul" if c.soul_id else "kling-3.0",   # verify current model names
        #     prompt=f"{c.hook} — {kit.psych.spine}",
        #     character_id=c.soul_id, aspect_ratio="9:16",
        # )
        # return controller.id
        The SDK's exact request/response shape isn't published outside the SDK — get a
        real Higgsfield account, read `higgsfield_client`'s own docstrings/examples, and
        wire this for real rather than guessing.
        """
        raise NotImplementedError(
            "HiggsfieldMCP.submit() — wire the higgsfield_client SDK call. The offline "
            "plan is used until then; see the integration-point comment on this method."
        )

    def poll(self, job_id: str) -> tuple[str, Optional[str]]:
        """Poll one job → (status, asset_url). Status: generating|ready|failed.

        ── Integration point ───────────────────────────────────────────────────
        # import higgsfield_client
        # result = higgsfield_client.status(job_id)
        # if result.status == "Completed":
        #     return "ready", result.result().output_url   # verify actual field names
        # if result.status in ("Failed", "NSFW", "Cancelled"):
        #     return "failed", None
        # return "generating", None
        """
        raise NotImplementedError(
            "HiggsfieldMCP.poll() — wire the higgsfield_client SDK call. See the "
            "integration-point comment on this method."
        )


def _drain(db, mcp, creatives, poll_interval: float, poll_timeout: float):
    """Poll a set of in-flight jobs to completion. Returns (notes, still_pending).

    A poll failure is never fatal here. The jobs are already paid for; crashing out
    of the loop would strand them with no record of what to collect. Transient errors
    are counted and retried on the next sweep; the deadline is the only exit."""
    notes: list[str] = []
    pending = {c.id: c for c in creatives if c.meta.get("job_id")}
    errors: dict[str, int] = {}
    deadline = time.time() + poll_timeout

    while pending and time.time() < deadline:
        for cid in list(pending):
            c = pending[cid]
            try:
                status, url = mcp.poll(c.meta["job_id"])
            except NotImplementedError:
                raise
            except Exception as e:                       # transient — keep the job alive
                errors[cid] = errors.get(cid, 0) + 1
                if errors[cid] == 1:
                    notes.append(f"{cid}: poll error ({type(e).__name__}) — retrying; "
                                 "the job is paid for and still tracked")
                continue
            if status in ("ready", "completed", "succeeded"):
                c.status, c.asset_url = "ready", url
                db.upsert_creative(c)
                del pending[cid]
            elif status in ("failed", "error"):
                c.status = "failed"
                db.upsert_creative(c)
                del pending[cid]
        if pending and time.time() < deadline:
            time.sleep(poll_interval)

    return notes, list(pending.values())


def recover_jobs(db: Database, mcp: Optional[HiggsfieldMCP] = None,
                 poll_interval: float = 5.0, poll_timeout: float = 300.0) -> str:
    """Collect assets for jobs that were submitted (and paid for) but never landed.

    Generation is charged at submit time, so a crash, a timeout, or a closed laptop
    between submit and poll means money spent for an asset the engine never saved.
    This finds every creative still marked 'generating' with a job id and re-polls it.
    Free — it spends nothing, it only collects what you already bought."""
    mcp = mcp or HiggsfieldMCP()
    orphans = [c for c in db.all_creatives()
               if c.status == "generating" and c.meta.get("job_id")]
    if not orphans:
        return "nothing to recover — no submitted jobs are unaccounted for."
    if not mcp.available:
        return (f"{len(orphans)} job(s) were submitted and paid for but never collected. "
                "Higgsfield isn't configured in this environment, so they can't be "
                "polled from here — set HIGGSFIELD_API_KEY and re-run `creative-recover` "
                "from the machine that has it. Do NOT re-generate; that pays twice.\n  "
                + "\n  ".join(f"{c.id} (job {c.meta['job_id']})" for c in orphans))

    notes, still = _drain(db, mcp, orphans, poll_interval, poll_timeout)
    got = len(orphans) - len(still)
    lines = [f"recovered {got} of {len(orphans)} paid-for job(s)."]
    lines += notes
    if still:
        lines.append(f"{len(still)} still generating — run `creative-recover` again "
                     "later; they stay tracked until they land.")
    return "\n".join(lines)


def generate_batch(
    db: Database,
    kit: CreativeKit,
    confirm: bool = False,
    mcp: Optional[HiggsfieldMCP] = None,
    poll_interval: float = 5.0,
    poll_timeout: float = 600.0,
) -> GenerationResult:
    """Plan the batch, then (with confirmation + a configured MCP) generate and poll.

    Never generates without confirm=True — generation spends money and every external
    action requires explicit operator confirmation.
    """
    mcp = mcp or HiggsfieldMCP()
    warnings = soul_consistency(db, kit.soul_id)

    planner = HiggsfieldClient()
    creatives = planner.plan(kit)
    # Persist the briefed plan FIRST — planning is free and never spends. This must
    # happen before the confirm gate so the build-creative step always advances the
    # pipeline (otherwise, with a key configured, the plan is never saved and the
    # loop re-proposes build-creative forever, never reaching generation).
    for c in creatives:
        c.meta = _asset_meta(c)
        db.upsert_creative(c)

    if mcp.available and not confirm:
        raise ConfirmationRequired(
            "Higgsfield MCP is configured but generation was not confirmed. Generation "
            "spends money — re-run with --confirm to actually generate the batch.\n"
            f"  SPEND IF CONFIRMED: {spend.estimate(len(creatives)).render()}"
        )

    notes: list[str] = []
    if kit.flagged:
        notes.append(f"{len(kit.flagged)} compliance flag(s) in the kit — rewrite before "
                     "exporting (see the brief).")

    if not mcp.available:
        notes.append("Set HIGGSFIELD_API_KEY (and install higgsfield-client) to generate "
                     "for real; the plan above is what would be submitted. Or, if you're "
                     "in a Claude Code session with the Higgsfield MCP connected, just "
                     "ask the agent to run this batch directly.")
        return GenerationResult(creatives=creatives, dry_run=True,
                                soul_warnings=warnings, notes=notes)

    # ── Spend preflight: size cap + dollar ceiling, before a single paid job ──
    est = spend.guard(len(creatives))
    notes.append(f"spend: {est.render()}")

    # ── Live path: submit every job, then poll to completion ──────────────────
    submitted: list[models.Creative] = []
    for c in creatives:
        try:
            job_id = mcp.submit(kit, c)
        except NotImplementedError as e:
            # A key is configured but the SDK call isn't wired. Fail cleanly and
            # LOUDLY — the plan is already persisted (briefed), so no work is lost.
            raise GenerationNotWired(
                "Higgsfield is configured but the higgsfield_client SDK integration "
                "point isn't wired yet, so the engine can't actually generate. The "
                f"batch is planned and saved as 'briefed'. Wire HiggsfieldMCP.submit/"
                f"poll (see the integration-point comments), or run the batch from a "
                f"Claude Code session with the Higgsfield MCP connected. ({e})"
            ) from e
        except Exception as e:
            # A paid job may already be in flight for everything in `submitted`.
            # STOP submitting (don't burn more), keep what's persisted recoverable,
            # and say plainly what was spent — silent partial batches are how money
            # disappears without a trace.
            raise PartialBatch(
                f"submit failed on {c.id} after {len(submitted)} job(s) were already "
                f"submitted and PAID FOR. Stopped before spending more. Those jobs are "
                f"saved with their job ids — run `creative-recover` to collect the "
                f"assets you already paid for. ({type(e).__name__}: {e})"
            ) from e
        c.status = "generating"
        c.meta["job_id"] = job_id
        db.upsert_creative(c)
        submitted.append(c)

    collected, still_pending = _drain(db, mcp, creatives, poll_interval, poll_timeout)
    notes.extend(collected)
    if still_pending:
        notes.append(
            f"{len(still_pending)} job(s) still generating after {poll_timeout:.0f}s. "
            "They are PAID FOR and saved with their job ids — run `creative-recover` "
            "to collect them; do not re-generate, that would pay twice.")

    return GenerationResult(creatives=creatives, dry_run=False,
                            soul_warnings=warnings, notes=notes)


@dataclass
class ExportResult:
    exported: list[models.Creative] = field(default_factory=list)
    blocked: list[models.Creative] = field(default_factory=list)
    not_ready: list[models.Creative] = field(default_factory=list)
    manifest_path: Optional[str] = None

    @property
    def summary(self) -> str:
        lines = [f"{len(self.exported)} creative(s) exported"
                 + (f" → {self.manifest_path}" if self.manifest_path else "")]
        if self.not_ready:
            lines.append(f"({len(self.not_ready)} not generated yet — status "
                         "briefed/generating — nothing to export; run `creative --confirm`)")
        for c in self.blocked:
            lines.append(f"⛔ BLOCKED {c.id}: missing AIGC disclosure in asset metadata — "
                         "regenerate through the pipeline; do not export undisclosed AI content")
        return "\n".join(lines)


def export_creatives(db: Database, product_id: str, out_path: str) -> ExportResult:
    """Write the export manifest. Two filters, in order: only generated assets
    (ready/exported) can be exported at all, and any creative without the AIGC
    disclosure in its metadata is refused and flagged — that is the guardrail."""
    from pathlib import Path

    result = ExportResult()
    for c in db.creatives_for(product_id):
        if c.status not in ("ready", "exported"):
            result.not_ready.append(c)
            continue
        if not c.meta.get("aigc_disclosure"):
            result.blocked.append(c)
            continue
        result.exported.append(c)

    if result.exported:
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        manifest = [{
            "id": c.id, "format": c.format, "hook": c.hook, "hook_type": c.hook_type,
            "soul_id": c.soul_id, "asset_url": c.asset_url, "status": "exported",
            "aigc_disclosure": c.meta["aigc_disclosure"],
        } for c in result.exported]
        out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        result.manifest_path = str(out)
        for c in result.exported:
            c.status = "exported"
            db.upsert_creative(c)
    return result
