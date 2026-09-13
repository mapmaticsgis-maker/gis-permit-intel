r"""
Daily synopsis of Enverus permit activity in the plays Mapmatics tracks for
BD purposes -- Haynesville, Eagle Ford, Permian -- regardless of county
corridors or client-family matches. Deterministic stats + a capped listing,
not a narrative: this is the "what's moving in the plays I watch" companion
to enverus_tx_pull.py/enverus_la_pull.py's "what did RRC/SONRIS miss" gap
check. Both TX and LA are queried, since Haynesville spans the state line.

Play/basin classification is by Enverus's own ENVPlay/ENVBasin tags,
confirmed against real records (2026-09-13):
  Haynesville: ENVPlay in {HAYNESVILLE, WESTERN HAYNESVILLE} (TX + LA both
    use the same tag -- no separate LA spelling)
  Eagle Ford:  ENVPlay == EAGLE FORD (TX only; LA has no Eagle Ford acreage)
  Permian:     ENVBasin in {MIDLAND, DELAWARE, PERMIAN OTHER} -- basin, not
    play, since "Permian" spans several named plays (Central Basin
    Platform, Delaware, Midland...) and the user's interest is basin-wide.

Deliberately read-only, like the two cross-check scripts -- never touches
master.csv/ledger.csv.

Requires ENVERUS_SECRET_KEY (see local_env.load_env()).

Run:  python enverus_synopsis.py
"""
import datetime as dt
import os
import sys
from pathlib import Path

import pandas as pd

from local_env import load_env
load_env()

from common import load_cfg
from enverus_common import fetch_raw_permits, depth_from_record
from enverus_developer_api import DAAuthException, DAQueryException

SYNOPSIS_LOOKBACK_DAYS = 14
TOP_N_LISTED = 15  # cap the detailed listing per play; the rollup stats above it cover the rest

PLAYS = {
    "Haynesville": lambda r: r.get("ENVPlay") in ("HAYNESVILLE", "WESTERN HAYNESVILLE"),
    "Eagle Ford": lambda r: r.get("ENVPlay") == "EAGLE FORD",
    "Permian": lambda r: r.get("ENVBasin") in ("MIDLAND", "DELAWARE", "PERMIAN OTHER"),
}


def _row(rec: dict, state: str) -> dict:
    return {
        "state": state,
        "operator": rec.get("RawOperator") or "",
        "county": rec.get("County") or "",
        "well": rec.get("LeaseName") or rec.get("WellName") or "",
        "well_num": rec.get("WellNumber") or "",
        "play": rec.get("ENVPlay") or "",
        "basin": rec.get("ENVBasin") or "",
        "trajectory": rec.get("Trajectory") or "",
        "lateral_ft": rec.get("PermittedLateralLength_FT"),
        "depth": depth_from_record(rec),
        "approved": (rec.get("ApprovedDate") or "")[:10],
    }


def build_play_section(name: str, rows: list[dict]) -> str:
    if not rows:
        return f"## {name}\n\n_No permits in the last {SYNOPSIS_LOOKBACK_DAYS} days._"
    df = pd.DataFrame(rows)
    L = [f"## {name} — {len(df)} permit(s) in the last {SYNOPSIS_LOOKBACK_DAYS} days"]

    top_ops = df["operator"].value_counts().head(6)
    L.append("\n**Top operators:**")
    for op, n in top_ops.items():
        L.append(f"- {op}: {n}")

    by_county = df.groupby(["state", "county"]).size().sort_values(ascending=False).head(8)
    L.append("\n**By county/parish:**")
    for (state, county), n in by_county.items():
        L.append(f"- {str(county).title()}, {state}: {n}")

    hz = df[df["trajectory"] == "HORIZONTAL"]
    if len(hz) and hz["lateral_ft"].notna().any():
        L.append(f"\n**Avg horizontal lateral length:** {hz['lateral_ft'].dropna().mean():,.0f} ft "
                  f"({hz['lateral_ft'].notna().sum()} of {len(hz)} horizontal permits reporting)")

    L.append(f"\n**Most recent {min(TOP_N_LISTED, len(df))}:**")
    recent = df.sort_values("approved", ascending=False).head(TOP_N_LISTED)
    for _, r in recent.iterrows():
        depth_str = f", {r['depth']:.0f}' TD" if pd.notna(r["depth"]) else ""
        L.append(f"- {r['approved']} — **{r['operator']}** — {r['well']} {r['well_num']} "
                  f"({str(r['county']).title()}, {r['state']}{depth_str})")
    return "\n".join(L)


def main() -> int:
    cfg = load_cfg()
    secret_key = os.environ.get("ENVERUS_SECRET_KEY")
    if not secret_key:
        print("ENVERUS_SECRET_KEY not set -- skipping Enverus synopsis.")
        return 0

    today = dt.date.today().isoformat()
    outd = Path(cfg["data_dir"]) / "enverus_out" / today
    outd.mkdir(parents=True, exist_ok=True)

    try:
        tx_recs = fetch_raw_permits(secret_key, "TX", SYNOPSIS_LOOKBACK_DAYS)
        la_recs = fetch_raw_permits(secret_key, "LA", SYNOPSIS_LOOKBACK_DAYS)
    except (DAAuthException, DAQueryException) as e:
        print(f"Enverus query failed: {e}")
        return 1

    rows = [_row(r, "TX") for r in tx_recs] + [_row(r, "LA") for r in la_recs]

    sections = [f"# Play Synopsis — {dt.date.today():%a %b %d %Y}\n"]
    for name, matcher in PLAYS.items():
        play_rows = [r for r in rows if matcher({"ENVPlay": r["play"], "ENVBasin": r["basin"]})]
        sections.append(build_play_section(name, play_rows))
    text = "\n\n---\n\n".join(sections)
    text += ("\n\n---\n_Source: Enverus Developer API (permits dataset), TX + LA. "
             f"Rolling {SYNOPSIS_LOOKBACK_DAYS}-day window, all operators -- not filtered to "
             "watched families or client corridors. This is play-wide activity, independent of "
             "the RRC/SONRIS gap cross-check above._")

    (outd / "synopsis.md").write_text(text, encoding="utf-8")
    print(f"Enverus play synopsis: {len(rows)} TX+LA permits scanned, "
          f"{sum(1 for r in rows if any(m({'ENVPlay': r['play'], 'ENVBasin': r['basin']}) for m in PLAYS.values()))} "
          f"matched a tracked play.")
    print(f"outputs: {outd}")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
