"""TX RRC daily pull -> diff -> digest.
Mode A: config texas.fetch_url set -> download automatically.
Mode B: newest file in texas.watch_dir (your manual download).
Run:  python tx_pull.py
"""
import os, glob, sys, io, requests, pandas as pd
from common import load_cfg, norm, load_master, save_master, diff, write_outputs
from digest import build_digest

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
    new, amended, _ = diff(master, today)
    known_ops = set(master["operator"].dropna()) if master is not None else set()
    new["first_seen"] = ~new["operator"].isin(known_ops)
    text = build_digest("Texas RRC", new, amended, cfg, "tx", "county")
    outd = write_outputs(cfg, "tx", new, amended, text)
    save_master(cfg, "tx", pd.concat([master, today], ignore_index=True).drop_duplicates("id", keep="last")
                if master is not None else today)
    print(f"source: {src}\nnew: {len(new)}  amended: {len(amended)}\noutputs: {outd}")
    print("\n" + text)

if __name__ == "__main__": main()
