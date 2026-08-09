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
