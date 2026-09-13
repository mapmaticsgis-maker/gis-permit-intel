r"""
New oil & gas lease filings, from Enverus LandTrac's point-based "Leases"
layer -- exported manually and dropped into data/enverus_lease_point/
(no public API for this; see LandTrac's Map View -> Map Tools -> Download
Shape File). This is the earliest-available BD signal in the whole
pipeline: a lease filing usually precedes a drilling permit by months.

The user's export is a ROLLING 3-MONTH WINDOW (LA + TX combined), pulled
fresh every day -- not an incremental "new since last time" file, so
day-to-day exports overlap heavily by design. That means dedup has to
happen at the row level, not the file level: a persistent store of
content-hashes for every lease row ever seen
(data/enverus_leases/seen_hashes.csv), so each day's digest only reports
rows whose hash isn't already in that store, regardless of how much of
the 3-month window is a repeat of yesterday's. The file-ingestion ledger
(data/enverus_leases/ledger.csv) is kept alongside it purely as an audit
trail of which files were processed when -- it does not gate processing,
since reprocessing the same file is already harmless (every row in it
would already be in seen_hashes.csv).

Schema confirmed 2026-09-13 against a real LandTrac LA export (41 columns
in the full-history version of this export; the same core columns are
used here regardless of window length). Key fields: State/Province,
County/Parish, DI Basin, DI Play, Grantor, Grantee, Grantee Alias,
Record Number, Instrument Type, Instrument Date, Record Date, Bonus,
Royalty, Term (Months), Area (Acres). Record Date lagged actual county
recording by ~6 weeks in that sample -- an early signal, not same-day.

This runs locally (wherever the user drops the daily export) and commits
its own output, the same way auto_download_subscriptions.py does for W-1
plats -- GitHub Actions has no access to this machine's filesystem, so
run_daily_ci.py can only include today's lease digest in the Enverus
Intel email if this script has already pushed it to the repo first.

Run:  python enverus_leases_pull.py
"""
import datetime as dt
import glob
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd

# Task Scheduler doesn't guarantee a working directory the way an
# interactive shell does -- load_cfg("config.yaml") and every relative
# data_dir path in this script assume cwd is the project root. Same fix
# every other Task-Scheduler-run script here already applies (see
# auto_download_subscriptions.py).
SCRIPT_DIR = Path(__file__).resolve().parent
os.chdir(SCRIPT_DIR)

from local_env import load_env
load_env()

from common import load_cfg, family_of, row_hash
from core.ledger import append_ingestion, hash_file

LEASE_DIR_NAME = "enverus_lease_point"  # matches the folder the user already created
LEDGER_STATE = "enverus_leases"

# Same regenerated-by-a-separate-local-task drift as auto_download_subscriptions.py
# guards against -- an unrelated arcpy job on this machine touches these paths.
KNOWN_DRIFT_PATHS = ["data/tx/master.csv", "data/tx/ledger.csv",
                      "data/la/master.csv", "data/la/ledger.csv"]
KNOWN_DRIFT_OUTPUT_DIRS = ["data/la/out/", "data/tx/out/"]


def _clear_known_local_drift():
    subprocess.run(["git", "checkout", "--", *KNOWN_DRIFT_PATHS],
                    cwd=str(SCRIPT_DIR), capture_output=True, timeout=30)
    subprocess.run(["git", "clean", "-fd", "--", *KNOWN_DRIFT_OUTPUT_DIRS],
                    cwd=str(SCRIPT_DIR), capture_output=True, timeout=30)


def git_commit_and_push(paths: list[Path]) -> bool:
    """Commits and pushes this run's outputs. Mirrors
    auto_download_subscriptions.py's git_commit_and_push -- same
    non-fast-forward recovery, since GitHub Actions' own automated commits
    routinely land on origin between this running and the push."""
    try:
        subprocess.run(["git", "add", *[str(p) for p in paths]],
                        cwd=str(SCRIPT_DIR), check=True, capture_output=True, timeout=30)
        result = subprocess.run(["git", "diff", "--staged", "--quiet"],
                                 cwd=str(SCRIPT_DIR), capture_output=True, timeout=10)
        if result.returncode == 0:
            print("Nothing new to commit (lease outputs unchanged or already committed)")
            return True
        subprocess.run(["git", "commit", "-m", f"Enverus lease filings: {dt.date.today().isoformat()}"],
                        cwd=str(SCRIPT_DIR), check=True, capture_output=True, timeout=30)
        try:
            subprocess.run(["git", "push"], cwd=str(SCRIPT_DIR), check=True,
                            capture_output=True, timeout=60)
        except subprocess.CalledProcessError:
            _clear_known_local_drift()
            subprocess.run(["git", "pull", "--no-edit"], cwd=str(SCRIPT_DIR),
                            check=True, capture_output=True, timeout=60)
            subprocess.run(["git", "push"], cwd=str(SCRIPT_DIR), check=True,
                            capture_output=True, timeout=60)
        return True
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode(errors="replace") if e.stderr else str(e)
        print(f"Git operation failed: {stderr}")
        return False

DISPLAY_COLUMNS = [
    "State/Province", "County/Parish", "DI Basin", "DI Play",
    "Grantor", "Grantee", "Grantee Alias", "Record Number",
    "Instrument Type", "Instrument Date", "Record Date",
    "Bonus", "Royalty", "Term (Months)", "Area (Acres)",
]
NUMERIC_COLUMNS = ["Area (Acres)", "Royalty", "Bonus"]


def _seen_path(cfg) -> Path:
    return Path(cfg["data_dir"]) / LEDGER_STATE / "seen_hashes.csv"


def _load_seen(cfg) -> set:
    p = _seen_path(cfg)
    if not p.exists():
        return set()
    return set(pd.read_csv(p, dtype=str)["lease_hash"])


def _append_seen(cfg, new_hashes: pd.Series) -> None:
    p = _seen_path(cfg)
    p.parent.mkdir(parents=True, exist_ok=True)
    today = dt.date.today().isoformat()
    out = pd.DataFrame({"lease_hash": new_hashes, "first_seen_date": today})
    out.to_csv(p, mode="a", header=not p.exists(), index=False)


def _newest_files(lease_dir: Path) -> list[Path]:
    """All CSVs currently in the folder, newest first. No file-hash skip
    gate here (see module docstring) -- the row-level hash store is what
    actually prevents double-reporting; this just decides processing
    order when more than one file is present."""
    return sorted((Path(p) for p in glob.glob(str(lease_dir / "*.[Cc][Ss][Vv]"))),
                  key=lambda p: p.stat().st_mtime, reverse=True)


def _load(path: Path) -> pd.DataFrame:
    """Loads every column LandTrac exports, not just the ones the digest
    displays. Confirmed 2026-09-13 against a real file: two rows can share
    the same grantor/grantee/record-number/dates and still be genuinely
    different tracts (different Section/Township/Range, different lat/
    long) -- hashing only the display subset collapsed 2142 of 4944 rows
    together, most of them NOT true duplicates. Hashing every column that
    exists in the export is the only way to be sure "identical row" means
    the same tract, not just the same instrument."""
    df = pd.read_csv(path, encoding="utf-8-sig", dtype=str)
    for c in DISPLAY_COLUMNS:
        if c not in df.columns:
            df[c] = None
    return df


def build_digest(df: pd.DataFrame, cfg) -> str:
    if df.empty:
        return "# New Lease Filings\n\n_No new lease filings since the last check._"

    fams = cfg["operator_families"]
    df = df.copy()
    df["_fam"] = df["Grantee Alias"].fillna(df["Grantee"]).map(lambda o: family_of(str(o), fams))

    L = [f"# New Lease Filings — {dt.date.today():%a %b %d %Y}",
         f"\n**{len(df)} new lease record(s)** since the last check, "
         f"across {df['County/Parish'].nunique()} counties/parishes."]

    watched = df[df["_fam"].notna()]
    if len(watched):
        L.append("\n## Watched-family lessees")
        for fam, g in watched.groupby("_fam"):
            total_acres = g["Area (Acres)"].sum()
            L.append(f"\n### {fam} — {len(g)} lease(s), {total_acres:,.1f} acres")
            for _, r in g.sort_values("Record Date", ascending=False).head(20).iterrows():
                royalty_str = f", {r['Royalty']:.4f} royalty" if pd.notna(r["Royalty"]) else ""
                acres_str = f", {r['Area (Acres)']:.1f} ac" if pd.notna(r["Area (Acres)"]) else ""
                L.append(f"- {r['Record Date']} — **{r['Grantor']}** -> {r['Grantee']} "
                         f"({str(r['County/Parish']).title()}{acres_str}{royalty_str})")

    L.append("\n## By county/parish")
    for county, g in df.groupby("County/Parish"):
        acres = g["Area (Acres)"].sum()
        top = g["Grantee Alias"].fillna(g["Grantee"]).value_counts().head(3)
        top_str = ", ".join(f"{name} ({n})" for name, n in top.items())
        L.append(f"- **{str(county).title()}**: {len(g)} lease(s), {acres:,.1f} acres -- top lessees: {top_str}")

    plays = df["DI Play"].dropna()
    if len(plays):
        L.append("\n## By play")
        for play, n in plays.value_counts().head(10).items():
            L.append(f"- {play}: {n}")

    return "\n".join(L)


def main() -> int:
    cfg = load_cfg()
    lease_dir = Path(cfg["data_dir"]) / LEASE_DIR_NAME
    lease_dir.mkdir(parents=True, exist_ok=True)
    today = dt.date.today().isoformat()
    outd = lease_dir / "out" / today
    outd.mkdir(parents=True, exist_ok=True)

    files = _newest_files(lease_dir)
    if not files:
        text = "# New Lease Filings\n\n_No lease export file found in data/enverus_lease_point/._"
        (outd / "digest.md").write_text(text, encoding="utf-8")
        print("No lease export files found.")
        print(text)
        return 0

    # Only the newest file matters for content -- it's a rolling window,
    # so an older same-day file is a strict subset of concern. Still
    # ingest all of them into the audit ledger so the record is complete.
    combined_raw = []
    for path in files:
        df = _load(path)
        combined_raw.append(df)
        append_ingestion(
            cfg["data_dir"], LEDGER_STATE,
            source_name=path.name, sha256=hash_file(path),
            ingested_at=dt.datetime.now().isoformat(timespec="seconds"),
            records_parsed=len(df), new=0, amended=0, resurfaced=0,
        )
        print(f"Ingested {path.name}: {len(df)} rows")

    combined = pd.concat(combined_raw, ignore_index=True)
    combined["_hash"] = row_hash(combined, list(combined.columns))
    combined = combined.drop_duplicates("_hash")

    seen = _load_seen(cfg)
    new_rows = combined[~combined["_hash"].isin(seen)].copy()
    # Only the genuinely new hashes -- appending combined's full set every run
    # (this session's first version of this script did exactly that) re-adds
    # thousands of already-seen hashes daily, since most of a rolling-window
    # export repeats yesterday's. Confirmed via a real second run: it grew
    # seen_hashes.csv by 4179 duplicate rows for zero new leases.
    if len(new_rows):
        _append_seen(cfg, new_rows["_hash"])

    new_rows = new_rows.drop(columns=["_hash"])
    for c in NUMERIC_COLUMNS:
        new_rows[c] = pd.to_numeric(new_rows[c], errors="coerce")
    new_rows.to_csv(outd / "new_leases.csv", index=False)

    text = build_digest(new_rows, cfg)
    text += ("\n\n---\n_Source: Enverus LandTrac (point-based Leases layer), manually exported daily "
              "as a rolling 3-month LA+TX window -- not part of the automated Enverus Developer API "
              "pull above. Record Date lags actual county recording by roughly 6 weeks in past "
              f"samples -- an early signal, not same-day. {len(combined)} total rows in today's "
              f"export window, {len(new_rows)} not previously seen._")
    (outd / "digest.md").write_text(text, encoding="utf-8")

    print(f"Total rows in window: {len(combined)} | new since last check: {len(new_rows)}")
    print(f"outputs: {outd}")
    print(text)

    pushed = git_commit_and_push([
        outd / "digest.md", outd / "new_leases.csv",
        _seen_path(cfg), Path(cfg["data_dir"]) / LEDGER_STATE / "ledger.csv",
    ])
    if not pushed:
        print("WARNING: lease outputs were NOT pushed -- today's Enverus Intel email "
              "will not include this section until this is resolved.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
