> **Superseded 2026-09-23:** never executed — the user redirected to an `.mxd`-last-modified starting point before Task 1 began. See `2026-09-23-rrog-doxa-mxd-datasource-inventory.md`.

# Client Activity Gmail Checklist Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce `C:\GIS\Client_Gmail_Checklist.xlsx` — a checklist of each client's report activity over the last 12 months, used to prioritize the per-client shapefile-attribute-sync work described in the design spec.

**Architecture:** Two-stage pipeline. Stage 1 (data gathering) uses the Gmail MCP tools directly (only available inside a Claude session, not a standalone script) to pull messages per client label and writes a plain JSON snapshot to `data/client_checklist/gmail_survey.json`. Stage 2 is a deterministic, testable Python script (`scripts/build_client_gmail_checklist.py`) that reads that JSON and writes the two-tab xlsx workbook. Splitting it this way means the xlsx-building logic can be unit tested with a small fixture, independent of live Gmail data.

**Tech Stack:** Python 3, `openpyxl` (already used elsewhere in this repo for report building — confirm via `pip show openpyxl`; install if missing), `pytest`.

## Global Constraints

- Survey window: last 365 days from run date (per spec §2).
- Excludes DLS from the "needs work" list but includes it as a single reference row marked "known-good, no action needed" (per spec §3).
- No shapefile or `.mxd`/`.aprx` parsing in this workbook (per spec §1, out of scope).
- Output path: `C:\GIS\Client_Gmail_Checklist.xlsx` (same root as `Mapmatics_Client_Master_UPDATED.xlsx`, per spec §3).
- Client → Gmail label mapping (confirmed against the live label list on 2026-09-23):

| Client folder (`C:\GIS\CLIENT\`) | Gmail label |
|---|---|
| BLACKBEARD | Blackbeard |
| CADDO_LEVEE_DISTRICT | Caddo Levee |
| CARR | Carr |
| DOXA | DOXA |
| EQV | EQV |
| HESTERLY | Hesterly |
| ROCKCHALK | Rock Chalk |
| RROG | RROG |
| SVR | SVR |
| TANOS | Tanos |
| VEF | Faulconer |
| DLS | DLS (reference row only, excluded from "needs work") |

KSA, MADOLE, RFE have no matching Gmail label found (and MADOLE/RFE have little or no `.mxd`/`.aprx` content either) — they're included on the summary tab with `Last Report Date`/`Report Count` blank and a Notes flag `"no Gmail label found — confirm with user"`, rather than silently dropped.

---

## File Structure

- Create: `data/client_checklist/gmail_survey.json` — raw survey snapshot (list of email records per client), produced by Stage 1, consumed by Stage 2. Not committed to git (data directory already gitignored for this kind of pull — verify `.gitignore` covers `data/client_checklist/`; add the entry if not).
- Create: `scripts/build_client_gmail_checklist.py` — Stage 2. Pure function `build_workbook(survey: dict) -> openpyxl.Workbook` plus a `main()` that reads the JSON path from argv (default `data/client_checklist/gmail_survey.json`), builds the workbook, and saves it to `C:\GIS\Client_Gmail_Checklist.xlsx`.
- Create: `tests/test_build_client_gmail_checklist.py` — unit tests for `build_workbook()` against a small fixture dict, no live Gmail/file-system dependency beyond a tmp path.

## Task 1: Gather the Gmail survey data and write the JSON snapshot

**Files:**
- Create: `data/client_checklist/gmail_survey.json`

**Interfaces:**
- Produces: a JSON file shaped like:
```json
{
  "generated_date": "2026-09-23",
  "window_days": 365,
  "clients": [
    {
      "client": "RROG",
      "label": "RROG",
      "label_found": true,
      "emails": [
        {"date": "2026-09-10", "sender": "jolie@...", "subject": "...", "attachments": ["Apex_Abstract Status Report_20260910.xlsx"]}
      ]
    },
    {
      "client": "KSA",
      "label": null,
      "label_found": false,
      "emails": []
    }
  ]
}
```
This is consumed by Task 2/3's `build_workbook()`.

- [ ] **Step 1: Confirm today's survey window**

Run date is 2026-09-23; cutoff is 2025-09-23. Use these two dates in every search.

- [ ] **Step 2: For each client/label pair in the Global Constraints table, search Gmail**

Use the `search_threads` Gmail MCP tool once per label, scoped to that label and the date window, for report-like content (spreadsheet/PDF attachments or subjects containing "status"/"report"/"update"). Record every match's date, sender, subject, and attachment filenames.

- [ ] **Step 3: For KSA, MADOLE, RFE — record `label_found: false`, empty `emails` list**

No search needed; these have no confirmed Gmail label.

- [ ] **Step 4: Add the DLS reference entry**

`{"client": "DLS", "label": "DLS", "label_found": true, "reference_only": true, "emails": []}` — DLS emails aren't surveyed (already known-good), so `emails` stays empty and the workbook builder treats `reference_only: true` as the signal to render it as the fixed reference row.

- [ ] **Step 5: Write the assembled dict to `data/client_checklist/gmail_survey.json`**

Pretty-printed (`indent=2`) so it's human-diffable if re-run later.

- [ ] **Step 6: Sanity-check the JSON**

Run: `python -c "import json; d=json.load(open('data/client_checklist/gmail_survey.json')); print(len(d['clients']), [c['client'] for c in d['clients']])"`
Expected: 12 clients listed (BLACKBEARD, CADDO_LEVEE_DISTRICT, CARR, DOXA, EQV, HESTERLY, ROCKCHALK, RROG, SVR, TANOS, VEF, KSA, MADOLE, RFE, DLS — 15 total, confirm the exact count matches the Global Constraints table plus the three no-label clients plus DLS).

- [ ] **Step 7: Ensure the data directory is gitignored, then commit only the script/test scaffolding (not the JSON)**

```bash
grep -q "^data/client_checklist/" .gitignore || echo "data/client_checklist/" >> .gitignore
git add .gitignore
git commit -m "Ignore client Gmail survey data directory"
```

## Task 2: Write `build_workbook()` and its unit test (TDD)

**Files:**
- Create: `scripts/build_client_gmail_checklist.py`
- Test: `tests/test_build_client_gmail_checklist.py`

**Interfaces:**
- Consumes: the JSON structure produced in Task 1 (as a Python dict, already parsed — `build_workbook()` takes the dict, not a file path, so it's testable without touching disk).
- Produces: `build_workbook(survey: dict) -> openpyxl.workbook.Workbook`, with two sheets: `"Summary"` and `"Detail"`. Later tasks (Task 3's `main()`) call this directly.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_build_client_gmail_checklist.py
import pytest
from scripts.build_client_gmail_checklist import build_workbook

FIXTURE = {
    "generated_date": "2026-09-23",
    "window_days": 365,
    "clients": [
        {
            "client": "RROG",
            "label": "RROG",
            "label_found": True,
            "emails": [
                {"date": "2026-09-10", "sender": "jolie@example.com", "subject": "Apex Abstract Status",
                 "attachments": ["Apex_Abstract Status Report_20260910.xlsx"]},
                {"date": "2026-07-01", "sender": "jolie@example.com", "subject": "Apex Abstract Status",
                 "attachments": ["Apex_Abstract Status Report_20260701.xlsx"]},
            ],
        },
        {"client": "KSA", "label": None, "label_found": False, "emails": []},
        {"client": "DLS", "label": "DLS", "label_found": True, "reference_only": True, "emails": []},
    ],
}


def test_summary_sheet_has_one_row_per_client_plus_header():
    wb = build_workbook(FIXTURE)
    summary = wb["Summary"]
    # header + 3 clients (RROG, KSA, DLS)
    assert summary.max_row == 4


def test_summary_row_reports_latest_date_and_count_for_active_client():
    wb = build_workbook(FIXTURE)
    summary = wb["Summary"]
    rows = {row[0].value: row for row in summary.iter_rows(min_row=2)}
    rrog_row = rows["RROG"]
    assert rrog_row[2].value == "2026-09-10"  # Last Report Date = most recent
    assert rrog_row[3].value == 2  # Report Count (12mo)


def test_summary_row_flags_missing_label():
    wb = build_workbook(FIXTURE)
    summary = wb["Summary"]
    rows = {row[0].value: row for row in summary.iter_rows(min_row=2)}
    ksa_row = rows["KSA"]
    assert ksa_row[2].value is None
    assert "no Gmail label" in ksa_row[5].value


def test_summary_row_marks_dls_as_reference_only():
    wb = build_workbook(FIXTURE)
    summary = wb["Summary"]
    rows = {row[0].value: row for row in summary.iter_rows(min_row=2)}
    dls_row = rows["DLS"]
    assert "known-good" in dls_row[5].value


def test_detail_sheet_has_one_row_per_email():
    wb = build_workbook(FIXTURE)
    detail = wb["Detail"]
    # header + 2 RROG emails (KSA/DLS contribute none)
    assert detail.max_row == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_build_client_gmail_checklist.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.build_client_gmail_checklist'`

- [ ] **Step 3: Write the minimal implementation**

```python
# scripts/build_client_gmail_checklist.py
import json
import sys
from pathlib import Path

from openpyxl import Workbook

SUMMARY_HEADERS = ["Client", "Gmail Label", "Last Report Date", "Report Count (12mo)", "Latest Attachment(s)", "Notes"]
DETAIL_HEADERS = ["Client", "Date", "Sender", "Subject", "Attachments"]

DEFAULT_SURVEY_PATH = Path("data/client_checklist/gmail_survey.json")
DEFAULT_OUTPUT_PATH = Path(r"C:\GIS\Client_Gmail_Checklist.xlsx")


def build_workbook(survey: dict) -> Workbook:
    wb = Workbook()
    summary = wb.active
    summary.title = "Summary"
    summary.append(SUMMARY_HEADERS)

    detail = wb.create_sheet("Detail")
    detail.append(DETAIL_HEADERS)

    for client in survey["clients"]:
        name = client["client"]
        label = client.get("label")
        emails = client.get("emails", [])
        reference_only = client.get("reference_only", False)
        label_found = client.get("label_found", True)

        if reference_only:
            summary.append([name, label, None, None, None, "known-good, no action needed"])
            continue

        if not label_found:
            summary.append([name, None, None, None, None, "no Gmail label found — confirm with user"])
            continue

        sorted_emails = sorted(emails, key=lambda e: e["date"], reverse=True)
        last_date = sorted_emails[0]["date"] if sorted_emails else None
        count = len(sorted_emails)
        latest_attachments = ", ".join(sorted_emails[0]["attachments"]) if sorted_emails else None
        summary.append([name, label, last_date, count, latest_attachments, None])

        for email in sorted_emails:
            detail.append([name, email["date"], email["sender"], email["subject"], ", ".join(email["attachments"])])

    return wb


def main(argv=None):
    argv = argv or sys.argv[1:]
    survey_path = Path(argv[0]) if argv else DEFAULT_SURVEY_PATH
    survey = json.loads(survey_path.read_text())
    wb = build_workbook(survey)
    wb.save(DEFAULT_OUTPUT_PATH)
    print(f"Wrote {DEFAULT_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_build_client_gmail_checklist.py -v`
Expected: PASS (all 5 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/build_client_gmail_checklist.py tests/test_build_client_gmail_checklist.py
git commit -m "Add Gmail survey to xlsx checklist builder"
```

## Task 3: Run the pipeline end-to-end and verify the real output

**Files:**
- Modify: none (uses artifacts from Task 1 and Task 2)

**Interfaces:**
- Consumes: `build_workbook()` from Task 2, `data/client_checklist/gmail_survey.json` from Task 1.
- Produces: `C:\GIS\Client_Gmail_Checklist.xlsx` (the real deliverable).

- [ ] **Step 1: Run the builder against the real survey data**

Run: `python scripts/build_client_gmail_checklist.py`
Expected: prints `Wrote C:\GIS\Client_Gmail_Checklist.xlsx`, exit code 0.

- [ ] **Step 2: Confirm the workbook opens and row counts look right**

Run: `python -c "from openpyxl import load_workbook; wb=load_workbook(r'C:\GIS\Client_Gmail_Checklist.xlsx'); print(wb.sheetnames); print(wb['Summary'].max_row, wb['Detail'].max_row)"`
Expected: `['Summary', 'Detail']`, Summary row count = 15 clients + 1 header = 16, Detail row count = header + total emails found (varies with live data).

- [ ] **Step 3: Hand off to the user for manual review**

Per spec §5: user opens `C:\GIS\Client_Gmail_Checklist.xlsx`, confirms client coverage looks complete (no missing labels beyond the three already flagged), and spot-checks 1-2 "Last Report Date" values against Gmail directly. No automated step here — this is the explicit manual verification gate from the spec.

- [ ] **Step 4: Commit any fixups made in response to user review**

If the user flags a wrong label mapping or missing client during review, fix Task 1's label table and/or re-run, then:
```bash
git add docs/superpowers/plans/2026-09-23-client-activity-gmail-checklist.md
git commit -m "Note verified client Gmail label mapping"
```
(Only if the Global Constraints table needed a correction — otherwise no commit needed for this step.)
