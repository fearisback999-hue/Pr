"""Bulk product intake — paste a messy list, get scored candidates.

The friction this removes: getting 15 products into the engine meant typing
`add --name ... --category ... --price ...` fifteen times, which is enough
pain that people just don't do it, and an engine with nothing in it judges
nothing.

So: you scroll TikTok Creative Center / Amazon / a supplier page yourself, copy
whatever you see, paste the whole blob in, and this parses it into real
products the engine can score.

WHY PASTE AND NOT A SCRAPER, since it's the obvious question:
scraping TikTok violates their ToS, and the enforcement lands on the identity
doing it — which for a TikTok Shop seller is the account their entire business
runs on. Trading that for saved scrolling is a bad bet at any odds. Pasting
what YOU looked at carries none of that risk, takes about a minute, and gets
the same data into the same scoring engine.

It parses forgivingly, because pasted text is always messy:

    Doorway Pull Up Bar $34.99 fitness
    2. Scalp Massager — $12.99 (beauty)
    Blue Light Glasses  19.99
    Meme Graphic Tee | $24.99 | apparel

Anything it can't read is REPORTED, never silently dropped — the same rule as
the CSV importers. A line without a price still becomes a product (you can add
the price later); a line without a name is skipped and named in the summary.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date as _date

from .db import Database, models

# Category words we recognise in a pasted line. Everything else → "uncategorized",
# which is honest: a wrong guess is worse than an obvious blank you can fix.
_CATEGORY_WORDS = {
    "home": "home", "kitchen": "home", "decor": "home", "bedroom": "home",
    "beauty": "beauty", "skincare": "beauty", "makeup": "beauty", "hair": "beauty",
    "wellness": "wellness", "health": "wellness", "massage": "wellness",
    "fitness": "fitness", "gym": "fitness", "workout": "fitness",
    "pet": "pet", "dog": "pet", "cat": "pet",
    "apparel": "apparel", "clothing": "apparel", "tee": "apparel",
    "shirt": "apparel", "hoodie": "apparel", "wear": "apparel",
    "electronics": "electronics", "tech": "electronics", "gadget": "electronics",
    "phone": "electronics", "charger": "electronics",
    "accessories": "accessories", "jewelry": "accessories", "bag": "accessories",
    "toys": "toys", "toy": "toys", "game": "toys",
    "hobby": "hobby", "craft": "hobby", "art": "hobby",
}

# Leading list junk: "1.", "1)", "-", "*", "•", "#3"
_LEAD = re.compile(r"^\s*(?:[#]?\d+[.)\]]?|[-*•·])\s+")
# A price anywhere in the line: $12.99 / 12.99 USD / 12,99
_PRICE = re.compile(r"\$\s*(\d{1,4}(?:[.,]\d{1,2})?)|(\d{1,4}[.,]\d{2})\s*(?:usd|dollars)?\b",
                    re.I)
_SEPARATORS = re.compile(r"\s*[|;–—]\s*|\s+[-]\s+")


@dataclass
class ParsedLine:
    name: str
    price: float | None
    category: str
    raw: str


@dataclass
class PasteResult:
    added: list[ParsedLine] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)   # (raw, why)

    @property
    def summary(self) -> str:
        lines = [f"{len(self.added)} product(s) added."]
        for p in self.added:
            price = f"${p.price:.2f}" if p.price is not None else "no price yet"
            lines.append(f"  • {p.name[:44]:44s} {price:>12s}  {p.category}")
        if self.skipped:
            lines.append(f"\n{len(self.skipped)} line(s) skipped:")
            for raw, why in self.skipped[:8]:
                lines.append(f"  – {raw[:50]!r}: {why}")
            if len(self.skipped) > 8:
                lines.append(f"  … and {len(self.skipped) - 8} more")
        no_price = [p for p in self.added if p.price is None]
        if no_price:
            lines.append(f"\n{len(no_price)} have no price — add one with "
                         "`add-metric <id> --units N --price P` when you know it.")
        lines.append("\nThese are CANDIDATES, not winners. Next: get a real supplier "
                     "quote for each (`add-supplier`), then `scorecard <id>` for the "
                     "verdict.")
        return "\n".join(lines)


def _clean_name(text: str) -> str:
    text = _LEAD.sub("", text).strip()
    # Drop a trailing parenthetical category and any stray separators/punctuation.
    text = re.sub(r"\s*\([^)]*\)\s*$", "", text).strip()
    return text.strip(" -–—|,;:").strip()


def parse_line(raw: str) -> ParsedLine | None:
    """One messy line → a product, or None when there's no usable name."""
    line = raw.strip()
    if not line:
        return None

    price = None
    m = _PRICE.search(line)
    if m:
        raw_price = (m.group(1) or m.group(2) or "").replace(",", ".")
        try:
            value = float(raw_price)
            # A bare 4-digit integer is far more likely a year or a view count
            # than a price on an impulse product; only trust decimals or a "$".
            if m.group(1) or "." in raw_price:
                price = value
        except ValueError:
            price = None
        line = line[:m.start()] + " " + line[m.end():]

    category = "uncategorized"
    matched_word = ""
    for word, cat in _CATEGORY_WORDS.items():
        if re.search(rf"\b{re.escape(word)}\b", line, re.I):
            category, matched_word = cat, word
            break
    # Strip a TRAILING category tag from the text ("Pull Up Bar fitness" → "Pull Up
    # Bar"). Leaving it in corrupts the name and, worse, makes the same product
    # parse to two different ids depending on whether you typed the tag.
    if matched_word:
        line = re.sub(rf"[\s|,;–—-]*\b{re.escape(matched_word)}\b\s*$", "",
                      line, flags=re.I)

    # Take the longest chunk when the line is separated (name | price | category).
    parts = [p for p in _SEPARATORS.split(line) if p.strip()]
    candidate = max(parts, key=len) if parts else line
    name = _clean_name(candidate)
    # A "name" that is only digits/punctuation isn't a product.
    if len(name) < 3 or not re.search(r"[a-z]{3}", name, re.I):
        return None
    return ParsedLine(name=name[:80], price=price, category=category, raw=raw.strip())


def product_id(name: str) -> str:
    slug = re.sub(r"[^A-Z0-9]+", "", name.upper())[:18]
    return f"P-{slug or 'ITEM'}"


def paste_products(db: Database, blob: str) -> PasteResult:
    """Parse a pasted blob into products and save them. Never invents a price;
    never silently drops a line it couldn't read."""
    result = PasteResult()
    seen: set[str] = set()
    today = _date.today().isoformat()

    for raw in blob.splitlines():
        if not raw.strip():
            continue
        parsed = parse_line(raw)
        if parsed is None:
            result.skipped.append((raw.strip(), "couldn't find a product name"))
            continue
        pid = product_id(parsed.name)
        if pid in seen:
            result.skipped.append((raw.strip(), "duplicate of an earlier line"))
            continue
        seen.add(pid)

        db.upsert_product(models.Product(
            id=pid, name=parsed.name, category=parsed.category, first_seen=today))
        if parsed.price is not None:
            # One observation is not a trend — but it anchors the price so the
            # margin gate has something real to work against once a cost lands.
            db.upsert_metric(models.DailyMetric(
                product_id=pid, date=today, units=0, gmv=0.0, price=parsed.price,
                sellers=0, promo_videos=0, ads=0, avg_ad_age=0.0))
        result.added.append(parsed)

    return result
