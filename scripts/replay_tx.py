r"""Rebuild TX master from empty across a date range, reporting per-day new counts.

Why this exists: same-day re-runs overwrote each day's new_permits.csv with
empty files (commit c29c268b had 62 rows for 2026-07-26; 479da72d had 0).
Replaying from the retained inbox files regenerates the true series.

The daf420 extract is month-to-date cumulative and RESETS at month start --
daf420.dat.07-01-2026 and 07-02-2026 carry June's cycle (974 and 1009 permit
headers) and must be excluded from a July replay.

Usage:
  python scripts/replay_tx.py --from 2026-07-03 --to 2026-07-28
  python scripts/replay_tx.py --from 2026-07-03 --to 2026-07-28 --write
"""
import argparse
import datetime as dt
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import load_cfg, save_master              # noqa: E402
from core.diff import diff                            # noqa: E402
from tx_daf420 import CHANGE_COLS, parse_rrc          # noqa: E402


def dated_inbox_files(watch_dir, start, end):
    out = []
    for p in Path(watch_dir).glob("daf420.dat.*"):
        m = re.search(r"(\d{2})-(\d{2})-(\d{4})", p.name)
        if not m:
            continue
        d = dt.date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
        if start <= d <= end:
            out.append((d, p))
    return sorted(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", required=True)
    ap.add_argument("--to", dest="end", required=True)
    ap.add_argument("--write", action="store_true",
                    help="persist the rebuilt master (default: report only)")
    args = ap.parse_args()

    cfg = load_cfg()
    start = dt.date.fromisoformat(args.start)
    end = dt.date.fromisoformat(args.end)
    files = dated_inbox_files(cfg["texas"]["watch_dir"], start, end)
    if not files:
        sys.exit(f"No daf420 files between {start} and {end}")

    master = None
    total_new = 0
    print(f"{'date':12} {'parsed':>7} {'new':>6} {'amended':>8} {'master':>7}")
    for day, path in files:
        parsed = parse_rrc(path)
        parsed = parsed.drop_duplicates(
            subset=["Permit_Number", "CountyCode", "Lease_Name", "Operator_Number",
                    "Well_Number", "Issue_Date", "Spud_Date"], keep="first").copy()
        parsed["Permit_Number"] = parsed["Permit_Number"].astype(str)
        # One row per permit, matching tx_daf420.main(). Without this the file's
        # 706 rows / 693 permits inflate `new` and reconciliation fails.
        parsed = parsed.drop_duplicates("Permit_Number", keep="last").copy()
        new, amended, _ = diff(master, parsed, key="Permit_Number",
                               change_cols=CHANGE_COLS, resurfaced_after_days=None)
        master = (parsed if master is None
                  else pd.concat([master, parsed], ignore_index=True)
                       .drop_duplicates("Permit_Number", keep="last"))
        total_new += len(new)
        print(f"{day.isoformat():12} {len(parsed):>7} {len(new):>6} "
              f"{len(amended):>8} {len(master):>7}")

    unique = master["Permit_Number"].nunique()
    print(f"\nper-day new sums to : {total_new}")
    print(f"master unique permits: {unique}")
    if total_new == unique:
        print("RECONCILED - every permit in master was reported new on exactly one day")
    else:
        print(f"MISMATCH - {total_new} != {unique}; the replay is losing or double-counting")
        sys.exit(1)

    if args.write:
        save_master(cfg, "tx", master)
        print(f"master written: {len(master)} rows")


if __name__ == "__main__":
    main()
