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


def test_keyword_filter_uses_word_boundaries_not_substrings():
    # "Reporter Ranch" contains "report" as a substring but is not a report
    # description -- must NOT be filtered. "weekly report" IS a real
    # deliverable description and must still be filtered.
    result = parse_dls_jobs("Reporter Ranch, weekly report, Zoch")
    assert "Reporter Ranch" in result
    assert "weekly report" not in result
    assert "Zoch" in result


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


def test_load_confirmed_geometries_skips_entry_missing_shapefile_path(tmp_path):
    cache = {"Flatland": {"status": "confirmed"}}
    assert load_confirmed_geometries(cache) == {}


def test_load_confirmed_geometries_skips_entry_with_none_shapefile_path(tmp_path):
    cache = {"Flatland": {"status": "confirmed", "shapefile_path": None}}
    assert load_confirmed_geometries(cache) == {}


def test_nearest_job_distances_returns_empty_when_both_points_missing(tmp_path):
    shp_path = tmp_path / "flatland.shp"
    _write_square_near_giddings(shp_path)
    geometries = load_confirmed_geometries(
        {"Flatland": {"status": "confirmed", "shapefile_path": str(shp_path)}}
    )
    permit_row = {"Surface_Lat": "", "Surface_Lon": "", "BHL_Lat": "", "BHL_Lon": ""}
    assert nearest_job_distances(permit_row, geometries) == []


def test_nearest_job_distances_uses_surface_only_when_bhl_missing(tmp_path):
    shp_path = tmp_path / "flatland.shp"
    _write_square_near_giddings(shp_path)
    geometries = load_confirmed_geometries(
        {"Flatland": {"status": "confirmed", "shapefile_path": str(shp_path)}}
    )
    # Surface point inside the test square, BHL fields blank (common in real
    # TX daf420 data -- confirmed 47% of a real day's permits lack BHL).
    permit_row = {
        "Surface_Lat": "30.105", "Surface_Lon": "-96.905",
        "BHL_Lat": "", "BHL_Lon": "",
    }
    assert nearest_job_distances(permit_row, geometries) == [("Flatland", 0.0)]


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
