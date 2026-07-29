"""Louisiana SONRIS daily pull -> diff -> digest.
Mode A: ArcGIS REST query (louisiana.rest_url) for permits since last run.
Mode B: ORDS CSV export URL. Mode C: watch_dir manual drop.
Run:  python la_pull.py
"""
import sys, os, glob, datetime as dt, requests, pandas as pd
try:
    sys.stdout.reconfigure(encoding="utf-8")  # clean em-dashes on Windows consoles
except Exception:
    pass
from common import load_cfg, norm, load_master, save_master, write_outputs
from core.diff import assert_usable_key, diff as core_diff
from core.ledger import append_ingestion, find_ingestion, hash_text
from digest import build_digest

LA_CHANGE_COLS = ["operator", "depth", "well", "status", "field"]

# Identifier columns must survive the day-file round-trip as text. A well
# serial number, API number, or section/township/range read back as a number
# loses leading zeros and gains a ".0"; both reach digest.md and the dashboard.
# `depth` is deliberately absent -- digest._fmt_depth formats it with :.0f and
# raises ValueError on a string.
LA_ID_COLS = {"id": str, "api": str, "well_num": str,
              "section": str, "township": str, "range": str}

def fetch_rest(cfg):
    la = cfg["louisiana"]
    today_ts = pd.Timestamp(dt.date.today())
    # Fixed 45-day lookback rather than deriving "since" from master's max
    # issue_date. That approach broke two ways: (1) SONRIS carries a legacy
    # well with a PERMIT_DATE years in the future (garbage placeholder on an
    # old P&A'd well), which pushed the computed "since" past today and
    # required a guard/fallback; (2) even the fallback (7 days) was too
    # narrow -- cross-checked against an Enverus permit export on 2026-07-28
    # and found 5 real permits (PERMIT_DATE 07-16/07-17) that SONRIS hadn't
    # surfaced into this queryable layer until well after their nominal
    # date, so any "since" window under ~2 weeks silently drops them forever
    # (diff() only catches genuinely new ids -- once a pull window passes a
    # permit by, it's never queried again). The full LA dataset is only
    # ~100-150 wells total, so a wide fixed window costs nothing in payload
    # size and removes this whole bug class.
    since = today_ts - pd.Timedelta(days=45)
    since_str = since.strftime("%Y-%m-%d")
    where = f"{la['date_field']} >= DATE '{since_str}'"
    params = {"where": where, "outFields": "*", "f": "json", "returnGeometry": "false",
              "resultRecordCount": 2000}
    r = requests.get(la["rest_url"], params=params, timeout=120); r.raise_for_status()
    js = r.json()
    if "error" in js: sys.exit(f"REST error: {js['error']} — verify rest_url/layer id in config.")
    feats = js.get("features", [])
    rows = [dict(f.get("attributes", {})) for f in feats]
    df = pd.DataFrame(rows)
    while js.get("exceededTransferLimit") and len(feats) > 0:
        params["resultOffset"] = params.get("resultOffset", 0) + len(feats)
        r = requests.get(la["rest_url"], params=params, timeout=120); r.raise_for_status()
        js = r.json()
        feats = js.get("features", [])
        if feats:
            df = pd.concat([df, pd.DataFrame([dict(f.get("attributes", {})) for f in feats])],
                            ignore_index=True)
        else:
            break
    for c in df.columns:
        if "DATE" in c.upper():
            try: df[c] = pd.to_datetime(df[c], unit="ms", errors="coerce")
            except Exception: pass
    return df

def collapse_operator_lines(df):
    """SONRIS's Oil/Gas Wells layer carries one row per ORGOP_LINE_ID (operator-of-record
    history), not one row per well -- a well that's changed hands or been re-permitted shows
    up multiple times under the same WELL_SERIAL_NUM. Keep only the current (highest
    ORGOP_LINE_ID) row per well so the digest doesn't show the same permit 2-5x."""
    if "ORGOP_LINE_ID" in df.columns and "WELL_SERIAL_NUM" in df.columns:
        df = df.sort_values(["WELL_SERIAL_NUM", "ORGOP_LINE_ID"])
        df = df.drop_duplicates("WELL_SERIAL_NUM", keep="last")
    return df

def main():
    cfg = load_cfg(); la = cfg["louisiana"]
    if la.get("rest_url"):
        raw = fetch_rest(cfg); src = "REST"
    elif la.get("ords_csv_url"):
        raw = pd.read_csv(la["ords_csv_url"]); src = "ORDS"
    else:
        files = sorted(glob.glob(os.path.join(la["watch_dir"], "*")), key=os.path.getmtime)
        if not files: sys.exit(f"Nothing configured and nothing in {la['watch_dir']}.")
        raw = pd.read_csv(files[-1]); src = files[-1]
    if not len(raw):
        print("No records returned - check rest_url / where clause / date range."); return
    raw = collapse_operator_lines(raw)
    today = norm(raw, la["fields"])
    # WELL_SERIAL_NUM comes back as an int from the ArcGIS REST JSON, while
    # master.csv (read via load_master's dtype=str) always stores id as a
    # string. Left uncast, the merge below's drop_duplicates("id") silently
    # fails to match "255778" (str, from master) against 255778 (int, from
    # today), so old and refreshed rows for the same well both survive as
    # "different" ids -- duplicate bloat accumulates every run it happens on.
    today["id"] = today["id"].astype(str)

    assert_usable_key(today, "id")

    sha = hash_text(today.sort_values("id").to_csv(index=False))
    prior = find_ingestion(cfg["data_dir"], "la", sha)
    if prior:
        print(f"source unchanged since {prior['ingested_at']} "
              f"({prior['records_parsed']} records) -- skipping. No outputs written.")
        return

    master = load_master(cfg, "la")
    new, amended, _ = core_diff(master, today, key="id",
                                change_cols=LA_CHANGE_COLS,
                                resurfaced_after_days=None)
    known_ops = set(master["operator"].dropna()) if master is not None else set()
    new["first_seen"] = ~new["operator"].isin(known_ops)
    # The digest describes the whole day, not this run's increment: it is
    # built from the day's unioned files after the CSVs are merged, which is
    # why write_outputs takes a builder rather than finished text.
    outd, text = write_outputs(
        cfg, "la", new, amended,
        lambda day_new, day_amended: build_digest(
            "Louisiana SONRIS", day_new, day_amended, cfg, "la", "parish"),
        key="id", id_cols=LA_ID_COLS)
    base = master if master is not None else today.iloc[0:0]
    updated_master = pd.concat([base, today], ignore_index=True).drop_duplicates("id", keep="last")
    save_master(cfg, "la", updated_master)
    append_ingestion(
        cfg["data_dir"], "la",
        source_name=src, sha256=sha,
        ingested_at=dt.datetime.now().isoformat(timespec="seconds"),
        records_parsed=len(today), new=len(new),
        amended=len(amended), resurfaced=0,
    )
    print(f"source: {src}\nparsed: {len(today)}  new: {len(new)}  amended: {len(amended)}\noutputs: {outd}")
    print("\n" + text)

if __name__ == "__main__": main()
