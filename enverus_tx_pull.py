r"""
TX permits cross-check via the Enverus Developer API (permits dataset) --
a backup/additional source alongside RRC's own daf420 file, for days RRC's
download is down or delayed.

Deliberately read-only: this never touches data/tx/master.csv or ledger.csv.
Merging a second source's records into the RRC-authoritative master would
corrupt tx_daf420.py's diff logic (different field coverage, different
permit-number reliability) for a one-day convenience. Instead: pull Enverus's
view of recent TX permits, and flag any whose Permit_Number RRC's own master
doesn't have yet -- "Enverus has this, RRC hasn't shown it yet" is exactly
the gap this cross-check exists to catch. A permit drops out of the list on
its own once RRC's master.csv catches up and includes it.

Requires ENVERUS_SECRET_KEY (see local_env.load_env()). Generate/copy yours
at https://app.enverus.com/provisioning/directaccess.

Run:  python enverus_tx_pull.py
"""
import datetime as dt
import os
import sys
from pathlib import Path

import pandas as pd

from local_env import load_env
load_env()

from common import load_cfg, load_master
from digest import build_digest
from enverus_developer_api import DeveloperAPIv3, DAAuthException, DAQueryException

# Same shape as tx_daf420.parse_rrc's output, so this can share digest.py's
# renamer and build_digest() unmodified.
FIELD_MAP = {
    "PermitNumber": "Permit_Number",
    "County": "County",
    "District": "District",
    "RawOperator": "Operator_Name",     # not ENVOperator -- that's Enverus's normalized
                                         # rollup name; family_of()/client-match regexes
                                         # expect the raw legal name RRC itself publishes.
    "LeaseName": "Lease_Name",
    "WellNumber": "Well_Number",
    "ApprovedDate": "Issue_Date",
    "SubmittedDate": "Received_Date",
    "Latitude": "Surface_Lat",
    "Longitude": "Surface_Lon",
    "Latitude_BH": "BHL_Lat",
    "Longitude_BH": "BHL_Lon",
}

RENAME_FOR_DIGEST = {"Operator_Name": "operator", "County": "county",
                     "Total_Depth": "depth", "Well_Number": "well_num",
                     "Lease_Name": "well"}


def _depth(rec) -> float | None:
    """PermitDepth_FT is populated far more often than the two more specific
    depth fields in practice (confirmed against sample TX records) -- fall
    back to them only when it's missing."""
    for k in ("PermitDepth_FT", "PermittedMeasuredDepth_FT", "PermittedTrueVerticalDepth_FT"):
        v = rec.get(k)
        if v not in (None, ""):
            try:
                return float(v)
            except (TypeError, ValueError):
                continue
    return None


def fetch_tx_permits(secret_key: str, lookback_days: int) -> pd.DataFrame:
    cutoff = (dt.date.today() - dt.timedelta(days=lookback_days)).isoformat()
    v3 = DeveloperAPIv3(secret_key=secret_key)
    rows = []
    for rec in v3.query("permits", stateprovince="TX", approveddate=f"gt({cutoff})", pagesize=1000):
        row = {dst: rec.get(src) for src, dst in FIELD_MAP.items()}
        row["Permit_Number"] = str(rec.get("PermitNumber") or "").strip().zfill(7)
        row["Total_Depth"] = _depth(rec)
        rows.append(row)
    df = pd.DataFrame(rows, columns=list(FIELD_MAP.values()) + ["Total_Depth"])
    if df.empty:
        return df
    df = df[df["Permit_Number"].str.len() > 1]  # drop blanks (zfill('') -> '0000000')
    return df.drop_duplicates("Permit_Number", keep="last")


def main() -> int:
    cfg = load_cfg()
    secret_key = os.environ.get("ENVERUS_SECRET_KEY")
    if not secret_key:
        print("ENVERUS_SECRET_KEY not set -- skipping Enverus cross-check.")
        return 0

    lookback_days = cfg["texas"].get("enverus_lookback_days", 21)
    today = dt.date.today().isoformat()
    outd = Path(cfg["data_dir"]) / "tx" / "enverus_out" / today
    outd.mkdir(parents=True, exist_ok=True)

    try:
        df = fetch_tx_permits(secret_key, lookback_days)
    except (DAAuthException, DAQueryException) as e:
        print(f"Enverus query failed: {e}")
        return 1

    master = load_master(cfg, "tx")
    known = set(master["Permit_Number"].astype(str)) if master is not None else set()
    gap = df[~df["Permit_Number"].isin(known)].copy() if not df.empty else df
    if not gap.empty:
        known_ops = set(master["Operator_Name"].dropna()) if master is not None else set()
        gap["first_seen"] = ~gap["Operator_Name"].isin(known_ops)

    gap.to_csv(outd / "gap_permits.csv", index=False)

    empty_amended = pd.DataFrame(columns=list(RENAME_FOR_DIGEST.values()))
    if gap.empty:
        text = (f"# Texas Enverus Cross-Check — {dt.date.today():%a %b %d %Y}\n\n"
                 f"**0 gap permits** vs RRC master (queried {len(df)} Enverus TX permit(s) "
                 f"approved in the last {lookback_days} days -- all already in RRC's master.csv).")
    else:
        text = build_digest("Texas (Enverus Cross-Check)", gap.rename(columns=RENAME_FOR_DIGEST),
                             empty_amended, cfg, "tx", "county")
    text += ("\n\n---\n_Source: Enverus Developer API (permits dataset), not RRC. "
             "These permits have not yet appeared in RRC's own daf420 file -- treat as an "
             "early, unconfirmed signal, not a replacement for the RRC pull above. "
             f"Lookback window: {lookback_days} days._")
    (outd / "digest.md").write_text(text, encoding="utf-8")

    print(f"Enverus TX permits queried: {len(df)} | gap vs RRC master: {len(gap)}")
    print(f"outputs: {outd}")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
