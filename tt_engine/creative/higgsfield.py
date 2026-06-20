"""Higgsfield adapter (Part 7). The pipeline: Hermes Agent (Click-to-Ad) drafts the brief,
a pre-trained Soul ID persona keeps one recurring face, the AI Hook Generator seeds the
openings, then a batch of 20–100 variations is generated and exported to TikTok.

Offline (no API key) this plans the batch and returns models.Creative rows with
status='briefed' so the rest of the engine (DB, tests, validation) works end-to-end.
Wire push() to the real API to actually generate assets.
"""

from __future__ import annotations

import itertools
from typing import Optional

from ..config import CONFIG
from ..db import models
from .brief import CreativeKit


class HiggsfieldClient:
    def __init__(self, api_key: Optional[str] = None, soul_id: Optional[str] = None):
        self.api_key = api_key or CONFIG.higgsfield_api_key
        self.soul_id = soul_id or CONFIG.higgsfield_soul_id

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def plan(self, kit: CreativeKit) -> list[models.Creative]:
        """Plan the batch: pair hooks × formats up to kit.variations. No network — this is
        the deterministic plan the real generator would execute."""
        creatives: list[models.Creative] = []
        pairs = itertools.product(kit.formats, kit.hooks)
        for i, (fmt, hook) in enumerate(itertools.islice(pairs, kit.variations)):
            creatives.append(models.Creative(
                id=f"{kit.product.id}-C{i:03d}",
                product_id=kit.product.id,
                format=fmt,
                hook=hook.text,
                hook_type=hook.type,
                soul_id=kit.soul_id or self.soul_id,
                asset_url=None,
                status="briefed",
            ))
        return creatives

    def push(self, kit: CreativeKit) -> list[models.Creative]:
        """Generate the batch. Offline: returns the plan. Online: implement the API calls."""
        creatives = self.plan(kit)
        if not self.available:
            return creatives  # offline plan — status stays 'briefed'

        # ── Integration point ──────────────────────────────────────────────────
        # import requests
        # 1) Hermes Agent (Click-to-Ad): POST the brief / product URL → draft.
        # 2) AI Hook Generator: POST kit.hooks → data-driven openings.
        # 3) Batch generate across formats with the Soul ID persona.
        # 4) Export each asset to TikTok in 9:16, set creative.asset_url + status.
        # for c in creatives:
        #     resp = requests.post(
        #         "https://api.higgsfield.ai/v1/generate",
        #         headers={"Authorization": f"Bearer {self.api_key}"},
        #         json={"format": c.format, "hook": c.hook, "soul_id": c.soul_id,
        #               "product": kit.product.name, "spine": kit.psych.spine},
        #         timeout=120,
        #     )
        #     resp.raise_for_status()
        #     c.asset_url = resp.json()["asset_url"]
        #     c.status = "ready"
        raise NotImplementedError(
            "HiggsfieldClient.push() — wire the Hermes/Hook-Generator/batch/export calls. "
            "The offline plan() is used until then."
        )
