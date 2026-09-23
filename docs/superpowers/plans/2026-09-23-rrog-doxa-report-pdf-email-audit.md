# RROG + DOXA Report -> MXD -> PDF -> Email Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce `C:\GIS\CLIENT\RROG_DOXA_Report_PDF_Email_Audit.xlsx` — one row per in-scope RROG/DOXA `.mxd` showing matched PDF output(s), candidate report(s) from Downloads, and a Gmail send confirmation if found.

**Architecture:** Three stages. Stage A is pure filename/token matching logic (no filesystem or network dependency, fully unit-tested). Stage B is a filesystem walk (RROG/DOXA `.mxd` files, `C:\PDF`, Downloads) that applies Stage A's matcher and writes an intermediate JSON — no Gmail involved, no arcpy needed (only filenames/dates, not `.mxd` internals). Stage C is a Gmail bulk lookup (run directly via the Gmail MCP tools in this session, not scriptable) that pulls every PDF-attachment message sent from each client's label in the last 12 months, then a final merge script matches those against Stage B's PDF list and writes the workbook.

**Tech Stack:** Python 3, `openpyxl`, `pytest`. No arcpy needed for this plan (unlike the mxd data-source inventory).

## Global Constraints

- Scope: RROG + DOXA `.mxd` files modified in the last 12 months (145 files, confirmed by `find CLIENT/RROG CLIENT/DOXA -iname "*.mxd" -newermt "2025-09-23" | wc -l`) — per spec §2.
- Sources: `C:\Users\mapma\Downloads`, `C:\PDF`, Gmail (RROG/DOXA labels) — per spec §2.
- Discovery only — no file moves, no `.mxd`/shapefile edits, no emails sent — per spec §1.
- Every in-scope `.mxd` gets a row even with no matches — gaps must stay visible, not be dropped — per spec §4.
- Confidence: `Exact` when the mxd basename (separators stripped) is a literal substring of the candidate filename; `Token` when only a partial token/digit-sequence match — per spec §3-4.

---

## File Structure

- Create: `scripts/report_audit/matching.py` — Stage A. Pure functions `normalize()`, `alnum_tokens()`, `digit_signature()`, `match_candidate()`.
- Create: `tests/test_matching.py` — unit tests for Stage A.
- Create: `scripts/report_audit/scan_filesystem.py` — Stage B. Walks the three sources, applies `match_candidate()`, writes `data/report_audit/filesystem_matches.json`.
- Create: `data/report_audit/gmail_sent_pdfs.json` — Stage C's Gmail pull, gathered by me directly via Gmail MCP tool calls in this session (not a script — Gmail tools aren't available outside a Claude session).
- Create: `scripts/report_audit/build_audit_workbook.py` — merges Stage B + Stage C JSON, writes the final xlsx. Pure function `build_workbook(filesystem_data: dict, gmail_data: dict) -> openpyxl.Workbook`, unit tested with fixtures.
- Create: `tests/test_build_audit_workbook.py` — unit tests for the merge/workbook logic.

## Task 1: Stage A — filename/token matching logic (TDD)

**Files:**
- Create: `scripts/report_audit/matching.py`
- Test: `tests/test_matching.py`

**Interfaces:**
- Produces: `match_candidate(mxd_basename: str, candidate_name: str) -> dict | None`, shaped `{"confidence": "Exact"|"Token", "matched_tokens": list[str]}` or `None` if no match. Used by Stage B (Task 2) and indirectly documented for Stage C reconciliation (Task 4).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_matching.py
from scripts.report_audit.matching import match_candidate, normalize, alnum_tokens, digit_signature


def test_normalize_strips_separators_and_uppercases():
    assert normalize("LA-CAD_2216N13W") == "LACAD2216N13W"


def test_digit_signature_concatenates_digits_in_order():
    assert digit_signature("LA-CAD_2216N13W") == "221613"
    assert digit_signature("22-16N-13W") == "221613"


def test_alnum_tokens_excludes_short_and_stopwords():
    tokens = alnum_tokens("LA-CAD_UNIT59_ABSTATUS")
    assert "UNIT" not in tokens  # stopword
    assert "ABSTATUS" in tokens
    assert "LA" not in tokens  # below length-3 minimum... actually LA is 2 chars, excluded


def test_match_candidate_exact_when_basename_is_literal_substring():
    result = match_candidate("LA-CAD_2216N13W", "20260922-LA-CAD_2216N13W-NEWTRACTS.pdf")
    assert result["confidence"] == "Exact"


def test_match_candidate_token_when_only_digit_signature_overlaps():
    result = match_candidate("LA-CAD_2216N13W", "22-16N-13W - Unit Survey update (1).xlsx")
    assert result is not None
    assert result["confidence"] == "Token"


def test_match_candidate_token_when_only_alpha_token_overlaps():
    result = match_candidate("TX-SHELBY-LEASE_STATUS", "20260917_TX-SHELBY-MINERAL_TRACTS.pdf")
    assert result is not None
    assert result["confidence"] == "Token"
    assert "SHELBY" in result["matched_tokens"]


def test_match_candidate_none_when_unrelated():
    assert match_candidate("LA-CAD_2216N13W", "invoice_1740252.pdf") is None


def test_match_candidate_none_for_short_digit_signature_no_alpha_overlap():
    # mxd with a short digit run shouldn't false-positive-match on digits alone
    assert match_candidate("LA-CAD_UNIT59_ABSTATUS", "invoice_1740252.pdf") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_matching.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.report_audit.matching'`

- [ ] **Step 3: Write the minimal implementation**

```python
# scripts/report_audit/matching.py
import os
import re

STOPWORDS = {
    "SHP", "LSE", "STATUS", "UNIT", "UNITS", "ABS", "OSR", "TITLE", "LGL",
    "WORK", "EXPORT", "MOR", "AER", "LTR", "PDF", "MXD", "NEW", "OLD",
    "FINAL", "DRAFT",
}

MIN_TOKEN_LEN = 3
MIN_DIGIT_SIGNATURE_LEN = 4


def normalize(name):
    return re.sub(r"[^A-Za-z0-9]", "", name).upper()


def alnum_tokens(name):
    tokens = set()
    for t in re.findall(r"[A-Za-z0-9]+", name):
        upper = t.upper()
        if len(upper) >= MIN_TOKEN_LEN and upper not in STOPWORDS:
            tokens.add(upper)
    return tokens


def digit_signature(name):
    return "".join(re.findall(r"\d", name))


def match_candidate(mxd_basename, candidate_name):
    candidate_stem = os.path.splitext(candidate_name)[0]

    norm_mxd = normalize(mxd_basename)
    norm_candidate = normalize(candidate_stem)
    if norm_mxd and norm_mxd in norm_candidate:
        return {"confidence": "Exact", "matched_tokens": [mxd_basename]}

    mxd_tokens = alnum_tokens(mxd_basename)
    candidate_tokens = alnum_tokens(candidate_name)
    shared = sorted(mxd_tokens & candidate_tokens)

    mxd_digits = digit_signature(mxd_basename)
    digit_match = (
        len(mxd_digits) >= MIN_DIGIT_SIGNATURE_LEN
        and mxd_digits in digit_signature(candidate_name)
    )

    if not shared and not digit_match:
        return None

    matched_tokens = list(shared)
    if digit_match:
        matched_tokens.append("digits:" + mxd_digits)

    return {"confidence": "Token", "matched_tokens": matched_tokens}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_matching.py -v`
Expected: PASS (all 7 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/report_audit/matching.py tests/test_matching.py
git commit -m "Add filename/token matching logic for report-PDF-email audit"
```

## Task 2: Stage B — filesystem scan (mxd list + PDF/Downloads matching)

**Files:**
- Create: `scripts/report_audit/scan_filesystem.py`
- Create: `data/report_audit/filesystem_matches.json` (generated, gitignored)

**Interfaces:**
- Consumes: `match_candidate()` from Task 1.
- Produces: `data/report_audit/filesystem_matches.json` shaped:
```json
{
  "generated_date": "2026-09-23",
  "window_days": 365,
  "clients": {"RROG": "C:\\GIS\\CLIENT\\RROG", "DOXA": "C:\\GIS\\CLIENT\\DOXA"},
  "rows": [
    {
      "client": "RROG",
      "mxd_path": "C:\\GIS\\CLIENT\\RROG\\LA-CAD_2216N13W.mxd",
      "mxd_basename": "LA-CAD_2216N13W",
      "mxd_modified": "2026-09-22",
      "pdf_matches": [{"path": "C:\\PDF\\20260922-LA-CAD_2216N13W-NEWTRACTS.pdf", "date": "2026-09-16", "confidence": "Exact", "matched_tokens": ["LA-CAD_2216N13W"]}],
      "report_candidates": [{"path": "C:\\Users\\mapma\\Downloads\\MOR-22-16N-13W - Unit Survey update (1).xlsx", "date": "2026-09-22", "confidence": "Token", "matched_tokens": ["digits:221613"]}]
    }
  ]
}
```
Consumed by Task 4's merge/`build_workbook()`.

- [ ] **Step 1: Write the scanner**

```python
# scripts/report_audit/scan_filesystem.py
import datetime
import json
import os
from pathlib import Path

from scripts.report_audit.matching import match_candidate

CLIENT_ROOTS = {
    "RROG": r"C:\GIS\CLIENT\RROG",
    "DOXA": r"C:\GIS\CLIENT\DOXA",
}
PDF_ROOT = r"C:\PDF"
DOWNLOADS_ROOT = r"C:\Users\mapma\Downloads"
WINDOW_DAYS = 365
OUTPUT_PATH = Path("data/report_audit/filesystem_matches.json")


def find_mxds(root, cutoff):
    matches = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            if not name.lower().endswith(".mxd"):
                continue
            full = os.path.join(dirpath, name)
            mtime = datetime.date.fromtimestamp(os.path.getmtime(full))
            if mtime >= cutoff:
                matches.append((full, mtime))
    return matches


def list_files(root):
    files = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            full = os.path.join(dirpath, name)
            try:
                mtime = datetime.date.fromtimestamp(os.path.getmtime(full))
            except OSError:
                continue
            files.append((full, name, mtime))
    return files


def main():
    cutoff = datetime.date.today() - datetime.timedelta(days=WINDOW_DAYS)
    pdf_files = list_files(PDF_ROOT)
    downloads_files = list_files(DOWNLOADS_ROOT)

    rows = []
    for client, root in CLIENT_ROOTS.items():
        for mxd_path, mtime in find_mxds(root, cutoff):
            basename = os.path.splitext(os.path.basename(mxd_path))[0]

            pdf_matches = []
            for full, name, pdf_mtime in pdf_files:
                result = match_candidate(basename, name)
                if result:
                    pdf_matches.append({"path": full, "date": pdf_mtime.isoformat(), **result})

            report_candidates = []
            for full, name, dl_mtime in downloads_files:
                if dl_mtime > mtime:
                    continue
                result = match_candidate(basename, name)
                if result:
                    report_candidates.append({"path": full, "date": dl_mtime.isoformat(), **result})

            rows.append({
                "client": client,
                "mxd_path": mxd_path,
                "mxd_basename": basename,
                "mxd_modified": mtime.isoformat(),
                "pdf_matches": pdf_matches,
                "report_candidates": report_candidates,
            })

    output = {
        "generated_date": datetime.date.today().isoformat(),
        "window_days": WINDOW_DAYS,
        "clients": CLIENT_ROOTS,
        "rows": rows,
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, indent=2))
    print(f"Wrote {len(rows)} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Ensure the data directory is gitignored**

```bash
grep -q "^data/report_audit/" .gitignore || echo "data/report_audit/" >> .gitignore
git add .gitignore
```

- [ ] **Step 3: Run the scanner**

Run: `python scripts/report_audit/scan_filesystem.py`
Expected: prints `Wrote 145 rows to data/report_audit/filesystem_matches.json` (145 matches the confirmed in-scope count; a small drift is fine if the clock has ticked past midnight since scoping, but it should not be wildly different).

- [ ] **Step 4: Spot-check the known LA-CAD_2216N13W case**

Run: `python -c "import json; d=json.load(open('data/report_audit/filesystem_matches.json')); row=[r for r in d['rows'] if r['mxd_basename']=='LA-CAD_2216N13W'][0]; print(row['pdf_matches']); print(row['report_candidates'])"`
Expected: `pdf_matches` includes an entry for `20260922-LA-CAD_2216N13W-NEWTRACTS.pdf` (or similar) with `confidence: Exact`; `report_candidates` includes the `MOR-22-16N-13W - Unit Survey update (1).xlsx` file with `confidence: Token`.

- [ ] **Step 5: Commit**

```bash
git add scripts/report_audit/scan_filesystem.py
git commit -m "Add filesystem scanner for report-PDF-email audit"
```

## Task 3: Stage C — Gmail bulk sent-PDF lookup (run in-session, not scripted)

**Files:**
- Create: `data/report_audit/gmail_sent_pdfs.json` (hand-assembled from tool results, gitignored)

**Interfaces:**
- Produces: `data/report_audit/gmail_sent_pdfs.json` shaped:
```json
{
  "generated_date": "2026-09-23",
  "window_days": 365,
  "sent_pdfs": [
    {"client": "RROG", "date": "2026-09-16", "subject": "...", "attachment_names": ["20260916-...pdf"]}
  ]
}
```
Consumed by Task 4's merge logic.

- [ ] **Step 1: For each client (RROG, DOXA), search Gmail sent mail for PDF attachments in the last 365 days**

Use `search_threads` with a query like `label:<label> in:sent has:attachment filename:pdf newer_than:365d`, paginating with `pageToken` if `nextPageToken` is present, up to the full result set.

- [ ] **Step 2: For each matching thread, record date, subject, and attachment filename(s)**

Use `get_thread` (messageFormat `METADATA_ONLY` or `MINIMAL`, or `PLAIN_TEXT`/`FULL_CONTENT` only if attachment names aren't visible in the lighter formats) to confirm attachment filenames where the search result alone doesn't include them.

- [ ] **Step 3: Write the assembled list to `data/report_audit/gmail_sent_pdfs.json`**

- [ ] **Step 4: Sanity-check row count is non-zero for both clients**

Run: `python -c "import json; d=json.load(open('data/report_audit/gmail_sent_pdfs.json')); from collections import Counter; print(Counter(r['client'] for r in d['sent_pdfs']))"`
Expected: both `RROG` and `DOXA` have at least one entry (both clients are active enough that a full year should have sent PDFs).

## Task 4: Merge and build the final workbook (TDD for the merge logic)

**Files:**
- Create: `scripts/report_audit/build_audit_workbook.py`
- Test: `tests/test_build_audit_workbook.py`

**Interfaces:**
- Consumes: `data/report_audit/filesystem_matches.json` (Task 2), `data/report_audit/gmail_sent_pdfs.json` (Task 3).
- Produces: `build_workbook(filesystem_data: dict, gmail_data: dict) -> openpyxl.workbook.Workbook`, and `main()` that reads both files and saves `C:\GIS\CLIENT\RROG_DOXA_Report_PDF_Email_Audit.xlsx`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_build_audit_workbook.py
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
        {"client": "RROG", "date": "2026-09-16", "subject": "RROG map update",
         "attachment_names": ["20260922-LA-CAD_2216N13W-NEWTRACTS.pdf"]},
    ],
}


def test_find_gmail_confirmation_matches_by_attachment_filename():
    confirmation = find_gmail_confirmation("20260922-LA-CAD_2216N13W-NEWTRACTS.pdf", GMAIL_DATA["sent_pdfs"])
    assert confirmation == "RROG map update (2026-09-16)"


def test_find_gmail_confirmation_none_when_no_match():
    assert find_gmail_confirmation("nonexistent.pdf", GMAIL_DATA["sent_pdfs"]) is None


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
    assert rrog_row[7].value == "RROG map update (2026-09-16)"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_build_audit_workbook.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.report_audit.build_audit_workbook'`

- [ ] **Step 3: Write the minimal implementation**

```python
# scripts/report_audit/build_audit_workbook.py
import json
import os
from pathlib import Path

from openpyxl import Workbook

HEADERS = [
    "Client", "MXD", "MXD Last Modified", "Matched PDF(s)", "PDF Date(s)",
    "Report Candidate(s)", "Report Date(s)", "Gmail Confirmation", "Confidence",
]

FILESYSTEM_PATH = Path("data/report_audit/filesystem_matches.json")
GMAIL_PATH = Path("data/report_audit/gmail_sent_pdfs.json")
OUTPUT_PATH = Path(r"C:\GIS\CLIENT\RROG_DOXA_Report_PDF_Email_Audit.xlsx")


def find_gmail_confirmation(pdf_filename, sent_pdfs):
    for entry in sent_pdfs:
        if pdf_filename in entry.get("attachment_names", []):
            return "{0} ({1})".format(entry["subject"], entry["date"])
    return None


def _best_confidence(matches):
    confidences = [m["confidence"] for m in matches]
    if "Exact" in confidences:
        return "Exact"
    if "Token" in confidences:
        return "Token"
    return None


def build_workbook(filesystem_data, gmail_data):
    sent_pdfs = gmail_data.get("sent_pdfs", [])

    wb = Workbook()
    ws = wb.active
    ws.title = "Audit"
    ws.append(HEADERS)

    for row in filesystem_data["rows"]:
        pdf_matches = row["pdf_matches"]
        report_candidates = row["report_candidates"]

        pdf_names = [os.path.basename(m["path"]) for m in pdf_matches]
        confirmations = [find_gmail_confirmation(name, sent_pdfs) for name in pdf_names]
        confirmations = [c for c in confirmations if c]

        confidence = _best_confidence(pdf_matches + report_candidates)

        ws.append([
            row["client"],
            row["mxd_path"],
            row["mxd_modified"],
            "; ".join(pdf_names) or None,
            "; ".join(m["date"] for m in pdf_matches) or None,
            "; ".join(os.path.basename(c["path"]) for c in report_candidates) or None,
            "; ".join(c["date"] for c in report_candidates) or None,
            "; ".join(confirmations) or None,
            confidence,
        ])

    return wb


def main():
    filesystem_data = json.loads(FILESYSTEM_PATH.read_text())
    gmail_data = json.loads(GMAIL_PATH.read_text())
    wb = build_workbook(filesystem_data, gmail_data)
    wb.save(OUTPUT_PATH)
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_build_audit_workbook.py -v`
Expected: PASS (all 5 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/report_audit/build_audit_workbook.py tests/test_build_audit_workbook.py
git commit -m "Add merge logic and workbook builder for report-PDF-email audit"
```

- [ ] **Step 6: Run the full pipeline against real data**

Run: `python scripts/report_audit/build_audit_workbook.py`
Expected: prints `Wrote C:\GIS\CLIENT\RROG_DOXA_Report_PDF_Email_Audit.xlsx`.

- [ ] **Step 7: Verify real output**

Run: `python -c "from openpyxl import load_workbook; wb=load_workbook(r'C:\GIS\CLIENT\RROG_DOXA_Report_PDF_Email_Audit.xlsx'); ws=wb.active; print(ws.max_row)"`
Expected: 146 (145 mxd rows + 1 header), or close to it.

- [ ] **Step 8: Hand off to the user for manual review**

Per spec §5: user opens the workbook, spot-checks the `LA-CAD_2216N13W` row, and specifically reviews `Confidence: Token` rows for false positives.
