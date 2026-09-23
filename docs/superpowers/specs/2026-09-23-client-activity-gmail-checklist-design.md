> **Superseded 2026-09-23:** the user redirected before this plan's Stage 1 ran — no Gmail data was gathered, nothing here was executed. The starting point is now "recently-modified `.mxd` files" instead of Gmail activity. See `2026-09-23-rrog-doxa-mxd-datasource-inventory-design.md` for the design actually implemented.

# Client Activity Checklist (Gmail Survey) — Design

**Date:** 2026-09-23
**Purpose:** First slice of a larger effort to bring every client's desktop GIS deliverables (`.mxd`/`.aprx` + their underlying shapefiles) into sync with the report spreadsheets clients actually send — updating attribute schemas (drop stale columns, add columns the current report drives) and, eventually, map colors/labels. DLS is the only client whose shapefiles are already known-good (its weekly `-JOIN` process, `C:\GIS\CLIENT\DLS`); every other client folder under `C:\GIS\CLIENT\` (BLACKBEARD, CADDO_LEVEE_DISTRICT, CARR, DOXA, EQV, HESTERLY, KSA, MADOLE, RFE, ROCKCHALK, RROG, SVR, TANOS, VEF, LOG_LIB, and others) is a candidate for the same treatment.

## 1. Scope of this slice

Produce **one spreadsheet**: a checklist of client report activity pulled from Gmail over the last 12 months, so we know which clients are actively sending reports (and how often) before deciding update order. Nothing else.

**Explicitly out of scope for this slice** (deferred to per-client work, later):
- Matching shapefiles to the `.mxd`/`.aprx` that actually references them.
- Reading/parsing any `.mxd` or `.aprx` project file.
- Any shapefile attribute edits (column add/drop) or symbology changes.

The user will point to the specific shapefile(s) and hand over the report(s) for each client individually once we start that client's update — this checklist is purely a discovery/prioritization artifact.

## 2. Gmail survey method

- Search **per client**, scoped by the client's existing Gmail label (the same labels used as the join key in the Mapmatics Client Master workbook, `C:\GIS\Mapmatics_Client_Master_UPDATED.xlsx`).
- Window: **last 365 days** from today (2026-09-23 → cutoff 2025-09-23).
- Within each label, look for messages carrying report-like attachments (`.xlsx`, `.csv`, `.pdf`) or report-like subject lines (e.g. "status", "report", "update").
- Client list to survey = every subfolder under `C:\GIS\CLIENT\` that has a corresponding Gmail label, **excluding DLS** (already confirmed good — may still get a reference row, see below).

## 3. Output

One `.xlsx` workbook, saved alongside the other client-facing reference material (`C:\GIS\` root, matching where the Client Master workbook lives).

**Summary tab** — one row per client:

| Client | Gmail Label | Last Report Date | Report Count (12mo) | Latest Attachment(s) | Notes |
|---|---|---|---|---|---|

`Notes` starts blank — filled in manually as each client is worked.

**Detail tab** — one row per matching email found (sender, subject, date, attachment filename(s), client), so nothing found by the search is silently dropped even if it doesn't make the summary rollup.

DLS is included as a single reference row on the summary tab (marked "known-good, no action needed") so the workbook accounts for the full client roster at a glance.

## 4. Process after this slice

This checklist feeds prioritization only. For each client, in an order the user picks from the checklist, we'll do a separate, scoped pass: user supplies the live shapefile + current report → compare attribute schema to the report → drop unneeded columns, add columns the report drives → confirm map coloring/labeling depends on the right fields. That is a new spec per client (or per small batch of similar clients), not part of this one.

## 5. Testing / verification

No code changes in this slice — it's a data-gathering task. Verification is manual: user reviews the workbook, confirms client coverage looks complete (no missing labels) and spot-checks a couple of "Last Report Date" values against Gmail directly.
