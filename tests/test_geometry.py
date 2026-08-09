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
