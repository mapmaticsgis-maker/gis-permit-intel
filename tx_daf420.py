r"""
TX RRC daf420 daily pipeline — v2 (integrates Jason's proven parser + GDB build).

parse daf420 -> coordinate cache -> DIFF vs master -> digest + MTD rollup
-> (optional, inside ArcGIS Pro python) full GDB build incl. NEW-ONLY feature classes.

Run:  python tx_daf420.py [path\to\daf420.dat.MM-DD-YYYY]
      (no arg: newest daf420* in texas.watch_dir)
"""
import os, re, sys, glob, datetime as dt
import requests
from pathlib import Path
import pandas as pd
from common import load_cfg, load_master, save_master
from core.diff import assert_usable_key, diff as core_diff
from core.ledger import append_ingestion, find_ingestion, hash_file
from core.outputs import clear_skip_marker, union_write_csv, write_skip_marker
from digest import build_digest
from county_lookup import COUNTY_LOOKUP

# ---------- Jason's parser (verbatim logic) ----------
def clean(s): return re.sub(r"\s+", " ", str(s).strip())
def ymd(s):
    s = clean(s)
    if len(s) == 8 and s.isdigit() and s != "00000000":
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    return None
def coord_from_line(line):
    m = re.search(r"(-?\d+\.\d+)\s+(-?\d+\.\d+)", line)
    return (float(m.group(2)), float(m.group(1))) if m else None

def parse_rrc(dat):
    rows, current = [], None
    with open(dat, "r", encoding="utf8", errors="ignore") as f:
        for raw in f:
            line = raw.rstrip("\n"); rec = line[:2]
            if rec == "01":
                if current: rows.append(current)
                cc = clean(line[11:14]).zfill(3)
                current = {"Permit_Number": clean(line[2:9]), "CountyCode": cc,
                    "County": COUNTY_LOOKUP.get(cc, cc), "Lease_Name": clean(line[14:46]),
                    "District": clean(line[46:48]), "Operator_Number": clean(line[48:54]),
                    "Received_Date": ymd(line[58:66]), "Operator_Name": clean(line[66:98]),
                    "Well_Number": None, "Total_Depth": None, "Issue_Date": None,
                    "Spud_Date": None, "Surface_Lat": None, "Surface_Lon": None,
                    "BHL_Lat": None, "BHL_Lon": None}
            elif current is None: continue
            elif rec == "02":
                current["Well_Number"] = clean(line[48:54])
                td = clean(line[54:59])
                if td.isdigit(): current["Total_Depth"] = int(td)
                current["Issue_Date"] = ymd(line[129:137])
                current["Spud_Date"] = ymd(line[153:161])
            elif rec == "14":
                c = coord_from_line(line)
                if c: current["Surface_Lat"], current["Surface_Lon"] = c
            elif rec == "15":
                c = coord_from_line(line)
                if c: current["BHL_Lat"], current["BHL_Lon"] = c
    if current: rows.append(current)
    return pd.DataFrame(rows)

# ---------- coordinate cache (Jason's, unchanged behavior) ----------
def apply_coordinate_cache(df_all, cache_csv):
    cols = ["Permit_Number","Surface_Lat","Surface_Lon","BHL_Lat","BHL_Lon"]
    cache_csv = Path(cache_csv); cache_csv.parent.mkdir(parents=True, exist_ok=True)
    df_all["Permit_Number"] = df_all["Permit_Number"].astype(str)
    cache = pd.read_csv(cache_csv, dtype={"Permit_Number": str}) if cache_csv.exists() \
            else pd.DataFrame(columns=cols)
    for c in cols:
        if c not in cache.columns: cache[c] = None
    today = df_all[df_all[cols[1:]].notna().any(axis=1)][cols].copy()
    cache = pd.concat([cache, today], ignore_index=True)
    for c in cols[1:]: cache[c] = pd.to_numeric(cache[c], errors="coerce")
    cache = cache.groupby("Permit_Number", as_index=False).agg({c: "last" for c in cols[1:]})
    cache.to_csv(cache_csv, index=False)
    df_all = df_all.merge(cache, on="Permit_Number", how="left", suffixes=("", "_c"))
    for c in cols[1:]:
        df_all[c] = df_all[c].combine_first(df_all[f"{c}_c"]); df_all.drop(columns=[f"{c}_c"], inplace=True)
    return df_all



# ---------- diff + intel ----------
CHANGE_COLS = ["Operator_Name", "Well_Number", "Total_Depth",
               "Issue_Date", "Spud_Date", "Lease_Name"]


def diff_master(master, today):
    return core_diff(master, today, key="Permit_Number",
                     change_cols=CHANGE_COLS, resurfaced_after_days=7)

def mtd_rollup(master, cfg):
    from common import family_of
    m = master.copy()
    m["Issue_Date"] = pd.to_datetime(m["Issue_Date"], errors="coerce")
    now = pd.Timestamp.now(); mtd = m[(m.Issue_Date.dt.month == now.month) & (m.Issue_Date.dt.year == now.year)]
    if not len(mtd): return "_No issued permits recorded this month yet._"
    L = [f"## Month-to-date ({now:%B %Y}) — {len(mtd)} permits issued"]
    L.append("\n**By county (top 12):**")
    for c, n in mtd.County.value_counts().head(12).items(): L.append(f"- {str(c).title()}: {n}")
    L.append("\n**By operator (top 12):**")
    for o, n in mtd.Operator_Name.value_counts().head(12).items(): L.append(f"- {o}: {n}")
    fams = mtd.Operator_Name.map(lambda o: family_of(str(o), cfg["operator_families"]))
    fam_counts = fams.value_counts()
    if len(fam_counts):
        L.append("\n**Watched families MTD:**")
        for f, n in fam_counts.items(): L.append(f"- {f}: {n}")
    sp = mtd[pd.to_datetime(mtd.Spud_Date, errors="coerce").notna()].copy()
    if len(sp):
        sp["cycle_days"] = (pd.to_datetime(sp.Spud_Date) - sp.Issue_Date).dt.days
        hot = sp[sp.cycle_days.between(0, 14)]
        if len(hot):
            L.append("\n**Hot cycles (spud <=14 days after issue):**")
            for _, r in hot.iterrows():
                L.append(f"- {r.Operator_Name} — {r.Lease_Name} {r.Well_Number} ({str(r.County).title()}): "
                         f"issued {r.Issue_Date:%m/%d}, spud {pd.to_datetime(r.Spud_Date):%m/%d} ({r.cycle_days}d)")
    return "\n".join(L)

# ---------- ArcGIS build: direct da.InsertCursor writes (bypasses the broken GP-tool/
# scratch-workspace environment on this machine -- ERROR 161025 on TableToTable/XYTableToPoint
# even against a brand-new GDB, confirmed to survive a full reboot). Falls back to shapefiles
# if arcpy itself is unavailable (e.g. running outside ArcGIS Pro's python). ----------
_GDB_FIELDS = [("Permit_Number","TEXT",16),("County","TEXT",24),("District","TEXT",4),
               ("Operator_Name","TEXT",64),("Operator_Number","TEXT",10),("Lease_Name","TEXT",64),
               ("Well_Number","TEXT",12),("Total_Depth","LONG",None),("Received_Date","TEXT",12),
               ("Issue_Date","TEXT",12),("Spud_Date","TEXT",12)]

def _write_gdb_cursors(gdb, name, df, geom):
    """geom: None=table | 'point_shl' | 'point_bhl' | 'line'."""
    import arcpy
    fc = gdb + "\\" + name
    if arcpy.Exists(fc): arcpy.management.Delete(fc)
    sr = arcpy.SpatialReference(4326)
    if geom is None:
        arcpy.management.CreateTable(gdb, name)
    else:
        arcpy.management.CreateFeatureclass(gdb, name,
            "POINT" if geom.startswith("point") else "POLYLINE", spatial_reference=sr)
    for fn, ft, ln in _GDB_FIELDS:
        arcpy.management.AddField(fc, fn, ft, field_length=ln)
    cols = [f[0] for f in _GDB_FIELDS]
    curs_fields = (["SHAPE@XY"] if geom and geom.startswith("point") else
                   ["SHAPE@"] if geom == "line" else []) + cols
    with arcpy.da.InsertCursor(fc, curs_fields) as cur:
        for _, r in df.iterrows():
            attrs = []
            for c in cols:
                v = r.get(c)
                if pd.isna(v): v = None
                elif c == "Total_Depth":
                    try: v = int(float(v))
                    except Exception: v = None
                else: v = str(v)[:64]
                attrs.append(v)
            if geom == "point_shl":
                if pd.isna(r.Surface_Lat) or pd.isna(r.Surface_Lon): continue
                row = [(float(r.Surface_Lon), float(r.Surface_Lat))] + attrs
            elif geom == "point_bhl":
                if pd.isna(r.BHL_Lat) or pd.isna(r.BHL_Lon): continue
                row = [(float(r.BHL_Lon), float(r.BHL_Lat))] + attrs
            elif geom == "line":
                if pd.isna(r.Surface_Lat) or pd.isna(r.BHL_Lat): continue
                arr = arcpy.Array([arcpy.Point(float(r.Surface_Lon), float(r.Surface_Lat)),
                                   arcpy.Point(float(r.BHL_Lon), float(r.BHL_Lat))])
                row = [arcpy.Polyline(arr, sr)] + attrs
            else:
                row = attrs
            cur.insertRow(row)

def _write_shapefiles(outdir, tag, df, date_tag):
    import shapefile
    outdir.mkdir(parents=True, exist_ok=True)
    prj = ('GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137,298.257223563]],'
           'PRIMEM["Greenwich",0],UNIT["Degree",0.017453292519943295]]')
    lns = df[df.Surface_Lat.notna() & df.BHL_Lat.notna()]
    if len(lns):
        w = shapefile.Writer(str(outdir / f"Permit_Lines_{tag}_{date_tag}"), shapeType=shapefile.POLYLINE)
        w.field("PERMIT","C",16); w.field("COUNTY","C",24); w.field("OPERATOR","C",64)
        w.field("LEASE","C",64); w.field("WELL","C",12); w.field("TD","N",10)
        w.field("ISSUE_DT","C",12); w.field("SPUD_DT","C",12)
        for _, r in lns.iterrows():
            w.line([[[float(r.Surface_Lon), float(r.Surface_Lat)], [float(r.BHL_Lon), float(r.BHL_Lat)]]])
            w.record(str(r.Permit_Number), str(r.County), str(r.Operator_Name)[:64], str(r.Lease_Name)[:64],
                      str(r.Well_Number)[:12], int(r.Total_Depth) if pd.notna(r.Total_Depth) else 0,
                      str(r.Issue_Date), str(r.Spud_Date))
        w.close()
        with open(outdir / f"Permit_Lines_{tag}_{date_tag}.prj", "w") as f: f.write(prj)
    pts = df[df.Surface_Lat.notna() & df.Surface_Lon.notna()]
    if len(pts):
        w = shapefile.Writer(str(outdir / f"Permit_Surface_{tag}_{date_tag}"), shapeType=shapefile.POINT)
        w.field("PERMIT","C",16); w.field("COUNTY","C",24); w.field("OPERATOR","C",64)
        for _, r in pts.iterrows():
            w.point(float(r.Surface_Lon), float(r.Surface_Lat))
            w.record(str(r.Permit_Number), str(r.County), str(r.Operator_Name)[:64])
        w.close()
        with open(outdir / f"Permit_Surface_{tag}_{date_tag}.prj", "w") as f: f.write(prj)

def build_arcgis(cfg, df_all, df_lines, df_new, date_tag):
    gdb = str(Path(cfg["texas"]["gdb"]))
    jobs = [("FULL", df_all), ("NEW", df_new)]
    try:
        import arcpy
        gdbp = Path(gdb)
        if not gdbp.exists():
            arcpy.management.CreateFileGDB(str(gdbp.parent), gdbp.name)
        arcpy.env.overwriteOutput = True
        for tag, df in jobs:
            if not len(df): continue
            _write_gdb_cursors(gdb, "Permit_Table_" + tag + "_" + date_tag, df, None)
            _write_gdb_cursors(gdb, "Permit_Surface_" + tag + "_" + date_tag, df, "point_shl")
            _write_gdb_cursors(gdb, "Permit_BHL_" + tag + "_" + date_tag, df, "point_bhl")
            _write_gdb_cursors(gdb, "Permit_Lines_" + tag + "_" + date_tag, df, "line")
        print("GDB build complete (cursor writes): " + gdb)
        return
    except Exception as e:
        print("GDB cursor build failed (" + str(e).splitlines()[0] + ") -- falling back to shapefiles.")
    shp_dir = Path(cfg["data_dir"]) / "tx" / "out" / dt.date.today().isoformat() / "shp"
    try:
        for tag, df in jobs:
            if len(df): _write_shapefiles(shp_dir, tag, df, date_tag)
        print("Shapefile fallback written: " + str(shp_dir) + "  (add directly in Pro)")
    except ImportError:
        print("pyshp not installed -- run:  pip install pyshp   then rerun for shapefile fallback.")

def main():
    cfg = load_cfg(); tx = cfg["texas"]
    if len(sys.argv) > 1:
        dat = Path(sys.argv[1])
    else:
        cands = sorted(glob.glob(os.path.join(tx["watch_dir"], "daf420*")), key=os.path.getmtime)
        if not cands: sys.exit(f"No daf420 file found in {tx['watch_dir']}. Commit a dated file to inbox.")
        dat = Path(cands[-1])
    m = re.search(r"(\d{2})-(\d{2})-(\d{4})", dat.name)
    date_tag = f"{m.group(3)}{m.group(1)}{m.group(2)}" if m else dt.date.today().strftime("%Y%m%d")

    day = dt.date.today().isoformat()
    outd = Path(cfg["data_dir"]) / "tx" / "out" / day

    sha = hash_file(dat)
    prior = find_ingestion(cfg["data_dir"], "tx", sha)
    if prior:
        reason = (f"source unchanged since {prior['ingested_at']} "
                  f"({prior['source_name']}, {prior['records_parsed']} records)")
        # Leave a marker so downstream can tell "correctly skipped, source
        # unchanged" from "run failed". daf420.dat.07-26-2026 and
        # .07-27-2026 are byte-identical, so this fires every weekend.
        write_skip_marker(outd, source_name=dat.name, reason=reason, prior=prior)
        print(f"{reason} -- skipping. No new outputs written.")
        return

    df_all = parse_rrc(dat)
    if df_all.empty: sys.exit("No permit headers parsed — check file.")
    df_all = df_all.drop_duplicates(
        subset=["Permit_Number","CountyCode","Lease_Name","Operator_Number","Well_Number","Issue_Date","Spud_Date"],
        keep="first").copy()
    df_all = df_all.drop_duplicates("Permit_Number", keep="last").copy()
    assert_usable_key(df_all, "Permit_Number")
    df_all = apply_coordinate_cache(df_all, tx.get("coord_cache", "./data/tx/rrc_coordinate_cache.csv"))

    master = load_master(cfg, "tx")
    new, amended, resurfaced = diff_master(master, df_all)
    known_ops = set(master["Operator_Name"].dropna()) if master is not None else set()
    new["first_seen"] = ~new["Operator_Name"].isin(known_ops)

    new_master = pd.concat([master, df_all], ignore_index=True).drop_duplicates(
        "Permit_Number", keep="last") if master is not None else df_all

    # This run produced real output, so any earlier same-day skip marker no
    # longer describes the day.
    clear_skip_marker(outd)
    union_write_csv(new, outd / "new_permits.csv", key="Permit_Number")
    union_write_csv(amended, outd / "amendments.csv", key="Permit_Number")
    union_write_csv(resurfaced, outd / "resurfaced.csv", key="Permit_Number")

    # The digest describes the whole day, not just this run's increment --
    # RRC can publish twice in a day and the second run's `new` is smaller.
    # Identifier columns must stay text. Every permit number carries a leading
    # zero (0917214 -> 917214 if inferred), as do CountyCode (001) and
    # District (06); 693 of 693 permits are affected. Stripping them would
    # reach digest.md, which the dashboard consumes.
    # Total_Depth is deliberately NOT in this dict: digest._fmt_depth formats
    # it with :.0f and raises ValueError on a string, so a blanket dtype=str
    # would trade one bug for another.
    ID_COLS = {"Permit_Number": str, "CountyCode": str, "District": str,
               "Operator_Number": str, "Well_Number": str}
    day_new = pd.read_csv(outd / "new_permits.csv", dtype=ID_COLS)
    day_amended = pd.read_csv(outd / "amendments.csv", dtype=ID_COLS)
    day_resurfaced = pd.read_csv(outd / "resurfaced.csv", dtype=ID_COLS)

    # canonical names for the shared digest builder
    ren = {"Operator_Name":"operator","County":"county","Total_Depth":"depth",
           "Well_Number":"well","Lease_Name":"lease"}
    text = build_digest("Texas RRC (daf420)", day_new.rename(columns=ren),
                        day_amended.rename(columns=ren), cfg, "tx", "county")
    if len(day_resurfaced):
        text += "\n\n## Resurfaced older files (issue date >7d old, new to master)\n"
        text += "\n".join(f"- {r.Operator_Name} — {r.Lease_Name} {r.Well_Number} "
                          f"({str(r.County).title()}), issued {r.Issue_Date}"
                          for _, r in day_resurfaced.iterrows())
    text += "\n\n" + mtd_rollup(new_master, cfg)

    (outd/"digest.md").write_text(text, encoding="utf-8")
    save_master(cfg, "tx", new_master)

    append_ingestion(
        cfg["data_dir"], "tx",
        source_name=dat.name, sha256=sha,
        ingested_at=dt.datetime.now().isoformat(timespec="seconds"),
        records_parsed=len(df_all), new=len(new),
        amended=len(amended), resurfaced=len(resurfaced),
    )

    print(f"parsed {len(df_all)} | new {len(new)} | amended {len(amended)} | resurfaced {len(resurfaced)}")
    print(f"outputs: {outd}\n")
    print(text)
    if cfg["texas"].get("build_gdb", True):
        build_arcgis(cfg, df_all,
                     df_all[df_all.Surface_Lat.notna() & df_all.BHL_Lat.notna()],
                     pd.concat([new, amended], ignore_index=True), date_tag)

if __name__ == "__main__": main()
