# RROG + DOXA .mxd Data Source Inventory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce `C:\GIS\CLIENT\RROG_DOXA_Datasource_Inventory.xlsx` — a 3-tab workbook (`Raw`, `Shared Sources`, `Flags`) showing every layer's real data source across every `.mxd` in `C:\GIS\CLIENT\RROG` and `C:\GIS\CLIENT\DOXA`, so duplicate/shared/broken/misplaced layers can be identified as consolidation candidates.

**Architecture:** Two-stage pipeline, split by required runtime. Stage 1 runs under ArcGIS Desktop's Python 2.7 (`C:\Python27\ArcGIS10.8\python.exe`, has `arcpy`) — walks both client folders, opens every `.mxd` with `arcpy.mapping.MapDocument`, records every layer's data source, writes one combined JSON snapshot. Stage 2 runs under system Python 3 (`openpyxl`, `pytest` available) — reads that JSON, classifies each data source (fine / broken / cross-client / outside `C:\GIS`), groups shared sources, and writes the xlsx. Stage 2's classification and grouping logic is pure and unit-tested against a fixture; Stage 1 is verified manually since it depends on arcpy and live `.mxd` files.

**Tech Stack:** Python 2.7 + `arcpy` (ArcGIS Desktop 10.8, already installed) for Stage 1; Python 3 + `openpyxl` + `pytest` for Stage 2.

## Global Constraints

- Scope: every `.mxd` recursively under `C:\GIS\CLIENT\RROG` and `C:\GIS\CLIENT\DOXA` (not just recently-modified ones) — per spec §2.
- No file moves, no attribute edits, no `.mxd` edits — discovery only, per spec §1.
- Only layers where `lyr.supports('DATASOURCE')` is true are recorded; group/basemap layers are skipped (confirmed behavior via the live RROG test in the design spec).
- For geodatabase feature classes (data source path contains `.gdb\`), existence is checked against the `.gdb` container path, not the feature class path — per spec §3.
- Output path: `C:\GIS\CLIENT\RROG_DOXA_Datasource_Inventory.xlsx` — per spec §4.
- A data source is only flagged in `Flags` as `Cross-Client` or `Outside C:\GIS`; a reference to a legitimate shared location under `C:\GIS` (e.g. `C:\GIS\BOUNDARY\...`) is not flagged — per spec §5.

---

## File Structure

- Create: `scripts/mxd_inventory/scan_mxd_datasources.py` — Stage 1. Run directly with the ArcGIS Desktop Python 2.7 interpreter. No importable functions needed (single-purpose script, not unit-tested — arcpy isn't available to the test runner).
- Create: `scripts/mxd_inventory/build_datasource_inventory.py` — Stage 2. Pure functions `classify_source()`, `group_shared_sources()`, `build_workbook()`, plus a `main()`.
- Create: `tests/test_build_datasource_inventory.py` — unit tests for the three Stage 2 functions.
- Create: `data/mxd_inventory/raw_inventory.json` — Stage 1 output, Stage 2 input. Gitignored (same pattern as the abandoned Gmail-checklist plan's data directory).

## Task 1: Write and run the Stage 1 scanner

**Files:**
- Create: `scripts/mxd_inventory/scan_mxd_datasources.py`
- Create: `data/mxd_inventory/raw_inventory.json` (generated, not committed)

**Interfaces:**
- Produces: `data/mxd_inventory/raw_inventory.json` shaped like:
```json
{
  "generated_date": "2026-09-23",
  "client_roots": {"RROG": "C:\\GIS\\CLIENT\\RROG", "DOXA": "C:\\GIS\\CLIENT\\DOXA"},
  "records": [
    {"client": "RROG", "mxd_path": "C:\\GIS\\CLIENT\\RROG\\LA-CAD_2216N13W.mxd",
     "layer_name": "COUNTY", "data_source": "C:\\GIS\\BOUNDARY\\COUNTY\\tl_2024_us_county.shp",
     "source_exists": true}
  ],
  "errors": [
    {"mxd_path": "C:\\GIS\\CLIENT\\RROG\\some_corrupt.mxd", "error": "..."}
  ]
}
```
Consumed by Task 2's `build_workbook()` (via `main()` in the same Task 2 file).

- [ ] **Step 1: Write the scanner script**

```python
# scripts/mxd_inventory/scan_mxd_datasources.py
# Run with: C:\Python27\ArcGIS10.8\python.exe scripts\mxd_inventory\scan_mxd_datasources.py
import arcpy
import datetime
import json
import os

CLIENT_ROOTS = {
    "RROG": r"C:\GIS\CLIENT\RROG",
    "DOXA": r"C:\GIS\CLIENT\DOXA",
}

OUTPUT_PATH = r"C:\GIS\permit_intel\data\mxd_inventory\raw_inventory.json"


def find_mxds(root):
    matches = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            if name.lower().endswith(".mxd"):
                matches.append(os.path.join(dirpath, name))
    return matches


def existence_check_path(data_source):
    lower = data_source.lower()
    idx = lower.find(".gdb\\")
    if idx != -1:
        return data_source[:idx + 4]
    return data_source


def scan_mxd(client, mxd_path, records, errors):
    try:
        mxd = arcpy.mapping.MapDocument(mxd_path)
    except Exception as exc:
        errors.append({"mxd_path": mxd_path, "error": str(exc)})
        return
    for df in arcpy.mapping.ListDataFrames(mxd):
        for lyr in arcpy.mapping.ListLayers(mxd, "", df):
            if not lyr.supports("DATASOURCE"):
                continue
            data_source = lyr.dataSource
            source_exists = os.path.exists(existence_check_path(data_source))
            records.append({
                "client": client,
                "mxd_path": mxd_path,
                "layer_name": lyr.name,
                "data_source": data_source,
                "source_exists": source_exists,
            })
    del mxd


def main():
    records = []
    errors = []
    for client, root in CLIENT_ROOTS.items():
        for mxd_path in find_mxds(root):
            scan_mxd(client, mxd_path, records, errors)

    output = {
        "generated_date": datetime.date.today().isoformat(),
        "client_roots": CLIENT_ROOTS,
        "records": records,
        "errors": errors,
    }

    output_dir = os.path.dirname(OUTPUT_PATH)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)

    print("Scanned {0} records, {1} errors. Wrote {2}".format(len(records), len(errors), OUTPUT_PATH))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the scanner**

Run: `"/c/Python27/ArcGIS10.8/python.exe" "C:\GIS\permit_intel\scripts\mxd_inventory\scan_mxd_datasources.py"`
Expected: prints `Scanned N records, M errors. Wrote C:\GIS\permit_intel\data\mxd_inventory\raw_inventory.json` with N > 0.

- [ ] **Step 3: Sanity-check the mxd count against a manual count**

Run: `find "/c/GIS/CLIENT/RROG" "/c/GIS/CLIENT/DOXA" -iname "*.mxd" | wc -l`
Then: `python -c "import json; d=json.load(open('data/mxd_inventory/raw_inventory.json')); print(len(set(r['mxd_path'] for r in d['records'])) + len(d['errors']))"`
Expected: the two counts match (every `.mxd` either contributed records or was logged as an error — none silently dropped).

- [ ] **Step 4: Spot-check the known RROG test case**

Run: `python -c "import json; d=json.load(open('data/mxd_inventory/raw_inventory.json')); rows=[r for r in d['records'] if r['mxd_path'].endswith('LA-CAD_2216N13W.mxd') and r['layer_name']=='COUNTY']; print(rows)"`
Expected: one row with `data_source` ending in `BOUNDARY\COUNTY\tl_2024_us_county.shp` and `source_exists: true` — matches the manual arcpy test already run during design.

- [ ] **Step 5: Ensure the data directory is gitignored, commit the scanner script**

```bash
grep -q "^data/mxd_inventory/" .gitignore || echo "data/mxd_inventory/" >> .gitignore
git add .gitignore scripts/mxd_inventory/scan_mxd_datasources.py
git commit -m "Add arcpy scanner for RROG/DOXA mxd data sources"
```

## Task 2: Write Stage 2 classification/grouping/workbook logic (TDD)

**Files:**
- Create: `scripts/mxd_inventory/build_datasource_inventory.py`
- Test: `tests/test_build_datasource_inventory.py`

**Interfaces:**
- Consumes: the JSON structure from Task 1 (as a parsed dict).
- Produces:
  - `classify_source(client: str, data_source: str, source_exists: bool, client_roots: dict) -> str | None` — returns `"Broken"`, `"Cross-Client"`, `"Outside C:\\GIS"`, or `None` (fine, not flagged).
  - `group_shared_sources(records: list[dict]) -> list[dict]` — returns one dict per data source referenced by 2+ distinct `mxd_path`s, each shaped `{"data_source": str, "reference_count": int, "referencing_mxds": list[str], "in_client_folder": bool}`, sorted by `reference_count` descending.
  - `build_workbook(survey: dict) -> openpyxl.workbook.Workbook` — calls the two functions above internally and assembles all three sheets. This is what Task 3's `main()` calls.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_build_datasource_inventory.py
from scripts.mxd_inventory.build_datasource_inventory import (
    classify_source,
    group_shared_sources,
    build_workbook,
)

CLIENT_ROOTS = {
    "RROG": r"C:\GIS\CLIENT\RROG",
    "DOXA": r"C:\GIS\CLIENT\DOXA",
}


def test_classify_source_broken_takes_priority():
    assert classify_source("RROG", r"C:\GIS\CLIENT\DOXA\missing.shp", False, CLIENT_ROOTS) == "Broken"


def test_classify_source_cross_client():
    assert classify_source("RROG", r"C:\GIS\CLIENT\DOXA\ZADECK\STICKS.shp", True, CLIENT_ROOTS) == "Cross-Client"


def test_classify_source_outside_gis():
    assert classify_source("RROG", r"C:\0-CLIENTS\DOXA\ZADECK\STICKS.shp", True, CLIENT_ROOTS) == "Outside C:\\GIS"


def test_classify_source_shared_boundary_not_flagged():
    assert classify_source("RROG", r"C:\GIS\BOUNDARY\COUNTY\tl_2024_us_county.shp", True, CLIENT_ROOTS) is None


def test_classify_source_own_folder_not_flagged():
    assert classify_source("RROG", r"C:\GIS\CLIENT\RROG\LINE2.shp", True, CLIENT_ROOTS) is None


RECORDS = [
    {"client": "RROG", "mxd_path": r"C:\GIS\CLIENT\RROG\a.mxd", "layer_name": "COUNTY",
     "data_source": r"C:\GIS\BOUNDARY\COUNTY\tl_2024_us_county.shp", "source_exists": True},
    {"client": "RROG", "mxd_path": r"C:\GIS\CLIENT\RROG\b.mxd", "layer_name": "COUNTY",
     "data_source": r"C:\GIS\BOUNDARY\COUNTY\tl_2024_us_county.shp", "source_exists": True},
    {"client": "RROG", "mxd_path": r"C:\GIS\CLIENT\RROG\a.mxd", "layer_name": "UNIQUE",
     "data_source": r"C:\GIS\CLIENT\RROG\a_only.shp", "source_exists": True},
]


def test_group_shared_sources_only_includes_multi_reference_sources():
    grouped = group_shared_sources(RECORDS)
    assert len(grouped) == 1
    assert grouped[0]["data_source"] == r"C:\GIS\BOUNDARY\COUNTY\tl_2024_us_county.shp"
    assert grouped[0]["reference_count"] == 2
    assert set(grouped[0]["referencing_mxds"]) == {r"C:\GIS\CLIENT\RROG\a.mxd", r"C:\GIS\CLIENT\RROG\b.mxd"}


SURVEY = {
    "generated_date": "2026-09-23",
    "client_roots": CLIENT_ROOTS,
    "records": RECORDS
    + [
        {"client": "RROG", "mxd_path": r"C:\GIS\CLIENT\RROG\c.mxd", "layer_name": "STICKS",
         "data_source": r"C:\0-CLIENTS\DOXA\ZADECK\STICKS.shp", "source_exists": True},
    ],
    "errors": [],
}


def test_build_workbook_has_three_sheets():
    wb = build_workbook(SURVEY)
    assert wb.sheetnames == ["Raw", "Shared Sources", "Flags"]


def test_build_workbook_raw_sheet_row_count():
    wb = build_workbook(SURVEY)
    # header + 4 records
    assert wb["Raw"].max_row == 5


def test_build_workbook_flags_sheet_has_outside_gis_row():
    wb = build_workbook(SURVEY)
    flags = wb["Flags"]
    rows = list(flags.iter_rows(min_row=2, values_only=True))
    assert any(row[4] == "Outside C:\\GIS" and row[3] == r"C:\0-CLIENTS\DOXA\ZADECK\STICKS.shp" for row in rows)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_build_datasource_inventory.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.mxd_inventory.build_datasource_inventory'`

- [ ] **Step 3: Write the minimal implementation**

```python
# scripts/mxd_inventory/build_datasource_inventory.py
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_build_datasource_inventory.py -v`
Expected: PASS (all 9 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/mxd_inventory/build_datasource_inventory.py tests/test_build_datasource_inventory.py
git commit -m "Add data-source classification and workbook builder for mxd inventory"
```

## Task 3: Run the full pipeline and verify the real output

**Files:** none (uses artifacts from Task 1 and Task 2)

**Interfaces:**
- Consumes: `build_workbook()` and `main()` from Task 2, `data/mxd_inventory/raw_inventory.json` from Task 1.
- Produces: `C:\GIS\CLIENT\RROG_DOXA_Datasource_Inventory.xlsx` (the real deliverable).

- [ ] **Step 1: Run the Stage 2 builder against the real Stage 1 output**

Run: `python scripts/mxd_inventory/build_datasource_inventory.py`
Expected: prints `Wrote C:\GIS\CLIENT\RROG_DOXA_Datasource_Inventory.xlsx`, exit code 0.

- [ ] **Step 2: Confirm sheet names and row counts**

Run: `python -c "from openpyxl import load_workbook; wb=load_workbook(r'C:\GIS\CLIENT\RROG_DOXA_Datasource_Inventory.xlsx'); print(wb.sheetnames); print({s: wb[s].max_row for s in wb.sheetnames})"`
Expected: `['Raw', 'Shared Sources', 'Flags']`, `Raw` row count = header + total layer records from Stage 1 (matches Task 1 Step 2's printed record count), `Shared Sources` and `Flags` row counts are non-negative and no larger than `Raw`.

- [ ] **Step 3: Hand off to the user for manual review**

Per spec §5: user opens `C:\GIS\CLIENT\RROG_DOXA_Datasource_Inventory.xlsx`, confirms `Shared Sources` surfaces layers they recognize as duplicated, and `Flags` doesn't have obvious false positives (a legitimate shared boundary-layer reference under `C:\GIS\BOUNDARY\...` should not appear in `Flags` — confirmed correct by `test_classify_source_shared_boundary_not_flagged` in Task 2, but worth a real-data glance since the fixture is small).

- [ ] **Step 4: Note any corrections from review**

If the user flags a wrong classification or a client-root path issue, fix `CLIENT_ROOTS` in the relevant script(s), re-run the affected stage, and commit the fix with a message describing what was wrong (e.g. `git commit -m "Fix RROG client root path in mxd scanner"`).
