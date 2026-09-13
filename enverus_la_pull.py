r"""
LA permits cross-check via the Enverus Developer API (permits dataset) --
same idea as enverus_tx_pull.py, for SONRIS instead of RRC. See that
script's docstring for the reasoning (read-only, never touches
data/la/master.csv or ledger.csv).

Join key: Enverus's PermitNumber for LA records is SONRIS's own
WELL_SERIAL_NUM (confirmed 2026-09-13 -- values pulled from Enverus for
recent LA permits land in the same numeric range as, and for overlapping
wells exactly match, la/master.csv's `id` column). Unlike TX/RRC's
Permit_Number, SONRIS well serial numbers aren't zero-padded.

Requires ENVERUS_SECRET_KEY (see local_env.load_env()).

Run:  python enverus_la_pull.py
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
from enverus_common import fetch_raw_permits, depth_from_record
from enverus_developer_api import DAAuthException, DAQueryException

# LA's master.csv already uses digest.py's canonical column names directly
# (config.yaml's field map applies them at ingestion) -- no rename step
# needed here, unlike TX.
FIELD_MAP = {
    "PermitNumber": "id",
    "County": "parish",
    "RawOperator": "operator",
    "LeaseName": "well",
    "WellNumber": "well_num",
    "ApprovedDate": "issue_date",
    "API_UWI": "api",
    "Section": "section",
    "Township": "township",
    "Range": "range",
    "Field": "field",
    "Latitude": "lat",
    "Longitude": "lon",
}


def fetch_la_permits(secret_key: str, lookback_days: int) -> pd.DataFrame:
    rows = []
    for rec in fetch_raw_permits(secret_key, "LA", lookback_days):
        row = {dst: rec.get(src) for src, dst in FIELD_MAP.items()}
        row["id"] = str(rec.get("PermitNumber") or "").strip()
        row["depth"] = depth_from_record(rec)
        rows.append(row)
    df = pd.DataFrame(rows, columns=list(FIELD_MAP.values()) + ["depth"])
    if df.empty:
        return df
    df = df[df["id"].str.len() > 0]
    return df.drop_duplicates("id", keep="last")


def main() -> int:
    cfg = load_cfg()
    secret_key = os.environ.get("ENVERUS_SECRET_KEY")
    if not secret_key:
        print("ENVERUS_SECRET_KEY not set -- skipping Enverus cross-check.")
        return 0

    lookback_days = cfg["texas"].get("enverus_lookback_days", 21)  # shared setting, not TX-specific
    today = dt.date.today().isoformat()
    outd = Path(cfg["data_dir"]) / "la" / "enverus_out" / today
    outd.mkdir(parents=True, exist_ok=True)

    try:
        df = fetch_la_permits(secret_key, lookback_days)
    except (DAAuthException, DAQueryException) as e:
        print(f"Enverus query failed: {e}")
        return 1

    master = load_master(cfg, "la")
    known = set(master["id"].astype(str)) if master is not None else set()
    gap = df[~df["id"].isin(known)].copy() if not df.empty else df

    gap.to_csv(outd / "gap_permits.csv", index=False)

    empty_amended = pd.DataFrame(columns=["operator", "parish", "well", "well_num", "depth"])
    if gap.empty:
        text = (f"# Louisiana Enverus Cross-Check — {dt.date.today():%a %b %d %Y}\n\n"
                 f"**0 gap permits** vs SONRIS master (queried {len(df)} Enverus LA permit(s) "
                 f"approved in the last {lookback_days} days -- all already in la/master.csv).")
    else:
        text = build_digest("Louisiana (Enverus Cross-Check)", gap, empty_amended, cfg, "la", "parish")
    text += ("\n\n---\n_Source: Enverus Developer API (permits dataset), not SONRIS. "
             "These wells have not yet appeared in the SONRIS pull above -- treat as an "
             "early, unconfirmed signal, not a replacement for it. "
             f"Lookback window: {lookback_days} days._")
    (outd / "digest.md").write_text(text, encoding="utf-8")

    print(f"Enverus LA permits queried: {len(df)} | gap vs SONRIS master: {len(gap)}")
    print(f"outputs: {outd}")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
