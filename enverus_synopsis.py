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
from enverus_common import fetch_raw_permits, fetch_raw_rigs, depth_from_record
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


def _rig_row(rec: dict, state: str) -> dict:
    return {
        "state": state,
        "operator": rec.get("InitialOperator") or rec.get("ENVOperator") or "",
        "county": rec.get("County") or "",
        "contractor": rec.get("ContractorName") or "",
        "play": rec.get("ENVPlay") or "",
        "basin": rec.get("ENVBasin") or "",
        "active": rec.get("ActiveStatus") == "ACTIVE",
        "days_on_location": rec.get("DaysOnLocation"),
        "first_day": (rec.get("FirstDay") or "")[:10],
    }


def _rig_section(rig_rows: list[dict]) -> list[str]:
    """Rig data runs noticeably more current than permits (confirmed
    2026-09-13: spuds recorded through the day of the query vs. permits
    lagging behind a stalled RRC feed), so this is worth showing even for
    a play with no new PERMITS in the lookback window -- a rig can still
    be actively turning on a permit issued earlier than that window."""
    if not rig_rows:
        return []
    rdf = pd.DataFrame(rig_rows)
    active = rdf[rdf["active"]]
    L = [f"\n**Active rigs:** {len(active)} of {len(rdf)} rig(s) spudded in the last "
         f"{SYNOPSIS_LOOKBACK_DAYS} days still on location"]
    if len(active):
        top_contractors = active["contractor"].value_counts().head(5)
        L.append("- Top contractors: " + ", ".join(f"{c} ({n})" for c, n in top_contractors.items()))
        for _, r in active.sort_values("days_on_location", ascending=False).head(8).iterrows():
            L.append(f"  - {r['operator']} — {str(r['county']).title()}, {r['state']} "
                      f"({r['contractor']}, spud {r['first_day']}, {r['days_on_location']:.0f}d on location)")
    return L


def build_play_section(name: str, rows: list[dict], rig_rows: list[dict]) -> str:
    if not rows:
        L = [f"## {name}\n\n_No permits in the last {SYNOPSIS_LOOKBACK_DAYS} days._"]
        L.extend(_rig_section(rig_rows))
        return "\n".join(L)
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

    L.extend(_rig_section(rig_rows))

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
        tx_rigs = fetch_raw_rigs(secret_key, "TX", SYNOPSIS_LOOKBACK_DAYS)
        la_rigs = fetch_raw_rigs(secret_key, "LA", SYNOPSIS_LOOKBACK_DAYS)
    except (DAAuthException, DAQueryException) as e:
        print(f"Enverus query failed: {e}")
        return 1

    rows = [_row(r, "TX") for r in tx_recs] + [_row(r, "LA") for r in la_recs]
    rig_rows = [_rig_row(r, "TX") for r in tx_rigs] + [_rig_row(r, "LA") for r in la_rigs]

    sections = [f"# Play Synopsis — {dt.date.today():%a %b %d %Y}\n"]
    for name, matcher in PLAYS.items():
        play_rows = [r for r in rows if matcher({"ENVPlay": r["play"], "ENVBasin": r["basin"]})]
        play_rig_rows = [r for r in rig_rows if matcher({"ENVPlay": r["play"], "ENVBasin": r["basin"]})]
        sections.append(build_play_section(name, play_rows, play_rig_rows))
    text = "\n\n---\n\n".join(sections)
    text += ("\n\n---\n_Source: Enverus Developer API (permits + rigs datasets), TX + LA. "
             f"Rolling {SYNOPSIS_LOOKBACK_DAYS}-day window, all operators -- not filtered to "
             "watched families or client corridors. This is play-wide activity, independent of "
             "the RRC/SONRIS gap cross-check above. Rig data runs more current than permits._")

    (outd / "synopsis.md").write_text(text, encoding="utf-8")
    print(f"Enverus play synopsis: {len(rows)} TX+LA permits scanned, "
          f"{sum(1 for r in rows if any(m({'ENVPlay': r['play'], 'ENVBasin': r['basin']}) for m in PLAYS.values()))} "
          f"matched a tracked play.")
    print(f"outputs: {outd}")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
