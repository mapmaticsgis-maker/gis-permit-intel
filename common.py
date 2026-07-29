import os, json, hashlib, datetime as dt
import pandas as pd, yaml

from core.outputs import union_write_csv

def load_cfg(path="config.yaml"):
    # encoding is explicit, not incidental. Python's default text encoding on
    # Windows is the ANSI codepage (cp1252 here), so a bare open() decoded
    # config.yaml's UTF-8 em-dash as three cp1252 chars: the corridor
    # "RROG + DOXA — NW Louisiana Haynesville" reached digest.md as
    # "RROG + DOXA â€" NW ...". That is not merely cosmetic -- "â€" is in
    # self_check.MOJIBAKE_MARKERS, so check_no_mojibake failed and a failure
    # alert fired on every day a corridor hit made it into the digest.
    with open(path, encoding="utf-8") as f: return yaml.safe_load(f)

def norm(df, fields):
    """Rename configured source columns to canonical names; keep everything else."""
    ren = {v: k for k, v in fields.items() if v and v in df.columns}
    df = df.rename(columns=ren)
    for k in fields:
        if k not in df.columns: df[k] = None
    if "operator" in df: df["operator"] = df["operator"].astype(str).str.upper().str.strip()
    return df

def master_path(cfg, state): return os.path.join(cfg["data_dir"], state, "master.csv")

def load_master(cfg, state):
    p = master_path(cfg, state)
    return pd.read_csv(p, dtype=str) if os.path.exists(p) else None

def save_master(cfg, state, df):
    p = master_path(cfg, state); os.makedirs(os.path.dirname(p), exist_ok=True)
    df.to_csv(p, index=False)

def row_hash(df, cols):
    use = [c for c in cols if c in df.columns]
    def _cell(v):
        return "" if pd.isna(v) else str(v)
    joined = df[use].apply(lambda row: "|".join(_cell(v) for v in row), axis=1)
    return joined.map(lambda s: hashlib.md5(s.encode()).hexdigest())

# common.diff removed -- core.diff.diff is the single implementation.
# core/diff.py's docstring already claimed to replace this one, but the
# consolidation left it in place with tx_pull.py still importing it, so the
# two "drifted apart" implementations the consolidation existed to merge were
# both still live. tx_pull.py now uses core.diff like every other caller.
# row_hash above is retained: it is this module's public helper and the
# removed function was its only in-repo caller, but it is not diff-specific.

def family_of(op, fams):
    if not isinstance(op, str): return None
    for f in fams.values():
        if any(a in op for a in f["aliases"]): return f["family"]
    return None

def corridor_of(row, corridors, state_key, area_field):
    a = str(row.get(area_field, "")).upper().strip()
    for name, m in corridors.items():
        if a in [str(x).upper() for x in m.get(state_key, [])]: return name
    return None

def write_outputs(cfg, state, new, amended, digest_fn, *, key, id_cols=None):
    """Write a day's outputs by UNION, then derive digest+geojson from the union.

    This was the original 2026-07-26 bug, still live on the LA path: bare
    to_csv replaced the day's files, so a second same-day run whose SONRIS
    content differed at all passed the ledger gate and overwrote the
    morning's findings with its own smaller increment. TX was fixed
    (tx_daf420.main); LA was not.

    Three things have to move together, which is why this function now owns
    all of them:

      1. The CSVs union on `key`, so a day's file means "everything detected
         on this date" rather than "whatever the last run happened to see".
      2. digest.md is built from the day's UNIONED frames, not from this
         run's increment -- otherwise the CSV says 41 and the digest says 4.
         Hence digest_fn(day_new, day_amended) rather than a pre-built string:
         the caller cannot build the right text before the union has happened.
      3. new_permits.geojson is rewritten UNCONDITIONALLY. It used to be
         written only `if len(pts)`, so a stale 12-feature geojson could sit
         beside a freshly-unioned CSV and misreport the map for the rest of
         the day. An empty FeatureCollection is a true statement; a stale one
         is not.

    id_cols: dtype map applied when re-reading the day's files. Identifier
    columns must survive as text (LA well serial numbers, section/township/
    range), while depth must stay numeric because digest._fmt_depth formats
    it with :.0f and raises ValueError on a string.
    """
    day = dt.date.today().isoformat()
    outd = os.path.join(cfg["data_dir"], state, "out", day); os.makedirs(outd, exist_ok=True)
    new_p = os.path.join(outd, "new_permits.csv")
    amended_p = os.path.join(outd, "amendments.csv")

    union_write_csv(new, new_p, key=key)
    union_write_csv(amended, amended_p, key=key)

    day_new = pd.read_csv(new_p, dtype=id_cols or {})
    day_amended = pd.read_csv(amended_p, dtype=id_cols or {})

    digest_text = digest_fn(day_new, day_amended)
    with open(os.path.join(outd, "digest.md"), "w", encoding="utf-8") as f: f.write(digest_text)

    # GeoJSON, rebuilt from the day's unioned rows
    latc = "shl_lat" if "shl_lat" in day_new.columns else "lat"
    lonc = "shl_lon" if "shl_lon" in day_new.columns else "lon"
    pts = (day_new.dropna(subset=[latc, lonc])
           if latc in day_new.columns and lonc in day_new.columns else day_new.iloc[0:0])
    gj = {"type":"FeatureCollection","features":[
        {"type":"Feature","geometry":{"type":"Point","coordinates":[float(r[lonc]),float(r[latc])]},
         "properties":{k:(None if pd.isna(v) else str(v)) for k,v in r.items() if not k.startswith("_")}}
        for _, r in pts.iterrows()]}
    with open(os.path.join(outd,"new_permits.geojson"),"w",encoding="utf-8") as f: json.dump(gj,f)
    return outd, digest_text
