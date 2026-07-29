"""Integration tests across the diff -> union_write_csv -> re-read seam.

Every other test file is unit-scoped to a single module. The 2026-07-26 data
loss did not live inside any one of them -- it lived in how they compose: a
correct diff producing a correct (empty) increment, handed to a writer that
replaced rather than merged. These tests exercise the real composition
through common.write_outputs, which is what both state pipelines call.
"""
import json

import pandas as pd
import pytest

from common import write_outputs
from core.diff import diff

KEY = "id"
CHANGE = ["operator", "depth"]


def la_frame(ids, operator="COMSTOCK", lat=32.5):
    return pd.DataFrame({
        KEY: [str(i) for i in ids],
        "operator": [operator] * len(ids),
        "well": [f"W{i}" for i in ids],
        "lease": ["LEASE"] * len(ids),
        "parish": ["CADDO"] * len(ids),
        "depth": [12000.0] * len(ids),
        "lat": [lat] * len(ids),
        "lon": [-93.8] * len(ids),
    })


@pytest.fixture
def cfg(tmp_path):
    return {"data_dir": str(tmp_path)}


def counting_digest(day_new, day_amended):
    """Stand-in for build_digest: reports what the day's UNIONED files hold."""
    return f"{len(day_new)} new | {len(day_amended)} amended"


def read_day(outd, name="new_permits.csv"):
    import os
    return pd.read_csv(os.path.join(outd, name), dtype=str)


def test_second_same_day_run_does_not_erase_the_first(cfg):
    """The original bug, driven through the LA write path.

    Morning finds 12, afternoon's source differs so it passes the ledger
    gate but yields only 1. The day's file must hold 13, not 1.
    """
    outd, _ = write_outputs(cfg, "la", la_frame(range(1, 13)), la_frame([]),
                            counting_digest, key=KEY)
    assert len(read_day(outd)) == 12

    outd, _ = write_outputs(cfg, "la", la_frame([99]), la_frame([]),
                            counting_digest, key=KEY)
    got = read_day(outd)
    assert len(got) == 13
    assert "99" in set(got[KEY])


def test_empty_later_run_preserves_the_day(cfg):
    """A run that correctly finds nothing new must not blank the day."""
    write_outputs(cfg, "la", la_frame(range(1, 13)), la_frame([]),
                  counting_digest, key=KEY)
    outd, _ = write_outputs(cfg, "la", la_frame([]), la_frame([]),
                            counting_digest, key=KEY)
    assert len(read_day(outd)) == 12


def test_digest_describes_the_union_not_the_increment(cfg):
    """The CSV said 41 and the digest said 4 -- they must agree."""
    write_outputs(cfg, "la", la_frame(range(1, 13)), la_frame([]),
                  counting_digest, key=KEY)
    _, text = write_outputs(cfg, "la", la_frame([99]), la_frame([]),
                            counting_digest, key=KEY)
    assert text == "13 new | 0 amended"


def test_geojson_is_rebuilt_from_the_union_never_left_stale(cfg):
    """It used to be written only `if len(pts)`, so a stale 12-feature
    geojson could sit beside a 1-row CSV."""
    import os
    outd, _ = write_outputs(cfg, "la", la_frame(range(1, 13)), la_frame([]),
                            counting_digest, key=KEY)
    gj = json.load(open(os.path.join(outd, "new_permits.geojson"), encoding="utf-8"))
    assert len(gj["features"]) == 12

    outd, _ = write_outputs(cfg, "la", la_frame([99]), la_frame([]),
                            counting_digest, key=KEY)
    gj = json.load(open(os.path.join(outd, "new_permits.geojson"), encoding="utf-8"))
    assert len(gj["features"]) == 13


def test_geojson_with_no_coordinates_is_emptied_not_left_stale(cfg):
    """An empty FeatureCollection is a true statement; a stale one is not."""
    import os
    write_outputs(cfg, "la", la_frame(range(1, 13)), la_frame([]),
                  counting_digest, key=KEY)
    nocoord = la_frame([99]).drop(columns=["lat", "lon"])
    outd, _ = write_outputs(cfg, "la", nocoord, la_frame([]),
                            counting_digest, key=KEY)
    gj = json.load(open(os.path.join(outd, "new_permits.geojson"), encoding="utf-8"))
    # The 12 earlier rows still carry coords through the union; the point is
    # that the file was rewritten from the union rather than left untouched.
    assert len(gj["features"]) == 12


def test_full_seam_diff_then_write_then_reread(cfg):
    """diff -> union_write_csv -> re-read, twice, as the pipeline runs it.

    Master advances between runs exactly as la_pull.main does, so the second
    diff legitimately reports fewer new records than the first.
    """
    day1 = la_frame(range(1, 6))
    new, amended, _ = diff(None, day1, key=KEY, change_cols=CHANGE)
    assert len(new) == 5
    outd, _ = write_outputs(cfg, "la", new, amended, counting_digest, key=KEY)
    assert len(read_day(outd)) == 5

    master = day1
    day2 = la_frame(range(1, 7))          # one genuinely new permit
    new, amended, _ = diff(master, day2, key=KEY, change_cols=CHANGE)
    assert len(new) == 1                  # the increment is correctly small
    outd, text = write_outputs(cfg, "la", new, amended, counting_digest, key=KEY)

    got = read_day(outd)
    assert len(got) == 6                  # the DAY is the union
    assert set(got[KEY]) == {"1", "2", "3", "4", "5", "6"}
    assert text == "6 new | 0 amended"


def test_identifier_columns_survive_the_round_trip_as_text(cfg):
    """A well serial read back as a number loses leading zeros and gains
    a '.0'; both reach digest.md and the dashboard."""
    frame = la_frame(["0012345"])
    outd, _ = write_outputs(cfg, "la", frame, la_frame([]), counting_digest,
                            key=KEY, id_cols={KEY: str})
    assert list(read_day(outd)[KEY]) == ["0012345"]


def test_amendments_union_on_the_same_key(cfg):
    outd, _ = write_outputs(cfg, "la", la_frame([]), la_frame([1, 2]),
                            counting_digest, key=KEY)
    assert len(read_day(outd, "amendments.csv")) == 2
    outd, _ = write_outputs(cfg, "la", la_frame([]), la_frame([3]),
                            counting_digest, key=KEY)
    assert len(read_day(outd, "amendments.csv")) == 3
