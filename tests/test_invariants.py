from datetime import date

from core import invariants


def rows(*pairs):
    return [{"ingested_at": ts, "records_parsed": str(n)} for ts, n in pairs]


def test_fresh_source_passes():
    name, ok, _ = invariants.check_source_freshness(
        rows(("2026-07-28T06:00:00", 706)), today=date(2026, 7, 28)
    )
    assert name == "source_freshness"
    assert ok is True


def test_two_day_plateau_still_passes():
    """07-19/07-20 both held 502 headers; short plateaus are legitimate."""
    _, ok, _ = invariants.check_source_freshness(
        rows(("2026-07-26T06:00:00", 706)), today=date(2026, 7, 28)
    )
    assert ok is True


def test_freshness_alarms_exactly_at_the_threshold():
    """alarm_after_days=3 means 3 days is already an alarm, not the last
    tolerated gap. Pins the boundary so it cannot drift silently."""
    _, ok, _ = invariants.check_source_freshness(
        rows(("2026-07-25T06:00:00", 669)), today=date(2026, 7, 28)
    )
    assert ok is False


def test_four_day_freeze_fails():
    _, ok, detail = invariants.check_source_freshness(
        rows(("2026-07-24T06:00:00", 637)), today=date(2026, 7, 28)
    )
    assert ok is False
    assert "2026-07-24" in detail


def test_empty_ledger_fails():
    _, ok, _ = invariants.check_source_freshness([], today=date(2026, 7, 28))
    assert ok is False


def test_records_advancing_passes_while_count_grows():
    _, ok, _ = invariants.check_records_advancing(
        rows(("2026-07-26T06:00:00", 669), ("2026-07-28T06:00:00", 706)),
        today=date(2026, 7, 28),
    )
    assert ok is True


def test_records_advancing_tolerates_a_two_day_plateau():
    """07-19..07-21 all held 502 headers -- last increase was 2 days back."""
    _, ok, _ = invariants.check_records_advancing(
        rows(("2026-07-26T06:00:00", 706), ("2026-07-28T06:00:00", 706)),
        today=date(2026, 7, 28),
    )
    assert ok is True


def test_records_advancing_catches_the_freeze_hash_freshness_misses():
    """The real 2026-07-26 freeze: the file's sha changed daily because
    coordinate records kept updating, so the newest ingestion is same-day and
    source_freshness passes -- but the permit count has not moved since 07-26."""
    ledger_rows = rows(("2026-07-26T06:00:00", 706), ("2026-07-29T06:00:00", 706))
    _, fresh_ok, _ = invariants.check_source_freshness(ledger_rows, today=date(2026, 7, 29))
    assert fresh_ok is True

    name, ok, detail = invariants.check_records_advancing(ledger_rows, today=date(2026, 7, 29))
    assert name == "records_advancing"
    assert ok is False
    assert "2026-07-26" in detail


def test_month_reset_is_not_a_freeze():
    """The extract resets at month start: 07-02 carried 1009 headers from
    June's cycle, 07-03 dropped to 59, and July never re-exceeded 1009. A
    high-water mark would pin the last increase at 07-02 and alarm all month
    while permits were in fact advancing daily.

    `today` sits well after the reset so the old and new logic disagree on
    `ok`, not merely on the detail string: a high-water scan pins the last
    increase at 07-02 and reports flat_days=8 (alarm), while consecutive-row
    comparison reports flat_days=0 (pass)."""
    _, ok, detail = invariants.check_records_advancing(
        rows(("2026-07-02T06:00:00", 1009),
             ("2026-07-03T06:00:00", 59),
             ("2026-07-04T06:00:00", 111),
             ("2026-07-08T06:00:00", 188),
             ("2026-07-10T06:00:00", 239)),
        today=date(2026, 7, 10),
    )
    assert ok is True
    assert "2026-07-10" in detail


def test_month_reset_then_genuine_freeze_still_alarms():
    """The reset must not mask a real stall that follows it."""
    _, ok, _ = invariants.check_records_advancing(
        rows(("2026-08-01T06:00:00", 706),
             ("2026-08-02T06:00:00", 41),
             ("2026-08-05T06:00:00", 41)),
        today=date(2026, 8, 5),
    )
    assert ok is False


def test_records_advancing_empty_ledger_fails():
    _, ok, _ = invariants.check_records_advancing([], today=date(2026, 7, 28))
    assert ok is False


def test_advance_with_no_new_records_fails():
    """Source grew but the diff found nothing -- parser or diff regression."""
    _, ok, _ = invariants.check_advance_produced_records(
        records_parsed=706, prev_records_parsed=669, new_count=0
    )
    assert ok is False


def test_advance_with_new_records_passes():
    _, ok, _ = invariants.check_advance_produced_records(
        records_parsed=706, prev_records_parsed=669, new_count=37
    )
    assert ok is True


def test_no_advance_and_no_new_is_not_a_contradiction():
    _, ok, _ = invariants.check_advance_produced_records(
        records_parsed=706, prev_records_parsed=706, new_count=0
    )
    assert ok is True


def test_run_all_returns_named_tuples(data_dir):
    from core import ledger
    ledger.append_ingestion(
        data_dir, "tx", source_name="f", sha256="a",
        ingested_at="2026-07-28T06:00:00", records_parsed=706,
        new=37, amended=0, resurfaced=0,
    )
    results = invariants.run_all(data_dir, "tx", today=date(2026, 7, 28))
    assert all(len(r) == 3 for r in results)
    assert {"source_freshness", "records_advancing"} <= {r[0] for r in results}


def test_run_all_compares_last_two_ledger_rows(data_dir):
    """A source that advanced while the diff found nothing must fail."""
    from core import ledger
    for sha, parsed, new in (("a", 669, 32), ("b", 706, 0)):
        ledger.append_ingestion(
            data_dir, "tx", source_name="f", sha256=sha,
            ingested_at="2026-07-28T06:00:00", records_parsed=parsed,
            new=new, amended=0, resurfaced=0,
        )
    results = invariants.run_all(data_dir, "tx", today=date(2026, 7, 28))
    advance = [r for r in results if r[0] == "advance_produced_records"]
    assert len(advance) == 1
    assert advance[0][1] is False
