"""TX RRC daily pull -> diff -> digest.

SUPERSEDED by tx_daf420.py -- do not run this for production TX intel.

It predates the daf420 fixed-width parser and expects a tabular CSV/XLSX
export mapped through config texas.fields. It is NOT wired into
run_daily_ci.py or run_daily.py, has no ingestion-ledger gate, and so gives
none of this branch's same-day re-run protection. Kept only because
README.md still documents it as the first-run bootstrap path and
config.texas.fetch_url is the download URL it was built around.

Mode A: config texas.fetch_url set -> download automatically.
Mode B: newest file in texas.watch_dir (your manual download).
Run:  python tx_pull.py
"""
import os, glob, sys, io, requests, pandas as pd
from common import load_cfg, norm, load_master, save_master, write_outputs
from core.diff import diff as core_diff
from digest import build_digest

# The change columns common.diff used to default to, now passed explicitly.
CHANGE_COLS = ("operator", "depth", "wellbore", "well", "lease")

# id/api carry leading zeros; depth stays numeric for digest._fmt_depth.
ID_COLS = {"id": str, "api": str, "well": str, "district": str}

def read_any(path_or_bytes, name=""):
    if isinstance(path_or_bytes, bytes):
        buf = io.BytesIO(path_or_bytes)
        for reader in (pd.read_csv, pd.read_excel):
            try: buf.seek(0); return reader(buf)
            except Exception: pass
        raise ValueError("Could not parse downloaded file")
    if name.lower().endswith((".xlsx",".xls")): return pd.read_excel(path_or_bytes)
    for sep in (",", "\t", "|"):
        try:
            df = pd.read_csv(path_or_bytes, sep=sep, engine="python")
            if df.shape[1] > 3: return df
        except Exception: pass
    raise ValueError(f"Could not parse {path_or_bytes}")

def main():
    cfg = load_cfg(); tx = cfg["texas"]
    if tx.get("fetch_url"):
        r = requests.get(tx["fetch_url"], timeout=120); r.raise_for_status()
        raw = read_any(r.content)
        src = "download"
    else:
        files = sorted(glob.glob(os.path.join(tx["watch_dir"], "*")), key=os.path.getmtime)
        if not files:
            sys.exit(f"No fetch_url set and nothing in {tx['watch_dir']} — drop today's RRC file there.")
        raw = read_any(files[-1], files[-1]); src = files[-1]
    today = norm(raw, tx["fields"])
    master = load_master(cfg, "tx")
    new, amended, _ = core_diff(master, today, key="id",
                                change_cols=CHANGE_COLS,
                                resurfaced_after_days=None)
    known_ops = set(master["operator"].dropna()) if master is not None else set()
    new["first_seen"] = ~new["operator"].isin(known_ops)
    outd, text = write_outputs(
        cfg, "tx", new, amended,
        lambda day_new, day_amended: build_digest(
            "Texas RRC", day_new, day_amended, cfg, "tx", "county"),
        key="id", id_cols=ID_COLS)
    save_master(cfg, "tx", pd.concat([master, today], ignore_index=True).drop_duplicates("id", keep="last")
                if master is not None else today)
    print(f"source: {src}\nnew: {len(new)}  amended: {len(amended)}\noutputs: {outd}")
    print("\n" + text)

if __name__ == "__main__": main()
