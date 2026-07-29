"""Checks for plausible-but-wrong pipeline output.

The 2026-07 failure was not a crash. The pipeline produced confident, empty
results for days. These checks target that class of failure: silence that
reads as success.

Each check returns (name, ok, detail) to match self_check.py's existing shape.
"""
from datetime import date, datetime

from core.ledger import read_ledger


def check_source_freshness(ledger_rows, today: date, max_stale_days: int = 3):
    """Fail when no new source content has been ingested recently.

    Threshold is 3 days because the source has legitimately flat days --
    07-19/07-20 both carried 502 permit headers, 07-13/07-14 both 348. Three
    days spans a weekend plateau without tolerating an indefinite freeze.
    """
    name = "source_freshness"
    if not ledger_rows:
        return (name, False, "ledger is empty -- nothing has ever been ingested")
    latest = max(r["ingested_at"] for r in ledger_rows)
    latest_date = datetime.fromisoformat(latest).date()
    stale_days = (today - latest_date).days
    ok = stale_days < max_stale_days
    return (name, ok,
            f"last new source content {latest_date.isoformat()} "
            f"({stale_days}d ago, threshold {max_stale_days}d)")


def check_advance_produced_records(records_parsed: int, prev_records_parsed: int,
                                   new_count: int):
    """Fail when the source grew but the diff found nothing.

    Growth with zero new records means the parser or the diff regressed. No
    growth with zero new records is normal and passes.
    """
    name = "advance_produced_records"
    advanced = records_parsed > prev_records_parsed
    ok = (not advanced) or new_count > 0
    return (name, ok,
            f"parsed {prev_records_parsed} -> {records_parsed}, new={new_count}")


def run_all(data_dir, state, today: date):
    """Both checks read from the ledger, so callers pass no counts.

    The ledger's last row is the most recent ingestion; comparing it to the row
    before gives the advance. Runs skipped by the ledger gate append no row, so
    consecutive rows are always genuinely different source content.
    """
    rows = read_ledger(data_dir, state)
    results = [check_source_freshness(rows, today)]
    if len(rows) >= 2:
        results.append(check_advance_produced_records(
            records_parsed=int(rows[-1]["records_parsed"]),
            prev_records_parsed=int(rows[-2]["records_parsed"]),
            new_count=int(rows[-1]["new"]),
        ))
    return results
