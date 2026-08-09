# DLS Proximity Pilot — Design

**Date:** 2026-08-09
**Status:** Approved for planning
**Relation to prior spec:** A scoped-down pilot of Phase 2 ("Registry + spatial") from
`docs/superpowers/specs/2026-07-28-mapmatics-intelligence-system-design.md`. That spec's
Phase 1 (sensor/ledger) is fully implemented; Phases 2-4 were never started. This is not
a replacement for that spec's Phase 2 -- it's a single-client proof of concept before
committing to the full multi-client build.

## Problem

The daily brief flags permits by county-level corridor (`config.yaml`'s `corridors`
block) -- broad, static lists set up once. It cannot say "this permit is 2 miles from
DLS's actual Flatland unit boundary," only "this permit is in a Giddings-corridor
county." The original design's Phase 2 proposed a full evidence-pack architecture with
proximity ranking across all active clients. That is a substantial, multi-week build.

## Why a pilot, and why DLS

Checked `C:\GIS\CLIENT\<CLIENT>\` for the three clients with the richest job lists in
the workbook. Folder organization varies enormously:

- **DLS**: job-matching subfolder names exist directly (`FLATLAND_NORTH`,
  `TURNPIKE_2025.gdb`, `CRESCENT_PASS-LEE_CO`) -- and `FLATLAND_NORTH` even contains a
  file literally named `AOI_NEW.shp`.
- **RROG, DOXA**: flat folders of shapefiles named by township-range grid code
  (`115N14W.shp`, `10N10W4_OSR.shp`) with no textual relationship to job names at all.

DLS is also the highest-volume client (near-daily contact per the workbook). Proving
proximity-ranking works well on DLS, where the geometry-matching problem is actually
tractable, is a cheap way to find out if this is worth building out further before
spending resolver effort on clients where automated matching will mostly shrug and fall
back to nothing.

## Scope

**In scope:** DLS only. Read DLS's job names from the workbook, resolve them to
geometry in `C:\GIS\CLIENT\DLS\`, compare against new TX permits, output a standalone
report.

**Out of scope (deliberately deferred, not rejected):** RROG/DOXA/other clients, LA
permits (TX only for this pilot -- DLS's stated work is Giddings/Eastern Eagle Ford,
Texas-only), wiring into the daily email (this is a separate standalone report while
unproven), the email analyst (Phase 3), client-ranked brief format (Phase 4),
`operator_families` migration out of `config.yaml` (the workbook has no "Corporate
Intel & Notes" sheet to migrate it to -- that sheet doesn't currently exist).

## Architecture

One new standalone script, `dls_proximity_report.py`, with five components:

```
dls_proximity_report.py
  parse_dls_jobs()          -- workbook cell -> list of job name strings
  resolve_geometry()        -- job name -> candidate shapefile matches (fuzzy token match)
  load_confirmed_cache()    -- reads/writes data/registry/dls_geometry_confirmed.json
  load_geometry(path)       -- pyshp read + reproject to EPSG:5070
  distance_to_permits(...)  -- permit points -> nearest confirmed job geometry
  build_report(...)         -- markdown output
```

No changes to `run_daily_ci.py`, `digest.py`, or the email pipeline. This reads
already-computed TX output (`data/tx/out/<date>/new_permits.csv`) rather than pulling
new data itself.

## Components

### 1. Job-name parser

DLS's "Jobs / Prospect Names" cell is one long free-text string:
`"Flatland (N/S, Tier 1-2), Turnpike, Updip/Caveman, Lee Co (Giddings, Sage, Crescent
Pass), Meteor Impact units (...), Zoch, Rosewood, Peebles, Blackshear, Parr, Monster
Rock, Flywheel, Barter Ranch, weekly Master/Flatland report + shapefile updates, DLS
dashboard"`. Splits on top-level commas, but must not split inside parentheses (e.g.
"Lee Co (Giddings, Sage, Crescent Pass)" is one job with three sub-areas, not four
jobs). Trailing non-job entries ("weekly Master/Flatland report + shapefile updates,
DLS dashboard") are report/deliverable descriptions, not job names -- the parser skips
any entry containing report/deliverable-type words (report, dashboard, update, updates,
shapefile) rather than treating it as a job to resolve. This is a narrow, testable rule,
not a semantic judgment call -- if it wrongly skips a real job name later, that's a
one-line fix to the keyword list, not a redesign.

### 2. Resolver

Fuzzy-matches each parsed job name against folder and file names under
`C:\GIS\CLIENT\DLS\`, reusing the token-overlap technique already proven in
`w1_intel.py` (tokenize, strip stopwords, score by overlap). Produces candidates, not
decisions -- multiple candidates for one job name (e.g. "Turnpike" plausibly matches
`TURNPIKE_2025.gdb`, `TURNPIKE_LGL`, `Turnpike 1st Well Unit`, `TurnpikeRevisedShapefiles_010424`)
are all surfaced for the confirmation step to sort out, preferring `.shp` candidates
over `.gdb` ones since this pilot only reads shapefiles (see Constraints).

### 3. Confirmation cache

`data/registry/dls_geometry_confirmed.json`: `{job_name: {shapefile_path, confirmed_by:
"user"|"unresolved", date}}`. Committed to the repo. On each run: entries already
present are loaded and trusted without re-asking; job names not yet in the cache get
resolver candidates written in as unconfirmed for the user to edit by hand (accept a
candidate path, or mark `"unresolved"` with a reason). A job name changing in the
workbook (e.g. wording edited) means the parser produces a new string that won't match
an existing cache key -- it will show up as a fresh unresolved entry, which is a known
and accepted limitation, not a bug to fix here.

### 4. Geometry + distance

Confirmed shapefiles are read via `pyshp` (already a project dependency -- no new
installs) and reprojected to **EPSG:5070** (NAD83 / CONUS Albers), the same CRS the
original 2026-07-28 spec chose for TX/LA-scale distance work, for consistency and to
avoid per-shapefile CRS bugs. Distance is measured from each new TX permit's location to
the nearest point on the actual job geometry (polygon/line), not a centroid -- a permit
landing inside an AOI polygon reads as 0 miles.

TX `daf420` carries both surface and bottomhole coordinates
(`Surface_Lat/Lon`, `BHL_Lat/Lon`). Matching the original spec's reasoning: distance is
computed to the wellbore segment (surface-to-bottomhole), not the surface point alone,
since a lateral can bottom miles from where it surfaces.

### 5. Report generator

`data/dls_proximity/<date>.md`: permits within 5 miles of a confirmed DLS job,
sorted by distance, each line naming the job, the permit, operator, and distance.
Unresolved jobs are listed at the top of the report as a visible gap, not silently
omitted -- consistent with the project's existing "provably-empty" philosophy (an empty
or partial result states why, it doesn't just look empty).

## Constraints

- **Shapefiles only, no GDB support.** The main pipeline's Python has `pyshp` but not
  `fiona`/`geopandas`/`osgeo` (confirmed by import test), so `.gdb` geodatabases like
  `EOG_Flatland_20260629.gdb` and `TURNPIKE_2025.gdb` can't be read directly. Checked
  that this doesn't block the pilot: `FLATLAND_NORTH` and `TURNPIKE_LGL` both have real
  shapefile equivalents alongside their GDB versions. If a future job turns out to only
  exist as a GDB with no shapefile counterpart, it lands in the report as unresolved
  with that reason stated, rather than silently skipped or blocked on a new dependency.
- **5-mile default radius**, matching the original spec's default. Not asked as an
  open question -- carried forward as a sensible starting point, adjustable later if
  DLS's actual work pattern calls for something tighter or looser.
- **TX only.** DLS's stated work areas are Texas Eagle Ford/Giddings corridors; no LA
  join for this pilot.

## Testing

The resolver's match *quality* is a judgment call by design -- that's what the
confirm-once cache is for, not something to unit-test. What gets tested directly:

1. Distance-to-polygon math against a couple of hand-verified known cases.
2. The job-name parser against DLS's actual current workbook cell (parenthetical
   sub-areas, comma-heavy entries, and the trailing non-job report-description text all
   need to parse correctly, not just a simplified example).
3. Confirmation cache round-trip (write, reload, entries stay stable across runs).

**Pilot acceptance check:** run against DLS's real current job list and a real recent
day of TX permits ([data/tx/out/2026-08-08](../../../data/tx/out/2026-08-08/) or later),
and the user reviews whether the resolved geometry list and flagged proximity permits
look sane -- same validation pattern used for every other piece of this pipeline so far
(W-1 OCR accuracy, SONRIS lag investigation, etc.), not a synthetic test fixture.

## Promotion criterion

Not addressed here, deliberately. Whether this pilot justifies extending to
RROG/DOXA/other clients (where the folder-naming gap means the resolver will mostly
fall back to nothing) is a decision for after the pilot ships and the user has seen real
output against real data for a few days -- consistent with how every other piece of this
system has been proven (W-1 automation, SONRIS enhancements) before expanding it
further.
