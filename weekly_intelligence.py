#!/usr/bin/env python
"""
Weekly permit intelligence — now a parameterized wrapper around market_brief.

market_brief.py provides rolling 7-day momentum, corridor analysis, and family
breakdowns. This script was previously hardcoded to July 19-26; now it generates
a fresh brief for any date you specify.

Run: python weekly_intelligence.py
     python weekly_intelligence.py --asof 2026-08-14
"""

import argparse
import pandas as pd
from datetime import datetime

from common import load_cfg
import market_brief

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asof", help="YYYY-MM-DD (default: today)")
    parser.add_argument("--out", default="weekly_intelligence.txt")
    args = parser.parse_args()

    cfg = load_cfg()
    asof = pd.Timestamp(args.asof) if args.asof else pd.Timestamp(datetime.now().date())

    brief_text = market_brief.build_brief(cfg, asof)

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(brief_text)

    print(brief_text)
    print(f"\n---\nWritten to {args.out}")
