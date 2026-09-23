from scripts.report_audit.build_audit_workbook import build_workbook, find_gmail_confirmation

FILESYSTEM_DATA = {
    "generated_date": "2026-09-23",
    "rows": [
        {
            "client": "RROG",
            "mxd_path": r"C:\GIS\CLIENT\RROG\LA-CAD_2216N13W.mxd",
            "mxd_basename": "LA-CAD_2216N13W",
            "mxd_modified": "2026-09-22",
            "pdf_matches": [
                {"path": r"C:\PDF\20260922-LA-CAD_2216N13W-NEWTRACTS.pdf", "date": "2026-09-16",
                 "confidence": "Exact", "matched_tokens": ["LA-CAD_2216N13W"]},
            ],
            "report_candidates": [
                {"path": r"C:\Users\mapma\Downloads\MOR-22-16N-13W - Unit Survey update (1).xlsx",
                 "date": "2026-09-22", "confidence": "Token", "matched_tokens": ["digits:221613"]},
            ],
        },
        {
            "client": "DOXA",
            "mxd_path": r"C:\GIS\CLIENT\DOXA\TX-CHE_FORTUNE-24X36.mxd",
            "mxd_basename": "TX-CHE_FORTUNE-24X36",
            "mxd_modified": "2026-09-18",
            "pdf_matches": [],
            "report_candidates": [],
        },
    ],
}

GMAIL_DATA = {
    "generated_date": "2026-09-23",
    "sent_pdfs": [
        {"client": "RROG", "date": "2026-09-16", "subject": "22 16N 13W - New tracts"},
        {"client": "RROG", "date": "2026-09-01", "subject": "Unrelated thread"},
    ],
}


def test_find_gmail_confirmation_matches_by_subject_token_overlap():
    confirmation = find_gmail_confirmation("LA-CAD_2216N13W", GMAIL_DATA["sent_pdfs"])
    assert confirmation == "22 16N 13W - New tracts (2026-09-16)"


def test_find_gmail_confirmation_none_when_no_match():
    assert find_gmail_confirmation("TX-CHE_FORTUNE-24X36", GMAIL_DATA["sent_pdfs"]) is None


def test_build_workbook_header_and_row_count():
    wb = build_workbook(FILESYSTEM_DATA, GMAIL_DATA)
    ws = wb.active
    assert ws.title == "Audit"
    # header + 2 rows (one per mxd)
    assert ws.max_row == 3


def test_build_workbook_gap_row_has_blank_matches():
    wb = build_workbook(FILESYSTEM_DATA, GMAIL_DATA)
    ws = wb.active
    rows = {row[1].value: row for row in ws.iter_rows(min_row=2)}
    doxa_row = rows[r"C:\GIS\CLIENT\DOXA\TX-CHE_FORTUNE-24X36.mxd"]
    assert doxa_row[3].value is None  # Matched PDF(s) column blank


def test_build_workbook_includes_gmail_confirmation():
    wb = build_workbook(FILESYSTEM_DATA, GMAIL_DATA)
    ws = wb.active
    rows = {row[1].value: row for row in ws.iter_rows(min_row=2)}
    rrog_row = rows[r"C:\GIS\CLIENT\RROG\LA-CAD_2216N13W.mxd"]
    assert rrog_row[7].value == "22 16N 13W - New tracts (2026-09-16)"
