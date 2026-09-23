# RROG + DOXA .mxd Data Source Inventory — Design

**Date:** 2026-09-23
**Supersedes:** `2026-09-23-client-activity-gmail-checklist-design.md` (abandoned before execution — see that file's header note).

## 1. Purpose

Start the larger "update data storage structure and overall efficiency of current projects" effort with the two highest-volume, most-recently-active client project sets: **RROG** (`C:\GIS\CLIENT\RROG`) and **DOXA** (`C:\GIS\CLIENT\DOXA`). Before touching any shapefile attributes or reorganizing anything, build a factual inventory of every layer's actual data source across every `.mxd` in those two folders, so we can see:

- Which shapefiles/feature classes are referenced by **more than one** `.mxd` (candidates for consolidating into a shared location instead of per-map copies).
- Which data sources live **outside** the client's own folder (e.g. a RROG map pointing at `C:\0-CLIENTS\DOXA\...` or `C:\Surface_Parcels-P2E\...`) — cross-client or stray references worth flagging.
- Which data sources are **broken** (path no longer exists) — dead layers.

This is a **discovery** pass only. No files move, no attributes change, no `.mxd` is edited. The output is a spreadsheet the user reviews to decide what to consolidate/relocate next.

**Not in scope:** TANOS, HESTERLY, VEF, DLS (DLS is already known-good and excluded per prior direction); shapefile attribute column changes; symbology/label changes; editing or resaving any `.mxd`.

## 2. Why RROG and DOXA, and why "all files not just recent"

The user picked these two because they're the highest-volume clients in the last 90 days (RROG 38 recently-modified `.mxd`, DOXA 37) and therefore the most likely to have accumulated duplicate/scattered data. But layer reuse is only visible with the **full** picture — a layer shared between a March map and a September map is still a consolidation candidate — so the inventory scans **every** `.mxd` under each client's folder (recursively, including subfolders like `RROG/` unit folders or `DOXA/SABINE/SHELBY/`), not just the last-90-days subset.

## 3. Technical approach

`.mxd` is ArcMap's binary project format. The only reliable way to read a layer's actual data source is `arcpy.mapping.MapDocument`, which requires **ArcGIS Desktop's Python 2.7** (`C:\Python27\ArcGIS10.8\python.exe`) — confirmed installed and working on this machine (verified against a live RROG `.mxd`: it correctly returns layer name + `dataSource` for every real layer, and correctly reports basemap/group layers as having no data source). ArcGIS Pro's `arcpy.mp` does not support `.mxd`.

Two-stage pipeline, same shape as the (abandoned) Gmail-checklist plan, because it's the right shape here too — one stage constrained to a specific runtime, one stage that's pure and testable:

- **Stage 1** (`C:\Python27\ArcGIS10.8\python.exe`, arcpy required): walks `CLIENT\RROG` and `CLIENT\DOXA` for `*.mxd`, opens each with `arcpy.mapping.MapDocument`, lists every layer via `arcpy.mapping.ListLayers`, records `{mxd_path, layer_name, data_source, source_exists}` for every layer that supports `DATASOURCE` (skip group/basemap layers, which don't). Writes one JSON file per client. `source_exists` is checked with `os.path.exists` on the data source path (for geodatabase feature classes like `...\Surface_Parcels.gdb\LA_BossierSurface_2020`, existence-check the `.gdb` container path, not the feature class path itself).
- **Stage 2** (system Python 3, `openpyxl`, no arcpy needed): reads both JSON files, computes the cross-file analysis, writes one xlsx workbook.

## 4. Output

One workbook: `C:\GIS\CLIENT\RROG_DOXA_Datasource_Inventory.xlsx`, three tabs:

**`Raw`** — one row per (mxd, layer) pair across both clients: `Client | MXD Path | Layer Name | Data Source | Source Exists`.

**`Shared Sources`** — one row per data source path referenced by **2+ distinct `.mxd` files**, sorted by reference count descending: `Data Source | Reference Count | Referencing MXDs (semicolon-joined) | In Client Folder? (Y/N)`. This is the primary consolidation candidate list.

**`Flags`** — one row per problem layer: broken sources (`source_exists = False`) and out-of-folder sources (data source path doesn't start with the owning client's own folder, e.g. a RROG `.mxd` pointing at a DOXA path). Columns: `Client | MXD Path | Layer Name | Data Source | Flag Type (Broken / Cross-Client / Outside C:\GIS)`.

## 5. Testing / verification

Stage 2's analysis logic (grouping by data source, counting references, flagging cross-client/broken sources) is pure and unit-testable against a small fixture — no arcpy or live filesystem dependency. Stage 1 is verified manually: spot-check the JSON row count against a manual `find -iname *.mxd` count for each client folder, and spot-check 2-3 known layers (e.g. the RROG test case already run) against the JSON output.

Final manual check: user opens the workbook, confirms the `Shared Sources` tab surfaces layers they recognize as duplicated, and the `Flags` tab doesn't have obvious false positives (e.g. a layer correctly stored in a shared boundary folder like `C:\GIS\BOUNDARY\...` shouldn't be flagged as "outside C:\GIS" — only as a legitimate shared reference, which is fine and expected, not a problem).
