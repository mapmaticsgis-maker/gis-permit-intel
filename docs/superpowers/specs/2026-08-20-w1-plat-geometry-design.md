# W-1 Plat Geometry Extraction — Design

**Date:** 2026-08-20
**Status:** Design approved, not yet planned/implemented.

## Problem

The daily pipeline currently derives well geometry (surface point + a straight SHL→BHL line) entirely from parsed `daf420.dat` coordinates. This is functional but limited: it's a two-point straight-line approximation of the wellbore, it has no bottom-hole point of its own (BHL only exists as a line endpoint), and it has no concept of the drilling/pooled unit the well sits in at all.

The W-1 subscription plats already downloaded daily (`data/tx/w1/<date>/`) turn out to contain far more: precise surveyed coordinates for every named point along the wellbore path (SHL, Point of Penetration, First/Last Take Point, Bottom Hole), and hand-drafted unit boundary polygons with stated acreages, drawn against a base layer of land-survey/abstract lines.

Two real plats were pulled apart to confirm this is real, extractable data, not an assumption:

- `917816_..._TRUMAN THREE H 03 TM..._LGR.pdf` (Magnolia Oil & Gas, surveyed by ELS Surveying & Mapping, Washington County) — one consolidated coordinate table (SHL/KOP-POP/FTP/IP/LTP/BHL, each in State Plane + Lat/Long + UTM), three named units (Mac Arthur, Henry Bredthauer, Yelderman-Bredthauer) drawn as shaded polygons with called acreages and per-tract ownership tables.
- `917412_..._F14H AVALON DS 4HH..._LTR.pdf` (TGNR Panola LLC, surveyed by Bowman/Michael Casey Griffis, Panola County) — coordinates given as distributed labeled callout boxes instead of one table, four named units (Anderson, B.S.A., LaGrone-Jeter, Powell A-2) the wellbore crosses, each with its own acreage and ownership table.

Both are vector-drawn CAD exports (confirmed via `pdfplumber`: thousands of extractable line/curve paths, zero extractable text characters — the same "text is vector-drawn glyphs" situation `w1_intel.py` already works around for operator/county OCR). Format varies meaningfully between surveying firms; a parser has to tolerate that rather than assume one fixed layout.

## Goal

For each new-signal W-1 plat in a client corridor county, produce:

1. A surface-hole-location point
2. A bottom-hole-location point
3. A multi-vertex wellbore path line (every named point the plat gives coordinates for, not just SHL/BHL)
4. One polygon per drilling/pooled unit the wellbore crosses, attributed with the unit's name and the plat's own stated acreage

— sourced entirely from the plat itself, since it's more precise than any public API and available at filing time (the entire point of the W-1 "early signal" work).

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Wellbore/BHL data source | Plat OCR, not RRC's public ArcGIS "Horizontal/Directional Lines" layer | The plat's own coordinate table is more precise (named intermediate points, not just SHL/BHL), available immediately at filing rather than waiting on RRC to publish, and shares infrastructure with the unit-polygon work regardless. Avoids a second, redundant data-source integration. |
| Unit polygon source | Traced from each plat's own vector geometry, georeferenced against the plat's own coordinate anchors | RRC publishes no drilling/pooled-unit boundary layer at all. The closest public thing (a "Surveys" layer) is land-survey/abstract lines — a different, older land-division concept, confirmed visually present as the *base grid* underneath the hand-drawn units on both sample plats, not a substitute for them. |
| Low-confidence handling | Auto-include only when both validation gates pass; otherwise skip the geometry and say so in the digest | A silently-wrong shape in a client-facing shapefile is worse than a visible gap. Two independent sanity checks, not one: (1) OCR'd SHL must land within a tight tolerance of the already-known daf420 SHL, confirming the affine calibration itself is trustworthy; (2) computed polygon area must fall within ~15% of the plat's own printed acreage label. Either failing (or no closed polygon / no usable coordinate labels found at all) means nothing is written for that feature — never a partial or guessed shape. |
| Scope | TX RRC W-1 plats only, corridor counties only | LA/SONRIS document pages are CAPTCHA-gated — no automated PDF access exists there at all, confirmed earlier in this project. Corridor-county scoping matches the existing plat-attachment filter already in `run_daily_ci.py`. |

## Architecture

```
w1_intel.py (existing per-plat loop, after its current OCR step)
        │
        ▼
plat_geometry.py                    -- NEW, pure extraction, no file I/O
  ├─ ocr_coordinate_labels(pdf)     -- rasterize + OCR, regex for
  │                                    Lat/Long-labeled values near
  │                                    point labels (SHL, BHL, POP, etc.)
  │                                    Tolerant of both layouts seen
  │                                    (one table vs. distributed boxes).
  ├─ extract_vector_paths(pdf)      -- pdfplumber lines/curves in PDF
  │                                    page-coordinate space
  ├─ find_unit_polygons(paths)      -- identify closed regions distinct
  │                                    from survey/property/dimension
  │                                    lines (fill color / line weight /
  │                                    closure heuristics)
  ├─ calibrate(ocr_points, known)   -- affine transform (scale + rotate
  │                                    + translate) from >=2 matched
  │                                    OCR-anchor / known-coordinate
  │                                    pairs (known = daf420 SHL/BHL,
  │                                    already in master.csv)
  ├─ validate(...)                  -- the two gates above; returns
  │                                    pass/fail + reason, never a
  │                                    "best guess"
  └─> structured result: wellbore path points, per-unit polygons +
      acreage + confidence, or a skip reason
        │
        ▼
Shapefile writer (extends the existing pyshp pattern from tx_daf420.py)
  data/tx/out/<date>/shp/
    W1_SHL_<date>.shp        (point)
    W1_BHL_<date>.shp        (point)
    W1_Wellbore_<date>.shp   (polyline, all found vertices)
    W1_Unit_Polygon_<date>.shp (polygon, one feature per unit)
  each feature carries Permit_Number (join key) + Confidence
        │
        ▼
w1_intel.py digest.md gets a per-permit line either way:
  "Geometry extracted (N units, high confidence)" or
  "Geometry not extracted -- <reason>, needs manual check"
```

## Error handling

This *is* the design's central concern, not an afterthought:

- Every extraction step can fail independently (OCR finds no usable labels; vector paths don't close into a polygon; calibration anchors don't match known coordinates). Any failure short-circuits to "skip, log why" — there is no fallback path that produces an unvalidated shape.
- All raw intermediate output (OCR text, matched anchor pairs, candidate polygon paths) gets logged to `logs/` alongside the existing download/reminder logs, so a plat that failed extraction is debuggable later without re-running anything.
- The digest note is mandatory in both outcomes so the gap is always visible in the normal daily read, never something that has to be discovered by checking a log.

## Testing

1. **Fixture tests** against the two plats already examined — assert extracted SHL/BHL match the plat's own printed coordinates (or pass the daf420 cross-check), assert each unit polygon's computed acreage matches its printed acreage within tolerance.
2. **Backlog validation, before daily-pipeline integration**: run standalone against ~15-20 real historical plats already sitting in `data/tx/w1/`, spanning multiple surveying firms/districts, and manually review the pass/skip split. This is the real test of whether the approach generalizes — two hand-picked fixtures prove the happy path works, not that the heuristics hold up across surveyor styles.
3. Only after that review passes does this get wired into the daily `w1_intel.py` run.

## Out of scope

- LA/SONRIS plats or documents (CAPTCHA-gated, no automated access exists).
- Non-corridor counties.
- Retroactive backfill of geometry for already-processed historical plats (could be a later follow-on, not part of this build).
- Any change to the existing `Permit_Surface_*`/`Permit_Lines_*` daf420-derived shapefiles that `tx_daf420.py` already writes daily — those stay as-is; this is new, additive output.
