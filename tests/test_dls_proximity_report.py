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
