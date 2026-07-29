# Phase 1 — Sensor Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make permit ingestion idempotent and self-monitoring so the pipeline stops destroying its own results, and recover the days already lost.

**Architecture:** An ingestion ledger keyed on source content hash gates every run. Already-ingested content is skipped entirely rather than re-diffed; a day's outputs union across runs so nothing is overwritten; a stale ledger is the source-freshness alarm. The existing diff logic is correct and is consolidated, not rewritten.

**Tech Stack:** Python 3.14, pandas, pytest, stdlib `csv`/`hashlib`. No new runtime dependencies.

## Global Constraints

- Repo root is `C:\GIS\permit_intel`. All paths below are relative to it.
- `data_dir` comes from `config.yaml` and is `./data`. Never hardcode `./data` in library code — take `data_dir` as a parameter.
- Windows. Open all text files with explicit `encoding="utf-8"`, and all CSV writers with `newline=""`.
- The existing `data/<state>/out/<date>/` file contract (`new_permits.csv`, `amendments.csv`, `digest.md`, `new_permits.geojson`, `resurfaced.csv` for TX) is consumed by Zach Gregory's dashboard. Column names and filenames do not change in this phase.
- TX business key is `Permit_Number`. LA business key is `id` (source column `WELL_SERIAL_NUM`).
- The daf420 extract is month-to-date cumulative and **resets at month start**. `data/tx/inbox/daf420.dat.07-01-2026` and `...07-02-2026` carry June's cycle (974 and 1009 permit headers); `...07-03-2026` resets to 59. July replay starts at 07-03.
- Never use `-Force` on `New-Item` against an existing file; never `git commit --no-verify`.

---

## File Structure

| File | Responsibility |
|---|---|
| `core/__init__.py` | Package marker. Empty. |
| `core/ledger.py` | Source hashing; read/append the ingestion ledger; look up prior ingestion by hash. |
| `core/outputs.py` | Union CSV writes so a day's outputs accumulate across runs. |
| `core/diff.py` | Single consolidated change-detection function, replacing the two near-duplicates. |
| `core/invariants.py` | Freshness and contradiction checks over the ledger. |
| `scripts/replay_tx.py` | Rebuild TX master from empty across a date range; the acceptance test harness. |
| `tests/conftest.py` | Shared fixtures: synthetic daf420 text, temp data dirs. |
| `tests/test_ledger.py`, `tests/test_outputs.py`, `tests/test_diff.py`, `tests/test_invariants.py` | Unit tests per module. |
| `tx_daf420.py` (modify) | Gate on ledger; union outputs; rebuild digest from the day; record ingestion. |
| `la_pull.py` (modify) | Same, hashing the fetched frame rather than a file. |
| `run_daily_ci.py` (modify) | Append the new invariants to the existing `checks` list. |
| `requirements.txt` (modify) | Add `pytest`. |

`self_check.py` is **not** modified: it is a library of check functions, and the collector that assembles and emails results lives in `run_daily_ci.py:88-101`.

`core/diff.py` deliberately does not import pandas at module scope beyond what it needs — it stays a pure function over DataFrames with no file I/O, so it is testable without fixtures on disk.

---

### Task 1: Ingestion ledger

**Files:**
- Create: `core/__init__.py`, `core/ledger.py`
- Create: `tests/conftest.py`, `tests/test_ledger.py`
- Modify: `requirements.txt`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `hash_file(path: str | Path) -> str`
  - `hash_text(text: str) -> str`
  - `ledger_path(data_dir, state) -> Path`
  - `read_ledger(data_dir, state) -> list[dict]`
  - `find_ingestion(data_dir, state, sha256: str) -> dict | None`
  - `append_ingestion(data_dir, state, *, source_name, sha256, ingested_at, records_parsed, new, amended, resurfaced) -> None`
  - `LEDGER_COLUMNS: list[str]`

- [ ] **Step 1: Install pytest and record the dependency**

```bash
python -m pip install pytest
```

Then append to `requirements.txt` (the file currently ends with `playwright`):

```
pytest
```

- [ ] **Step 2: Create the test fixture module**

Create `tests/conftest.py`:

```python
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def data_dir(tmp_path):
    """An isolated data_dir with the tx/la subdirs the pipeline expects."""
    for state in ("tx", "la"):
        (tmp_path / state).mkdir(parents=True)
    return tmp_path
```

- [ ] **Step 3: Write the failing tests**

Create `tests/test_ledger.py`:

```python
from core import ledger


def test_hash_file_is_stable_and_content_sensitive(tmp_path):
    a = tmp_path / "a.dat"
    b = tmp_path / "b.dat"
    a.write_text("01PERMIT\n", encoding="utf-8")
    b.write_text("01PERMIT\n", encoding="utf-8")
    assert ledger.hash_file(a) == ledger.hash_file(b)

    b.write_text("01PERMIT\n02WELL\n", encoding="utf-8")
    assert ledger.hash_file(a) != ledger.hash_file(b)


def test_read_ledger_is_empty_when_absent(data_dir):
    assert ledger.read_ledger(data_dir, "tx") == []


def test_append_then_find_round_trips(data_dir):
    ledger.append_ingestion(
        data_dir, "tx",
        source_name="daf420.dat.07-26-2026", sha256="abc123",
        ingested_at="2026-07-26T06:00:00", records_parsed=706,
        new=62, amended=3, resurfaced=1,
    )
    found = ledger.find_ingestion(data_dir, "tx", "abc123")
    assert found is not None
    assert found["source_name"] == "daf420.dat.07-26-2026"
    assert found["new"] == "62"
    assert ledger.find_ingestion(data_dir, "tx", "notpresent") is None


def test_append_writes_header_once(data_dir):
    for sha in ("aaa", "bbb"):
        ledger.append_ingestion(
            data_dir, "tx",
            source_name="f", sha256=sha, ingested_at="2026-07-26T06:00:00",
            records_parsed=1, new=1, amended=0, resurfaced=0,
        )
    text = ledger.ledger_path(data_dir, "tx").read_text(encoding="utf-8")
    assert text.count("sha256") == 1
    assert len(ledger.read_ledger(data_dir, "tx")) == 2


def test_ledger_is_per_state(data_dir):
    ledger.append_ingestion(
        data_dir, "tx",
        source_name="f", sha256="shared", ingested_at="2026-07-26T06:00:00",
        records_parsed=1, new=1, amended=0, resurfaced=0,
    )
    assert ledger.find_ingestion(data_dir, "la", "shared") is None
```

- [ ] **Step 4: Run the tests to verify they fail**

```bash
python -m pytest tests/test_ledger.py -v
```

Expected: collection error — `ModuleNotFoundError: No module named 'core'`.

- [ ] **Step 5: Create the package marker**

Create `core/__init__.py` as an empty file.

```bash
python -c "open('core/__init__.py','w').close()"
```

- [ ] **Step 6: Implement the ledger**

Create `core/ledger.py`:

```python
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
```

- [ ] **Step 7: Run the tests to verify they pass**

```bash
python -m pytest tests/test_ledger.py -v
```

Expected: 5 passed.

- [ ] **Step 8: Commit**

```bash
git add core/__init__.py core/ledger.py tests/conftest.py tests/test_ledger.py requirements.txt
git commit -m "Add ingestion ledger keyed on source content hash"
```

---

### Task 2: Union output writes

A day's output file accumulates every permit newly detected **that day**, across however many runs. RRC can publish more than once in a day; the ledger gate lets a genuine second publication through, and that run's `new` set is legitimately smaller than the morning's. Replacing would lose the morning's findings; refusing would crash a valid run. Merging on the business key is the only option that keeps `new_permits.csv` meaning "what was new on this date."

**Files:**
- Create: `core/outputs.py`, `tests/test_outputs.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `class OutputWouldShrink(Exception)` — defensive pre-condition; refuses the write, never reports after it
  - `count_data_rows(path) -> int` — data rows excluding header; 0 if absent
  - `union_write_csv(df, path, *, key: str, replace: bool = False) -> None`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_outputs.py`:

```python
import pandas as pd
import pytest

from core.outputs import OutputWouldShrink, count_data_rows, union_write_csv

KEY = "Permit_Number"


def permits(*nums, operator="EOG"):
    return pd.DataFrame({KEY: [str(n) for n in nums],
                         "Operator_Name": [operator] * len(nums)})


def test_count_data_rows_absent_file_is_zero(tmp_path):
    assert count_data_rows(tmp_path / "nope.csv") == 0


def test_count_data_rows_excludes_header(tmp_path):
    p = tmp_path / "x.csv"
    pd.DataFrame({"a": [1, 2, 3]}).to_csv(p, index=False)
    assert count_data_rows(p) == 3


def test_write_creates_file_and_parent_dirs(tmp_path):
    p = tmp_path / "out" / "2026-07-28" / "new_permits.csv"
    union_write_csv(permits(1, 2), p, key=KEY)
    assert count_data_rows(p) == 2


def test_second_run_adds_its_new_permits(tmp_path):
    """06:00 finds 37, 14:00 finds 4 more -- the day's file holds 41."""
    p = tmp_path / "new_permits.csv"
    union_write_csv(permits(*range(37)), p, key=KEY)
    union_write_csv(permits(100, 101, 102, 103), p, key=KEY)
    assert count_data_rows(p) == 41


def test_repeated_permit_updates_in_place_without_duplicating(tmp_path):
    p = tmp_path / "new_permits.csv"
    union_write_csv(permits(1, 2, operator="EOG"), p, key=KEY)
    union_write_csv(permits(2, operator="PIONEER"), p, key=KEY)
    out = pd.read_csv(p, dtype=str)
    assert len(out) == 2
    assert out.loc[out[KEY] == "2", "Operator_Name"].item() == "PIONEER"


def test_empty_result_never_erases_the_day(tmp_path):
    """The exact 2026-07-26 failure: 62 rows must survive an empty later run."""
    p = tmp_path / "new_permits.csv"
    union_write_csv(permits(*range(62)), p, key=KEY)
    union_write_csv(permits(), p, key=KEY)
    assert count_data_rows(p) == 62


def test_replace_rewrites_wholesale(tmp_path):
    p = tmp_path / "new_permits.csv"
    union_write_csv(permits(1, 2), p, key=KEY)
    union_write_csv(permits(9), p, key=KEY, replace=True)
    out = pd.read_csv(p, dtype=str)
    assert list(out[KEY]) == ["9"]


def test_missing_key_column_is_rejected(tmp_path):
    p = tmp_path / "new_permits.csv"
    union_write_csv(permits(1), p, key=KEY)
    with pytest.raises(ValueError):
        union_write_csv(pd.DataFrame({"other": ["x"]}), p, key=KEY)


def test_key_type_mismatch_does_not_duplicate(tmp_path):
    """Existing rows read back as str must match an int-typed incoming key."""
    p = tmp_path / "new_permits.csv"
    union_write_csv(permits(255778), p, key=KEY)
    union_write_csv(pd.DataFrame({KEY: [255778], "Operator_Name": ["X"]}), p, key=KEY)
    assert count_data_rows(p) == 1


def test_shrink_guard_refuses_before_writing(tmp_path, monkeypatch):
    """The guard must refuse the write, not report it after the fact.

    Unreachable through the public path by construction, so the merge is
    sabotaged to return fewer rows. What matters is that the file on disk is
    untouched when the guard fires.
    """
    import core.outputs as outputs

    p = tmp_path / "new_permits.csv"
    union_write_csv(permits(1, 2, 3), p, key=KEY)

    monkeypatch.setattr(outputs.pd, "concat", lambda frames, **kw: frames[1])
    with pytest.raises(OutputWouldShrink):
        union_write_csv(permits(9), p, key=KEY)

    assert count_data_rows(p) == 3
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
python -m pytest tests/test_outputs.py -v
```

Expected: collection error — `ModuleNotFoundError: No module named 'core.outputs'`.

- [ ] **Step 3: Implement**

Create `core/outputs.py`:

```python
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

    # Check BEFORE writing. A guard that fires after to_csv has already
    # overwritten the file is a re-run of the 2026-07-26 failure with an
    # exception attached -- it must refuse the write, not report it.
    if not replace and len(combined) < before:
        raise OutputWouldShrink(
            f"{p}: merge produced {len(combined)} rows from {before} -- "
            f"refusing to write; union logic is wrong"
        )

    combined.to_csv(p, index=False)
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
python -m pytest tests/test_outputs.py -v
```

Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add core/outputs.py tests/test_outputs.py
git commit -m "Add union CSV writes so same-day runs accumulate"
```

---

### Task 3: Consolidate change detection

The TX and LA diffs are near-duplicates with different change columns and different resurfaced handling. This task merges them into one function with identical observable behaviour. It is a refactor: the tests encode current behaviour first.

**Files:**
- Create: `core/diff.py`, `tests/test_diff.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `diff(master, today, *, key: str, change_cols: list[str], resurfaced_after_days: int | None = None) -> tuple[DataFrame, DataFrame, DataFrame]` returning `(new, amended, resurfaced)`
  - `class UnusableKeyError(Exception)`
  - `assert_usable_key(df, key) -> None` — raises on null or duplicate key values

Note for callers: TX parses **706 rows but only 693 unique `Permit_Number` values** — the existing composite `drop_duplicates` in `tx_daf420.main()` keeps rows that share a permit number but differ in other fields. Callers must reduce to one row per business key *before* asserting. Tasks 5 and 7 do this explicitly.

Callers use `key="Permit_Number"`, `change_cols=["Operator_Name","Well_Number","Total_Depth","Issue_Date","Spud_Date","Lease_Name"]`, `resurfaced_after_days=7` for TX; `key="id"`, `change_cols=["operator","depth","well","status","field"]`, `resurfaced_after_days=None` for LA. LA's resurfaced frame is always empty, matching today's behaviour.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_diff.py`:

```python
import pandas as pd
import pytest

from core.diff import UnusableKeyError, assert_usable_key, diff

CHANGE = ["Operator_Name", "Total_Depth"]


def frame(rows):
    return pd.DataFrame(rows)


def test_everything_is_new_against_empty_master():
    today = frame([{"Permit_Number": "1", "Operator_Name": "EOG", "Total_Depth": 100}])
    new, amended, resurfaced = diff(None, today, key="Permit_Number", change_cols=CHANGE)
    assert len(new) == 1
    assert len(amended) == 0
    assert len(resurfaced) == 0


def test_known_unchanged_record_is_neither_new_nor_amended():
    row = {"Permit_Number": "1", "Operator_Name": "EOG", "Total_Depth": 100}
    new, amended, _ = diff(frame([row]), frame([row]), key="Permit_Number", change_cols=CHANGE)
    assert len(new) == 0
    assert len(amended) == 0


def test_changed_change_col_is_amended():
    master = frame([{"Permit_Number": "1", "Operator_Name": "EOG", "Total_Depth": 100}])
    today = frame([{"Permit_Number": "1", "Operator_Name": "EOG", "Total_Depth": 200}])
    new, amended, _ = diff(master, today, key="Permit_Number", change_cols=CHANGE)
    assert len(new) == 0
    assert len(amended) == 1


def test_key_is_compared_as_string_not_int():
    """Regression: LA WELL_SERIAL_NUM arrives as int from REST but master
    stores it as str. Left uncast, the same well counts as new forever."""
    master = frame([{"Permit_Number": "255778", "Operator_Name": "X", "Total_Depth": 1}])
    today = frame([{"Permit_Number": 255778, "Operator_Name": "X", "Total_Depth": 1}])
    new, amended, _ = diff(master, today, key="Permit_Number", change_cols=CHANGE)
    assert len(new) == 0


def test_numeric_formatting_difference_is_not_an_amendment():
    """100 vs 100.0 must not read as a change."""
    master = frame([{"Permit_Number": "1", "Operator_Name": "EOG", "Total_Depth": "100"}])
    today = frame([{"Permit_Number": "1", "Operator_Name": "EOG", "Total_Depth": 100.0}])
    _, amended, _ = diff(master, today, key="Permit_Number", change_cols=CHANGE)
    assert len(amended) == 0


def test_old_issue_dates_split_into_resurfaced_when_window_set():
    master = frame([{"Permit_Number": "0", "Operator_Name": "X", "Total_Depth": 1,
                     "Issue_Date": "2026-07-27"}])
    today = frame([
        {"Permit_Number": "1", "Operator_Name": "X", "Total_Depth": 1, "Issue_Date": "2026-07-27"},
        {"Permit_Number": "2", "Operator_Name": "X", "Total_Depth": 1, "Issue_Date": "2020-01-01"},
    ])
    new, _, resurfaced = diff(master, today, key="Permit_Number",
                              change_cols=CHANGE, resurfaced_after_days=7)
    assert list(new["Permit_Number"]) == ["1"]
    assert list(resurfaced["Permit_Number"]) == ["2"]


def test_resurfaced_is_empty_when_window_is_none():
    master = frame([{"Permit_Number": "0", "Operator_Name": "X", "Total_Depth": 1,
                     "Issue_Date": "2026-07-27"}])
    today = frame([{"Permit_Number": "2", "Operator_Name": "X", "Total_Depth": 1,
                    "Issue_Date": "2020-01-01"}])
    new, _, resurfaced = diff(master, today, key="Permit_Number",
                              change_cols=CHANGE, resurfaced_after_days=None)
    assert len(new) == 1
    assert len(resurfaced) == 0


def test_null_keys_are_dropped():
    today = frame([
        {"Permit_Number": "1", "Operator_Name": "X", "Total_Depth": 1},
        {"Permit_Number": None, "Operator_Name": "Y", "Total_Depth": 2},
    ])
    new, _, _ = diff(None, today, key="Permit_Number", change_cols=CHANGE)
    assert list(new["Permit_Number"]) == ["1"]


def test_diff_does_not_mutate_its_inputs():
    master = frame([{"Permit_Number": 1, "Operator_Name": "X", "Total_Depth": 1}])
    today = frame([{"Permit_Number": 2, "Operator_Name": "Y", "Total_Depth": 2}])
    master_before = master.copy(deep=True)
    today_before = today.copy(deep=True)
    diff(master, today, key="Permit_Number", change_cols=CHANGE)
    pd.testing.assert_frame_equal(master, master_before)
    pd.testing.assert_frame_equal(today, today_before)


def test_cold_start_ignores_the_resurfaced_window():
    """An empty master means nothing has surfaced before, so nothing can
    resurface -- every record is new regardless of how old its Issue_Date is.
    This is tx_daf420.diff_master's original early-return behavior."""
    today = frame([
        {"Permit_Number": "1", "Operator_Name": "X", "Total_Depth": 1,
         "Issue_Date": "2026-07-27"},
        {"Permit_Number": "2", "Operator_Name": "X", "Total_Depth": 1,
         "Issue_Date": "2004-07-30"},
    ])
    new, amended, resurfaced = diff(None, today, key="Permit_Number",
                                    change_cols=CHANGE, resurfaced_after_days=7)
    assert list(new["Permit_Number"]) == ["1", "2"]
    assert len(resurfaced) == 0


def test_float_upcast_key_still_matches_master():
    """One null in the key column upcasts it to float64; the surviving key
    must not stringify as "255778.0" and count as new forever."""
    master = frame([{"Permit_Number": "255778", "Operator_Name": "X", "Total_Depth": 1}])
    today = frame([
        {"Permit_Number": 255778, "Operator_Name": "X", "Total_Depth": 1},
        {"Permit_Number": None, "Operator_Name": "Y", "Total_Depth": 2},
    ])
    assert str(today["Permit_Number"].dtype) == "float64"
    new, amended, _ = diff(master, today, key="Permit_Number", change_cols=CHANGE)
    assert len(new) == 0


def test_assert_usable_key_rejects_duplicates():
    df = frame([{"Permit_Number": "1"}, {"Permit_Number": "1"}])
    with pytest.raises(UnusableKeyError):
        assert_usable_key(df, "Permit_Number")


def test_assert_usable_key_rejects_nulls():
    """Spec: null keys are alerted on, never silently dropped."""
    df = frame([{"Permit_Number": "1"}, {"Permit_Number": None}])
    with pytest.raises(UnusableKeyError):
        assert_usable_key(df, "Permit_Number")


def test_assert_usable_key_rejects_missing_column():
    with pytest.raises(UnusableKeyError):
        assert_usable_key(frame([{"other": "1"}]), "Permit_Number")


def test_assert_usable_key_accepts_unique():
    assert_usable_key(frame([{"Permit_Number": "1"}, {"Permit_Number": "2"}]), "Permit_Number")
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
python -m pytest tests/test_diff.py -v
```

Expected: collection error — `ModuleNotFoundError: No module named 'core.diff'`.

- [ ] **Step 3: Implement**

Create `core/diff.py`:

```python
"""Consolidated change detection.

Replaces two near-duplicate implementations (tx_daf420.diff_master and
common.diff) that had drifted apart in change-column handling and resurfaced
logic. TX's comparison semantics win throughout: LA's original hashed rows
without numeric normalization, so 100 vs 100.0 read as an amendment on every
run. Master-side duplicate keys resolve keep='last' (TX's rule) rather than
LA's keep='first'.

Pure function: no file I/O, no mutation of its arguments.
"""
import pandas as pd


class UnusableKeyError(Exception):
    pass


def assert_usable_key(df, key: str) -> None:
    """A business key must be present, unique and non-null, or the diff is
    meaningless. Callers reduce to one row per key before calling this.

    Keys must be the source's stable identifier (Permit_Number for TX,
    WELL_SERIAL_NUM for LA) -- never a service-assigned OBJECTID, which can
    change between queries and would make every record look new.
    """
    if key not in df.columns:
        raise UnusableKeyError(f"key column {key!r} is absent")
    nulls = int(df[key].isna().sum())
    if nulls:
        raise UnusableKeyError(f"{nulls} null value(s) in key {key!r}")
    keyed = df[key].astype(str)
    dupes = keyed[keyed.duplicated()].unique()
    if len(dupes):
        raise UnusableKeyError(
            f"{len(dupes)} duplicate value(s) in key {key!r}: {list(dupes)[:5]}"
        )


def _normalize(series) -> pd.Series:
    """Render a column as comparable text: 100, '100', and 100.0 are equal."""
    return series.map(
        lambda v: "" if pd.isna(v) or str(v) in ("None", "nan", "")
        else str(v).removesuffix(".0").strip()
    )


def _normalize_key(series) -> pd.Series:
    """Keys compare as strings with float artifacts stripped.

    A key column holding any null makes pandas upcast the whole column to
    float64, so 255778 stringifies as "255778.0" and never matches master's
    clean "255778" -- the same record then counts as new forever. Plain
    astype(str) does not close this.
    """
    return series.map(lambda v: str(v).removesuffix(".0").strip())


def diff(master, today, *, key: str, change_cols, resurfaced_after_days: int | None = None):
    """Return (new, amended, resurfaced) for today's records against master.

    resurfaced_after_days: when set, records absent from master whose Issue_Date
    is older than this many days are split out of `new` into `resurfaced`.
    When None, `resurfaced` is always empty.
    """
    today = today.dropna(subset=[key]).copy()
    today[key] = _normalize_key(today[key])
    empty = today.iloc[0:0]

    if master is None or master.empty:
        # Cold start: nothing has been seen before, so "resurfaced" has no
        # meaning -- everything is new. Matches tx_daf420.diff_master's
        # original early return, which bypassed the resurfaced split here.
        return today, empty, empty

    master = master.copy()
    master[key] = _normalize_key(master[key])
    known = master.drop_duplicates(key, keep="last").set_index(key)
    is_new = ~today[key].isin(known.index)
    new = today[is_new].copy()
    both = today[~is_new].copy()
    if len(both):
        old = known.loc[both[key]]
        changed = pd.Series(False, index=both.index)
        for c in change_cols:
            old_vals = _normalize(old[c]).values if c in old.columns else ""
            new_vals = _normalize(both[c]).values
            changed |= pd.Series(old_vals != new_vals, index=both.index)
        amended = both[changed]
    else:
        amended = empty

    if resurfaced_after_days is not None and len(new) and "Issue_Date" in new.columns:
        issued = pd.to_datetime(new["Issue_Date"], errors="coerce")
        is_old = (issued < (pd.Timestamp.now() - pd.Timedelta(days=resurfaced_after_days))).fillna(False)
        resurfaced = new[is_old]
        new = new[~is_old]
    else:
        resurfaced = empty

    return new, amended, resurfaced
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
python -m pytest tests/test_diff.py -v
```

Expected: 15 passed.

- [ ] **Step 5: Commit**

```bash
git add core/diff.py tests/test_diff.py
git commit -m "Consolidate TX and LA change detection into core/diff.py"
```

---

### Task 4: Invariant checks

**Files:**
- Create: `core/invariants.py`, `tests/test_invariants.py`

**Interfaces:**
- Consumes: `core.ledger.read_ledger` (Task 1).
- Produces, each returning `(name: str, ok: bool, detail: str)` to match the tuple shape `self_check.py` already uses:
  - `check_source_freshness(ledger_rows, today: date, max_stale_days: int = 3)`
  - `check_advance_produced_records(records_parsed: int, prev_records_parsed: int, new_count: int)`
  - `run_all(data_dir, state, today) -> list[tuple]` — derives both checks from the ledger itself, so callers pass no counts

- [ ] **Step 1: Write the failing tests**

Create `tests/test_invariants.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
python -m pytest tests/test_invariants.py -v
```

Expected: collection error — `ModuleNotFoundError: No module named 'core.invariants'`.

- [ ] **Step 3: Implement**

Create `core/invariants.py`:

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
python -m pytest tests/test_invariants.py -v
```

Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add core/invariants.py tests/test_invariants.py
git commit -m "Add source-freshness and diff-regression invariants"
```

---

### Task 5: Gate tx_daf420.py on the ledger

**Files:**
- Modify: `tx_daf420.py` — imports at line 14, `diff_master` at lines 82-114 (delete), `main()` at lines 249-302

**Interfaces:**
- Consumes: `core.ledger`, `core.outputs.union_write_csv`, `core.diff.diff` and `assert_usable_key`.
- Produces: `main()` exits early with code 0 and message `"source unchanged since <date> -- skipping"` when the source hash is already in the ledger.

- [ ] **Step 1: Replace the imports**

In `tx_daf420.py`, replace line 14:

```python
from common import load_cfg, load_master, save_master
```

with:

```python
from common import load_cfg, load_master, save_master
from core.diff import assert_usable_key, diff as core_diff
from core.ledger import append_ingestion, find_ingestion, hash_file
from core.outputs import union_write_csv
```

- [ ] **Step 2: Delete the local diff and call the shared one**

Delete lines 82-114 entirely (`CHANGE_COLS` and the whole `diff_master` function), and add in their place:

```python
CHANGE_COLS = ["Operator_Name", "Well_Number", "Total_Depth",
               "Issue_Date", "Spud_Date", "Lease_Name"]


def diff_master(master, today):
    return core_diff(master, today, key="Permit_Number",
                     change_cols=CHANGE_COLS, resurfaced_after_days=7)
```

- [ ] **Step 3: Add the ledger gate to main()**

In `main()`, immediately after the `date_tag` assignment (currently line 258) and before `df_all = parse_rrc(dat)`, insert:

```python
    sha = hash_file(dat)
    prior = find_ingestion(cfg["data_dir"], "tx", sha)
    if prior:
        print(f"source unchanged since {prior['ingested_at']} "
              f"({prior['source_name']}, {prior['records_parsed']} records) -- skipping. "
              f"No outputs written.")
        return
```

- [ ] **Step 4: Union the outputs, rebuild the digest from the day, record the ingestion**

The digest is currently built from this run's `new` frame. Once outputs union across runs, that would make `digest.md` describe only the afternoon increment while `new_permits.csv` holds the whole day. The digest must be built from the day's file, so the writes have to happen first.

Delete the digest-building block (currently lines 272-284, from `# canonical names for the shared digest builder` through `text += "\n\n" + mtd_rollup(new_master, cfg)`) and the output block (lines 286-292). Replace both with:

```python
    new_master = pd.concat([master, df_all], ignore_index=True).drop_duplicates(
        "Permit_Number", keep="last") if master is not None else df_all

    day = dt.date.today().isoformat()
    outd = Path(cfg["data_dir"]) / "tx" / "out" / day
    union_write_csv(new, outd / "new_permits.csv", key="Permit_Number")
    union_write_csv(amended, outd / "amendments.csv", key="Permit_Number")
    union_write_csv(resurfaced, outd / "resurfaced.csv", key="Permit_Number")

    # The digest describes the whole day, not just this run's increment --
    # RRC can publish twice in a day and the second run's `new` is smaller.
    day_new = pd.read_csv(outd / "new_permits.csv")
    day_amended = pd.read_csv(outd / "amendments.csv")
    day_resurfaced = pd.read_csv(outd / "resurfaced.csv")

    # canonical names for the shared digest builder
    ren = {"Operator_Name":"operator","County":"county","Total_Depth":"depth",
           "Well_Number":"well","Lease_Name":"lease"}
    text = build_digest("Texas RRC (daf420)", day_new.rename(columns=ren),
                        day_amended.rename(columns=ren), cfg, "tx", "county")
    if len(day_resurfaced):
        text += "\n\n## Resurfaced older files (issue date >7d old, new to master)\n"
        text += "\n".join(f"- {r.Operator_Name} — {r.Lease_Name} {r.Well_Number} "
                          f"({str(r.County).title()}), issued {r.Issue_Date}"
                          for _, r in day_resurfaced.iterrows())
    text += "\n\n" + mtd_rollup(new_master, cfg)

    (outd/"digest.md").write_text(text, encoding="utf-8")
    save_master(cfg, "tx", new_master)

    append_ingestion(
        cfg["data_dir"], "tx",
        source_name=dat.name, sha256=sha,
        ingested_at=dt.datetime.now().isoformat(timespec="seconds"),
        records_parsed=len(df_all), new=len(new),
        amended=len(amended), resurfaced=len(resurfaced),
    )
```

`union_write_csv` creates `outd`, so the existing `outd.mkdir(parents=True, exist_ok=True)` on line 287 is no longer needed — delete it. The ledger records **this run's** counts (`len(new)`), not the day's total, because the invariants compare consecutive ingestions.

The `print` on line 294 and the `build_arcgis` call on lines 297-300 stay as they are; `build_arcgis` continues to receive this run's `new`/`amended`, which is correct — it tags the increment.

- [ ] **Step 5: Reduce to one row per permit, then assert the key**

The existing composite `drop_duplicates` leaves **706 rows for 693 distinct permits** — rows sharing a `Permit_Number` but differing in another field survive. That inflates `new` with duplicate permits and makes the key unusable. Immediately after the `df_all = df_all.drop_duplicates(...)` call (currently ending line 264), insert:

```python
    df_all = df_all.drop_duplicates("Permit_Number", keep="last").copy()
    assert_usable_key(df_all, "Permit_Number")
```

`keep="last"` matches how master already dedupes (`tx_daf420.py:282-283`), so the row that wins here is the row that wins there.

Verify the reduction against the real file before moving on:

```bash
python -c "from tx_daf420 import parse_rrc; d=parse_rrc('data/tx/inbox/daf420.dat.07-28-2026'); print(len(d), d.Permit_Number.nunique())"
```

Expected: `706 693`. After this step the pipeline should report `parsed 693`.

- [ ] **Step 6: Verify the gate works against the real frozen source**

```bash
python tx_daf420.py data/tx/inbox/daf420.dat.07-28-2026
```

Expected on first run: normal output ending with `parsed 693 | new 0 | ...` and a new `data/tx/ledger.csv`.

```bash
python tx_daf420.py data/tx/inbox/daf420.dat.07-28-2026
```

Expected on second run: `source unchanged since <timestamp> (daf420.dat.07-28-2026, 693 records) -- skipping. No outputs written.` and **no modification** to `data/tx/out/`. Confirm with:

```bash
git status --short data/tx/out/
```

Expected: no output. This is Bug 1 fixed — the second run is now a no-op.

- [ ] **Step 7: Commit**

```bash
git add tx_daf420.py
git commit -m "Gate TX ingestion on the ledger; union same-day outputs"
```

---

### Task 6: Gate la_pull.py on the ledger

LA has no source file to hash — it fetches from REST. Hash the normalized frame content instead.

**Files:**
- Modify: `la_pull.py` — imports at lines 11-12, `main()` at lines 67-100

**Interfaces:**
- Consumes: `core.ledger`, `core.outputs`, `core.diff`.
- Produces: same early-exit contract as Task 5.

- [ ] **Step 1: Replace the imports**

Replace lines 11-12:

```python
from common import load_cfg, norm, load_master, save_master, diff, write_outputs
from digest import build_digest
```

with:

```python
from common import load_cfg, norm, load_master, save_master, write_outputs
from core.diff import assert_usable_key, diff as core_diff
from core.ledger import append_ingestion, find_ingestion, hash_text
from digest import build_digest

LA_CHANGE_COLS = ["operator", "depth", "well", "status", "field"]
```

- [ ] **Step 2: Assert the key, then add the ledger gate**

In `main()`, after `today["id"] = today["id"].astype(str)` (currently line 87), insert:

```python
    assert_usable_key(today, "id")

    sha = hash_text(today.sort_values("id").to_csv(index=False))
    prior = find_ingestion(cfg["data_dir"], "la", sha)
    if prior:
        print(f"source unchanged since {prior['ingested_at']} "
              f"({prior['records_parsed']} records) -- skipping. No outputs written.")
        return
```

Sorting by `id` before hashing matters: the REST service does not guarantee row order, and an unsorted hash would differ run-to-run on identical data, defeating the gate.

`assert_usable_key` should pass here because `collapse_operator_lines` (`la_pull.py:57-65`) already reduces SONRIS's one-row-per-`ORGOP_LINE_ID` shape to one row per `WELL_SERIAL_NUM`. If it raises, that collapse has regressed — investigate rather than removing the assertion.

- [ ] **Step 3: Call the shared diff and record the ingestion**

Replace line 89:

```python
    new, amended, _ = diff(master, today, change_cols=("operator","depth","well","status","field"))
```

with:

```python
    new, amended, _ = core_diff(master, today, key="id",
                                change_cols=LA_CHANGE_COLS,
                                resurfaced_after_days=None)
```

Then after `save_master(cfg, "la", updated_master)` (currently line 96), insert:

```python
    append_ingestion(
        cfg["data_dir"], "la",
        source_name=src, sha256=sha,
        ingested_at=dt.datetime.now().isoformat(timespec="seconds"),
        records_parsed=len(today), new=len(new),
        amended=len(amended), resurfaced=0,
    )
```

- [ ] **Step 4: Verify the gate**

```bash
python la_pull.py
```

Expected: normal output, `data/la/ledger.csv` created.

```bash
python la_pull.py
```

Expected: `source unchanged since <timestamp> ... -- skipping. No outputs written.`

- [ ] **Step 5: Commit**

```bash
git add la_pull.py
git commit -m "Gate LA ingestion on the ledger; use shared diff"
```

---

### Task 7: Replay harness and recovery

Rebuilds TX master from empty across the July files, regenerating the per-day results that were overwritten. This is the acceptance test for the whole phase.

**Files:**
- Create: `scripts/replay_tx.py`

**Interfaces:**
- Consumes: `tx_daf420.parse_rrc`, `core.diff.diff`.
- Produces: CLI `python scripts/replay_tx.py --from 2026-07-03 --to 2026-07-28 [--write]`. Prints a per-day table and a reconciliation line. Without `--write` it computes and reports only.

- [ ] **Step 1: Implement the replay harness**

Create `scripts/replay_tx.py`:

```python
r"""Rebuild TX master from empty across a date range, reporting per-day new counts.

Why this exists: same-day re-runs overwrote each day's new_permits.csv with
empty files (commit c29c268b had 62 rows for 2026-07-26; 479da72d had 0).
Replaying from the retained inbox files regenerates the true series.

The daf420 extract is month-to-date cumulative and RESETS at month start --
daf420.dat.07-01-2026 and 07-02-2026 carry June's cycle (974 and 1009 permit
headers) and must be excluded from a July replay.

Usage:
  python scripts/replay_tx.py --from 2026-07-03 --to 2026-07-28
  python scripts/replay_tx.py --from 2026-07-03 --to 2026-07-28 --write
"""
import argparse
import datetime as dt
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import load_cfg, save_master              # noqa: E402
from core.diff import diff                            # noqa: E402
from tx_daf420 import CHANGE_COLS, parse_rrc          # noqa: E402


def dated_inbox_files(watch_dir, start, end):
    out = []
    for p in Path(watch_dir).glob("daf420.dat.*"):
        m = re.search(r"(\d{2})-(\d{2})-(\d{4})", p.name)
        if not m:
            continue
        d = dt.date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
        if start <= d <= end:
            out.append((d, p))
    return sorted(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", required=True)
    ap.add_argument("--to", dest="end", required=True)
    ap.add_argument("--write", action="store_true",
                    help="persist the rebuilt master (default: report only)")
    args = ap.parse_args()

    cfg = load_cfg()
    start = dt.date.fromisoformat(args.start)
    end = dt.date.fromisoformat(args.end)
    files = dated_inbox_files(cfg["texas"]["watch_dir"], start, end)
    if not files:
        sys.exit(f"No daf420 files between {start} and {end}")

    master = None
    total_new = 0
    print(f"{'date':12} {'parsed':>7} {'new':>6} {'amended':>8} {'master':>7}")
    for day, path in files:
        parsed = parse_rrc(path)
        parsed = parsed.drop_duplicates(
            subset=["Permit_Number", "CountyCode", "Lease_Name", "Operator_Number",
                    "Well_Number", "Issue_Date", "Spud_Date"], keep="first").copy()
        parsed["Permit_Number"] = parsed["Permit_Number"].astype(str)
        # One row per permit, matching tx_daf420.main(). Without this the file's
        # 706 rows / 693 permits inflate `new` and reconciliation fails.
        parsed = parsed.drop_duplicates("Permit_Number", keep="last").copy()
        new, amended, _ = diff(master, parsed, key="Permit_Number",
                               change_cols=CHANGE_COLS, resurfaced_after_days=None)
        master = (parsed if master is None
                  else pd.concat([master, parsed], ignore_index=True)
                       .drop_duplicates("Permit_Number", keep="last"))
        total_new += len(new)
        print(f"{day.isoformat():12} {len(parsed):>7} {len(new):>6} "
              f"{len(amended):>8} {len(master):>7}")

    unique = master["Permit_Number"].nunique()
    print(f"\nper-day new sums to : {total_new}")
    print(f"master unique permits: {unique}")
    if total_new == unique:
        print("RECONCILED - every permit in master was reported new on exactly one day")
    else:
        print(f"MISMATCH - {total_new} != {unique}; the replay is losing or double-counting")
        sys.exit(1)

    if args.write:
        save_master(cfg, "tx", master)
        print(f"master written: {len(master)} rows")


if __name__ == "__main__":
    main()
```

Note `resurfaced_after_days=None` in the replay: the resurfaced split is relative to *now*, so replaying historical days with a 7-day window would misclassify almost everything as resurfaced. The replay measures new-permit detection, not the resurfaced heuristic.

- [ ] **Step 2: Run the replay and confirm reconciliation**

```bash
python scripts/replay_tx.py --from 2026-07-03 --to 2026-07-28
```

Expected: a per-day table starting at 59 parsed on 07-03 and climbing to 706 on 07-26, flat at 706 for 07-27 and 07-28 with `new` of 0 on those two days, ending with:

```
per-day new sums to : 693
master unique permits: 693
RECONCILED - every permit in master was reported new on exactly one day
```

If the counts disagree, stop — the diff is losing records and Task 3 needs revisiting before proceeding.

- [ ] **Step 3: Commit**

```bash
git add scripts/replay_tx.py
git commit -m "Add TX replay harness; reconciles 693 permits across July"
```

---

### Task 8: Wire invariants into the daily run

`self_check.py` is a library of check functions with no collector of its own. The list of `(name, ok, detail)` tuples is assembled in `run_daily_ci.py:88-101`, which is what emails the failure alert. That is where the new checks belong.

**Files:**
- Modify: `run_daily_ci.py` — imports at lines 18-20, checks block at lines 88-101

**Interfaces:**
- Consumes: `core.invariants.run_all` (Task 4).
- Produces: entries named `tx_source_freshness`, `la_source_freshness`, `tx_advance_produced_records`, `la_advance_produced_records` in the `checks` list, which feeds `send_email.send_failure_alert` and `self_check.log_run` unchanged.

- [ ] **Step 1: Add the import**

In `run_daily_ci.py`, after line 20 (`import send_email`), add:

```python
from core.invariants import run_all as run_invariants
```

- [ ] **Step 2: Append the invariants to the checks list**

Immediately after line 101 (`checks.append(self_check.check_run_not_stale(RUN_LOG))`) and before line 103 (`failed = [c for c in checks if not c[1]]`), insert:

```python
    for state in ("tx", "la"):
        for name, ok, detail in run_invariants(cfg["data_dir"], state, dt.date.today()):
            checks.append((f"{state}_{name}", ok, detail))
```

`cfg` is already in scope from line 76 and `dt` from line 13. These run regardless of whether the individual pulls succeeded, which is deliberate: a pull that exits early via the ledger gate reports success, and the freshness check is what distinguishes "nothing to do" from "source is frozen."

- [ ] **Step 3: Confirm the frozen source is reported**

```bash
python -c "import datetime as dt; from common import load_cfg; from core.invariants import run_all; cfg=load_cfg(); [print(r) for s in ('tx','la') for r in run_all(cfg['data_dir'], s, dt.date.today())]"
```

Expected: a `('source_freshness', False, ...)` tuple for `tx`, because the TX source has not advanced since 2026-07-26. **This failure is correct** — it is the alarm working against a genuinely frozen source, and it should stay red until Task 9's cause is fixed.

- [ ] **Step 4: Note on `check_volume_sane`**

`run_daily_ci.py:92` calls `check_volume_sane(tx_new, "tx", floor=0, ceiling=300)`. A floor of 0 means zero new permits passes — one reason nothing alarmed for ten days. Leave the floor at 0: with the ledger gate in place, a zero-new run only happens when the source genuinely did not advance, and `advance_produced_records` now covers the case where it did. Changing the floor here would produce daily false alarms on legitimately quiet days.

- [ ] **Step 5: Commit**

```bash
git add run_daily_ci.py
git commit -m "Report source-freshness invariants in the daily run"
```

---

### Task 9: Diagnose the frozen RRC source

Investigation, not code. Bug 2 is upstream of this repo and cannot be fixed by changing the pipeline.

**Files:**
- Create: `docs/superpowers/notes/2026-07-28-rrc-source-freeze.md`

- [ ] **Step 1: Establish whether the served file differs from the stored one**

```bash
python -c "import hashlib,requests,yaml; u=yaml.safe_load(open('config.yaml'))['texas']['fetch_url']; r=requests.get(u,timeout=120); print(r.status_code, len(r.content), hashlib.sha256(r.content).hexdigest()[:16], r.headers.get('last-modified'), r.headers.get('content-type'))"
```

Compare the hash and length against the stored file:

```bash
python -c "import hashlib; d=open('data/tx/inbox/daf420.dat.07-28-2026','rb').read(); print(len(d), hashlib.sha256(d).hexdigest()[:16])"
```

- [ ] **Step 2: Interpret and record the result**

Three outcomes, each with a different remedy:

- **The response is HTML, not fixed-width data** — the MFT share link has expired or now requires a session. `auto_download_rrc.py` uses Playwright specifically because this endpoint redirects; the link likely needs reissuing from the RRC portal.
- **The response is data and its hash differs from the stored file** — the downloader is caching or writing stale content. The bug is in `auto_download_rrc.py`.
- **The response is data and the hash matches** — RRC itself has not published new permits since 07-26. Verify independently before concluding this: RRC publishes daily, so a multi-day gap warrants checking the portal directly.

Write the finding, the evidence, and the chosen remedy to `docs/superpowers/notes/2026-07-28-rrc-source-freeze.md`.

- [ ] **Step 3: Commit the finding**

```bash
git add docs/superpowers/notes/2026-07-28-rrc-source-freeze.md
git commit -m "Record RRC source freeze diagnosis"
```

---

## Done when

- [ ] `python -m pytest tests/ -v` passes (39 tests).
- [ ] `python scripts/replay_tx.py --from 2026-07-03 --to 2026-07-28` prints `RECONCILED` with 693 on both lines.
- [ ] Running `tx_daf420.py` twice on the same file leaves `git status --short data/tx/out/` empty on the second run.
- [ ] `run_daily_ci.py`'s checks include `tx_source_freshness` failing while the source remains frozen.
- [ ] `docs/superpowers/notes/2026-07-28-rrc-source-freeze.md` names the cause of the freeze and the remedy.

## Spec invariants deliberately not implemented here

Three invariants listed in the design spec are subsumed by the ledger and are not
implemented separately, to avoid two alarms for one condition:

- *"Master row count flat across a rolling week"* — master cannot grow unless the source
  advances, which `source_freshness` already detects, and sooner.
- *"Expected daf420 file absent for the run date"* — an absent file produces no ledger row,
  so `source_freshness` fires within its 3-day threshold. `run_daily.py:57-60` already logs
  the absence at the time it happens.
- *"Output would shrink"* as a check — enforced as an exception at write time
  (`core.outputs.OutputWouldShrink`) rather than reported after the fact, because refusing
  the bad write is strictly better than reporting it.

## Out of scope for Phase 1

Client registry, spatial join, evidence pack, email layer, brief composition, repertoire. Those are Phases 2-4 in the design spec.
