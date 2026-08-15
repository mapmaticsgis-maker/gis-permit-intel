"""
Deterministic evidence pack for the intel-insight narrative brief.

Companion to market_brief.py, but a different layer: market_brief.py produces
mechanical stats (rolling averages, corridor rollups). This produces the raw
material for narrative judgment -- pad/campaign clusters, per-operator named
inventory, fresh-spud detection via snapshot diff, aging client-watch permits,
and watchlist candidates. Facts only, no prose. Matches the governing rule in
docs/superpowers/specs/2026-07-28-mapmatics-intelligence-system-design.md:
"anything that might be shown to a client is computed deterministically;
anything that is a judgment call is Claude's."

Maintains a snapshot of each state's master (data/<state>/.intel_snapshot.csv)
so "fresh spud postings" means "Spud_Date newly populated since the last time
this ran," not a single day's issue date -- a spud can post against a permit
issued weeks earlier, and a day-scoped filter would miss it.

Run: python intel_insight_evidence.py --out data/intel_insight/<date>.json
     python intel_insight_evidence.py --dry-run   (skip snapshot update, for testing)
"""
import argparse
import datetime as dt
import json
import re
from pathlib import Path

import pandas as pd

from common import load_cfg, load_master, family_of
from market_brief import lease_stem

ROOT = Path(__file__).resolve().parent

WATCHLIST_MIN_DAY_PERMITS = 5   # unfamiliar-operator single-day count, one county, to flag as a watch candidate
PAD_WINDOW_DAYS = 21            # lookback for pad/campaign clustering
AGING_MIN_DAYS = 14             # client-watch: unspudded permits at least this old

SCHEMA_COLS = ["key", "operator", "county", "well_name", "well_num",
               "issue_date", "spud_date", "status"]


def snapshot_path(cfg, state):
    return Path(cfg["data_dir"]) / state / ".intel_snapshot.csv"


def load_snapshot(cfg, state):
    p = snapshot_path(cfg, state)
    if not p.exists():
        return None
    df = pd.read_csv(p, dtype=str)
    df["issue_date"] = pd.to_datetime(df["issue_date"], errors="coerce")
    df["spud_date"] = pd.to_datetime(df["spud_date"], errors="coerce")
    return df


def save_snapshot(cfg, state, df):
    p = snapshot_path(cfg, state)
    p.parent.mkdir(parents=True, exist_ok=True)
    out = df.copy()
    out["issue_date"] = out["issue_date"].dt.date.astype(str).replace("NaT", "")
    out["spud_date"] = out["spud_date"].dt.date.astype(str).replace("NaT", "")
    out.to_csv(p, index=False)


def normalize_tx(master):
    df = master.rename(columns={
        "Permit_Number": "key", "Operator_Name": "operator", "County": "county",
        "Lease_Name": "well_name", "Well_Number": "well_num",
        "Issue_Date": "issue_date", "Spud_Date": "spud_date",
    }).copy()
    df["issue_date"] = pd.to_datetime(df["issue_date"], errors="coerce")
    df["spud_date"] = pd.to_datetime(df["spud_date"], errors="coerce")
    df["operator"] = df["operator"].astype(str).str.upper().str.strip()
    df["county"] = df["county"].astype(str).str.upper().str.strip()
    df["status"] = None  # not yet parsed for TX -- see daf420-field-map.md Tier 1 (unverified offsets)
    return df[SCHEMA_COLS]


def normalize_la(master):
    df = master.rename(columns={
        "id": "key", "operator": "operator", "parish": "county",
        "well": "well_name", "well_num": "well_num",
        "issue_date": "issue_date", "spud": "spud_date", "status_desc": "status",
    }).copy()
    df["issue_date"] = pd.to_datetime(df["issue_date"], errors="coerce")
    df["spud_date"] = pd.to_datetime(df["spud_date"], errors="coerce")
    df["operator"] = df["operator"].astype(str).str.upper().str.strip()
    df["county"] = df["county"].astype(str).str.upper().str.strip()
    return df[SCHEMA_COLS]


MAX_GAP_SPAN = 30  # a real skipped well slot is a small local gap; a large span means the
                    # leading number is a tract/unit code (e.g. COG's "211".."1010"), not a
                    # sequential well slot, and computing gaps there just produces noise


def well_number_gaps(well_numbers: list) -> list:
    """['5H','6H','7H','9H','10H','11H'] -> [8]. Surfaces a skipped well slot
    in an otherwise-sequential pad, called out explicitly in the target brief
    style ('well 8H notably skipped'). Returns [] when the numbers don't look
    like a tight local sequence (see MAX_GAP_SPAN)."""
    nums = set()
    for w in well_numbers:
        m = re.match(r"(\d+)", str(w))
        if m:
            nums.add(int(m.group(1)))
    if len(nums) < 2 or (max(nums) - min(nums)) > MAX_GAP_SPAN:
        return []
    return sorted(set(range(min(nums), max(nums) + 1)) - nums)


def cluster_pads(df, asof, window_days=PAD_WINDOW_DAYS):
    """Group recently-issued permits into pads: same operator + county + lease
    stem. One dict per pad with 2+ wells in the window."""
    recent = df[df["issue_date"] >= (asof - pd.Timedelta(days=window_days))].copy()
    if recent.empty:
        return []
    recent["_stem"] = recent["well_name"].map(lease_stem)
    pads = []
    for (op, county, stem), group in recent.groupby(["operator", "county", "_stem"]):
        if len(group) < 2 or not stem:
            continue
        wells = group.sort_values("issue_date")
        pads.append({
            "operator": op, "county": county, "pad": stem,
            "well_count": len(group),
            "wells": [
                {"well_num": r["well_num"], "date": r["issue_date"].date().isoformat()}
                for _, r in wells.iterrows() if pd.notna(r["issue_date"])
            ],
            "gaps": well_number_gaps(wells["well_num"].tolist()),
        })
    pads.sort(key=lambda p: -p["well_count"])
    return pads


def operator_inventory(df, operator, county=None):
    """All known pads (lease stems) for one operator, optionally restricted to
    one county, with well counts -- the running 'X-pack' inventory list."""
    sub = df[df["operator"] == operator]
    if county:
        sub = sub[sub["county"] == county.upper()]
    if sub.empty:
        return []
    sub = sub.copy()
    sub["_stem"] = sub["well_name"].map(lease_stem)
    sub = sub[sub["_stem"] != ""]
    counts = sub.groupby(["county", "_stem"])["well_num"].nunique()
    return [
        {"county": c, "pad": stem, "well_count": int(n)}
        for (c, stem), n in counts.sort_values(ascending=False).items()
    ]


def detect_fresh_spuds(current, snapshot):
    """Permits present in both current and snapshot where spud_date was blank
    in the snapshot but is populated now."""
    if snapshot is None:
        return current.iloc[0:0]
    prev = snapshot.set_index("key")
    both = current[current["key"].isin(prev.index)].copy()
    if both.empty:
        return both
    prev_spud = prev.loc[both["key"], "spud_date"]
    was_blank = prev_spud.isna().values
    now_set = both["spud_date"].notna().values
    return both[was_blank & now_set]


def new_since_snapshot(current, snapshot):
    if snapshot is None:
        return current
    known = set(snapshot["key"])
    return current[~current["key"].isin(known)]


def daily_board(new_df, top_n=8):
    if new_df.empty:
        return []
    counts = new_df.groupby(["operator", "county"]).size().sort_values(ascending=False)
    return [{"operator": op, "county": county, "count": int(n)}
            for (op, county), n in counts.head(top_n).items()]


def watchlist_candidates(new_df, known_operators, families, min_count=WATCHLIST_MIN_DAY_PERMITS):
    if new_df.empty:
        return []
    candidates = []
    counts = new_df.groupby(["operator", "county"]).size()
    for (op, county), n in counts.items():
        if n < min_count:
            continue
        if family_of(op, families):
            continue  # already a tracked family, not a new-name watch item
        candidates.append({"operator": op, "county": county, "count": int(n),
                           "known_before_this_pull": op in known_operators})
    candidates.sort(key=lambda c: -c["count"])
    return candidates


def client_watch(df, families, corridor_counties, asof, min_age_days=AGING_MIN_DAYS):
    """Aging unspudded permits for watched operator families, restricted to
    corridor counties so this isn't just 'every slow permit anywhere.'"""
    watched = df[df["operator"].map(lambda o: family_of(o, families) is not None)]
    watched = watched[watched["county"].isin(corridor_counties)]
    unspudded = watched[watched["spud_date"].isna() & watched["issue_date"].notna()]
    unspudded = unspudded.copy()
    unspudded["age_days"] = (asof - unspudded["issue_date"]).dt.days
    unspudded = unspudded[unspudded["age_days"] >= min_age_days]
    unspudded = unspudded.sort_values("age_days", ascending=False)
    return [
        {"operator": r["operator"], "county": r["county"], "well_name": r["well_name"],
         "well_num": r["well_num"], "issue_date": r["issue_date"].date().isoformat(),
         "age_days": int(r["age_days"]), "status": r["status"]}
        for _, r in unspudded.iterrows()
    ]


def build_evidence(cfg, asof: pd.Timestamp) -> dict:
    families = cfg["operator_families"]
    all_corridor_counties = set()
    for corridor in cfg["corridors"].values():
        all_corridor_counties |= {str(c).upper() for c in corridor.get("tx", [])}
        all_corridor_counties |= {str(c).upper() for c in corridor.get("la", [])}

    evidence = {"run_date": asof.date().isoformat(), "states": {}}

    for state, normalize_fn in (("tx", normalize_tx), ("la", normalize_la)):
        master = load_master(cfg, state)
        if master is None:
            evidence["states"][state] = {"error": "no master.csv found"}
            continue
        df = normalize_fn(master)
        snapshot = load_snapshot(cfg, state)
        known_operators = set(snapshot["operator"]) if snapshot is not None else set()

        new_df = new_since_snapshot(df, snapshot)
        fresh_spuds = detect_fresh_spuds(df, snapshot)
        pads = cluster_pads(df, asof)
        board = daily_board(new_df)
        watchlist = watchlist_candidates(new_df, known_operators, families)
        watch = client_watch(df, families, all_corridor_counties, asof)

        # Named inventory only for operators who actually moved since the last
        # snapshot -- computing it for every operator in the master would be
        # thousands of pads nobody asked about.
        active_operators = sorted(set(new_df["operator"]) | set(fresh_spuds["operator"]))
        inventory = {}
        for op in active_operators:
            counties_hit = set(new_df[new_df["operator"] == op]["county"]) | \
                           set(fresh_spuds[fresh_spuds["operator"] == op]["county"])
            for county in counties_hit:
                if county not in all_corridor_counties:
                    continue
                key = f"{op} / {county}"
                inventory[key] = operator_inventory(df, op, county)

        evidence["states"][state] = {
            "total_rows": len(df),
            "latest_issue_date": df["issue_date"].max().date().isoformat() if df["issue_date"].notna().any() else None,
            "new_since_last_run": len(new_df),
            "new_permits": [
                {"operator": r["operator"], "county": r["county"], "well_name": r["well_name"],
                 "well_num": r["well_num"],
                 "issue_date": r["issue_date"].date().isoformat() if pd.notna(r["issue_date"]) else None}
                for _, r in new_df.iterrows()
            ],
            "fresh_spuds": [
                {"operator": r["operator"], "county": r["county"], "well_name": r["well_name"],
                 "well_num": r["well_num"], "spud_date": r["spud_date"].date().isoformat()}
                for _, r in fresh_spuds.iterrows()
            ],
            "pads": pads,
            "daily_board": board,
            "watchlist_candidates": watchlist,
            "client_watch_aging": watch,
            "operator_inventory": inventory,
        }

        evidence["_snapshots"] = evidence.get("_snapshots", {})
        evidence["_snapshots"][state] = df  # stashed for the caller to persist after writing evidence

    return evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--out", default=None)
    parser.add_argument("--dry-run", action="store_true", help="Skip snapshot update")
    args = parser.parse_args()

    cfg = load_cfg(args.config)
    asof = pd.Timestamp(dt.date.today())

    evidence = build_evidence(cfg, asof)
    snapshots = evidence.pop("_snapshots", {})

    out_path = Path(args.out) if args.out else (
        ROOT / "data" / "intel_insight" / f"{asof.date().isoformat()}.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(evidence, indent=2, default=str), encoding="utf-8")
    print(f"Evidence written: {out_path}")

    if not args.dry_run:
        for state, df in snapshots.items():
            save_snapshot(cfg, state, df)
        print("Snapshots updated.")
    else:
        print("--dry-run: snapshots not updated.")


if __name__ == "__main__":
    main()
