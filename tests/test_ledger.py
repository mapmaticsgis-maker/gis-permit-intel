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
