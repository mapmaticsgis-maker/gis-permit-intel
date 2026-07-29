"""Union writes for daily output files.

A day's output accumulates every record newly detected that day, across all
runs. On 2026-07-26 a later same-day run wrote an empty new_permits.csv over
one holding 62 detected permits (commits c29c268b -> 479da72d). Replacing
loses findings; refusing a smaller write would crash the legitimate case where
RRC publishes twice in a day and the afternoon run's `new` set is genuinely
smaller. Merging on the business key is the only behaviour that keeps the file
meaning "what was new on this date".

replace=True is for the replay harness, which deliberately rebuilds a day.
"""
import csv
import json
from datetime import datetime
from pathlib import Path

import pandas as pd


class OutputWouldShrink(Exception):
    """Defensive pre-condition. The union should make shrinkage impossible;
    if this ever raises, the merge logic is wrong. Refuses the write to prevent
    data loss, rather than reporting damage after the fact."""


def count_data_rows(path) -> int:
    """Count CSV *records*, not physical lines.

    A quoted field may legally contain a newline, and one physical line then
    counts as one record. This is inert for TX -- daf420 is fixed-width and
    parse_rrc's clean() collapses whitespace -- but LA's SONRIS LOCATION and
    COMMENTS fields are free text and do carry embedded newlines. Counting
    lines inflated `before`, which union_write_csv compares against the
    merged row count: an inflated `before` makes a correct union look like a
    shrink and raises OutputWouldShrink on a write that was never wrong.
    """
    p = Path(path)
    if not p.exists():
        return 0
    with open(p, newline="", encoding="utf-8") as f:
        return max(0, sum(1 for row in csv.reader(f) if row) - 1)


# A run that skips because the source is byte-identical to one already
# ingested is CORRECT -- daf420.dat.07-26-2026 and .07-27-2026 are identical,
# so this recurs every weekend. But the skip path returned without creating an
# output directory at all, and downstream could not tell that from a crash:
# count_new returned None and check_volume_sane reported "no new_permits.csv
# found -- run likely failed", while the brief carried a blank TX section with
# no explanation because tx_ok was True. Skipping the work is right; reporting
# it as a probable failure is not.
#
# The marker is a new file alongside the day's outputs. The dashboard contract
# (new_permits.csv / amendments.csv / resurfaced.csv / digest.md and their
# columns) is untouched -- this is additive, and the directory previously did
# not exist at all on a skip.
SKIP_MARKER = "skipped.json"


def write_skip_marker(outd, *, source_name, reason, prior=None) -> Path:
    d = Path(outd)
    d.mkdir(parents=True, exist_ok=True)
    payload = {
        "skipped": True,
        "reason": reason,
        "source_name": source_name,
        "written_at": datetime.now().isoformat(timespec="seconds"),
    }
    if prior:
        payload["prior_ingested_at"] = prior.get("ingested_at")
        payload["prior_source_name"] = prior.get("source_name")
        payload["records_parsed"] = prior.get("records_parsed")
    p = d / SKIP_MARKER
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return p


def read_skip_marker(outd) -> dict | None:
    p = Path(outd) / SKIP_MARKER
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        # An unreadable marker must not crash the daily run -- that would be
        # finding 3 all over again in a different function.
        return None


def clear_skip_marker(outd) -> None:
    """A later run on the same day that DOES produce output supersedes an
    earlier skip; leaving the marker would misdescribe the day."""
    p = Path(outd) / SKIP_MARKER
    if p.exists():
        p.unlink()


def union_write_csv(df, path, *, key: str, replace: bool = False) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    before = count_data_rows(p)

    if key not in df.columns:
        raise ValueError(f"incoming frame has no key column {key!r}")

    if replace or before == 0:
        combined = df
    else:
        existing = pd.read_csv(p, dtype=str)
        if key not in existing.columns:
            raise ValueError(f"{p}: existing file has no key column {key!r}")
        incoming = df.copy()
        # Both sides must compare as strings: a key read back from CSV is str
        # while an incoming key may be int, and an unmatched pair duplicates.
        existing[key] = existing[key].astype(str)
        incoming[key] = incoming[key].astype(str)
        combined = (pd.concat([existing, incoming], ignore_index=True)
                    .drop_duplicates(key, keep="last"))

    # Check BEFORE writing. A guard that fires after to_csv has already
    # overwritten the file is a re-run of the 2026-07-26 failure with an
    # exception attached -- it must refuse the write, not report it.
    if not replace and len(combined) < before:
        raise OutputWouldShrink(
            f"{p}: merge produced {len(combined)} rows from {before} -- "
            f"refusing to write; union logic is wrong"
        )

    combined.to_csv(p, index=False)
