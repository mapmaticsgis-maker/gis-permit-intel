import os, json, hashlib, datetime as dt
import pandas as pd, yaml

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

def diff(master, today, key="id", change_cols=("operator","depth","wellbore","well","lease")):
    """Return (new_records, amended_records, resurfaced) vs master."""
    today = today.dropna(subset=[key]).copy()
    today[key] = today[key].astype(str)
    if master is None or master.empty:
        return today, today.iloc[0:0], today.iloc[0:0]
    master = master.copy(); master[key] = master[key].astype(str)
    known = set(master[key])
    new = today[~today[key].isin(known)].copy()
    both = today[today[key].isin(known)].copy()
    if len(both):
        mh = master.set_index(key); mh = mh[~mh.index.duplicated()]
        both["_h_new"] = row_hash(both, change_cols)
        old = mh.loc[both[key]].reset_index()
        both["_h_old"] = row_hash(old, change_cols).values
        amended = both[both["_h_new"] != both["_h_old"]].drop(columns=["_h_new","_h_old"])
    else:
        amended = today.iloc[0:0]
    return new, amended, today.iloc[0:0]

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

def write_outputs(cfg, state, new, amended, digest_text):
    day = dt.date.today().isoformat()
    outd = os.path.join(cfg["data_dir"], state, "out", day); os.makedirs(outd, exist_ok=True)
    new.to_csv(os.path.join(outd, "new_permits.csv"), index=False)
    amended.to_csv(os.path.join(outd, "amendments.csv"), index=False)
    with open(os.path.join(outd, "digest.md"), "w", encoding="utf-8") as f: f.write(digest_text)
    # GeoJSON when coordinates exist
    latc = "shl_lat" if "shl_lat" in new.columns else "lat"
    lonc = "shl_lon" if "shl_lon" in new.columns else "lon"
    pts = new.dropna(subset=[latc, lonc]) if latc in new.columns else new.iloc[0:0]
    if len(pts):
        gj = {"type":"FeatureCollection","features":[
            {"type":"Feature","geometry":{"type":"Point","coordinates":[float(r[lonc]),float(r[latc])]},
             "properties":{k:(None if pd.isna(v) else str(v)) for k,v in r.items() if not k.startswith("_")}}
            for _, r in pts.iterrows()]}
        with open(os.path.join(outd,"new_permits.geojson"),"w") as f: json.dump(gj,f)
    return outd
