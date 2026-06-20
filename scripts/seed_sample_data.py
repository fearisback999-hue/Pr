#!/usr/bin/env python3
"""Seed the local database with the offline sample dataset (products, metrics, suppliers)
plus optional synthetic outcomes for the Part-13 recalibration demo.

    python scripts/seed_sample_data.py [--demo-outcomes]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tt_engine import seed  # noqa: E402
from tt_engine.config import CONFIG  # noqa: E402
from tt_engine.db import Database  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo-outcomes", action="store_true")
    ap.add_argument("--db", default=CONFIG.db_path)
    args = ap.parse_args()
    with Database(args.db) as db:
        n = seed.seed_sample(db)
        print(f"seeded {n} products + suppliers into {db.path}")
        if args.demo_outcomes:
            m = seed.seed_demo_outcomes(db)
            print(f"seeded {m} synthetic outcomes for recalibration")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
