#!/usr/bin/env python3
"""Daily cron (Part 12): pull velocity + saturation, update metrics, run detection, score
everything, and alert on new 80+ candidates with a short window.

Schedule (example):  0 13 * * *  python /path/to/scripts/daily_cron.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tt_engine import pipeline  # noqa: E402
from tt_engine.config import CONFIG  # noqa: E402
from tt_engine.db import Database  # noqa: E402


def main() -> int:
    with Database(CONFIG.db_path) as db:
        result = pipeline.daily(db)
        print(f"[daily {result.date}] {result.headline}")
        for c in result.new_candidates:
            s = c.breakdown.score
            print(f"  ALERT  {s.product_id}  {s.total:.0f}/100  ~{s.window_days:.0f}d runway "
                  f"— move before the window closes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
