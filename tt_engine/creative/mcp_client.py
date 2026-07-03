"""Higgsfield batch generation via MCP (Phase 2).

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

The MCP server is configured with HIGGSFIELD_MCP_URL (a streamable-HTTP MCP endpoint).
Unset → dry-run mode: the batch is planned and persisted as 'briefed' so the rest of the
engine works end-to-end offline.
"""

from __future__ import annotations

import json
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Optional

from ..config import CONFIG
from ..db import Database, models
from .brief import CreativeKit
from .compliance import DISCLOSURE
from .higgsfield import HiggsfieldClient


class ConfirmationRequired(RuntimeError):
    """Raised when generation is attempted without explicit operator confirmation."""


@dataclass
class GenerationResult:
    creatives: list[models.Creative]
    dry_run: bool
    soul_warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        mode = "DRY-RUN (no MCP configured — plan persisted as 'briefed')" if self.dry_run \
            else "generated via Higgsfield MCP"
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
    """Minimal MCP client over streamable HTTP (JSON-RPC 2.0, stdlib only)."""

    def __init__(self, url: Optional[str] = None, tool: Optional[str] = None):
        self.url = url if url is not None else CONFIG.higgsfield_mcp_url
        self.tool = tool or CONFIG.higgsfield_mcp_tool

    @property
    def available(self) -> bool:
        return bool(self.url)

    def _rpc(self, method: str, params: dict, timeout: float = 120.0) -> dict:
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                           "params": params}).encode()
        req = urllib.request.Request(
            self.url, data=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode())
        if "error" in payload:
            raise RuntimeError(f"MCP error from {method}: {payload['error']}")
        return payload.get("result", {})

    def submit(self, kit: CreativeKit, c: models.Creative) -> str:
        """Submit one generation job; returns the job id."""
        result = self._rpc("tools/call", {
            "name": self.tool,
            "arguments": {
                "format": c.format, "hook": c.hook, "soul_id": c.soul_id,
                "product": kit.product.name, "spine": kit.psych.spine,
                "aspect_ratio": "9:16", "disclosure": DISCLOSURE,
            },
        })
        return _extract(result, "job_id") or _extract(result, "id") or c.id

    def poll(self, job_id: str) -> tuple[str, Optional[str]]:
        """Poll one job → (status, asset_url). Status: generating|ready|failed."""
        result = self._rpc("tools/call", {
            "name": f"{self.tool}_status", "arguments": {"job_id": job_id},
        })
        status = _extract(result, "status") or "generating"
        return status, _extract(result, "asset_url") or _extract(result, "url")


def _extract(result: dict, key: str) -> Optional[str]:
    """Pull a key out of an MCP tool result (top level, or JSON in content[0].text)."""
    if key in result:
        return result[key]
    for item in result.get("content", []):
        if item.get("type") == "text":
            try:
                data = json.loads(item["text"])
                if key in data:
                    return data[key]
            except (ValueError, TypeError):
                continue
    return None


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
    for c in creatives:
        c.meta = _asset_meta(c)

    if mcp.available and not confirm:
        raise ConfirmationRequired(
            "Higgsfield MCP is configured but generation was not confirmed. Generation "
            "spends money — re-run with --confirm to actually generate the batch."
        )

    notes: list[str] = []
    if kit.flagged:
        notes.append(f"{len(kit.flagged)} compliance flag(s) in the kit — rewrite before "
                     "exporting (see the brief).")

    if not mcp.available:
        for c in creatives:
            db.upsert_creative(c)
        notes.append("Set HIGGSFIELD_MCP_URL to generate for real; the plan above is "
                     "what would be submitted.")
        return GenerationResult(creatives=creatives, dry_run=True,
                                soul_warnings=warnings, notes=notes)

    # ── Live path: submit every job, then poll to completion ──────────────────
    for c in creatives:
        job_id = mcp.submit(kit, c)
        c.status = "generating"
        c.meta["job_id"] = job_id
        db.upsert_creative(c)

    deadline = time.time() + poll_timeout
    pending = {c.id: c for c in creatives}
    while pending and time.time() < deadline:
        for cid in list(pending):
            c = pending[cid]
            status, url = mcp.poll(c.meta["job_id"])
            if status in ("ready", "completed", "succeeded"):
                c.status, c.asset_url = "ready", url
                db.upsert_creative(c)
                del pending[cid]
            elif status in ("failed", "error"):
                c.status = "failed"
                db.upsert_creative(c)
                del pending[cid]
        if pending:
            time.sleep(poll_interval)
    for c in pending.values():
        notes.append(f"{c.id}: still generating after {poll_timeout:.0f}s — re-poll later")

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
        out.write_text(json.dumps(manifest, indent=2))
        result.manifest_path = str(out)
        for c in result.exported:
            c.status = "exported"
            db.upsert_creative(c)
    return result
