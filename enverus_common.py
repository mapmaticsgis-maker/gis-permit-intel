r"""
Shared fetch logic for the Enverus Developer API v3 'permits' dataset,
used by both enverus_tx_pull.py (RRC cross-check) and enverus_la_pull.py
(SONRIS cross-check). Field mapping and the join key are deliberately left
to each caller -- TX (zero-padded RRC Permit_Number, county) and LA
(unpadded SONRIS WELL_SERIAL_NUM, parish) differ enough that a shared
mapping would just be two half-fitting special cases.
"""
import datetime as dt

from enverus_developer_api import DeveloperAPIv3


def fetch_raw_permits(secret_key: str, state_abbr: str, lookback_days: int) -> list[dict]:
    """Yields raw Enverus permit records (dicts, all 65 dataset fields) for
    a state, approved within the lookback window. ApprovedDate is used
    (not UpdatedDate) so this matches "permits approved in the last N
    days" -- the same thing RRC's/SONRIS's own digests describe."""
    cutoff = (dt.date.today() - dt.timedelta(days=lookback_days)).isoformat()
    v3 = DeveloperAPIv3(secret_key=secret_key)
    return list(v3.query("permits", stateprovince=state_abbr,
                          approveddate=f"gt({cutoff})", pagesize=1000))


def depth_from_record(rec: dict) -> float | None:
    """PermitDepth_FT is populated far more often than the two more specific
    depth fields in practice (confirmed against sample TX/LA records) --
    fall back to them only when it's missing."""
    for k in ("PermitDepth_FT", "PermittedMeasuredDepth_FT", "PermittedTrueVerticalDepth_FT"):
        v = rec.get(k)
        if v not in (None, ""):
            try:
                return float(v)
            except (TypeError, ValueError):
                continue
    return None
