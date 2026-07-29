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
from pathlib import Path

import pandas as pd


class OutputWouldShrink(Exception):
    """Defensive post-condition. The union should make shrinkage impossible;
    if this ever raises, the merge logic is wrong."""


def count_data_rows(path) -> int:
    p = Path(path)
    if not p.exists():
        return 0
    with open(p, newline="", encoding="utf-8") as f:
        return max(0, sum(1 for _ in f) - 1)


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

    combined.to_csv(p, index=False)

    after = count_data_rows(p)
    if not replace and after < before:
        raise OutputWouldShrink(
            f"{p}: went from {before} to {after} rows -- union logic is wrong"
        )
