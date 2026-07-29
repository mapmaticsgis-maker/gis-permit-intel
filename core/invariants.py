"""Checks for plausible-but-wrong pipeline output.

The 2026-07 failure was not a crash. The pipeline produced confident, empty
results for days. These checks target that class of failure: silence that
reads as success.

Each check returns (name, ok, detail) to match self_check.py's existing shape.
"""
from datetime import date, datetime

from core.ledger import read_ledger


def check_source_freshness(ledger_rows, today: date, alarm_after_days: int = 3):
    """Fail when nothing at all has been ingested recently.

    This catches a dead downloader -- expired MFT link, broken session,
    network down. It does NOT catch a frozen source: the daf420 extract's
    sha256 changes daily because coordinate records keep updating, so a run
    still ingests and still records a row. check_records_advancing covers that.

    alarm_after_days means what it says: a gap of that many days already
    fails. Legitimate plateaus in July 2026 ran to 2 days.
    """
    name = "source_freshness"
    if not ledger_rows:
        return (name, False, "ledger is empty -- nothing has ever been ingested")
    latest = max(r["ingested_at"] for r in ledger_rows)
    latest_date = datetime.fromisoformat(latest).date()
    stale_days = (today - latest_date).days
    ok = stale_days < alarm_after_days
    return (name, ok,
            f"last ingestion {latest_date.isoformat()} "
            f"({stale_days}d ago, alarms at {alarm_after_days}d)")


def check_records_advancing(ledger_rows, today: date, alarm_after_days: int = 3):
    """Fail when the record count has not increased for too long.

    This is the freeze detector, and the reason hash freshness is not enough.
    The RRC extract is month-to-date cumulative: it keeps appending coordinate
    records (14/15) to a fixed set of permit headers, so the file hash moves
    daily while the permit count stands still. On 2026-07-28 the file had a
    fresh hash and 706 permits for the third consecutive day.

    Calibrated against July 2026: legitimate plateaus ran to 2 days
    (07-12..07-14 all 348 headers, 07-19..07-21 all 502); the freeze held 706
    from 07-26 onward.

    Moved means changed, not grew. The extract is month-to-date cumulative
    and resets at month start, so a drop is a new cycle beginning -- evidence
    the source is alive, not stalled.
    """
    name = "records_advancing"
    if not ledger_rows:
        return (name, False, "ledger is empty -- nothing has ever been ingested")

    # Compare consecutive rows, never an all-time high. The extract resets at
    # month start (07-02 carried 1009 headers from June, 07-03 dropped to 59,
    # and July never re-exceeded 1009), so a high-water mark would pin
    # last_move at the previous month's peak and alarm for the whole month.
    # A DECREASE is a legitimate new cycle -- the source moving, not stalling.
    ordered = sorted(ledger_rows, key=lambda r: r["ingested_at"])
    last_move = ordered[0]["ingested_at"]
    count = int(ordered[0]["records_parsed"])
    for row in ordered[1:]:
        parsed = int(row["records_parsed"])
        if parsed != count:
            last_move = row["ingested_at"]
        count = parsed

    last_date = datetime.fromisoformat(last_move).date()
    flat_days = (today - last_date).days
    ok = flat_days < alarm_after_days
    return (name, ok,
            f"record count last moved {last_date.isoformat()} (now {count}) "
            f"({flat_days}d ago, alarms at {alarm_after_days}d)")


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
    results = [check_source_freshness(rows, today),
               check_records_advancing(rows, today)]
    if len(rows) >= 2:
        results.append(check_advance_produced_records(
            records_parsed=int(rows[-1]["records_parsed"]),
            prev_records_parsed=int(rows[-2]["records_parsed"]),
            new_count=int(rows[-1]["new"]),
        ))
    return results
