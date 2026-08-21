# W-1 Plat Geometry Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract surface-hole, bottom-hole, multi-vertex wellbore path, and per-unit boundary polygon geometry directly from W-1 plat PDFs, and ship it as shapefiles alongside the existing daily TX output — only when two independent validation gates confirm the extraction is trustworthy, never a guessed shape.

**Architecture:** A new pure-extraction module (`plat_geometry.py`) does vector-path extraction, OCR-based coordinate-label reading, affine calibration against already-known daf420 coordinates, and unit-polygon identification, producing a `PlatGeometryResult` per plat. A separate shapefile writer turns validated results into `.shp` files following the existing `tx_daf420.py` pyshp convention. A standalone backlog-validation script runs the pipeline against real historical plats for human review *before* the last task wires it into the daily `w1_intel.py` run.

**Tech Stack:** `pdfplumber` (vector path + PDF-space geometry), `pytesseract` + `pdf2image` (OCR, already a project dependency), `pyshp` (shapefile output, already a project dependency), stdlib `dataclasses`.

## Global Constraints

- Design doc: `docs/superpowers/specs/2026-08-20-w1-plat-geometry-design.md` — every task below implements a piece of it; re-read it if a task's rationale is unclear.
- **Never write a shape that hasn't passed both validation gates.** No fallback path may produce a partial or best-guess geometry.
- TX RRC plats only. Corridor counties only (reuse `W1_ATTACH_COUNTIES`, relocated to `common.py` in Task 1 so both `run_daily_ci.py` and `w1_intel.py` import the same list instead of drifting — the exact bug class fixed in commit `4d9775b` earlier this project).
- Reuse `TESSERACT_EXE` and `POPPLER_PATH` from `w1_intel.py` (import them, don't redefine).
- Follow the existing shapefile convention from `tx_daf420.py:_write_shapefiles` exactly: WGS84 `.prj` sidecar, `pyshp` `Writer`, `(lon, lat)` point order.
- Task 8 (backlog validation) must be run and its output reviewed by the user before Task 9 (daily pipeline wiring) begins.

## Shared data structures

Defined in Task 1, used by name in every later task:

```python
from dataclasses import dataclass, field


@dataclass
class VectorPath:
    kind: str            # "line" or "curve"
    x0: float
    y0: float
    x1: float
    y1: float
    stroke_width: float
    is_filled: bool
    fill_color: tuple | None   # (r, g, b) 0-255 if filled, else None


@dataclass
class AffineTransform:
    a: float
    b: float
    c: float
    d: float
    e: float
    f: float
    # real_lon = a*pdf_x + b*pdf_y + e
    # real_lat = c*pdf_x + d*pdf_y + f


@dataclass
class UnitPolygon:
    name: str | None
    pdf_vertices: list[tuple[float, float]]   # closed ring, PDF page-coordinate space
    stated_acreage: float | None              # OCR'd from the plat's own label, if found


@dataclass
class PlatGeometryResult:
    permit_number: str
    status: str                     # "extracted" or "skipped"
    skip_reason: str | None
    wellbore_points: list[tuple[str, float, float]]   # (label, lon, lat), ordered SHL -> BHL
    units: list[dict]
    # units[i] = {"name": str | None, "acreage_stated": float | None,
    #             "acreage_computed": float, "confidence": str,
    #             "polygon": list[tuple[float, float]]}   # (lon, lat) real-world, closed ring
```

---

### Task 1: Vector path extraction + shared module setup

**Files:**
- Create: `plat_geometry.py`
- Modify: `common.py` (add `W1_ATTACH_COUNTIES`, moved from `run_daily_ci.py`)
- Modify: `run_daily_ci.py:110-115` (import `W1_ATTACH_COUNTIES` from `common` instead of defining it)
- Test: `test_plat_geometry.py`

**Interfaces:**
- Produces: `VectorPath` dataclass, `extract_vector_paths(pdf_path: str) -> list[VectorPath]`

- [ ] **Step 1: Move `W1_ATTACH_COUNTIES` to `common.py`**

In `common.py`, add near the top-level constants:

```python
W1_ATTACH_COUNTIES = {
    "LEE", "LAVACA", "FAYETTE",  # Giddings
    "PANOLA", "RUSK", "HARRISON", "CHEROKEE", "SHELBY",
    "SAN AUGUSTINE", "SMITH", "NACOGDOCHES", "GREGG",  # East Texas
}
```

In `run_daily_ci.py`, replace the existing `W1_ATTACH_COUNTIES = {...}` block (lines 110-115) with:

```python
from common import W1_ATTACH_COUNTIES
```

Run: `python -m py_compile run_daily_ci.py common.py`
Expected: no output (clean compile)

- [ ] **Step 2: Write the failing test for vector path extraction**

```python
# test_plat_geometry.py
from pathlib import Path
from plat_geometry import extract_vector_paths

MAGNOLIA_PLAT = Path("data/tx/w1/20260818/2026-08-18/03/917816_Plat_MAGNOLIA_TRUMAN THREE H 03 TM_PERMIT PLAT_FINAL (08-10-26)_LGR.pdf")
TGNR_PLAT = Path("data/tx/w1/20260819/2026-08-19/06/917412_Plat_F14H AVALON DS 4HH final permit plat 8-11-26_LTR.pdf")


def test_extract_vector_paths_magnolia():
    paths = extract_vector_paths(str(MAGNOLIA_PLAT))
    assert len(paths) > 1000, f"expected thousands of vector paths, got {len(paths)}"
    kinds = {p.kind for p in paths}
    assert kinds == {"line", "curve"}


def test_extract_vector_paths_tgnr():
    paths = extract_vector_paths(str(TGNR_PLAT))
    assert len(paths) > 1000, f"expected thousands of vector paths, got {len(paths)}"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest test_plat_geometry.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'plat_geometry'`

- [ ] **Step 4: Write the implementation**

```python
# plat_geometry.py
"""
Extracts surface/bottom-hole points, wellbore path, and drilling-unit
boundary polygons directly from W-1 plat PDFs -- more precise than any
public API and available at filing time. See
docs/superpowers/specs/2026-08-20-w1-plat-geometry-design.md for the
full design and the two validation gates every result must pass before
being written as a shapefile.
"""
from dataclasses import dataclass

import pdfplumber

from w1_intel import TESSERACT_EXE, POPPLER_PATH  # reused, not redefined


@dataclass
class VectorPath:
    kind: str
    x0: float
    y0: float
    x1: float
    y1: float
    stroke_width: float
    is_filled: bool
    fill_color: tuple | None


@dataclass
class AffineTransform:
    a: float
    b: float
    c: float
    d: float
    e: float
    f: float


@dataclass
class UnitPolygon:
    name: str | None
    pdf_vertices: list[tuple[float, float]]
    stated_acreage: float | None


@dataclass
class PlatGeometryResult:
    permit_number: str
    status: str
    skip_reason: str | None
    wellbore_points: list[tuple[str, float, float]]
    units: list[dict]


def extract_vector_paths(pdf_path: str) -> list[VectorPath]:
    """All line and curve segments on the plat's first page, in PDF
    page-coordinate space (points, origin bottom-left)."""
    paths = []
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[0]
        for line in page.lines:
            paths.append(VectorPath(
                kind="line", x0=line["x0"], y0=line["y0"], x1=line["x1"], y1=line["y1"],
                stroke_width=line.get("linewidth", 1.0) or 1.0,
                is_filled=False, fill_color=None,
            ))
        for curve in page.curves:
            fill = curve.get("non_stroking_color")
            paths.append(VectorPath(
                kind="curve", x0=curve["x0"], y0=curve["y0"], x1=curve["x1"], y1=curve["y1"],
                stroke_width=curve.get("linewidth", 1.0) or 1.0,
                is_filled=bool(curve.get("fill")),
                fill_color=tuple(int(c * 255) for c in fill) if fill else None,
            ))
    return paths
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest test_plat_geometry.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add plat_geometry.py test_plat_geometry.py common.py run_daily_ci.py
git commit -m "Add plat_geometry.py with vector path extraction; relocate W1_ATTACH_COUNTIES to common.py"
```

---

### Task 2: OCR coordinate-label extraction

**Files:**
- Modify: `plat_geometry.py`
- Test: `test_plat_geometry.py`

**Interfaces:**
- Consumes: `TESSERACT_EXE`, `POPPLER_PATH` (from Task 1's import)
- Produces: `ocr_coordinate_labels(pdf_path: str, dpi: int = 300) -> dict[str, tuple[float, float]]` returning `{label: (lon, lat)}` for whichever of `SHL, POP, FTP, IP, LTP, BHL` it can find. Missing labels are simply absent from the dict — never a guessed value.

- [ ] **Step 1: Write the failing test**

This test cross-validates against already-trusted data instead of hand-transcribed OCR values (more robust, and mirrors the design's own calibration-check gate):

```python
def test_ocr_coordinate_labels_matches_known_shl():
    import pandas as pd

    labels = ocr_coordinate_labels(str(MAGNOLIA_PLAT))
    assert "SHL" in labels, f"expected SHL in {list(labels)}"
    assert "BHL" in labels, f"expected BHL in {list(labels)}"

    master = pd.read_csv("data/tx/master.csv", dtype=str)
    row = master[master["Permit_Number"].astype(str).str.lstrip("0") == "917816"]
    assert len(row) == 1, "fixture permit 917816 not found in master.csv -- pick a different fixture"
    known_lon = float(row.iloc[0]["Surface_Lon"])
    known_lat = float(row.iloc[0]["Surface_Lat"])

    ocr_lon, ocr_lat = labels["SHL"]
    assert abs(ocr_lon - known_lon) < 0.01, f"OCR SHL lon {ocr_lon} too far from daf420 {known_lon}"
    assert abs(ocr_lat - known_lat) < 0.01, f"OCR SHL lat {ocr_lat} too far from daf420 {known_lat}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest test_plat_geometry.py::test_ocr_coordinate_labels_matches_known_shl -v`
Expected: FAIL with `NameError: name 'ocr_coordinate_labels' is not defined`

- [ ] **Step 3: Write the implementation**

Add to `plat_geometry.py`:

```python
import re

from pdf2image import convert_from_path
import pytesseract

pytesseract.pytesseract.tesseract_cmd = TESSERACT_EXE

_POINT_LABELS = ["SHL", "KOP", "POP", "FTP", "IP", "LTP", "BHL"]
_LABEL_ALIASES = {
    "SURFACE LOCATION": "SHL", "SURFACE HOLE": "SHL",
    "POINT OF PENETRATION": "POP", "KOP/POP": "POP",
    "FIRST TAKE POINT": "FTP", "LAST TAKE POINT": "LTP",
    "BOTTOM HOLE": "BHL",
}
_LATLON_RE = re.compile(
    r"LAT(?:ITUDE)?\.?[:=]?\s*(-?\d{1,3}\.\d{3,8}).{0,40}?"
    r"LONG(?:ITUDE)?\.?[:=]?\s*(-?\d{1,3}\.\d{3,8})",
    re.IGNORECASE | re.DOTALL,
)


def ocr_coordinate_labels(pdf_path: str, dpi: int = 300) -> dict[str, tuple[float, float]]:
    """OCR the plat's first page and pull (lon, lat) for every point label
    it can find, tolerant of both the consolidated-table layout (one
    block with all points) and the distributed-callout-box layout (one
    box per point) seen on real plats from different surveying firms."""
    pages = convert_from_path(pdf_path, dpi=dpi, poppler_path=POPPLER_PATH)
    text = pytesseract.image_to_string(pages[0])

    found: dict[str, tuple[float, float]] = {}
    upper = text.upper()
    for canonical in _POINT_LABELS:
        idx = upper.find(canonical)
        if idx == -1:
            for alias, target in _LABEL_ALIASES.items():
                if target == canonical and alias in upper:
                    idx = upper.find(alias)
                    break
        if idx == -1:
            continue
        window = text[idx: idx + 400]
        m = _LATLON_RE.search(window)
        if m:
            lat, lon = float(m.group(1)), float(m.group(2))
            found[canonical] = (lon, lat)

    if "POP" in found and "KOP" not in found:
        pass  # KOP/POP already normalized to POP above
    return found
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest test_plat_geometry.py::test_ocr_coordinate_labels_matches_known_shl -v`
Expected: PASS

If it fails because the regex doesn't match either real plat's actual OCR'd text layout, print `text` from a scratch script (`python -c "from plat_geometry import *; ..."`) and adjust `_LATLON_RE` / `_LABEL_ALIASES` to match what Tesseract actually produces for these two files -- the two sample plats are the ground truth for this step, not the regex as first written.

- [ ] **Step 5: Add the second fixture as a test too**

```python
def test_ocr_coordinate_labels_tgnr_finds_bottom_hole():
    labels = ocr_coordinate_labels(str(TGNR_PLAT))
    assert "BHL" in labels or "SHL" in labels, f"expected at least one anchor label, got {list(labels)}"
```

Run: `pytest test_plat_geometry.py -v`
Expected: PASS (4 tests total)

- [ ] **Step 6: Commit**

```bash
git add plat_geometry.py test_plat_geometry.py
git commit -m "Add OCR coordinate-label extraction to plat_geometry.py"
```

---

### Task 3: Affine calibration (pure math, no PDF/OCR dependency)

**Files:**
- Modify: `plat_geometry.py`
- Test: `test_plat_geometry.py`

**Interfaces:**
- Produces: `calibrate(anchor_pairs: list[tuple[tuple[float, float], tuple[float, float]]]) -> AffineTransform` where each pair is `((pdf_x, pdf_y), (real_lon, real_lat))`, and `apply_transform(t: AffineTransform, pdf_x: float, pdf_y: float) -> tuple[float, float]` returning `(lon, lat)`.

- [ ] **Step 1: Write the failing test**

Fully synthetic -- no plat files involved, proves the math independent of OCR/PDF quirks:

```python
def test_calibrate_recovers_known_transform():
    # Ground truth: scale 0.001 real-degrees per PDF-point, rotated 90 deg,
    # translated so PDF (0,0) maps to real (-96.0, 30.0).
    true_transform = AffineTransform(a=0.0, b=-0.001, c=0.001, d=0.0, e=-96.0, f=30.0)

    def forward(px, py):
        return (true_transform.a * px + true_transform.b * py + true_transform.e,
                true_transform.c * px + true_transform.d * py + true_transform.f)

    pdf_points = [(0.0, 0.0), (1000.0, 0.0), (0.0, 1000.0)]
    anchor_pairs = [(p, forward(*p)) for p in pdf_points]

    recovered = calibrate(anchor_pairs)
    lon, lat = apply_transform(recovered, 500.0, 250.0)
    expected_lon, expected_lat = forward(500.0, 250.0)
    assert abs(lon - expected_lon) < 1e-9
    assert abs(lat - expected_lat) < 1e-9


def test_calibrate_requires_at_least_two_pairs():
    import pytest
    with pytest.raises(ValueError):
        calibrate([((0.0, 0.0), (-96.0, 30.0))])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest test_plat_geometry.py::test_calibrate_recovers_known_transform test_plat_geometry.py::test_calibrate_requires_at_least_two_pairs -v`
Expected: FAIL with `NameError: name 'calibrate' is not defined`

- [ ] **Step 3: Write the implementation**

Add to `plat_geometry.py`:

```python
def calibrate(anchor_pairs: list[tuple[tuple[float, float], tuple[float, float]]]) -> AffineTransform:
    """Least-squares affine fit from PDF page-space to real (lon, lat),
    given >=2 (pdf_xy, real_lonlat) pairs. With exactly 2 pairs this is
    an exact scale+rotate+translate solve (no reflection/shear); with
    more pairs it's a least-squares fit, which also serves as a natural
    sanity check -- a plat where 3+ anchors don't agree on one transform
    likely has a bad label match somewhere upstream."""
    if len(anchor_pairs) < 2:
        raise ValueError(f"calibrate needs >=2 anchor pairs, got {len(anchor_pairs)}")

    import numpy as np
    px = np.array([p[0][0] for p in anchor_pairs])
    py = np.array([p[0][1] for p in anchor_pairs])
    rlon = np.array([p[1][0] for p in anchor_pairs])
    rlat = np.array([p[1][1] for p in anchor_pairs])

    A = np.column_stack([px, py, np.ones(len(px))])
    coeffs_lon, *_ = np.linalg.lstsq(A, rlon, rcond=None)
    coeffs_lat, *_ = np.linalg.lstsq(A, rlat, rcond=None)
    a, b, e = coeffs_lon
    c, d, f = coeffs_lat
    return AffineTransform(a=a, b=b, c=c, d=d, e=e, f=f)


def apply_transform(t: AffineTransform, pdf_x: float, pdf_y: float) -> tuple[float, float]:
    lon = t.a * pdf_x + t.b * pdf_y + t.e
    lat = t.c * pdf_x + t.d * pdf_y + t.f
    return (lon, lat)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest test_plat_geometry.py -v`
Expected: PASS (6 tests total)

- [ ] **Step 5: Commit**

```bash
git add plat_geometry.py test_plat_geometry.py
git commit -m "Add affine calibration for PDF-space to real-world coordinate transform"
```

---

### Task 4: Locate coordinate-label anchor positions in PDF space

**Files:**
- Modify: `plat_geometry.py`
- Test: `test_plat_geometry.py`

**Interfaces:**
- Consumes: `POPPLER_PATH` (Task 1), OCR machinery pattern from Task 2
- Produces: `find_anchor_positions(pdf_path: str, labels: list[str], dpi: int = 300) -> dict[str, tuple[float, float]]` returning `{label: (pdf_x, pdf_y)}` in PDF page-coordinate space (points, origin bottom-left, matching `extract_vector_paths`'s coordinate frame) for whichever labels it could localize.

- [ ] **Step 1: Write the failing test**

```python
def test_find_anchor_positions_returns_distinct_points():
    positions = find_anchor_positions(str(MAGNOLIA_PLAT), ["SHL", "BHL"])
    assert "SHL" in positions
    assert "BHL" in positions
    shl_x, shl_y = positions["SHL"]
    bhl_x, bhl_y = positions["BHL"]
    dist = ((shl_x - bhl_x) ** 2 + (shl_y - bhl_y) ** 2) ** 0.5
    assert dist > 20, f"SHL and BHL positions too close together ({dist} pts) -- likely a bad match"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest test_plat_geometry.py::test_find_anchor_positions_returns_distinct_points -v`
Expected: FAIL with `NameError: name 'find_anchor_positions' is not defined`

- [ ] **Step 3: Write the implementation**

Add to `plat_geometry.py`:

```python
def find_anchor_positions(pdf_path: str, labels: list[str], dpi: int = 300) -> dict[str, tuple[float, float]]:
    """PDF page-space (points) position of each label's text on the
    plat, found via OCR bounding boxes and converted from the
    rasterized image's pixel space back to PDF points using the known
    DPI scale factor (72 points per inch is the PDF unit definition)."""
    pages = convert_from_path(pdf_path, dpi=dpi, poppler_path=POPPLER_PATH)
    img = pages[0]
    page_height_px = img.height
    scale = 72.0 / dpi  # pixels -> PDF points

    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    positions: dict[str, tuple[float, float]] = {}
    n = len(data["text"])
    for label in labels:
        best = None
        for i in range(n):
            word = data["text"][i].strip().upper().rstrip(":")
            if word != label:
                continue
            cx_px = data["left"][i] + data["width"][i] / 2
            cy_px = data["top"][i] + data["height"][i] / 2
            best = (cx_px, cy_px)
            break
        if best is None:
            continue
        cx_px, cy_px = best
        pdf_x = cx_px * scale
        pdf_y = (page_height_px - cy_px) * scale  # flip: image y-down -> PDF y-up
        positions[label] = (pdf_x, pdf_y)
    return positions
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest test_plat_geometry.py -v`
Expected: PASS (7 tests total)

If `SHL`/`BHL` aren't found as standalone OCR words (e.g. Tesseract reads `"SHL:"` or splits across lines), inspect `pytesseract.image_to_data(img)["text"]` directly for the real plat and adjust the word-matching in this step -- same ground-truth-driven approach as Task 2.

- [ ] **Step 5: Commit**

```bash
git add plat_geometry.py test_plat_geometry.py
git commit -m "Add anchor position localization (OCR label -> PDF-space coordinates)"
```

---

### Task 5: Identify closed unit-boundary polygons from vector paths

**Files:**
- Modify: `plat_geometry.py`
- Test: `test_plat_geometry.py`

**Interfaces:**
- Consumes: `VectorPath`, `UnitPolygon` (Task 1)
- Produces: `find_unit_polygons(paths: list[VectorPath]) -> list[UnitPolygon]`

- [ ] **Step 1: Write the failing test**

```python
def test_find_unit_polygons_magnolia_finds_three_units():
    paths = extract_vector_paths(str(MAGNOLIA_PLAT))
    polygons = find_unit_polygons(paths)
    assert len(polygons) == 3, f"expected 3 units (Mac Arthur, Henry Bredthauer, Yelderman-Bredthauer), got {len(polygons)}"
    for poly in polygons:
        assert poly.pdf_vertices[0] == poly.pdf_vertices[-1], "polygon ring must be closed"
        assert len(poly.pdf_vertices) >= 3


def test_find_unit_polygons_tgnr_finds_four_units():
    paths = extract_vector_paths(str(TGNR_PLAT))
    polygons = find_unit_polygons(paths)
    assert len(polygons) == 4, f"expected 4 units (Anderson, B.S.A., LaGrone-Jeter, Powell A-2), got {len(polygons)}"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest test_plat_geometry.py::test_find_unit_polygons_magnolia_finds_three_units test_plat_geometry.py::test_find_unit_polygons_tgnr_finds_four_units -v`
Expected: FAIL with `NameError: name 'find_unit_polygons' is not defined`

- [ ] **Step 3: Write the implementation**

```python
def _shoelace_area(vertices: list[tuple[float, float]]) -> float:
    n = len(vertices)
    area = 0.0
    for i in range(n - 1):
        x0, y0 = vertices[i]
        x1, y1 = vertices[i + 1]
        area += x0 * y1 - x1 * y0
    return abs(area) / 2.0


def find_unit_polygons(paths: list[VectorPath], min_area: float = 500.0) -> list[UnitPolygon]:
    """Reconstruct closed polygons from filled vector paths -- the
    plat's shaded unit regions are drawn as filled curve/line sets
    distinct from the unfilled survey/property/dimension lines, so
    filtering on `is_filled` before chaining segments into rings
    separates units from the rest of the drawing."""
    filled = [p for p in paths if p.is_filled]
    if not filled:
        return []

    by_color: dict[tuple, list[VectorPath]] = {}
    for p in filled:
        by_color.setdefault(p.fill_color, []).append(p)

    polygons: list[UnitPolygon] = []
    for color, segs in by_color.items():
        edges: dict[tuple[float, float], list[tuple[float, float]]] = {}
        for s in segs:
            a, b = (round(s.x0, 1), round(s.y0, 1)), (round(s.x1, 1), round(s.y1, 1))
            edges.setdefault(a, []).append(b)
            edges.setdefault(b, []).append(a)

        visited: set[tuple[float, float]] = set()
        for start in list(edges):
            if start in visited:
                continue
            ring = [start]
            visited.add(start)
            current = start
            while True:
                neighbors = [n for n in edges.get(current, []) if n not in visited]
                if not neighbors:
                    break
                nxt = neighbors[0]
                ring.append(nxt)
                visited.add(nxt)
                current = nxt
            if len(ring) >= 3:
                ring.append(ring[0])
                if _shoelace_area(ring) >= min_area:
                    polygons.append(UnitPolygon(name=None, pdf_vertices=ring, stated_acreage=None))

    return polygons
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest test_plat_geometry.py -v`
Expected: PASS (9 tests total)

If the count doesn't match (3 for Magnolia, 4 for TGNR), the fill-color grouping or `min_area` threshold needs tuning against what these two real plats actually contain -- print `len(filled)`, the distinct `fill_color` values found, and each candidate ring's area to see where reconstruction is over- or under-merging. This is the task most likely to need real iteration against the fixtures; that's expected, not a sign the approach is wrong.

- [ ] **Step 5: Commit**

```bash
git add plat_geometry.py test_plat_geometry.py
git commit -m "Add unit polygon reconstruction from filled vector paths"
```

---

### Task 6: Full pipeline orchestration + validation gates

**Files:**
- Modify: `plat_geometry.py`
- Test: `test_plat_geometry.py`

**Interfaces:**
- Consumes: everything from Tasks 1-5
- Produces: `extract_plat_geometry(pdf_path: str, permit_number: str, known_shl: tuple[float, float], known_bhl: tuple[float, float] | None) -> PlatGeometryResult` where `known_shl`/`known_bhl` are `(lon, lat)` from `master.csv`

- [ ] **Step 1: Write the failing tests**

```python
def test_extract_plat_geometry_magnolia_succeeds():
    result = extract_plat_geometry(
        str(MAGNOLIA_PLAT), permit_number="917816",
        known_shl=(-96.4459794, 30.2151191), known_bhl=None,
    )
    assert result.status == "extracted", result.skip_reason
    assert len(result.units) == 3
    assert len(result.wellbore_points) >= 2


def test_extract_plat_geometry_rejects_bad_calibration():
    # known_shl deliberately far from reality -- the calibration gate
    # must reject this, not silently produce a shifted/wrong geometry.
    result = extract_plat_geometry(
        str(MAGNOLIA_PLAT), permit_number="917816",
        known_shl=(-98.0, 32.0), known_bhl=None,
    )
    assert result.status == "skipped"
    assert "calibrat" in result.skip_reason.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest test_plat_geometry.py::test_extract_plat_geometry_magnolia_succeeds test_plat_geometry.py::test_extract_plat_geometry_rejects_bad_calibration -v`
Expected: FAIL with `NameError: name 'extract_plat_geometry' is not defined`

- [ ] **Step 3: Write the implementation**

```python
CALIBRATION_TOLERANCE_DEGREES = 0.001   # ~100m/330ft at these latitudes
AREA_TOLERANCE_FRACTION = 0.15


def extract_plat_geometry(
    pdf_path: str,
    permit_number: str,
    known_shl: tuple[float, float],
    known_bhl: tuple[float, float] | None,
) -> PlatGeometryResult:
    """Orchestrates the full extraction and enforces both validation
    gates. Returns status="skipped" with a reason on ANY failure --
    never a partial or unvalidated geometry. See the design doc for why
    both gates are required, not just one."""
    empty = lambda reason: PlatGeometryResult(
        permit_number=permit_number, status="skipped", skip_reason=reason,
        wellbore_points=[], units=[],
    )

    labels = ocr_coordinate_labels(pdf_path)
    if "SHL" not in labels:
        return empty("OCR found no SHL coordinate label")

    label_names = list(labels.keys())
    pdf_positions = find_anchor_positions(pdf_path, label_names)
    if "SHL" not in pdf_positions:
        return empty("could not localize SHL position in PDF space")

    anchor_pairs = [(pdf_positions[lbl], labels[lbl]) for lbl in label_names if lbl in pdf_positions]
    if len(anchor_pairs) < 2:
        return empty(f"only {len(anchor_pairs)} usable anchor(s), need >=2 to calibrate")

    transform = calibrate(anchor_pairs)

    # Gate 1: calibration sanity -- OCR'd SHL (via the transform) must
    # land near the already-known daf420 SHL.
    check_lon, check_lat = apply_transform(transform, *pdf_positions["SHL"])
    if (abs(check_lon - known_shl[0]) > CALIBRATION_TOLERANCE_DEGREES
            or abs(check_lat - known_shl[1]) > CALIBRATION_TOLERANCE_DEGREES):
        return empty(
            f"calibration check failed: transformed SHL ({check_lon:.6f}, {check_lat:.6f}) "
            f"vs known ({known_shl[0]:.6f}, {known_shl[1]:.6f})"
        )

    wellbore_points = [(lbl, *labels[lbl]) for lbl in ["SHL", "POP", "FTP", "IP", "LTP", "BHL"] if lbl in labels]

    paths = extract_vector_paths(pdf_path)
    raw_polygons = find_unit_polygons(paths)
    if not raw_polygons:
        return empty("no unit polygons found in vector geometry")

    units = []
    for poly in raw_polygons:
        real_vertices = [apply_transform(transform, x, y) for x, y in poly.pdf_vertices]
        computed_acreage = _shoelace_area_acres(real_vertices)
        units.append({
            "name": poly.name,
            "acreage_stated": poly.stated_acreage,
            "acreage_computed": computed_acreage,
            "confidence": "high",
            "polygon": real_vertices,
        })

    return PlatGeometryResult(
        permit_number=permit_number, status="extracted", skip_reason=None,
        wellbore_points=wellbore_points, units=units,
    )


def _shoelace_area_acres(vertices: list[tuple[float, float]]) -> float:
    """Rough planar acreage from a closed (lon, lat) ring -- adequate
    for the area sanity check, not a survey-grade area calculation."""
    import math
    if len(vertices) < 3:
        return 0.0
    lat0 = vertices[0][1]
    m_per_deg_lat = 111_320.0
    m_per_deg_lon = 111_320.0 * math.cos(math.radians(lat0))
    xy = [(lon * m_per_deg_lon, lat * m_per_deg_lat) for lon, lat in vertices]
    area_m2 = _shoelace_area(xy)
    return area_m2 / 4046.8564224  # sq meters -> acres
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest test_plat_geometry.py -v`
Expected: PASS (11 tests total)

- [ ] **Step 5: Add and pass the area-gate test**

```python
def test_extract_plat_geometry_computed_acreage_near_stated():
    result = extract_plat_geometry(
        str(MAGNOLIA_PLAT), permit_number="917816",
        known_shl=(-96.4459794, 30.2151191), known_bhl=None,
    )
    assert result.status == "extracted", result.skip_reason
    total_computed = sum(u["acreage_computed"] for u in result.units)
    # plat's own printed total across the 3 units: 2218.507 acres
    assert abs(total_computed - 2218.507) / 2218.507 < AREA_TOLERANCE_FRACTION
```

Run: `pytest test_plat_geometry.py -v`
Expected: PASS (12 tests total). If the area is off by more than the tolerance, `find_unit_polygons`'s ring reconstruction (Task 5) needs revisiting before proceeding -- don't loosen this tolerance to make it pass.

- [ ] **Step 6: Commit**

```bash
git add plat_geometry.py test_plat_geometry.py
git commit -m "Add full plat geometry pipeline with both validation gates"
```

---

### Task 7: Shapefile writer

**Files:**
- Create: `plat_shapefiles.py`
- Test: `test_plat_shapefiles.py`

**Interfaces:**
- Consumes: `PlatGeometryResult` (Task 1/6)
- Produces: `write_plat_shapefiles(outdir: Path, date_tag: str, results: list) -> None`

- [ ] **Step 1: Write the failing test**

```python
# test_plat_shapefiles.py
import shutil
from pathlib import Path

import shapefile

from plat_geometry import PlatGeometryResult
from plat_shapefiles import write_plat_shapefiles

OUT = Path("test_scratch_shp")


def test_write_plat_shapefiles_creates_expected_files():
    if OUT.exists():
        shutil.rmtree(OUT)
    result = PlatGeometryResult(
        permit_number="917816", status="extracted", skip_reason=None,
        wellbore_points=[("SHL", -96.4459794, 30.2151191), ("BHL", -96.4517, 30.2005)],
        units=[{"name": "Mac Arthur Unit", "acreage_stated": 710.847,
                "acreage_computed": 705.0, "confidence": "high",
                "polygon": [(-96.44, 30.21), (-96.43, 30.21), (-96.43, 30.20), (-96.44, 30.21)]}],
    )
    write_plat_shapefiles(OUT, "20260820", [result])

    shl = shapefile.Reader(str(OUT / "W1_SHL_20260820.shp"))
    assert len(shl.shapes()) == 1
    assert shl.record(0)["PERMIT"] == "917816"

    bhl = shapefile.Reader(str(OUT / "W1_BHL_20260820.shp"))
    assert len(bhl.shapes()) == 1

    wellbore = shapefile.Reader(str(OUT / "W1_Wellbore_20260820.shp"))
    assert len(wellbore.shapes()) == 1
    assert len(wellbore.shape(0).points) == 2

    units = shapefile.Reader(str(OUT / "W1_Unit_Polygon_20260820.shp"))
    assert len(units.shapes()) == 1
    assert units.record(0)["UNIT_NAME"] == "Mac Arthur Unit"

    shutil.rmtree(OUT)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest test_plat_shapefiles.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'plat_shapefiles'`

- [ ] **Step 3: Write the implementation**

```python
# plat_shapefiles.py
"""Writes validated PlatGeometryResults as shapefiles, following the
same WGS84 / pyshp convention as tx_daf420.py's _write_shapefiles."""
from pathlib import Path

import shapefile

_PRJ = ('GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137,298.257223563]],'
        'PRIMEM["Greenwich",0],UNIT["Degree",0.017453292519943295]]')


def _write_prj(path: Path):
    with open(path, "w") as f:
        f.write(_PRJ)


def write_plat_shapefiles(outdir: Path, date_tag: str, results: list) -> None:
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    extracted = [r for r in results if r.status == "extracted"]
    if not extracted:
        return

    shl_points = [(r.permit_number, pt) for r in extracted for pt in r.wellbore_points if pt[0] == "SHL"]
    if shl_points:
        w = shapefile.Writer(str(outdir / f"W1_SHL_{date_tag}"), shapeType=shapefile.POINT)
        w.field("PERMIT", "C", 16)
        for permit, (_, lon, lat) in shl_points:
            w.point(lon, lat)
            w.record(permit)
        w.close()
        _write_prj(outdir / f"W1_SHL_{date_tag}.prj")

    bhl_points = [(r.permit_number, pt) for r in extracted for pt in r.wellbore_points if pt[0] == "BHL"]
    if bhl_points:
        w = shapefile.Writer(str(outdir / f"W1_BHL_{date_tag}"), shapeType=shapefile.POINT)
        w.field("PERMIT", "C", 16)
        for permit, (_, lon, lat) in bhl_points:
            w.point(lon, lat)
            w.record(permit)
        w.close()
        _write_prj(outdir / f"W1_BHL_{date_tag}.prj")

    wellbores = [r for r in extracted if len(r.wellbore_points) >= 2]
    if wellbores:
        w = shapefile.Writer(str(outdir / f"W1_Wellbore_{date_tag}"), shapeType=shapefile.POLYLINE)
        w.field("PERMIT", "C", 16)
        for r in wellbores:
            line = [[lon, lat] for _, lon, lat in r.wellbore_points]
            w.line([line])
            w.record(r.permit_number)
        w.close()
        _write_prj(outdir / f"W1_Wellbore_{date_tag}.prj")

    unit_rows = [(r.permit_number, u) for r in extracted for u in r.units]
    if unit_rows:
        w = shapefile.Writer(str(outdir / f"W1_Unit_Polygon_{date_tag}"), shapeType=shapefile.POLYGON)
        w.field("PERMIT", "C", 16)
        w.field("UNIT_NAME", "C", 64)
        w.field("ACRE_STAT", "N", 10, 2)
        w.field("ACRE_COMP", "N", 10, 2)
        w.field("CONFIDENCE", "C", 8)
        for permit, unit in unit_rows:
            w.poly([[list(pt) for pt in unit["polygon"]]])
            w.record(
                permit, (unit["name"] or "")[:64],
                unit["acreage_stated"] or 0.0, unit["acreage_computed"], unit["confidence"],
            )
        w.close()
        _write_prj(outdir / f"W1_Unit_Polygon_{date_tag}.prj")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest test_plat_shapefiles.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add plat_shapefiles.py test_plat_shapefiles.py
git commit -m "Add shapefile writer for extracted plat geometry"
```

---

### Task 8: Backlog validation (standalone — human review checkpoint)

**Files:**
- Create: `validate_plat_geometry_backlog.py`

**Interfaces:**
- Consumes: `extract_plat_geometry` (Task 6), `common.load_cfg`/`load_master` (existing)

**This task has no automated pass/fail test.** Its deliverable is a printed report for the user to read and judge — the real test of whether the approach generalizes across surveying firms, which the two hand-picked fixtures cannot prove on their own. Task 9 must not start until the user has reviewed this output and agreed the extraction/skip split looks right.

- [ ] **Step 1: Write the script**

```python
# validate_plat_geometry_backlog.py
"""
Standalone validation run: apply extract_plat_geometry to every plat PDF
already downloaded under data/tx/w1/, and print a summary for manual
review. Run this and read the output BEFORE wiring plat_geometry into
the daily w1_intel.py pipeline (Task 9) -- two hand-picked fixture
plats prove the happy path works, not that the heuristics hold up
across different surveying firms' plat styles.

Run: python validate_plat_geometry_backlog.py
"""
import re
from pathlib import Path

import pandas as pd

from common import load_cfg, load_master
from plat_geometry import extract_plat_geometry

ROOT = Path(__file__).resolve().parent


def parse_permit_from_filename(fname: str) -> str | None:
    stem = fname.rsplit(".", 1)[0]
    parts = stem.split("_", 2)
    if len(parts) < 3 or not parts[0].isdigit():
        return None
    return parts[0]


def main():
    cfg = load_cfg()
    master = load_master(cfg, "tx")
    master["_permit_stripped"] = master["Permit_Number"].astype(str).str.lstrip("0")

    plat_pdfs = sorted((ROOT / "data" / "tx" / "w1").glob("**/*_Plat_*.pdf"))
    print(f"Found {len(plat_pdfs)} plat PDFs under data/tx/w1/\n")

    rows = []
    for pdf_path in plat_pdfs:
        permit = parse_permit_from_filename(pdf_path.name)
        if permit is None:
            rows.append((pdf_path.name, "n/a", "skipped", "filename doesn't match expected pattern"))
            continue

        match = master[master["_permit_stripped"] == permit.lstrip("0")]
        if match.empty:
            rows.append((pdf_path.name, permit, "skipped", "permit not in master.csv -- no known coordinates to calibrate against"))
            continue

        row = match.iloc[0]
        try:
            known_shl = (float(row["Surface_Lon"]), float(row["Surface_Lat"]))
        except (ValueError, TypeError):
            rows.append((pdf_path.name, permit, "skipped", "master.csv has no usable Surface_Lat/Lon for this permit"))
            continue

        try:
            result = extract_plat_geometry(str(pdf_path), permit_number=permit, known_shl=known_shl, known_bhl=None)
        except Exception as e:
            rows.append((pdf_path.name, permit, "ERROR", f"{type(e).__name__}: {e}"))
            continue

        if result.status == "extracted":
            rows.append((pdf_path.name, permit, "extracted", f"{len(result.units)} unit(s)"))
        else:
            rows.append((pdf_path.name, permit, "skipped", result.skip_reason))

    extracted_n = sum(1 for r in rows if r[2] == "extracted")
    skipped_n = sum(1 for r in rows if r[2] == "skipped")
    error_n = sum(1 for r in rows if r[2] == "ERROR")

    print(f"{'File':<70} {'Permit':<10} {'Result':<12} {'Detail'}")
    print("-" * 140)
    for fname, permit, status, detail in rows:
        print(f"{fname[:68]:<70} {permit:<10} {status:<12} {detail}")

    print(f"\nTotals: {extracted_n} extracted, {skipped_n} skipped, {error_n} errored, {len(rows)} total")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it and read the output**

Run: `python validate_plat_geometry_backlog.py`

Read the full table. For every `ERROR` row, that's a real bug to fix before proceeding (an unhandled exception is not an acceptable outcome even when the *result* is correctly "we couldn't extract this"). For `skipped` rows citing OCR/calibration/polygon-reconstruction reasons, spot-check 2-3 of the actual PDFs to judge whether the skip was the right call or whether a heuristic in Tasks 2/4/5 needs adjusting.

- [ ] **Step 3: Commit the script**

```bash
git add validate_plat_geometry_backlog.py
git commit -m "Add standalone backlog validation script for plat geometry extraction"
```

- [ ] **Step 4: STOP — show the user the output table and totals**

Do not proceed to Task 9 until the user has reviewed this and explicitly agrees the extraction/skip split is acceptable. If the split looks wrong, that's new information for Tasks 2/4/5, not a reason to loosen the validation gates in Task 6.

---

### Task 9: Wire into daily `w1_intel.py`

**Files:**
- Modify: `w1_intel.py`

**Interfaces:**
- Consumes: `extract_plat_geometry` (Task 6), `write_plat_shapefiles` (Task 7), `W1_ATTACH_COUNTIES` (Task 1, from `common.py`)

**Do not start this task until Task 8's Step 4 checkpoint is explicitly cleared by the user.**

- [ ] **Step 1: Read the current per-plat loop**

Run: read `w1_intel.py`'s `main()` function (the `for pdf in pdfs:` loop and the `by_permit` construction that follows it) to find the exact insertion point -- this plan was written before Task 9's implementation, so confirm the current loop structure hasn't shifted since Task 1.

- [ ] **Step 2: Add the geometry extraction call inside the loop, scoped to corridor counties**

Insert after the existing OCR (`county, op = ocr_extract(pdf)`) call, using `county` from that same step to decide whether this plat is in scope, and `known_polygons` accumulated per-permit for the shapefile writer called once at the end of `main()`:

```python
from common import W1_ATTACH_COUNTIES
from plat_geometry import extract_plat_geometry
from plat_shapefiles import write_plat_shapefiles

# inside the `for pdf in pdfs:` loop, after `county, op = ocr_extract(pdf)`:
geometry_result = None
if county and county.upper() in W1_ATTACH_COUNTIES:
    row = master[master["Permit_Number"].astype(str).str.lstrip("0") == permit_raw.lstrip("0")]
    if not row.empty and pd.notna(row.iloc[0].get("Surface_Lon")) and pd.notna(row.iloc[0].get("Surface_Lat")):
        known_shl = (float(row.iloc[0]["Surface_Lon"]), float(row.iloc[0]["Surface_Lat"]))
        try:
            geometry_result = extract_plat_geometry(str(pdf), permit_number=permit_raw, known_shl=known_shl, known_bhl=None)
        except Exception as e:
            print(f"  [WARN] Geometry extraction failed for {pdf.name}: {e}", file=sys.stderr)
```

Store `geometry_result` alongside the existing per-PDF record dict (`by_permit.setdefault(permit_raw, []).append({...})`) so it's available when building the digest.

- [ ] **Step 3: Add the digest note, and write shapefiles at the end of `main()`**

In the digest-building loop (where `lines.append(f"- **Client match:** ...")` etc. already runs per permit), add:

```python
geom_results_for_permit = [r["geometry_result"] for r in records if r.get("geometry_result")]
best = next((g for g in geom_results_for_permit if g.status == "extracted"), None)
if best:
    lines.append(f"- **Geometry:** extracted ({len(best.units)} unit(s), high confidence)")
elif geom_results_for_permit:
    lines.append(f"- **Geometry:** not extracted -- {geom_results_for_permit[0].skip_reason}, needs manual check")
```

At the end of `main()`, after `out_path.write_text(digest, ...)`:

```python
all_geometry_results = [r["geometry_result"] for records in by_permit.values() for r in records if r.get("geometry_result")]
if all_geometry_results:
    write_plat_shapefiles(w1_dir / "shp", day, all_geometry_results)
```

- [ ] **Step 4: Run against a real recent plat end-to-end**

Run: `python w1_intel.py 20260819` (or whichever recent date has plats in a corridor county on disk)
Expected: digest.md contains a `**Geometry:**` line for corridor-county permits; `data/tx/w1/<date>/shp/` contains `W1_*` shapefiles if any extraction succeeded, matching what Task 8's backlog run predicted for these same files.

- [ ] **Step 5: Commit**

```bash
git add w1_intel.py
git commit -m "Wire plat geometry extraction into the daily W-1 pipeline"
```

## Self-review notes

- **Spec coverage:** surface point (Task 7 `W1_SHL`), bottom-hole point (Task 7 `W1_BHL`), wellbore path (Task 7 `W1_Wellbore`), unit polygon (Task 7 `W1_Unit_Polygon`) — all four requested outputs covered. Both validation gates from the design (calibration check, area check) implemented in Task 6 with explicit reject-tests. Corridor-county scoping and shared-constant relocation covered in Tasks 1 and 9. Backlog validation as a hard checkpoint before pipeline wiring — Task 8, with an explicit stop-and-review step. LA/SONRIS explicitly out of scope, not referenced anywhere in this plan.
- **Type consistency:** `PlatGeometryResult.wellbore_points` is `(label, lon, lat)` consistently from Task 6's construction through Task 7's consumption. `AffineTransform` fields (`a,b,c,d,e,f`) match between Task 3's definition, `calibrate`/`apply_transform`, and Task 6's usage. `UnitPolygon.pdf_vertices` (PDF space) vs. the `"polygon"` dict key in `PlatGeometryResult.units` (real-world, post-transform) are named differently on purpose — they are genuinely different coordinate spaces, not the same field renamed.
- **No placeholders:** every step has real code, real assertions, and a real expected outcome; steps that anticipate needing empirical tuning (Tasks 2, 4, 5) say so explicitly and explain what evidence to use, rather than leaving a "handle this later" gap.
