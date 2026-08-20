# Caspiana Little Creek Lease Abstract & Dashboard — Design

## Context

Client: Sabine (via Diversified Energy). Project folder: `C:\GIS\CLIENT\DOXA\SABINE\CASPIANA\Caspiana Little Creek T14-R16 & T13-R16` (outside this git repo).

Task: go through the leases covering 10 sections — Sec 17, 18 (T14N-R16W, Caddo Parish); Sec 19, 20, 29, 30, 31, 32 (T14N-R16W, DeSoto Parish); Sec 5, 6 (T13N-R16W, DeSoto Parish) — and produce:

1. An organized spreadsheet capturing, per lease/tract: location, gross acres, net acres, and working interest.
2. A GIS layer placing each lease tract spatially within the 10 sections.
3. An Excel-native dashboard (pivots/slicers) inside the workbook.
4. A separate web dashboard (filterable table + map + summary charts).

## Source documents (as found)

Each section's `Diversified File Downlaod/Sec N .../Lease Agreement` folder contains a mix of document types, not raw leases only:

- **LPR (Lease Transmittal)** — landman software output (v5.6.17). Per-lease header (Lessor, Lessee, dates, royalty, total gross/net acres) plus an itemized **Legal Description table**: Location (S-T-R), Tract#, Gross, Interest, Net — the most authoritative source when present. **Only present for Sec 5 and Sec 6** in this download; the other 8 sections have no LPR subfolder.
- **OGML (Land Record Form)** — a standardized landman abstract card: Lessor, Lessee, Lease/Effective/Expiration dates, Term, Royalty, Lessor's Mineral Interest, Lease Gross Acres, Lease Net Acres, Gross/Net Acres Assigned, legal description, Pooling/Pugh/Free Gas flags, Working Interest Owners with WI fractions. Present for most leases across all 10 sections. A single PDF file can contain more than one card (e.g. one card per unit assignment).
- **Raw support documents** (AMENDMENT, MISC, Payment, Title, Plat subfolders) — actual executed legal instruments (leases, amendments, ratifications) and supporting title/plat material, multi-page legal prose with no acreage/WI field spelled out directly.

All PDFs sampled are **scanned images with no text layer** (confirmed via `pdftotext` — near-zero character extraction).

Existing chain-of-title (COT) tract spreadsheets in `IPL Tract Folders/` give independent per-tract acreage (GMA/NMA) and current owner splits, useful as a cross-check but are title work product, not lease abstracts.

## Source priority (per row)

1. **LPR Legal Description line** if the lease has one (Sec 5 & 6 only).
2. **OGML Land Record Form card** otherwise.
3. **Raw AMENDMENT/MISC text**, minimally, only for leases with neither an LPR nor an OGML card — flagged `Needs Review` if gross/net/WI can't be confidently determined from the raw text alone.

Every row carries a `Source` column (`LPR` / `OGML` / `Raw`) and a `Confidence` column (`High` / `Medium` / `Low` / `Needs Review`) so nothing is silently guessed.

## Row granularity

One row = one LPR tract-line-item or one OGML Land Record Form card — the atomic unit that carries its own gross acres / net acres / working interest / unit assignment. A single source PDF may produce multiple rows. A `Source File` column always traces a row back to its PDF.

## Pipeline

1. **Inventory** — walk all 10 section folders, classify every PDF (LPR / OGML / raw support) into a file manifest.
2. **OCR extraction** — rasterize each LPR/OGML page (`pdftoppm`, already on PATH) and run Tesseract OCR (already installed), then regex-parse against the two known templates. Both templates are clean, consistent, machine-typewritten forms, which makes bulk OCR viable.
3. **Claude vision QA pass** — re-render and vision-check: any numeric-critical field (gross ac, net ac, interest fraction) with low OCR confidence; any handwritten correction/marginalia (observed circled interlineations on sampled cards); any lease with no LPR/OGML card (fall back to raw-text derivation).
4. **Master dataset assembly** — columns: Section, Township-Range, Parish, Lessor, Lessee, Legal Description, Gross Acres, Net Acres, Lessor's Mineral Interest, Working Interest Owner(s) + WI%, Royalty, Lease Date, Effective Date, Expiration Date, Unit Name/No (if applicable), Source, Source File, Confidence.
5. **GIS layer** — pull PLSS section polygons for the 10 sections from BLM's public Cadastral (CadNSDI) ArcGIS REST service (free, no auth — same pattern already used for the RRC operator inventory technique). Subdivide each section polygon per its aliquot legal description (e.g. "N/2 N/2 NE/4") into tract polygons. Join to the master dataset by Section + Description key. Output as GeoJSON/shapefile plus a rendered overview map image.
6. **Deliverables**:
   - Excel workbook: master data sheet, per-section filter/sheets, and a Dashboard sheet (PivotTables + slicers by Section / Lessee / Working Interest Owner, KPI summary: total gross ac, total net ac, net ac by WI owner).
   - Web dashboard: standalone HTML Artifact — filterable table, map view, summary charts, reading from the same master dataset.

## QA / validation

- Confidence flag per row; ambiguous values become `Needs Review`, never a silent best-guess.
- After the full pass: spot-check ~10-15% of rows against direct Claude-vision reads of the source PDF to validate real OCR pipeline accuracy before treating the data as final.
- Per-section reconciliation: sum of net acres across a section's rows checked against that section's known total acreage (from COT tract files / Plats); mismatches flagged, not hidden.

## Output location

All deliverables (Excel workbook, GIS layer files, web dashboard HTML) are saved inside the Caspiana client folder itself, in a new `Deliverables` subfolder under `Caspiana Little Creek T14-R16 & T13-R16\`, alongside the existing `Plats`, `GIS`, and `IPL Tract Folders`. This keeps the client engagement self-contained and separate from the `permit_intel` pipeline repo. (This design spec and the implementation plan still live in this repo, since that's where the working session and its tooling live.)

## Known open risk

Only 2 of 10 sections have an LPR on hand. Per user direction, the other 8 sections proceed on OGML cards as the source of record, clearly flagged as such — not blocked on sourcing the missing LPRs first.
