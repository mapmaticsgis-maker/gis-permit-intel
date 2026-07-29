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
from core.ledger import record_replay_ingestion       # noqa: E402
from tx_daf420 import CHANGE_COLS, parse_rrc          # noqa: E402


DAF420_NAME = re.compile(r"daf420\.dat\.(\d{2})-(\d{2})-(\d{4})$")


def dated_inbox_files(watch_dir, start, end):
    """Only exactly-named dated extracts. The pattern is anchored because an
    unanchored search would accept daf420.dat.test-07-27-2026 -- a filename
    that has actually existed in this repo (commit 765f938) -- and silently
    fold test data into the recovery numbers."""
    out = []
    for p in Path(watch_dir).glob("daf420.dat.*"):
        m = DAF420_NAME.fullmatch(p.name)
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
    seen_new = []
    last = None
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
        seen_new.extend(new["Permit_Number"].tolist())
        last = {"path": path, "parsed": len(parsed),
                "new": len(new), "amended": len(amended)}
        print(f"{day.isoformat():12} {len(parsed):>7} {len(new):>6} "
              f"{len(amended):>8} {len(master):>7}")

    # Set identity, not count equality. Comparing only totals lets two
    # opposite-signed errors cancel -- one permit reported new on two days
    # while another reaches master without ever being reported -- and the
    # replay would print RECONCILED while being wrong in both directions.
    in_master = set(master["Permit_Number"])
    reported = set(seen_new)
    repeated = len(seen_new) - len(reported)
    never_reported = in_master - reported
    reported_not_in_master = reported - in_master

    print(f"\nper-day new sums to : {len(seen_new)}")
    print(f"master unique permits: {len(in_master)}")
    if repeated or never_reported or reported_not_in_master:
        print("MISMATCH -"
              f" {repeated} permit(s) reported new on more than one day;"
              f" {len(never_reported)} in master never reported new;"
              f" {len(reported_not_in_master)} reported new but absent from master")
        for label, s in (("repeat/extra", reported_not_in_master),
                         ("never reported", never_reported)):
            if s:
                print(f"  {label}: {sorted(s)[:10]}")
        sys.exit(1)
    print("RECONCILED - every permit in master was reported new on exactly one day")

    if args.write:
        save_master(cfg, "tx", master)
        print(f"master written: {len(master)} rows")
        # Master and the ledger are a unit. Persisting one without the other
        # is the very failure this branch exists to fix: without this row the
        # ledger still ends at the last pre-incident run, so source_freshness
        # and records_advancing both go red on the next run -- while an
        # operator is mid-incident and least able to afford a false alarm.
        row = record_replay_ingestion(
            cfg["data_dir"], "tx",
            source_path=last["path"], records_parsed=last["parsed"],
            new=last["new"], amended=last["amended"])
        print(f"ledger row appended: {row['source_name']} "
              f"@ {row['ingested_at']} ({row['records_parsed']} records)")
        print("master and ledger are now consistent; the next scheduled run "
              "will correctly skip this source.")


if __name__ == "__main__":
    main()
