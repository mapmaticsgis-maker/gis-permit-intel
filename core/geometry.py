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


def point_in_rings(x: float, y: float, rings: list[list[tuple[float, float]]]) -> bool:
    """Even-odd containment across every ring of a shape combined -- unlike
    point_in_ring (single ring only), this correctly handles multi-part
    polygons where interior rings are holes: a point inside a hole is NOT
    "inside" the shape, even though it may be inside the exterior ring.
    A point on the boundary of any ring counts as inside (matches
    point_in_ring's boundary-inclusion behavior)."""
    inside = False
    for ring in rings:
        n = len(ring)
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
    if geometry.is_polygon and point_in_rings(x, y, geometry.rings):
        return 0.0
    if geometry.is_polygon and geometry.rings:
        # Point is outside the polygon (using even-odd rule across all rings).
        # When a point is outside, it may be inside an interior ring (hole), so
        # always compute distance to all ring boundaries, not just the exterior.
        distances = []
        for ring in geometry.rings:
            min_dist_m = min(
                _dist_point_to_segment(x, y, ring[i][0], ring[i][1], ring[i + 1][0], ring[i + 1][1])
                for i in range(len(ring) - 1)
            )
            distances.append(min_dist_m / METERS_PER_MILE)
        return min(distances)
    return min(distance_point_to_ring_miles(x, y, ring) for ring in geometry.rings)
