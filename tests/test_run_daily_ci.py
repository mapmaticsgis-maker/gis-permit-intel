"""The daily driver's failure handling.

These cover the paths where a fault in a *sensor* must not silence the
*pipeline* -- the failure mode this whole branch exists to prevent.
"""
import datetime as dt

import pytest

from run_daily_ci import collect_invariants

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
