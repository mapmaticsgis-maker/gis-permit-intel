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
