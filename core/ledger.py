"""Ingestion ledger — records every source ingested, keyed by content hash.

This exists because ingestion was not idempotent. The pipeline has three
redundant triggers (Windows Task Scheduler, a GitHub Actions workflow, and
trigger_github_workflow.py). Before this ledger, a second run on the same day
would diff against the already-updated master, correctly find nothing new, and
overwrite that day's outputs with empty files. On 2026-07-26 that destroyed 62
detected permits between commits c29c268b and 479da72d.
"""
import csv
import hashlib
from pathlib import Path

LEDGER_COLUMNS = [
    "source_name", "sha256", "ingested_at",
    "records_parsed", "new", "amended", "resurfaced",
]


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def hash_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ledger_path(data_dir, state) -> Path:
    return Path(data_dir) / state / "ledger.csv"


def read_ledger(data_dir, state) -> list[dict]:
    p = ledger_path(data_dir, state)
    if not p.exists():
        return []
    with open(p, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def find_ingestion(data_dir, state, sha256: str) -> dict | None:
    for row in read_ledger(data_dir, state):
        if row.get("sha256") == sha256:
            return row
    return None


def record_replay_ingestion(data_dir, state, *, source_path, records_parsed,
                            new, amended, ingested_at=None) -> dict:
    """Record that a recovery replay persisted master, so the two stay a unit.

    Master and the ledger are a unit -- that is this branch's hard-won lesson,
    and replay_tx.py --write violated exactly it. --write is the documented
    recovery path: after a real recovery master was full while the ledger
    still ended at the last pre-incident run, so check_source_freshness and
    check_records_advancing both went red on the next run, while an operator
    was mid-incident and least able to afford a spurious alarm.

    One row is appended for the newest replayed file. Its sha256 is the real
    file hash, so the ledger gate correctly skips that file on the next run --
    master already contains it. source_name is prefixed "replay:" so the row
    is never mistaken for a normal ingestion when reading history.
    """
    from datetime import datetime

    sha = hash_file(source_path)
    row = {
        "source_name": f"replay:{Path(source_path).name}",
        "sha256": sha,
        "ingested_at": ingested_at or datetime.now().isoformat(timespec="seconds"),
        "records_parsed": records_parsed,
        "new": new,
        "amended": amended,
        "resurfaced": 0,
    }
    append_ingestion(data_dir, state, **row)
    return row


def append_ingestion(data_dir, state, *, source_name, sha256, ingested_at,
                     records_parsed, new, amended, resurfaced) -> None:
    p = ledger_path(data_dir, state)
    p.parent.mkdir(parents=True, exist_ok=True)
    write_header = not p.exists()
    with open(p, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=LEDGER_COLUMNS)
        if write_header:
            w.writeheader()
        w.writerow({
            "source_name": source_name,
            "sha256": sha256,
            "ingested_at": ingested_at,
            "records_parsed": records_parsed,
            "new": new,
            "amended": amended,
            "resurfaced": resurfaced,
        })
