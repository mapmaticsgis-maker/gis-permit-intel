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
from common import load_cfg, norm, load_master, save_master, diff, write_outputs
from digest import build_digest

def fetch_rest(cfg):
    la = cfg["louisiana"]
    master = load_master(cfg, "la")
    today_ts = pd.Timestamp(dt.date.today())
    since = None
    if master is not None and "issue_date" in master and master["issue_date"].notna().any():
        since = pd.to_datetime(master["issue_date"], errors="coerce").max() - pd.Timedelta(days=3)
    # Guard against bad source data: SONRIS carries at least one legacy well with a
    # PERMIT_DATE years in the future (garbage placeholder on an old P&A'd well). A single
    # such record would otherwise lock "since" onto that bad date forever, starving every
    # future pull. Clip to a sane recent window if the computed value is missing or absurd.
    if since is None or pd.isna(since) or since > today_ts or since < today_ts - pd.Timedelta(days=120):
        since = today_ts - pd.Timedelta(days=7 if master is not None else 60)
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
    master = load_master(cfg, "la")
    new, amended, _ = diff(master, today, change_cols=("operator","depth","well","status","field"))
    known_ops = set(master["operator"].dropna()) if master is not None else set()
    new["first_seen"] = ~new["operator"].isin(known_ops)
    text = build_digest("Louisiana SONRIS", new, amended, cfg, "la", "parish")
    outd = write_outputs(cfg, "la", new, amended, text)
    base = master if master is not None else today.iloc[0:0]
    updated_master = pd.concat([base, today], ignore_index=True).drop_duplicates("id", keep="last")
    save_master(cfg, "la", updated_master)
    print(f"source: {src}\nparsed: {len(today)}  new: {len(new)}  amended: {len(amended)}\noutputs: {outd}")
    print("\n" + text)

if __name__ == "__main__": main()
