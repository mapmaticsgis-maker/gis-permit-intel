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


def check_volume_sane(new_count, label: str, floor: int = 0, ceiling: int = 500):
    if new_count is None:
        return (f"{label}_volume_sane", False, "no new_permits.csv found — run likely failed")
    ok = floor <= new_count <= ceiling
    return (f"{label}_volume_sane", ok, f"{new_count} new (expected {floor}-{ceiling})")


def check_run_not_stale(run_log: Path, max_gap_hours: int = 36):
    if not run_log.exists():
        return ("run_not_stale", True, "first run, no history yet")
    with open(run_log, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    successes = [r for r in rows if r["status"] == "OK"]
    if not successes:
        return ("run_not_stale", True, "no prior successful run logged yet")
    last = datetime.fromisoformat(successes[-1]["date"])
    gap = datetime.now() - last
    ok = gap < timedelta(hours=max_gap_hours)
    return ("run_not_stale", ok, f"last success {gap} ago")


def count_new(outd: Path) -> int | None:
    p = outd / "new_permits.csv"
    if not p.exists():
        return None
    with open(p) as f:
        return max(sum(1 for _ in f) - 1, 0)  # minus header


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
