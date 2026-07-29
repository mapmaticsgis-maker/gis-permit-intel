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


def test_four_day_freeze_fails():
    _, ok, detail = invariants.check_source_freshness(
        rows(("2026-07-24T06:00:00", 637)), today=date(2026, 7, 28)
    )
    assert ok is False
    assert "2026-07-24" in detail


def test_empty_ledger_fails():
    _, ok, _ = invariants.check_source_freshness([], today=date(2026, 7, 28))
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
    assert any(r[0] == "source_freshness" for r in results)


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
