from pathlib import Path

import pytest

from core.geometry import distance_point_to_ring_miles, point_in_ring, read_prj_wkt, reproject_points

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


import shapefile as pyshp

from core.geometry import GeometryLoadError, distance_miles, load_shapefile_rings, point_in_rings

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
    assert len(geometry.shapes) == 1
    assert len(geometry.shapes[0]) == 1
    # Reprojected coordinates should be in EPSG:5070 meters, not raw
    # lon/lat degrees -- a sanity range check, not an exact value, since
    # the exact projected position isn't the point of this test.
    x, y = geometry.shapes[0][0][0]
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


def test_point_in_rings_handles_donut_hole():
    outer = [(-2000, -2000), (2000, -2000), (2000, 2000), (-2000, 2000), (-2000, -2000)]
    hole = [(-500, -500), (500, -500), (500, 500), (-500, 500), (-500, -500)]
    # Point in the hole -- must NOT be inside the donut shape.
    assert point_in_rings(0, 0, [outer, hole]) is False
    # Point in the donut's "meat" (between hole and outer boundary) -- inside.
    assert point_in_rings(1000, 1000, [outer, hole]) is True
    # Point outside the outer ring entirely -- not inside.
    assert point_in_rings(5000, 5000, [outer, hole]) is False


def test_distance_miles_nonzero_for_point_inside_polygon_hole(tmp_path):
    with pyshp.Writer(str(tmp_path / "donut.shp")) as w:
        w.field("name", "C")
        w.poly([
            [(-96.93, 30.08), (-96.87, 30.08), (-96.87, 30.12), (-96.93, 30.12), (-96.93, 30.08)],
            [(-96.905, 30.095), (-96.895, 30.095), (-96.895, 30.105), (-96.905, 30.105), (-96.905, 30.095)],
        ])
        w.record("donut")
    (tmp_path / "donut.prj").write_text(WGS84_WKT, encoding="utf-8")

    geometry = load_shapefile_rings(tmp_path / "donut.shp")
    # Center of the hole -- reprojected the same way as the shapefile.
    hx, hy = reproject_points([(-96.9, 30.1)], WGS84_WKT)[0]

    assert distance_miles(hx, hy, geometry) > 0.0


def test_distance_miles_correct_for_two_separate_nested_polygon_shapes(tmp_path):
    """Regression test for finding #5: two separate, non-overlapping-as-a-
    single-shape polygons (each its own shape record -- NOT one shape with a
    hole) in ONE shapefile. Flattening both shapes' rings into a single pool
    and applying even-odd across all of them (the old, buggy behavior) treats
    the inner shape's ring as if it were a hole in the outer shape, so a
    point genuinely inside both shapes incorrectly reads as outside. Each
    shape's containment must be evaluated independently."""
    shp_path = tmp_path / "nested_shapes.shp"
    with pyshp.Writer(str(shp_path)) as w:
        w.field("name", "C")
        # Shape A: a large square.
        w.poly([[(-96.95, 30.05), (-96.85, 30.05), (-96.85, 30.15), (-96.95, 30.15), (-96.95, 30.05)]])
        w.record("shape_a")
        # Shape B: a small square nested entirely inside shape A's extent,
        # but written as a SEPARATE shape -- not a hole ring of shape A.
        w.poly([[(-96.905, 30.095), (-96.895, 30.095), (-96.895, 30.105), (-96.905, 30.105), (-96.905, 30.095)]])
        w.record("shape_b")
    (shp_path.with_suffix(".prj")).write_text(WGS84_WKT, encoding="utf-8")

    geometry = load_shapefile_rings(shp_path)
    assert len(geometry.shapes) == 2

    # Center of shape B -- inside both shape A and shape B.
    cx, cy = reproject_points([(-96.9, 30.1)], WGS84_WKT)[0]
    assert distance_miles(cx, cy, geometry) == 0.0


def test_distance_miles_positive_for_point_near_open_polyline(tmp_path):
    """Regression test for finding #6: a line geometry (is_polygon=False)
    must never be given a phantom "interior" via a containment check. A point
    near but not on any segment of an open polyline must return its real
    distance to the nearest segment, not 0.0."""
    shp_path = tmp_path / "line.shp"
    with pyshp.Writer(str(shp_path)) as w:
        w.field("name", "C")
        w.line([[(-96.91, 30.10), (-96.90, 30.10), (-96.90, 30.11)]])
        w.record("test_line")
    (shp_path.with_suffix(".prj")).write_text(WGS84_WKT, encoding="utf-8")

    geometry = load_shapefile_rings(shp_path)
    assert geometry.is_polygon is False

    # Roughly the centroid of the line's points -- not exactly on any segment.
    cx, cy = reproject_points([(-96.905, 30.103)], WGS84_WKT)[0]
    assert distance_miles(cx, cy, geometry) > 0.0
