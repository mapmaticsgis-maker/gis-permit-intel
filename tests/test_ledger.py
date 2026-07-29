import datetime as dt

from core import ledger
from core.invariants import check_records_advancing, check_source_freshness


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


# --------------------------------------------------------------------------
# Finding 6: replay --write must leave master and the ledger consistent.
# --------------------------------------------------------------------------

def stale_ledger(data_dir):
    """A ledger frozen before the incident, as after a real outage."""
    ledger.append_ingestion(
        data_dir, "tx",
        source_name="daf420.dat.07-20-2026", sha256="old1",
        ingested_at="2026-07-20T06:00:00", records_parsed=400,
        new=10, amended=0, resurfaced=0,
    )


def test_replay_row_makes_the_source_findable_so_the_next_run_skips(data_dir, tmp_path):
    src = tmp_path / "daf420.dat.07-28-2026"
    src.write_text("01PERMIT\n", encoding="utf-8")

    row = ledger.record_replay_ingestion(
        data_dir, "tx", source_path=src, records_parsed=693, new=0, amended=0)

    found = ledger.find_ingestion(data_dir, "tx", ledger.hash_file(src))
    assert found is not None, "next run must skip a source already in master"
    assert found["source_name"] == "replay:daf420.dat.07-28-2026"
    assert row["records_parsed"] == 693


def test_replay_row_is_marked_so_history_is_not_misread(data_dir, tmp_path):
    src = tmp_path / "daf420.dat.07-28-2026"
    src.write_text("01PERMIT\n", encoding="utf-8")
    row = ledger.record_replay_ingestion(
        data_dir, "tx", source_path=src, records_parsed=693, new=0, amended=0)
    assert row["source_name"].startswith("replay:")


def test_recovery_without_a_ledger_row_leaves_invariants_red(data_dir):
    """The bug: master is full, the ledger is stale, and the operator gets
    two red checks while mid-incident."""
    stale_ledger(data_dir)
    rows = ledger.read_ledger(data_dir, "tx")
    today = dt.date(2026, 7, 29)
    assert check_source_freshness(rows, today)[1] is False
    assert check_records_advancing(rows, today)[1] is False


def test_recovery_with_a_ledger_row_leaves_invariants_green(data_dir, tmp_path):
    """After the fix, the same recovery reports healthy."""
    stale_ledger(data_dir)
    src = tmp_path / "daf420.dat.07-28-2026"
    src.write_text("01PERMIT\n", encoding="utf-8")
    ledger.record_replay_ingestion(
        data_dir, "tx", source_path=src, records_parsed=693, new=0, amended=0,
        ingested_at="2026-07-29T09:00:00")

    rows = ledger.read_ledger(data_dir, "tx")
    today = dt.date(2026, 7, 29)
    assert check_source_freshness(rows, today)[1] is True
    assert check_records_advancing(rows, today)[1] is True
