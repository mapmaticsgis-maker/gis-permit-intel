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
