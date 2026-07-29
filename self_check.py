"""
Sanity checks run after each day's TX + LA pulls, before anything gets
emailed. Works against the actual repo layout (common.load_master,
data/<state>/out/<date>/...) rather than a separate pickle store.

Philosophy: this catches *pipeline* failures (source unreachable, a
parser silently returning nothing, encoding corruption) — it is not
trying to judge whether the day's permit activity itself is unusual.
"""
import csv
from datetime import datetime, timedelta
from pathlib import Path

from core.outputs import count_data_rows

MOJIBAKE_MARKERS = ("â€", "Ã©", "Ã¢", "\ufffd")


def has_mojibake(text: str) -> bool:
    return any(m in text for m in MOJIBAKE_MARKERS)


def check_master_grew(prev_rows: int, new_rows: int, label: str):
    ok = new_rows >= prev_rows
    return (f"{label}_master_monotonic", ok, f"{prev_rows} -> {new_rows} rows")


def check_no_mojibake(text: str, label: str):
    ok = not has_mojibake(text)
    return (f"{label}_no_mojibake", ok,
            "clean" if ok else "mojibake markers found in digest text")


def check_volume_sane(new_count, label: str, floor: int = 0, ceiling: int = 500,
                      skip: dict | None = None):
    """skip: the day's skip marker, when the run correctly did no work.

    Absent this, a skipped run was indistinguishable from a failed one. The
    ledger gate is keyed on content hash globally rather than per-day, so an
    unchanged source (daf420.dat.07-26-2026 and .07-27-2026 are byte-identical)
    made the run return without creating an output directory -- and this check
    then reported "run likely failed" on a run that behaved exactly right.
    That recurs every weekend.
    """
    if skip:
        return (f"{label}_volume_sane", True,
                f"skipped: {skip.get('reason', 'source unchanged')}")
    if new_count is None:
        return (f"{label}_volume_sane", False, "no new_permits.csv found — run likely failed")
    ok = floor <= new_count <= ceiling
    return (f"{label}_volume_sane", ok, f"{new_count} new (expected {floor}-{ceiling})")


def skip_note(label: str, skip: dict) -> str:
    """The brief must say plainly why a state's section is empty."""
    prior = skip.get("prior_ingested_at")
    records = skip.get("records_parsed")
    detail = f" It was already ingested {prior}" if prior else ""
    if records:
        detail += f" ({records} records)"
    return (f"# {label}\n\n"
            f"_No new data today: {skip.get('reason', 'source unchanged')}._\n\n"
            f"_The source file was byte-identical to one already processed, so this "
            f"run correctly did no work.{detail}. This is a skip, not a failure._")


def check_run_not_stale(run_log: Path, max_gap_hours: int = 36):
    """Detects the pipeline going silent (Actions disabled, trigger stopped
    firing, etc.) -- a different concern from any individual day's checks
    failing. Previously this keyed off only fully-clean ("OK") runs, which
    conflated the two: one caught-and-same-day-fixed data issue made this
    fire again on every subsequent run for the next 36h, even though the
    pipeline itself never stopped running. Now it just asks "did *a* run
    happen recently," regardless of whether that run was perfectly clean --
    checks_failed on any given day is already surfaced by its own alert.
    """
    if not run_log.exists():
        return ("run_not_stale", True, "first run, no history yet")
    with open(run_log, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return ("run_not_stale", True, "no prior run logged yet")
    last = datetime.fromisoformat(rows[-1]["date"])
    gap = datetime.now() - last
    ok = gap < timedelta(hours=max_gap_hours)
    return ("run_not_stale", ok, f"last run {gap} ago")


def count_new(outd: Path) -> int | None:
    """None means "no file" -- see check_volume_sane, which distinguishes that
    from a skipped run.

    Counts parsed CSV records, not physical lines. This had the same embedded-
    newline flaw as core.outputs.count_data_rows, and it is the one that
    actually reaches the operator: its result is what check_volume_sane
    reports and what the run log stores, so a quoted newline in a SONRIS
    LOCATION field inflated the LA count in the daily brief.
    """
    p = outd / "new_permits.csv"
    if not p.exists():
        return None
    return count_data_rows(p)


def read_digest(outd: Path) -> str:
    p = outd / "digest.md"
    return p.read_text(encoding="utf-8") if p.exists() else ""


RUN_LOG_FIELDS = ["date", "tx_new", "la_new", "checks_passed", "checks_failed", "status"]


def log_run(run_log: Path, tx_new, la_new, checks, status: str):
    run_log.parent.mkdir(parents=True, exist_ok=True)
    passed = sum(1 for _, ok, _ in checks if ok)
    failed = sum(1 for _, ok, _ in checks if not ok)
    row = {
        "date": datetime.now().isoformat(timespec="seconds"),
        "tx_new": tx_new if tx_new is not None else "",
        "la_new": la_new if la_new is not None else "",
        "checks_passed": passed,
        "checks_failed": failed,
        "status": status,
    }
    write_header = not run_log.exists()
    with open(run_log, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=RUN_LOG_FIELDS)
        if write_header:
            w.writeheader()
        w.writerow(row)
