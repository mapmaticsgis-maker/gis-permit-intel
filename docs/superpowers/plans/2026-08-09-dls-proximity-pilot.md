# DLS Proximity Pilot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone daily report that flags new TX RRC permits within 5 miles of DLS's actual job-site boundaries (not just corridor counties), as a pilot before extending proximity-ranking to other clients.

**Architecture:** A new `core/geometry.py` module (shapefile reading, reprojection, point/polygon distance math) plus a new top-level `dls_proximity_report.py` script (workbook job-name parsing, a fuzzy-match resolver with a human-confirmed cache, and report generation). No changes to the existing daily email pipeline — this reads already-computed `data/tx/out/<date>/new_permits.csv` and writes its own separate output.

**Tech Stack:** Python 3.14, `pyshp` (already a dependency) for shapefile reads, `pyproj` (new dependency, confirmed installs cleanly via prebuilt wheel) for coordinate reprojection, `openpyxl` (already a dependency) for the workbook, `pytest` for tests.

## Global Constraints

- Shapefiles only, no `.gdb` support (confirmed no `fiona`/`geopandas`/`osgeo` available; `FLATLAND_NORTH` and `TURNPIKE_LGL` both have real `.shp` equivalents alongside their `.gdb` versions, so this doesn't block the pilot).
- All distance math happens in **EPSG:5070** (NAD83 / CONUS Albers) after reprojection — never compare raw lat/lon from mismatched source CRSs directly.
- Default proximity radius: **5 miles**.
- TX permits only for this pilot (DLS's stated work is Texas Eagle Ford/Giddings).
- Distance to a permit is the **minimum of surface-point and bottomhole-point** distance to a job's boundary (approximates "distance to wellbore segment" from the spec without needing full segment-to-polygon geometry — documented as an approximation in code, not silently different from the spec's stated intent).
- Permit lat/lon is assumed **EPSG:4269 (NAD83 geographic)** — RRC's standard public-data CRS; this assumption is stated in code, not verified against an authoritative RRC source.
- Unresolved jobs and unreadable shapefiles are reported explicitly in the output, never silently dropped (matches the project's existing "provably-empty" philosophy — see `self_check.py`, `digest.py`).

---

## File Structure

- **Create:** `core/geometry.py` — shapefile reading, reprojection, point/polygon distance primitives. Pure functions, no I/O side effects beyond reading the shapefile itself.
- **Create:** `tests/test_geometry.py` — unit tests for reprojection accuracy and distance math against synthetic, hand-computable geometry.
- **Create:** `dls_proximity_report.py` — top-level script (matches the existing pattern of `w1_intel.py`, `la_pull.py`): job-name parsing, resolver, confirmation cache I/O, report generation, `main()`.
- **Create:** `tests/test_dls_proximity_report.py` — unit tests for the parser, resolver, and cache logic using temp directories and DLS's real workbook cell text as a fixture.
- **Modify:** `requirements.txt` — add `pyproj`.
- **Create (at runtime, not by a task):** `data/registry/dls_geometry_confirmed.json` — the confirmation cache, produced by running the script, not hand-authored.

---

### Task 1: Add pyproj dependency and coordinate reprojection

**Files:**
- Modify: `requirements.txt`
- Create: `core/geometry.py`
- Test: `tests/test_geometry.py`

**Interfaces:**
- Produces: `reproject_points(points: list[tuple[float, float]], source_wkt: str) -> list[tuple[float, float]]` — reprojects a list of (lon, lat) pairs from the CRS described by `source_wkt` to EPSG:5070, returns list of (x, y) in meters.
- Produces: `read_prj_wkt(prj_path: Path) -> str` — reads a `.prj` sidecar file's WKT text.

- [ ] **Step 1: Add pyproj to requirements.txt and install it**

Add this line to `requirements.txt` (keep alphabetical grouping with existing entries, or append at end):
```
pyproj
```

Run: `pip install pyproj`
Expected: `Successfully installed pyproj-3.7.2` (or similar recent version)

- [ ] **Step 2: Write the failing tests**

Create `tests/test_geometry.py`:
```python
from pathlib import Path

import pytest

from core.geometry import read_prj_wkt, reproject_points

NAD27_GEOGRAPHIC_WKT = (
    'GEOGCS["GCS_North_American_1927",'
    'DATUM["D_North_American_1927",SPHEROID["Clarke_1866",6378206.4,294.9786982]],'
    'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]'
)


def test_reproject_known_point_to_epsg5070():
    # Rough Giddings, TX-area coordinate. Expected EPSG:5070 x,y verified via
    # a direct pyproj.Transformer call against EPSG:4267 (NAD27 geographic).
    result = reproject_points([(-96.9, 30.1)], NAD27_GEOGRAPHIC_WKT)
    assert len(result) == 1
    x, y = result[0]
    assert x == pytest.approx(-86664.87, abs=1.0)
    assert y == pytest.approx(780907.63, abs=1.0)


def test_reproject_preserves_point_count_and_order():
    points = [(-96.9, 30.1), (-96.8, 30.2), (-96.7, 30.0)]
    result = reproject_points(points, NAD27_GEOGRAPHIC_WKT)
    assert len(result) == 3
    # Order preserved: increasing longitude should still increase x (same
    # general direction in an equal-area CRS over this small an extent).
    assert result[0][0] < result[1][0]


def test_read_prj_wkt_reads_file_contents(tmp_path):
    prj_path = tmp_path / "test.prj"
    prj_path.write_text(NAD27_GEOGRAPHIC_WKT, encoding="utf-8")
    assert read_prj_wkt(prj_path) == NAD27_GEOGRAPHIC_WKT
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_geometry.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.geometry'` (the module doesn't exist yet)

- [ ] **Step 4: Write the implementation**

Create `core/geometry.py`:
```python
"""
Shapefile geometry reading, reprojection, and distance math for the DLS
proximity pilot (docs/superpowers/plans/2026-08-09-dls-proximity-pilot.md).

All distance math happens in EPSG:5070 (NAD83 / CONUS Albers) -- shapefiles
in this pipeline have been observed in multiple source CRSs (e.g. NAD27
geographic on a real DLS shapefile), so raw lat/lon from different files is
never directly comparable without reprojecting to a common CRS first.
"""
from pathlib import Path

from pyproj import CRS, Transformer

TARGET_CRS = "EPSG:5070"

_transformer_cache: dict[str, Transformer] = {}


def _get_transformer(source_wkt: str) -> Transformer:
    if source_wkt not in _transformer_cache:
        source_crs = CRS.from_wkt(source_wkt)
        _transformer_cache[source_wkt] = Transformer.from_crs(
            source_crs, TARGET_CRS, always_xy=True
        )
    return _transformer_cache[source_wkt]


def reproject_points(
    points: list[tuple[float, float]], source_wkt: str
) -> list[tuple[float, float]]:
    """Reproject a list of (lon, lat) pairs from source_wkt's CRS to EPSG:5070.
    Returns a list of (x, y) in meters."""
    transformer = _get_transformer(source_wkt)
    return [transformer.transform(lon, lat) for lon, lat in points]


def read_prj_wkt(prj_path: Path) -> str:
    return prj_path.read_text(encoding="utf-8")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_geometry.py -v`
Expected: PASS (3 passed)

- [ ] **Step 6: Commit**

```bash
git add requirements.txt core/geometry.py tests/test_geometry.py
git commit -m "Add pyproj dependency and EPSG:5070 reprojection primitive"
```

---

### Task 2: Point-in-polygon and point-to-segment distance math

**Files:**
- Modify: `core/geometry.py`
- Test: `tests/test_geometry.py`

**Interfaces:**
- Consumes: nothing new from Task 1's public interface (these are independent geometry primitives).
- Produces: `point_in_ring(x: float, y: float, ring: list[tuple[float, float]]) -> bool`
- Produces: `distance_point_to_ring_miles(x: float, y: float, ring: list[tuple[float, float]]) -> float` — minimum distance in miles from a point to any edge of the ring (0.0 if the point is inside).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_geometry.py`:
```python
from core.geometry import distance_point_to_ring_miles, point_in_ring

# A 2000m x 2000m square in EPSG:5070 meters, centered at the origin.
SQUARE_RING = [(-1000, -1000), (1000, -1000), (1000, 1000), (-1000, 1000), (-1000, -1000)]


def test_point_inside_square_is_in_ring():
    assert point_in_ring(0, 0, SQUARE_RING) is True


def test_point_outside_square_is_not_in_ring():
    assert point_in_ring(5000, 5000, SQUARE_RING) is False


def test_point_on_boundary_counts_as_inside():
    assert point_in_ring(1000, 0, SQUARE_RING) is True


def test_distance_zero_for_point_inside():
    assert distance_point_to_ring_miles(0, 0, SQUARE_RING) == 0.0


def test_distance_for_point_outside_square():
    # 1000m due east of the square's right edge (edge at x=1000, y=0 is on
    # the boundary) -> straight-line distance is exactly 1000m = 0.6214 mi.
    result = distance_point_to_ring_miles(2000, 0, SQUARE_RING)
    assert result == pytest.approx(0.6214, abs=0.001)


def test_distance_for_point_diagonally_outside_square():
    # 1000m past the top-right corner (1000,1000) in both x and y ->
    # nearest point on the ring is the corner itself. Distance =
    # sqrt(1000^2 + 1000^2) meters = 1414.2m = 0.8788 mi.
    result = distance_point_to_ring_miles(2000, 2000, SQUARE_RING)
    assert result == pytest.approx(0.8788, abs=0.001)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_geometry.py -v`
Expected: FAIL with `ImportError: cannot import name 'point_in_ring'`

- [ ] **Step 3: Write the implementation**

Append to `core/geometry.py`:
```python
METERS_PER_MILE = 1609.34


def point_in_ring(x: float, y: float, ring: list[tuple[float, float]]) -> bool:
    """Ray-casting point-in-polygon test. A point exactly on the boundary
    counts as inside -- a permit sited on a job's AOI edge is "in" the job,
    not a coin-flip based on floating-point edge cases."""
    n = len(ring)
    inside = False
    for i in range(n - 1):
        x1, y1 = ring[i]
        x2, y2 = ring[i + 1]
        if _on_segment(x, y, x1, y1, x2, y2):
            return True
        if (y1 > y) != (y2 > y):
            x_intersect = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < x_intersect:
                inside = not inside
    return inside


def _on_segment(px, py, x1, y1, x2, y2, tol=1e-6) -> bool:
    return _dist_point_to_segment(px, py, x1, y1, x2, y2) <= tol


def _dist_point_to_segment(px, py, x1, y1, x2, y2) -> float:
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return ((px - x1) ** 2 + (py - y1) ** 2) ** 0.5
    t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    nearest_x, nearest_y = x1 + t * dx, y1 + t * dy
    return ((px - nearest_x) ** 2 + (py - nearest_y) ** 2) ** 0.5


def distance_point_to_ring_miles(x: float, y: float, ring: list[tuple[float, float]]) -> float:
    if point_in_ring(x, y, ring):
        return 0.0
    min_dist_m = min(
        _dist_point_to_segment(x, y, ring[i][0], ring[i][1], ring[i + 1][0], ring[i + 1][1])
        for i in range(len(ring) - 1)
    )
    return min_dist_m / METERS_PER_MILE
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_geometry.py -v`
Expected: PASS (8 passed)

- [ ] **Step 5: Commit**

```bash
git add core/geometry.py tests/test_geometry.py
git commit -m "Add point-in-polygon and point-to-boundary distance math"
```

---

### Task 3: Load and reproject a real shapefile

**Files:**
- Modify: `core/geometry.py`
- Test: `tests/test_geometry.py`

**Interfaces:**
- Consumes: `reproject_points()`, `read_prj_wkt()` (Task 1), `point_in_ring()`, `distance_point_to_ring_miles()` (Task 2).
- Produces: `Geometry` (a `NamedTuple` with fields `rings: list[list[tuple[float, float]]]`, `is_polygon: bool`).
- Produces: `load_shapefile_rings(shp_path: Path) -> Geometry` — reads a `.shp`/`.prj` pair via `pyshp`, reprojects to EPSG:5070, raises `GeometryLoadError` (new exception, defined in this module) on read failure rather than a raw pyshp/IO exception, so callers can catch one clear type.
- Produces: `distance_miles(x: float, y: float, geometry: Geometry) -> float` — 0.0 if inside any polygon ring, else the minimum distance to any ring's boundary (lines have no "inside", so this is always boundary-distance for `is_polygon=False`).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_geometry.py`:
```python
import shapefile as pyshp

from core.geometry import GeometryLoadError, distance_miles, load_shapefile_rings

WGS84_WKT = (
    'GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563]],'
    'PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433]]'
)


def _write_test_polygon_shapefile(base_path: Path):
    """A small square polygon roughly 500m on a side near Giddings, TX,
    written in WGS84 lon/lat -- mirrors how a real DLS AOI shapefile looks
    (geographic CRS, not already projected)."""
    with pyshp.Writer(str(base_path)) as w:
        w.field("name", "C")
        w.poly([[(-96.91, 30.10), (-96.90, 30.10), (-96.90, 30.11), (-96.91, 30.11), (-96.91, 30.10)]])
        w.record("test_aoi")
    (base_path.with_suffix(".prj")).write_text(WGS84_WKT, encoding="utf-8")


def test_load_shapefile_rings_reprojects_polygon(tmp_path):
    shp_path = tmp_path / "test_aoi.shp"
    _write_test_polygon_shapefile(shp_path)
    geometry = load_shapefile_rings(shp_path)
    assert geometry.is_polygon is True
    assert len(geometry.rings) == 1
    # Reprojected coordinates should be in EPSG:5070 meters, not raw
    # lon/lat degrees -- a sanity range check, not an exact value, since
    # the exact projected position isn't the point of this test.
    x, y = geometry.rings[0][0]
    assert abs(x) > 1000
    assert abs(y) > 1000


def test_load_shapefile_missing_file_raises_geometry_load_error(tmp_path):
    with pytest.raises(GeometryLoadError):
        load_shapefile_rings(tmp_path / "does_not_exist.shp")


def test_distance_miles_zero_for_point_inside_loaded_polygon(tmp_path):
    shp_path = tmp_path / "test_aoi.shp"
    _write_test_polygon_shapefile(shp_path)
    geometry = load_shapefile_rings(shp_path)
    # Center of the test square, reprojected the same way.
    cx, cy = reproject_points([(-96.905, 30.105)], WGS84_WKT)[0]
    assert distance_miles(cx, cy, geometry) == 0.0


def test_distance_miles_positive_for_point_outside_loaded_polygon(tmp_path):
    shp_path = tmp_path / "test_aoi.shp"
    _write_test_polygon_shapefile(shp_path)
    geometry = load_shapefile_rings(shp_path)
    # Roughly 50 miles east -- far outside the test square.
    fx, fy = reproject_points([(-96.0, 30.105)], WGS84_WKT)[0]
    assert distance_miles(fx, fy, geometry) > 10.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_geometry.py -v`
Expected: FAIL with `ImportError: cannot import name 'load_shapefile_rings'`

- [ ] **Step 3: Write the implementation**

Append to `core/geometry.py`:
```python
from typing import NamedTuple

import shapefile as pyshp


class Geometry(NamedTuple):
    rings: list[list[tuple[float, float]]]
    is_polygon: bool


class GeometryLoadError(Exception):
    pass


def load_shapefile_rings(shp_path: Path) -> Geometry:
    prj_path = shp_path.with_suffix(".prj")
    try:
        source_wkt = read_prj_wkt(prj_path)
        reader = pyshp.Reader(str(shp_path))
        shapes = reader.shapes()
    except Exception as e:
        raise GeometryLoadError(f"Failed to load {shp_path}: {e}") from e

    if not shapes:
        raise GeometryLoadError(f"{shp_path} has no shapes")

    is_polygon = shapes[0].shapeType in (pyshp.POLYGON, pyshp.POLYGONZ, pyshp.POLYGONM)
    rings: list[list[tuple[float, float]]] = []
    for shape in shapes:
        points = list(shape.points)
        parts = list(shape.parts) + [len(points)]
        for i in range(len(parts) - 1):
            ring = points[parts[i]:parts[i + 1]]
            rings.append(reproject_points(ring, source_wkt))
    return Geometry(rings=rings, is_polygon=is_polygon)


def distance_miles(x: float, y: float, geometry: Geometry) -> float:
    if geometry.is_polygon and any(point_in_ring(x, y, ring) for ring in geometry.rings):
        return 0.0
    return min(distance_point_to_ring_miles(x, y, ring) for ring in geometry.rings)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_geometry.py -v`
Expected: PASS (12 passed)

- [ ] **Step 5: Commit**

```bash
git add core/geometry.py tests/test_geometry.py
git commit -m "Load and reproject real shapefiles into distance-ready geometry"
```

---

### Task 4: DLS job-name parser

**Files:**
- Create: `dls_proximity_report.py`
- Test: `tests/test_dls_proximity_report.py`

**Interfaces:**
- Produces: `NON_JOB_KEYWORDS: set[str]`
- Produces: `parse_dls_jobs(cell_text: str) -> list[str]` — splits DLS's workbook cell into individual job names, respecting parenthesis nesting, filtering out report/deliverable descriptions.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_dls_proximity_report.py`:
```python
from dls_proximity_report import parse_dls_jobs

# DLS's actual current "Jobs / Prospect Names" cell text, verbatim.
DLS_REAL_CELL = (
    "Flatland (N/S, Tier 1-2), Turnpike, Updip/Caveman, Lee Co (Giddings, Sage, "
    "Crescent Pass), Meteor Impact units (War Admiral, Robert Grimm, Skater, "
    "Fountain, Spectre, Velocity), Zoch, Rosewood, Peebles, Blackshear, Parr, "
    "Monster Rock, Flywheel, Barter Ranch, weekly Master/Flatland report + "
    "shapefile updates, DLS dashboard"
)


def test_splits_simple_comma_separated_jobs():
    assert parse_dls_jobs("Zoch, Rosewood, Peebles") == ["Zoch", "Rosewood", "Peebles"]


def test_does_not_split_inside_parentheses():
    result = parse_dls_jobs("Lee Co (Giddings, Sage, Crescent Pass), Zoch")
    assert result == ["Lee Co (Giddings, Sage, Crescent Pass)", "Zoch"]


def test_filters_report_and_dashboard_entries():
    result = parse_dls_jobs("Zoch, weekly Master/Flatland report + shapefile updates, DLS dashboard")
    assert result == ["Zoch"]


def test_real_dls_cell_produces_expected_job_count():
    result = parse_dls_jobs(DLS_REAL_CELL)
    # 15 real job names: Flatland, Turnpike, Updip/Caveman, Lee Co, Meteor
    # Impact units, Zoch, Rosewood, Peebles, Blackshear, Parr, Monster Rock,
    # Flywheel, Barter Ranch -- the report/dashboard trailer is filtered.
    assert len(result) == 13
    assert "Flatland (N/S, Tier 1-2)" in result
    assert "Lee Co (Giddings, Sage, Crescent Pass)" in result
    assert not any("report" in job.lower() for job in result)
    assert not any("dashboard" in job.lower() for job in result)


def test_strips_whitespace_around_each_job():
    assert parse_dls_jobs("Zoch,  Rosewood ,Peebles") == ["Zoch", "Rosewood", "Peebles"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_dls_proximity_report.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'dls_proximity_report'`

- [ ] **Step 3: Write the implementation**

Create `dls_proximity_report.py`:
```python
#!/usr/bin/env python
"""
DLS proximity pilot: flags new TX RRC permits within 5 miles of DLS's actual
job-site boundaries, using real shapefile geometry rather than county-level
corridors. See docs/superpowers/specs/2026-08-09-dls-proximity-pilot-design.md.

Standalone report -- not wired into the daily email while unproven. Reads
already-computed data/tx/out/<date>/new_permits.csv rather than pulling new
data itself.

Run: python dls_proximity_report.py [YYYY-MM-DD]   (defaults to today)
"""
import re

NON_JOB_KEYWORDS = {"report", "dashboard", "update", "updates", "shapefile"}


def parse_dls_jobs(cell_text: str) -> list[str]:
    """Split DLS's workbook "Jobs / Prospect Names" cell into individual job
    names. Splits on top-level commas only -- a comma inside parentheses
    (e.g. "Lee Co (Giddings, Sage, Crescent Pass)") is a sub-area list for
    one job, not three separate jobs. Entries that look like report/
    deliverable descriptions rather than job names (containing any of
    NON_JOB_KEYWORDS) are dropped -- this is a narrow keyword rule, not a
    semantic judgment call, so a real job wrongly filtered later is a
    one-line fix to the keyword set."""
    jobs = []
    depth = 0
    current = []
    for ch in cell_text:
        if ch == "(":
            depth += 1
            current.append(ch)
        elif ch == ")":
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            jobs.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    if current:
        jobs.append("".join(current).strip())

    return [
        job for job in jobs
        if job and not any(kw in job.lower() for kw in NON_JOB_KEYWORDS)
    ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_dls_proximity_report.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add dls_proximity_report.py tests/test_dls_proximity_report.py
git commit -m "Add DLS job-name parser"
```

---

### Task 5: Fuzzy-match resolver

**Files:**
- Modify: `dls_proximity_report.py`
- Test: `tests/test_dls_proximity_report.py`

**Interfaces:**
- Consumes: nothing from earlier tasks directly (independent of the parser).
- Produces: `tokenize_for_match(name: str) -> set[str]`
- Produces: `resolve_candidates(job_name: str, search_dir: Path, limit: int = 5) -> list[Path]` — returns up to `limit` `.shp` file paths under `search_dir`, ranked by token overlap with `job_name`, highest first. Empty list if nothing scores above zero overlap.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_dls_proximity_report.py`:
```python
from pathlib import Path

from dls_proximity_report import resolve_candidates, tokenize_for_match


def test_tokenize_lowercases_and_splits_on_non_alnum():
    assert tokenize_for_match("Lee Co (Giddings, Sage)") == {"lee", "giddings", "sage"}


def test_tokenize_drops_short_tokens():
    # "Co" is 2 chars, dropped; this matters because "Co" appears in many
    # unrelated folder names and would otherwise cause false-positive matches.
    assert "co" not in tokenize_for_match("Lee Co")


def _touch(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")


def test_resolve_candidates_ranks_by_token_overlap(tmp_path):
    _touch(tmp_path / "FLATLAND_NORTH" / "AOI_NEW.shp")
    _touch(tmp_path / "TURNPIKE_LGL" / "turnpike_boundary.shp")
    _touch(tmp_path / "unrelated_folder" / "random.shp")

    result = resolve_candidates("Flatland (N/S, Tier 1-2)", tmp_path)

    assert len(result) >= 1
    assert result[0].name == "AOI_NEW.shp"
    assert "unrelated_folder" not in str(result[0])


def test_resolve_candidates_empty_when_nothing_matches(tmp_path):
    _touch(tmp_path / "completely_unrelated" / "random.shp")
    result = resolve_candidates("Flatland", tmp_path)
    assert result == []


def test_resolve_candidates_respects_limit(tmp_path):
    for i in range(10):
        _touch(tmp_path / f"turnpike_v{i}" / "turnpike.shp")
    result = resolve_candidates("Turnpike", tmp_path, limit=3)
    assert len(result) == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_dls_proximity_report.py -v`
Expected: FAIL with `ImportError: cannot import name 'tokenize_for_match'`

- [ ] **Step 3: Write the implementation**

Append to `dls_proximity_report.py` (add `Path` import at top):
```python
from pathlib import Path


def tokenize_for_match(name: str) -> set[str]:
    words = re.findall(r"[A-Za-z0-9]+", name.upper())
    return {w.lower() for w in words if len(w) >= 3}


def resolve_candidates(job_name: str, search_dir: Path, limit: int = 5) -> list[Path]:
    """Fuzzy-match a DLS job name against every .shp file under search_dir,
    scored by token overlap between the job name and the file's full path
    (so both folder and file names contribute -- FLATLAND_NORTH/AOI_NEW.shp
    matches "Flatland" via the folder name, not the filename)."""
    job_tokens = tokenize_for_match(job_name)
    if not job_tokens:
        return []

    scored = []
    for shp_path in search_dir.glob("**/*.shp"):
        path_tokens = tokenize_for_match(str(shp_path.relative_to(search_dir)))
        overlap = len(job_tokens & path_tokens)
        if overlap > 0:
            scored.append((overlap, shp_path))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [path for _, path in scored[:limit]]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_dls_proximity_report.py -v`
Expected: PASS (10 passed)

- [ ] **Step 5: Commit**

```bash
git add dls_proximity_report.py tests/test_dls_proximity_report.py
git commit -m "Add fuzzy-match resolver for DLS job names to shapefiles"
```

---

### Task 6: Confirmation cache

**Files:**
- Modify: `dls_proximity_report.py`
- Test: `tests/test_dls_proximity_report.py`

**Interfaces:**
- Consumes: `resolve_candidates()` (Task 5).
- Produces: `load_cache(cache_path: Path) -> dict` — returns `{}` if the file doesn't exist yet.
- Produces: `save_cache(cache_path: Path, cache: dict) -> None`
- Produces: `update_cache_with_new_jobs(cache: dict, job_names: list[str], search_dir: Path) -> dict` — for any `job_names` entry not already a key in `cache`, adds `{"status": "unconfirmed", "candidates": [str, ...]}` (candidate paths as strings, from `resolve_candidates`). Existing keys are left untouched. Returns the updated dict (mutates and returns the same object).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_dls_proximity_report.py`:
```python
import json

from dls_proximity_report import load_cache, save_cache, update_cache_with_new_jobs


def test_load_cache_returns_empty_dict_when_file_missing(tmp_path):
    assert load_cache(tmp_path / "does_not_exist.json") == {}


def test_save_and_load_cache_round_trip(tmp_path):
    cache_path = tmp_path / "cache.json"
    original = {"Zoch": {"status": "confirmed", "shapefile_path": "/x/zoch.shp"}}
    save_cache(cache_path, original)
    assert load_cache(cache_path) == original


def test_update_cache_adds_unconfirmed_entry_for_new_job(tmp_path):
    _touch_shp = tmp_path / "search" / "FLATLAND_NORTH" / "AOI_NEW.shp"
    _touch_shp.parent.mkdir(parents=True)
    _touch_shp.write_bytes(b"")

    cache = {}
    updated = update_cache_with_new_jobs(cache, ["Flatland (N/S, Tier 1-2)"], tmp_path / "search")

    assert "Flatland (N/S, Tier 1-2)" in updated
    entry = updated["Flatland (N/S, Tier 1-2)"]
    assert entry["status"] == "unconfirmed"
    assert any("AOI_NEW.shp" in c for c in entry["candidates"])


def test_update_cache_does_not_touch_existing_confirmed_entry(tmp_path):
    cache = {"Zoch": {"status": "confirmed", "shapefile_path": "/x/zoch.shp"}}
    updated = update_cache_with_new_jobs(cache, ["Zoch"], tmp_path)
    assert updated["Zoch"] == {"status": "confirmed", "shapefile_path": "/x/zoch.shp"}


def test_update_cache_marks_unresolved_when_no_candidates(tmp_path):
    (tmp_path / "search").mkdir()
    updated = update_cache_with_new_jobs({}, ["Completely Unmatchable Xyz"], tmp_path / "search")
    assert updated["Completely Unmatchable Xyz"]["status"] == "unconfirmed"
    assert updated["Completely Unmatchable Xyz"]["candidates"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_dls_proximity_report.py -v`
Expected: FAIL with `ImportError: cannot import name 'load_cache'`

- [ ] **Step 3: Write the implementation**

Append to `dls_proximity_report.py` (add `json` import at top):
```python
import json


def load_cache(cache_path: Path) -> dict:
    if not cache_path.exists():
        return {}
    return json.loads(cache_path.read_text(encoding="utf-8"))


def save_cache(cache_path: Path, cache: dict) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, indent=2, sort_keys=True), encoding="utf-8")


def update_cache_with_new_jobs(cache: dict, job_names: list[str], search_dir: Path) -> dict:
    for job_name in job_names:
        if job_name in cache:
            continue
        candidates = resolve_candidates(job_name, search_dir)
        cache[job_name] = {
            "status": "unconfirmed",
            "candidates": [str(p) for p in candidates],
        }
    return cache
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_dls_proximity_report.py -v`
Expected: PASS (15 passed)

- [ ] **Step 5: Commit**

```bash
git add dls_proximity_report.py tests/test_dls_proximity_report.py
git commit -m "Add confirmation cache read/write for resolved job geometry"
```

---

### Task 7: Nearest-job distance for a permit

**Files:**
- Modify: `dls_proximity_report.py`
- Test: `tests/test_dls_proximity_report.py`

**Interfaces:**
- Consumes: `core.geometry.load_shapefile_rings`, `core.geometry.distance_miles`, `core.geometry.reproject_points`, `core.geometry.GeometryLoadError` (Task 3); `load_cache` (Task 6).
- Produces: `PERMIT_CRS_WKT: str` (EPSG:4269 NAD83 geographic, module-level constant).
- Produces: `load_confirmed_geometries(cache: dict) -> dict[str, "core.geometry.Geometry"]` — for entries with `status == "confirmed"`, loads geometry; skips (with no exception) any that fail to load, so one bad shapefile doesn't crash the whole run.
- Produces: `nearest_job_distances(permit_row: dict, geometries: dict) -> list[tuple[str, float]]` — for a permit row with `Surface_Lat`/`Surface_Lon`/`BHL_Lat`/`BHL_Lon` keys, returns `[(job_name, distance_miles), ...]` for every confirmed job, using the closer of the surface or bottomhole point per job. Sorted nearest first.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_dls_proximity_report.py`:
```python
import shapefile as pyshp

from dls_proximity_report import load_confirmed_geometries, nearest_job_distances

WGS84_WKT_FOR_TEST = (
    'GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563]],'
    'PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433]]'
)


def _write_square_near_giddings(shp_path: Path):
    shp_path.parent.mkdir(parents=True, exist_ok=True)
    with pyshp.Writer(str(shp_path)) as w:
        w.field("name", "C")
        w.poly([[(-96.91, 30.10), (-96.90, 30.10), (-96.90, 30.11), (-96.91, 30.11), (-96.91, 30.10)]])
        w.record("test")
    shp_path.with_suffix(".prj").write_text(WGS84_WKT_FOR_TEST, encoding="utf-8")


def test_load_confirmed_geometries_skips_unconfirmed_entries(tmp_path):
    cache = {"Flatland": {"status": "unconfirmed", "candidates": []}}
    assert load_confirmed_geometries(cache) == {}


def test_load_confirmed_geometries_loads_confirmed_shapefile(tmp_path):
    shp_path = tmp_path / "flatland.shp"
    _write_square_near_giddings(shp_path)
    cache = {"Flatland": {"status": "confirmed", "shapefile_path": str(shp_path)}}

    geometries = load_confirmed_geometries(cache)

    assert "Flatland" in geometries


def test_load_confirmed_geometries_skips_unreadable_shapefile(tmp_path):
    cache = {"Flatland": {"status": "confirmed", "shapefile_path": str(tmp_path / "missing.shp")}}
    assert load_confirmed_geometries(cache) == {}


def test_nearest_job_distances_permit_inside_job_boundary(tmp_path):
    shp_path = tmp_path / "flatland.shp"
    _write_square_near_giddings(shp_path)
    geometries = load_confirmed_geometries(
        {"Flatland": {"status": "confirmed", "shapefile_path": str(shp_path)}}
    )
    permit_row = {
        "Surface_Lat": "30.105", "Surface_Lon": "-96.905",
        "BHL_Lat": "30.105", "BHL_Lon": "-96.905",
    }

    result = nearest_job_distances(permit_row, geometries)

    assert result == [("Flatland", 0.0)]


def test_nearest_job_distances_uses_closer_of_surface_or_bhl(tmp_path):
    shp_path = tmp_path / "flatland.shp"
    _write_square_near_giddings(shp_path)
    geometries = load_confirmed_geometries(
        {"Flatland": {"status": "confirmed", "shapefile_path": str(shp_path)}}
    )
    # Surface point far away, bottomhole point inside the square -- the
    # wellbore's BHL end is what should register as "in the job."
    permit_row = {
        "Surface_Lat": "31.0", "Surface_Lon": "-97.5",
        "BHL_Lat": "30.105", "BHL_Lon": "-96.905",
    }

    result = nearest_job_distances(permit_row, geometries)

    assert result == [("Flatland", 0.0)]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_dls_proximity_report.py -v`
Expected: FAIL with `ImportError: cannot import name 'load_confirmed_geometries'`

- [ ] **Step 3: Write the implementation**

Append to `dls_proximity_report.py` (add import at top: `from core.geometry import GeometryLoadError, distance_miles, load_shapefile_rings, reproject_points`):
```python
from core.geometry import GeometryLoadError, distance_miles, load_shapefile_rings, reproject_points

# RRC's public daf420 extract is standard NAD83 geographic -- assumed, not
# verified against an authoritative RRC source. If proximity results look
# systematically off by a small but consistent amount, this is the first
# thing to check.
PERMIT_CRS_WKT = (
    'GEOGCS["NAD83",DATUM["North_American_Datum_1983",'
    'SPHEROID["GRS 1980",6378137,298.257222101]],'
    'PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433]]'
)


def load_confirmed_geometries(cache: dict) -> dict:
    geometries = {}
    for job_name, entry in cache.items():
        if entry.get("status") != "confirmed":
            continue
        try:
            geometries[job_name] = load_shapefile_rings(Path(entry["shapefile_path"]))
        except GeometryLoadError:
            continue
    return geometries


def nearest_job_distances(permit_row: dict, geometries: dict) -> list[tuple[str, float]]:
    surface_lon, surface_lat = float(permit_row["Surface_Lon"]), float(permit_row["Surface_Lat"])
    bhl_lon, bhl_lat = float(permit_row["BHL_Lon"]), float(permit_row["BHL_Lat"])
    (sx, sy), (bx, by) = reproject_points(
        [(surface_lon, surface_lat), (bhl_lon, bhl_lat)], PERMIT_CRS_WKT
    )

    results = []
    for job_name, geometry in geometries.items():
        d = min(distance_miles(sx, sy, geometry), distance_miles(bx, by, geometry))
        results.append((job_name, d))

    results.sort(key=lambda pair: pair[1])
    return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_dls_proximity_report.py -v`
Expected: PASS (20 passed)

- [ ] **Step 5: Commit**

```bash
git add dls_proximity_report.py tests/test_dls_proximity_report.py
git commit -m "Compute nearest DLS job distance for a permit (surface + BHL aware)"
```

---

### Task 8: Report generation and main()

**Files:**
- Modify: `dls_proximity_report.py`
- Test: `tests/test_dls_proximity_report.py`

**Interfaces:**
- Consumes: everything from Tasks 4-7.
- Produces: `RADIUS_MILES: float = 5.0` (module-level constant).
- Produces: `build_report(day: str, unresolved_jobs: list[str], hits: list[dict]) -> str` — `hits` is a list of `{"permit": str, "operator": str, "job_name": str, "distance": float}` dicts, already filtered to `<= RADIUS_MILES` and sorted nearest first. Returns a markdown string with unresolved jobs listed first (if any), then hits grouped by job.
- Produces: `main() -> int` — CLI entry point, reads `sys.argv[1]` as an optional `YYYY-MM-DD` date (defaults to today), orchestrates the full pipeline, writes `data/dls_proximity/<date>.md`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_dls_proximity_report.py`:
```python
from dls_proximity_report import build_report


def test_build_report_lists_unresolved_jobs_first():
    report = build_report("2026-08-09", unresolved_jobs=["Zoch"], hits=[])
    assert "Zoch" in report
    assert "unresolved" in report.lower()
    # With no hits, the only other content is the "no permits found" line --
    # unresolved jobs must appear before it, not after.
    assert report.index("Zoch") < report.index("No new permits")


def test_build_report_lists_hits_grouped_by_job():
    hits = [
        {"permit": "917410", "operator": "TGNR PANOLA LLC", "job_name": "Flatland", "distance": 1.2},
        {"permit": "917999", "operator": "EOG RESOURCES, INC.", "job_name": "Flatland", "distance": 3.8},
    ]
    report = build_report("2026-08-09", unresolved_jobs=[], hits=hits)
    assert "Flatland" in report
    assert "917410" in report
    assert "1.2" in report
    assert "917999" in report


def test_build_report_states_when_no_hits_found():
    report = build_report("2026-08-09", unresolved_jobs=[], hits=[])
    assert "no" in report.lower() and "5" in report
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_dls_proximity_report.py -v`
Expected: FAIL with `ImportError: cannot import name 'build_report'`

- [ ] **Step 3: Write the implementation**

Append to `dls_proximity_report.py` (add imports at top: `import sys`, `import datetime as dt`; `import pandas as pd`; `import openpyxl`):
```python
import datetime as dt
import sys

import openpyxl
import pandas as pd

RADIUS_MILES = 5.0

ROOT = Path(__file__).resolve().parent
CACHE_PATH = ROOT / "data" / "registry" / "dls_geometry_confirmed.json"
DLS_SEARCH_DIR = Path(r"C:\GIS\CLIENT\DLS")
CLIENT_WORKBOOK = Path(r"C:\GIS\Mapmatics_Client_Master_UPDATED.xlsx")


def build_report(day: str, unresolved_jobs: list[str], hits: list[dict]) -> str:
    lines = [f"# DLS Proximity Report — {day}\n"]

    if unresolved_jobs:
        lines.append("## Unresolved jobs (no confirmed geometry -- edit the cache file)\n")
        for job in unresolved_jobs:
            lines.append(f"- {job}")
        lines.append("")

    if not hits:
        lines.append(f"No new permits found within {RADIUS_MILES} miles of a confirmed DLS job today.")
        return "\n".join(lines)

    lines.append(f"## Permits within {RADIUS_MILES} miles of a DLS job\n")
    by_job: dict[str, list[dict]] = {}
    for hit in hits:
        by_job.setdefault(hit["job_name"], []).append(hit)

    for job_name, job_hits in by_job.items():
        lines.append(f"### {job_name}")
        for hit in sorted(job_hits, key=lambda h: h["distance"]):
            lines.append(f"- {hit['operator']} — Permit #{hit['permit']} ({hit['distance']:.1f} mi)")
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    day = sys.argv[1] if len(sys.argv) > 1 else dt.date.today().isoformat()

    wb = openpyxl.load_workbook(CLIENT_WORKBOOK, data_only=True)
    ws = wb["Client Master"]
    dls_row = next(r for r in ws.iter_rows(min_row=2, values_only=True) if r[2] == "DLS")
    jobs_cell = dls_row[6]

    job_names = parse_dls_jobs(jobs_cell)
    cache = load_cache(CACHE_PATH)
    cache = update_cache_with_new_jobs(cache, job_names, DLS_SEARCH_DIR)
    save_cache(CACHE_PATH, cache)

    unresolved = [j for j in job_names if cache.get(j, {}).get("status") != "confirmed"]
    geometries = load_confirmed_geometries(cache)

    permits_path = ROOT / "data" / "tx" / "out" / day / "new_permits.csv"
    hits = []
    if permits_path.exists():
        permits = pd.read_csv(permits_path, dtype=str)
        for _, row in permits.iterrows():
            # No pre-filter on missing lat/lon here: nearest_job_distances
            # (Task 7, fixed after a reviewer found it crashing on the 47%
            # of a real day's TX permits missing BHL) already handles a
            # permit with only one usable point, returning [] only when
            # NEITHER point parses. Filtering here on "either missing" would
            # silently discard exactly the permits that fix was built to
            # still process.
            distances = nearest_job_distances(row.to_dict(), geometries)
            for job_name, distance in distances:
                if distance <= RADIUS_MILES:
                    hits.append({
                        "permit": row["Permit_Number"],
                        "operator": row["Operator_Name"],
                        "job_name": job_name,
                        "distance": distance,
                    })

    report = build_report(day, unresolved, hits)
    out_path = ROOT / "data" / "dls_proximity" / f"{day}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")
    print(report)
    print(f"\nSaved: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_dls_proximity_report.py -v`
Expected: PASS (23 passed)

- [ ] **Step 5: Commit**

```bash
git add dls_proximity_report.py tests/test_dls_proximity_report.py
git commit -m "Add report generation and main() entry point for DLS proximity pilot"
```

---

### Task 9: Pilot acceptance check (real data, human review)

**Files:** none created -- this task runs the real script and reviews real output, per the spec's "Pilot acceptance check" section.

**Interfaces:**
- Consumes: `main()` (Task 8), run as `python dls_proximity_report.py <date>` against real data.

- [ ] **Step 1: Run the full test suite once more to confirm a clean baseline**

Run: `pytest tests/test_geometry.py tests/test_dls_proximity_report.py -v`
Expected: all tests pass

- [ ] **Step 2: Run the script against real DLS data and a real recent TX permit day**

```bash
python dls_proximity_report.py 2026-08-08
```

Expected: runs without crashing, prints a report to stdout, writes `data/dls_proximity/2026-08-08.md`. Most or all of DLS's ~13 job names will show up as unresolved on this first run (the cache starts empty) -- this is expected, not a bug.

- [ ] **Step 3: Review the unresolved-jobs list and the proposed candidates**

Open `data/registry/dls_geometry_confirmed.json`. For each `"status": "unconfirmed"` entry, look at its `"candidates"` list and either:
- Change `"status"` to `"confirmed"` and add `"shapefile_path": "<the chosen candidate>"`, or
- Leave as `"unconfirmed"` with an empty or wrong candidate list if nothing in `C:\GIS\CLIENT\DLS\` actually represents that job yet.

This step needs the user's judgment (which shapefile is *actually* Flatland's current AOI) -- present the candidate list and ask, don't guess silently.

- [ ] **Step 4: Re-run with the confirmed cache and review the actual report**

```bash
python dls_proximity_report.py 2026-08-08
```

Expected: fewer or zero unresolved jobs; any permits within 5 miles of a confirmed job now show up under "Permits within 5 miles of a DLS job." Review with the user: do the flagged permits look plausible (right counties, right operators for that area)?

- [ ] **Step 5: Commit the confirmed cache**

```bash
git add data/registry/dls_geometry_confirmed.json data/dls_proximity/2026-08-08.md
git commit -m "Confirm initial DLS job-to-geometry mapping from pilot run"
```

---

## Self-Review

**Spec coverage:** Job-name parser (Task 4), resolver (Task 5), confirmation cache (Task 6), geometry + distance via pyshp/EPSG:5070 (Tasks 1-3, 7), surface+BHL-aware distance (Task 7), report generator (Task 8), unresolved-jobs-stated-not-dropped (Task 8's `build_report`), pilot acceptance check against real data (Task 9). All spec sections have a corresponding task.

**Placeholder scan:** No TBD/TODO markers; every step has complete, runnable code.

**Type consistency:** `Geometry` NamedTuple (Task 3) used consistently in Tasks 7-8. `cache` dict shape (`{job_name: {"status": ..., "candidates": [...] | "shapefile_path": ...}}`) consistent across Tasks 6-8. `hits` list-of-dicts shape consistent between Task 8's `main()` and `build_report()`.
