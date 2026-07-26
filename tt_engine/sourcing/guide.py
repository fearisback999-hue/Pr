"""Where to source: US-warehouse / fast-handling suppliers, and how to vet them.

The engine already SCORES suppliers (supplier.py) — shipping speed is 25% of the
score, a US warehouse lifts refund-risk and scalability, and slow/overseas suppliers
get flagged. What it can't do is find the supplier for you or vouch for one it's
never ordered from. This is the researched directory to check (2026-07, re-verify —
platforms and warehouses change), plus the vetting discipline the engine enforces
(a sample order is mandatory before scaling — never assume quality from a listing).

Why US / fast matters, concretely: TikTok Shop expects a real carrier tracking scan
within ~24–48h of the order and buyers expect ~3–6 day US delivery. Overseas 2–4 week
shipping is a refund machine AND an account-health hit — the opposite of what you want.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SupplierSource:
    name: str
    us_speed: str
    good_for: str
    watch_out: str


# Researched US-warehouse / fast-shipping options (2026-07). Directories to CHECK —
# not endorsements; order a sample and confirm the dispatch SLA before you commit.
SOURCES: tuple[SupplierSource, ...] = (
    SupplierSource(
        "CJ Dropshipping", "~3–6 day US (East/West warehouses when pre-stocked)",
        "TikTok-Shop integration + a TikTok-ready catalog; a solid default first stop",
        "the fast times only apply when the item is already in a US warehouse — "
        "confirm THAT SKU is US-stocked, not shipping from CN"),
    SupplierSource(
        "TopDawg", "~2–5 day US across the board",
        "3,000+ verified US suppliers, 500k+ products — genuinely US-based fulfilment",
        "subscription tiers; margins can be thinner than sourcing direct"),
    SupplierSource(
        "Spocket", "~3–6 day US/EU",
        "real US & EU BRAND suppliers (not overseas relabelers) — quality + speed",
        "curated = higher unit cost; check the margin still clears the 45% gate"),
    SupplierSource(
        "Zendrop", "~5–8 day US",
        "automated US fulfilment + custom branding; easy TikTok Shop workflow",
        "automation convenience is priced in — verify landed cost per unit"),
    SupplierSource(
        "HyperSKU", "US warehouse options + fast routes",
        "US warehousing, branding, and print-on-demand under one roof",
        "confirm the specific product's route is the fast one before you rely on it"),
    SupplierSource(
        "Amazon Multi-Channel Fulfillment (MCF)", "~2–5 day US",
        "if you can get product into Amazon FBA, MCF fulfils your TikTok orders fast "
        "from US warehouses — often the fastest, most reliable tracking",
        "you front inventory into FBA (cash lock-up); best once a product is proven"),
    SupplierSource(
        "USAdrop", "fast US shipping, verified partners",
        "verified suppliers with fast-shipping focus and sourcing support",
        "still order a sample — 'verified' is not the same as you having held it"),
)


def render() -> str:
    lines = [
        "# Where to source — US warehouse / fast handling",
        "",
        "TikTok Shop expects a carrier tracking scan within ~24–48h and buyers expect "
        "~3–6 day US delivery. Overseas 2–4 week shipping = refunds + account-health "
        "hits. So: prefer a US warehouse, or a supplier with a proven fast route.",
        "",
        "## Directories to check (not endorsements — sample before you scale)",
        "",
    ]
    for s in SOURCES:
        lines += [
            f"### {s.name}",
            f"- **US speed:** {s.us_speed}",
            f"- **Good for:** {s.good_for}",
            f"- **Watch out:** {s.watch_out}",
            "",
        ]
    lines += [
        "## Vet a supplier before you commit (the engine enforces this)",
        "",
        "1. Confirm the SPECIFIC SKU ships from a US warehouse (not just that the "
        "supplier 'has' one) — ask for the dispatch SLA and typical tracking-scan time.",
        "2. Order a SAMPLE. Non-negotiable — the engine flags 'SAMPLE ORDER required "
        "before scaling' on every supplier. Judge the real quality, packaging, and "
        "actual delivery speed yourself.",
        "3. Get the true landed cost (unit + shipping) — you need it for economics to "
        "score at all; the engine refuses to score margin without a real number.",
        "4. Enter it: `add-supplier <product-id> --cost X --ship-cost Y --ship-days N "
        "--us-warehouse`. The score rewards a US warehouse + sub-5-day shipping and "
        "flags slow/overseas; `packet <id>` (or the product page) ranks suppliers "
        "best-first.",
        "",
        "The engine can't order for you or vouch for a supplier it's never used — it "
        "makes the CHOICE disciplined once you've entered real quotes.",
    ]
    return "\n".join(lines) + "\n"


SOURCES_CITED = (
    "https://dodropshipping.com/best-dropshipping-suppliers-for-tiktok-shop/",
    "https://www.sellthetrend.com/resources/dropshipping/the-best-25-dropshipping-suppliers-in-the-usa",
    "https://www.autods.com/blog/suppliers-marketplaces/dropshipping-suppliers-for-tiktok-shop/",
    "https://usadrop.com/10-best-dropshipping-suppliers/",
    "https://trueprofit.io/blog/find-dropshipping-suppliers-for-tiktok-shop",
)
