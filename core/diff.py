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


def _normalize_key(series) -> pd.Series:
    """Keys compare as strings with float artifacts stripped.

    A key column holding any null makes pandas upcast the whole column to
    float64, so 255778 stringifies as "255778.0" and never matches master's
    clean "255778" -- the same record then counts as new forever. Plain
    astype(str) does not close this.
    """
    return series.map(lambda v: str(v).removesuffix(".0").strip())


def _normalize(series) -> pd.Series:
    """Render a column as comparable text: 100, '100', and 100.0 are equal."""
    return series.map(
        lambda v: "" if pd.isna(v) or str(v) in ("None", "nan", "")
        else str(v).removesuffix(".0").strip()
    )


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
