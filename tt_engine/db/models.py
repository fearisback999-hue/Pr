"""Typed records mirroring the schema. Thin dataclasses — they carry data between
the pipeline stages and in/out of the database."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as _date
from typing import Optional


@dataclass
class Product:
    id: str
    name: str
    category: str
    supplier_ref: Optional[str] = None
    first_seen: str = field(default_factory=lambda: _date.today().isoformat())
    branded: bool = False
    restricted: bool = False
    reviews: list[str] = field(default_factory=list)  # corpus for psychology + return-risk


@dataclass
class DailyMetric:
    product_id: str
    date: str
    units: int
    gmv: float
    price: float
    sellers: int
    promo_videos: int
    ads: int
    avg_ad_age: float


@dataclass
class Score:
    product_id: str
    date: str
    viral_demo: float
    market_demand: float
    competition_timing: float
    economics: float
    content_potential: float
    brand_potential: float
    total: float
    gates_passed: bool
    gate_failures: list[str] = field(default_factory=list)
    window_days: Optional[float] = None


@dataclass
class Supplier:
    ref: str
    product_id: Optional[str] = None
    name: str = ""
    cost: float = 0.0
    ship_cost: float = 0.0
    ship_days: float = 0.0
    moq: int = 1
    us_warehouse: bool = False
    rating: Optional[float] = None
    response_hrs: Optional[float] = None
    quality_notes: str = ""


@dataclass
class Creative:
    id: str
    product_id: str
    format: str
    hook: str
    hook_type: Optional[str] = None
    soul_id: Optional[str] = None
    asset_url: Optional[str] = None
    status: str = "briefed"
    meta: dict = field(default_factory=dict)  # aigc_disclosure, format_tag, job_id…


@dataclass
class Test:
    id: str
    creative_id: str
    date: str
    spend: float = 0.0
    impressions: int = 0
    three_sec_vr: Optional[float] = None
    ctr: Optional[float] = None
    atc: Optional[float] = None
    cvr: Optional[float] = None
    roas: Optional[float] = None


@dataclass
class Result:
    product_id: str
    date: str
    net_margin: Optional[float] = None
    refund_rate: Optional[float] = None
    roas: Optional[float] = None
    decision: Optional[str] = None
