import json
import sys
from collections import defaultdict
from pathlib import Path

from openpyxl import Workbook

RAW_HEADERS = ["Client", "MXD Path", "Layer Name", "Data Source", "Source Exists"]
SHARED_HEADERS = ["Data Source", "Reference Count", "Referencing MXDs", "In Client Folder?"]
FLAGS_HEADERS = ["Client", "MXD Path", "Layer Name", "Data Source", "Flag Type"]

DEFAULT_RAW_PATH = Path("data/mxd_inventory/raw_inventory.json")
DEFAULT_OUTPUT_PATH = Path(r"C:\GIS\CLIENT\RROG_DOXA_Datasource_Inventory.xlsx")


def classify_source(client, data_source, source_exists, client_roots):
    if not source_exists:
        return "Broken"
    normalized = data_source.replace("/", "\\").lower()
    own_root = client_roots[client].lower()
    if normalized.startswith(own_root):
        return None
    for other_client, root in client_roots.items():
        if other_client != client and normalized.startswith(root.lower()):
            return "Cross-Client"
    if not normalized.startswith(r"c:\gis"):
        return "Outside C:\\GIS"
    return None


def group_shared_sources(records):
    by_source = defaultdict(set)
    client_roots_seen = defaultdict(set)
    for r in records:
        by_source[r["data_source"]].add(r["mxd_path"])
        client_roots_seen[r["data_source"]].add(r["client"])

    grouped = []
    for source, mxds in by_source.items():
        if len(mxds) < 2:
            continue
        grouped.append({
            "data_source": source,
            "reference_count": len(mxds),
            "referencing_mxds": sorted(mxds),
            "in_client_folder": len(client_roots_seen[source]) == 1,
        })
    grouped.sort(key=lambda g: g["reference_count"], reverse=True)
    return grouped


def build_workbook(survey):
    records = survey["records"]
    client_roots = survey["client_roots"]

    wb = Workbook()
    raw = wb.active
    raw.title = "Raw"
    raw.append(RAW_HEADERS)
    for r in records:
        raw.append([r["client"], r["mxd_path"], r["layer_name"], r["data_source"], r["source_exists"]])

    shared = wb.create_sheet("Shared Sources")
    shared.append(SHARED_HEADERS)
    for g in group_shared_sources(records):
        shared.append([
            g["data_source"], g["reference_count"],
            "; ".join(g["referencing_mxds"]), "Y" if g["in_client_folder"] else "N",
        ])

    flags = wb.create_sheet("Flags")
    flags.append(FLAGS_HEADERS)
    for r in records:
        flag = classify_source(r["client"], r["data_source"], r["source_exists"], client_roots)
        if flag:
            flags.append([r["client"], r["mxd_path"], r["layer_name"], r["data_source"], flag])

    return wb


def main(argv=None):
    argv = argv or sys.argv[1:]
    raw_path = Path(argv[0]) if argv else DEFAULT_RAW_PATH
    survey = json.loads(raw_path.read_text())
    wb = build_workbook(survey)
    wb.save(DEFAULT_OUTPUT_PATH)
    print(f"Wrote {DEFAULT_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
