# RROG + DOXA Report → MXD → PDF → Email Audit — Design

**Date:** 2026-09-23
**Follows:** `2026-09-23-rrog-doxa-mxd-datasource-inventory-design.md` (same two clients, same "recently active" rationale). This is a separate, parallel investigation — it doesn't depend on that inventory's output and can run independently.

## 1. Purpose

For RROG and DOXA, trace the actual workflow behind each map: **client sends a report (spreadsheet/data) → an `.mxd`/shapefile gets updated → a PDF gets produced (`C:\PDF`) → the PDF goes back to the client (Gmail reply/send)**. Right now that trail only lives in scattered filenames and email history. This builds one audit spreadsheet that reconstructs it, so gaps (a map updated with no report behind it, a report received with no PDF ever sent back, an old PDF nobody re-sent) become visible.

**Discovery only** — no files move, no `.mxd`/shapefile is touched, no email is sent. This directly feeds the eventual "organize my data" reorg, but that's a later, separate pass.

## 2. Scope

- Clients: RROG and DOXA only (same as the mxd inventory work), all `.mxd` files under `C:\GIS\CLIENT\RROG` and `C:\GIS\CLIENT\DOXA` modified in the **last 12 months**.
- Sources searched: `C:\Users\mapma\Downloads` (2,748 files, back to 2023-08-13), `C:\PDF` (2,914 files, back to 2017-06-20), Gmail (RROG and DOXA labels).
- No file moves, no reorganization — that's a later, separate effort per the user's explicit choice.

## 3. Matching approach

Filenames are the primary signal — spot-checked and confirmed reliable (e.g. `C:\PDF\LA-CAD_2216N13W-MOR.pdf` and `20260608_TX-SHELBY.pdf` both clearly derive from their `.mxd` basenames `LA-CAD_2216N13W.mxd` / `TX-SHELBY.mxd`).

For each in-scope `.mxd`:

1. **PDF match** (`C:\PDF`): case-insensitive substring match of the mxd's basename (stripped of extension) against PDF filenames. Record every match's filename and file-created date.
2. **Report candidate match** (Downloads): tokenize both the mxd basename and each Downloads filename into alphanumeric runs (split on `_`, `-`, space — e.g. `LA-CAD_2216N13W` → `{LA, CAD, 2216N13W}`, and further strip letters from digit-letter runs so `2216N13W` and `22-16N-13W` both reduce to a comparable digit sequence `22 16 13`). A Downloads file is a report candidate if it shares at least one non-trivial token (length ≥ 3, excluding generic words like state/parish abbreviations that appear in nearly every filename) **and** its modified date is on or before the mxd's last-modified date. Record filename, date, and which token(s) matched.
3. **Gmail confirmation**: for each matched PDF from step 1, search the client's Gmail label (`search_threads`) within a ±14 day window of the PDF's created date for a sent message whose attachment filename matches the PDF, or whose subject shares the same matched token(s). Record the thread subject/date if found.
4. **Confidence**: `Exact` if the PDF/report filename match is the full mxd basename verbatim; `Token` if it's a partial/tokenized match only. This is surfaced so weak matches are easy to spot-check rather than trusted blindly — tokenized filename matching over thousands of files will produce some false positives.

## 4. Output

One workbook, `C:\GIS\CLIENT\RROG_DOXA_Report_PDF_Email_Audit.xlsx`, one row per in-scope `.mxd`:

| Client | MXD | MXD Last Modified | Matched PDF(s) | PDF Date(s) | Report Candidate(s) (Downloads) | Report Date(s) | Gmail Confirmation (subject/date or blank) | Confidence |
|---|---|---|---|---|---|---|---|---|

Multiple matches in a cell are semicolon-joined (same convention as the mxd inventory's `Shared Sources` tab). An mxd with no PDF match and no report candidate is still a row — that's a gap worth seeing, not something to drop silently.

## 5. Testing / verification

The tokenization/matching logic (step 2's token-extraction and comparison) is pure and unit-testable against fixture filenames — no filesystem or Gmail dependency. The PDF/Downloads filesystem walk and the Gmail search are verified manually: spot-check the `LA-CAD_2216N13W` and `TX-SHELBY` cases already confirmed during design against the generated rows, and have the user review the `Confidence: Token` rows specifically for false positives, since those are the ones most likely to be wrong.
