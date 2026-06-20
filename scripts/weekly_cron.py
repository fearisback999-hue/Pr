#!/usr/bin/env python3
"""Weekly cron (Part 12): generate the opportunity report with attack packets, auto-trigger
Higgsfield kit planning for the top picks, and write testing recommendations.

Schedule (example):  0 14 * * 1  python /path/to/scripts/weekly_cron.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tt_engine import pipeline  # noqa: E402
from tt_engine.config import CONFIG  # noqa: E402
from tt_engine.db import Database  # noqa: E402
from tt_engine.llm import LLMClient  # noqa: E402

OUT_DIR = str(Path(__file__).resolve().parent.parent / "reports" / "out")


def main() -> int:
    with Database(CONFIG.db_path) as db:
        report = pipeline.weekly(db, out_dir=OUT_DIR, llm=LLMClient())
        print(f"[weekly {report.date}] {report.headline} → {OUT_DIR}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
