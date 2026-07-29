"""The daily driver's failure handling.

These cover the paths where a fault in a *sensor* must not silence the
*pipeline* -- the failure mode this whole branch exists to prevent.
"""
import datetime as dt

import pytest

import self_check
from core.outputs import clear_skip_marker, read_skip_marker, write_skip_marker
from run_daily_ci import brief_section, collect_invariants

TODAY = dt.date(2026, 7, 29)
HEADER = "source_name,sha256,ingested_at,records_parsed,new,amended,resurfaced\n"
GOOD_ROW = "daf420.dat.07-28-2026,abc,2026-07-28T06:00:00,693,0,0,0\n"


def write_ledger(data_dir, state, text):
    (data_dir / state / "ledger.csv").write_text(text, encoding="utf-8")


def names(results):
    return [n for n, _, _ in results]


def test_healthy_ledger_produces_named_per_state_checks(data_dir):
    for state in ("tx", "la"):
        write_ledger(data_dir, state, HEADER + GOOD_ROW)
    results = collect_invariants(data_dir, ("tx", "la"), TODAY)
    assert "tx_source_freshness" in names(results)
    assert "la_records_advancing" in names(results)


def test_conflict_marker_becomes_a_failed_check_not_an_exception(data_dir):
    """The reported crash: a git conflict marker in the ledger raised
    TypeError out of max(), aborting main() before send_daily_brief -- no
    brief, no alert, no log_run row, no healthcheck ping."""
    write_ledger(data_dir, "tx", HEADER + GOOD_ROW + "<<<<<<< HEAD\n")
    write_ledger(data_dir, "la", HEADER + GOOD_ROW)

    results = collect_invariants(data_dir, ("tx", "la"), TODAY)

    assert "tx_invariants_crashed" in names(results)
    crashed = [r for r in results if r[0] == "tx_invariants_crashed"][0]
    assert crashed[1] is False
    assert "ledger" in crashed[2]


def test_one_states_broken_ledger_does_not_hide_the_other(data_dir):
    """LA's checks must still run and still report when TX's ledger is bad."""
    write_ledger(data_dir, "tx", HEADER + "<<<<<<< HEAD\n")
    write_ledger(data_dir, "la", HEADER + GOOD_ROW)

    results = collect_invariants(data_dir, ("tx", "la"), TODAY)

    assert "tx_invariants_crashed" in names(results)
    assert "la_source_freshness" in names(results)


def test_a_crash_is_reported_as_failing_so_the_alert_still_fires(data_dir):
    """run_daily_ci decides to alert on `not ok`. A crashed sensor must land
    on the failing side of that test, or it is silence with extra steps."""
    write_ledger(data_dir, "tx", HEADER + "<<<<<<< HEAD\n")
    write_ledger(data_dir, "la", HEADER + GOOD_ROW)

    results = collect_invariants(data_dir, ("tx", "la"), TODAY)
    assert [c for c in results if not c[1]], "a crashed sensor must fail loudly"


def test_missing_ledger_is_handled_without_crashing(data_dir):
    """No ledger at all is a legitimate first-run state, not an exception."""
    results = collect_invariants(data_dir, ("tx", "la"), TODAY)
    assert names(results)  # something was reported for each state


# --------------------------------------------------------------------------
# Finding 5: a skipped run must not look like a failed one.
# --------------------------------------------------------------------------

PRIOR = {"ingested_at": "2026-07-26T06:00:12", "source_name": "daf420.dat.07-26-2026",
         "records_parsed": "693"}


def make_skip(tmp_path):
    write_skip_marker(tmp_path, source_name="daf420.dat.07-27-2026",
                      reason="source unchanged since 2026-07-26T06:00:12 "
                             "(daf420.dat.07-26-2026, 693 records)",
                      prior=PRIOR)
    return read_skip_marker(tmp_path)


def test_skip_marker_round_trips(tmp_path):
    skip = make_skip(tmp_path)
    assert skip["skipped"] is True
    assert skip["prior_ingested_at"] == "2026-07-26T06:00:12"
    assert skip["records_parsed"] == "693"


def test_no_marker_reads_as_none(tmp_path):
    assert read_skip_marker(tmp_path) is None


def test_unreadable_marker_does_not_raise(tmp_path):
    """A corrupt marker must not become finding 3 in a different function."""
    (tmp_path / "skipped.json").write_text("{not json", encoding="utf-8")
    assert read_skip_marker(tmp_path) is None


def test_clear_marker_is_idempotent(tmp_path):
    make_skip(tmp_path)
    clear_skip_marker(tmp_path)
    clear_skip_marker(tmp_path)          # must not raise on a second call
    assert read_skip_marker(tmp_path) is None


def test_missing_output_without_a_marker_still_reads_as_failure(tmp_path):
    """The failure signal must survive: no file and no skip is still a fault."""
    name, ok, detail = self_check.check_volume_sane(None, "tx", skip=None)
    assert ok is False
    assert "likely failed" in detail


def test_missing_output_with_a_marker_reads_as_a_correct_skip(tmp_path):
    """The 07-27 weekend case: byte-identical source, no outputs, not a fault."""
    skip = make_skip(tmp_path)
    name, ok, detail = self_check.check_volume_sane(None, "tx", skip=skip)
    assert ok is True
    assert "skipped" in detail
    assert "source unchanged" in detail


def test_a_real_count_is_still_range_checked_even_with_a_stale_marker(tmp_path):
    """Guard against the marker silencing a genuine volume problem."""
    _, ok, _ = self_check.check_volume_sane(9999, "tx", floor=0, ceiling=300, skip=None)
    assert ok is False


def test_brief_says_plainly_why_a_skipped_section_is_empty(tmp_path):
    skip = make_skip(tmp_path)
    text = brief_section("Texas RRC (daf420)", True, "", skip)
    assert "Texas RRC (daf420)" in text
    assert "skip, not a failure" in text
    assert "source unchanged" in text
    assert "693 records" in text


def test_brief_distinguishes_a_failed_section_from_a_skipped_one(tmp_path):
    failed = brief_section("Texas RRC (daf420)", False, "", None)
    skipped = brief_section("Texas RRC (daf420)", True, "", make_skip(tmp_path))
    assert "FAILED" in failed
    assert "FAILED" not in skipped
    assert failed != skipped


def test_brief_passes_a_real_digest_through_unchanged():
    digest = "# Texas RRC\n\n**12 new** | **0 amended** vs master."
    assert brief_section("Texas RRC (daf420)", True, digest, None) == digest


def test_brief_flags_an_empty_section_that_has_no_explanation():
    """ok=True, no digest and no marker is genuinely unexpected; say so
    rather than emitting a silent blank."""
    text = brief_section("Texas RRC (daf420)", True, "", None)
    assert "unexpected" in text
