"""
One-time migration: fix Mc-block county labels already baked into master.csv.

Dropping in the corrected county_lookup.py only fixes FUTURE parses. Every row
written before the fix — everything master.csv has accumulated since April —
still carries the old wrong label, because tx_daf420.py writes County as a
value, not a formula. The corrected lookup and this migration are two separate
steps; both are required.

Recomputes County from the stored CountyCode using the corrected lookup and
overwrites in place, for the nine affected codes only (307-323). Everything
else in master.csv is untouched. Writes a timestamped backup first.

Run once, right after county_lookup.py is corrected:

    python migrate_county_labels.py --master ./data/tx/master.csv

Safe to run twice — the second run finds nothing left to fix and says so.
"""

import argparse
import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd

from county_lookup import COUNTY_LOOKUP

AFFECTED_CODES = {"307", "309", "311", "313", "315", "317", "319", "321", "323"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--master", required=True)
    parser.add_argument("--dry-run", action="store_true",
                        help="Report what would change without writing")
    args = parser.parse_args()

    master_path = Path(args.master)
    df = pd.read_csv(master_path, dtype=str)

    if "CountyCode" not in df.columns or "County" not in df.columns:
        raise SystemExit(f"{master_path} has no CountyCode/County columns — "
                         "wrong file?")

    code = df["CountyCode"].astype(str).str.zfill(3)
    affected = code.isin(AFFECTED_CODES)
    correct = code.map(COUNTY_LOOKUP)

    wrong = affected & (df["County"] != correct) & correct.notna()
    n_wrong = int(wrong.sum())

    if n_wrong == 0:
        print(f"No mislabeled rows found in {master_path}. "
              f"Already migrated, or the bug never reached this file.")
        return

    print(f"Found {n_wrong} rows with stale Mc-block county labels.")
    preview = df.loc[wrong, ["Permit_Number", "CountyCode", "County"]].copy()
    preview["Corrected"] = correct[wrong]
    print(preview.groupby(["CountyCode", "County", "Corrected"]).size()
          .reset_index(name="n").to_string(index=False))

    if args.dry_run:
        print("\n--dry-run: no changes written.")
        return

    backup = master_path.with_name(
        f"{master_path.stem}.pre-county-fix.{datetime.now():%Y%m%d%H%M%S}.csv"
    )
    shutil.copy2(master_path, backup)
    print(f"\nBackup written: {backup}")

    df.loc[wrong, "County"] = correct[wrong]
    df.to_csv(master_path, index=False)
    print(f"Corrected {n_wrong} rows in place: {master_path}")


if __name__ == "__main__":
    main()
