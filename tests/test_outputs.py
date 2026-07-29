import pandas as pd
import pytest

from core.outputs import count_data_rows, union_write_csv

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
