# Caspiana Little Creek Lease Abstract & Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn ~200 scanned lease documents across 10 sections of the Caspiana Little Creek prospect into one reconciled dataset (location, gross ac, net ac, working interest per lease/tract), a GIS tract layer, an Excel workbook with a native dashboard, and a standalone web dashboard.

**Architecture:** An OCR-first hybrid pipeline: classify every source PDF (LPR / OGML / raw support), OCR the two structured template types with Tesseract, regex-parse them into a common row schema, score confidence per row, and route anything ambiguous to a Claude-vision QA pass instead of guessing. The reconciled master dataset then feeds three independent, parallel-buildable outputs: a GIS tract layer, an Excel workbook, and a web dashboard.

**Tech Stack:** Python 3.11 (`C:\Users\mapma\AppData\Local\Programs\Python\Python311\python.exe` — the only interpreter on this machine with geopandas/shapely/fiona alongside pytesseract/pdf2image/openpyxl/pandas), Tesseract OCR + poppler (already installed, same paths `w1_intel.py` uses), pandas, openpyxl, shapely, requests (BLM PLSS REST), pytest.

## Global Constraints

- Python interpreter: `C:\Users\mapma\AppData\Local\Programs\Python\Python311\python.exe` (Python 3.14 on this machine lacks geopandas/shapely/fiona — do not use it for this project).
- Tesseract: `C:\Program Files\Tesseract-OCR\tesseract.exe` — set via `pytesseract.pytesseract.tesseract_cmd`, same as `w1_intel.py`.
- Poppler: `C:\Users\mapma\AppData\Local\Microsoft\WinGet\Packages\oschwartz10612.Poppler_Microsoft.Winget.Source_8wekyb3d8bbwe\poppler-25.07.0\Library\bin` — passed as `poppler_path=` to `pdf2image.convert_from_path`, same as `w1_intel.py`.
- `CASPIANA_ROOT = Path(r"C:\GIS\CLIENT\DOXA\SABINE\CASPIANA\Caspiana Little Creek T14-R16 & T13-R16")` — all source PDFs live under `CASPIANA_ROOT / "Diversified File Downlaod"`.
- `DELIVERABLES_DIR = CASPIANA_ROOT / "Deliverables"` — every output file (manifest, master dataset, OCR cache, GIS layer, Excel workbook, dashboard HTML) is written here, never into the git repo. This directory does not get `git add`ed.
- Source priority per row: LPR Legal Description line > OGML Land Record Form card > raw AMENDMENT/MISC text (flagged `Needs Review` if acreage/WI can't be confidently read).
- One row = one LPR tract-line-item or one OGML Land Record Form card (not one row per source PDF — a PDF can contain multiple cards).
- Every row carries `Source` (`LPR`/`OGML`/`Raw`), `Source File`, and `Confidence` (`High`/`Medium`/`Low`/`Needs Review`) columns.
- A section can have *both* an LPR and OGML documents (confirmed for Sec 5 & 6). When it does, OGML rows for that section are still parsed and kept (for their working-interest-owner detail, which LPR doesn't carry) but flagged `superseded_by_lpr=True` and excluded from acreage KPI totals and the GIS layer, so LPR's numbers are never double-counted alongside OGML's for the same tracts.
- No real client data (names, acreages, scanned images, OCR text of real leases) is ever committed to git — test fixtures use fabricated placeholder data that mimics the templates' field vocabulary, not real lease content.
- PLSS section polygons come from BLM's public Cadastral (CadNSDI) ArcGIS REST service: `https://gis.blm.gov/arcgis/rest/services/Cadastral/BLM_Natl_PLSS_CadNSDI/MapServer` (no auth required).

---

## Task 1: Section-folder inventory & manifest

**Files:**
- Create: `core/caspiana/__init__.py`
- Create: `core/caspiana/inventory.py`
- Test: `tests/test_caspiana_inventory.py`

**Interfaces:**
- Produces: `classify_file(path: Path) -> str` returning one of `"LPR"`, `"OGML"`, `"RAW"`. `build_manifest(diversified_root: Path) -> list[dict]` where each dict has keys `section`, `township_range`, `parish`, `doc_type` (`LPR`/`OGML`/`RAW`), `path` (str). `SECTION_DIR_RE` — compiled regex other tasks reuse to parse `"Sec 29 T14N R16W - DeSoto Parish, LA"`-style folder names into `(section, township_range, parish)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_caspiana_inventory.py
from pathlib import Path

from core.caspiana.inventory import build_manifest, classify_file


def _make_tree(tmp_path: Path) -> Path:
    root = tmp_path / "Diversified File Downlaod"
    sec17 = root / "Sec 17 T14N R16W - Caddo Parish, LA" / "Lease Agreement"
    (sec17 / "OGML").mkdir(parents=True)
    (sec17 / "AMENDMENT").mkdir(parents=True)
    (sec17 / "OGML" / "card_one.pdf").write_text("x")
    (sec17 / "AMENDMENT" / "amend_one.pdf").write_text("x")

    sec5 = root / "Sec 5 T13N R16W - DeSoto Parish, LA" / "Lease Agreement"
    (sec5 / "LPR").mkdir(parents=True)
    (sec5 / "LPR" / "transmittal.pdf").write_text("x")
    return root


def test_classify_file_by_parent_folder_name(tmp_path):
    p = tmp_path / "Lease Agreement" / "OGML" / "card.pdf"
    p.parent.mkdir(parents=True)
    p.write_text("x")
    assert classify_file(p) == "OGML"

    p2 = tmp_path / "Lease Agreement" / "LPR" / "t.pdf"
    p2.parent.mkdir(parents=True)
    p2.write_text("x")
    assert classify_file(p2) == "LPR"

    p3 = tmp_path / "Lease Agreement" / "MISC" / "m.pdf"
    p3.parent.mkdir(parents=True)
    p3.write_text("x")
    assert classify_file(p3) == "RAW"


def test_build_manifest_parses_section_township_parish(tmp_path):
    root = _make_tree(tmp_path)
    rows = build_manifest(root)

    assert len(rows) == 3
    sec17_rows = [r for r in rows if r["section"] == "17"]
    assert len(sec17_rows) == 2
    assert {r["doc_type"] for r in sec17_rows} == {"OGML", "RAW"}
    assert sec17_rows[0]["township_range"] == "T14N R16W"
    assert sec17_rows[0]["parish"] == "Caddo"

    sec5_rows = [r for r in rows if r["section"] == "5"]
    assert sec5_rows[0]["doc_type"] == "LPR"
    assert sec5_rows[0]["township_range"] == "T13N R16W"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:\Users\mapma\AppData\Local\Programs\Python\Python311\python.exe -m pytest tests/test_caspiana_inventory.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.caspiana'`

- [ ] **Step 3: Write the implementation**

```python
# core/caspiana/__init__.py
```

```python
# core/caspiana/inventory.py
"""Walks the Caspiana 'Diversified File Downlaod' tree and classifies every
lease-related PDF into LPR / OGML / RAW so every downstream row can trace
back to a source file and a document-type source-priority tier."""
import re
from pathlib import Path

SECTION_DIR_RE = re.compile(
    r"^Sec\s+(?P<section>\d+)\s+(?P<tr>T\d+N\s+R\d+W)\s*-\s*(?P<parish>[A-Za-z]+)\s+Parish",
    re.IGNORECASE,
)

# Folder name (uppercased) -> doc_type tier. Anything not listed here
# (MISC, AMENDMENT, Payment, Title, Plat, FEDERAL, ...) is RAW.
_DOC_TYPE_BY_FOLDER = {
    "LPR": "LPR",
    "OGML": "OGML",
}


def classify_file(path: Path) -> str:
    """Classify a single PDF by its immediate parent folder name."""
    parent_name = path.parent.name.upper()
    return _DOC_TYPE_BY_FOLDER.get(parent_name, "RAW")


def build_manifest(diversified_root: Path) -> list[dict]:
    """Return one dict per PDF found under diversified_root, with section /
    township-range / parish parsed from the section folder name."""
    rows = []
    for section_dir in sorted(diversified_root.iterdir()):
        if not section_dir.is_dir():
            continue
        m = SECTION_DIR_RE.match(section_dir.name)
        if not m:
            continue
        section = m.group("section")
        township_range = m.group("tr").upper()
        parish = m.group("parish").title()

        for pdf_path in section_dir.rglob("*"):
            if pdf_path.is_file() and pdf_path.suffix.lower() == ".pdf":
                rows.append({
                    "section": section,
                    "township_range": township_range,
                    "parish": parish,
                    "doc_type": classify_file(pdf_path),
                    "path": str(pdf_path),
                })
    return rows
```

- [ ] **Step 4: Run test to verify it passes**

Run: `C:\Users\mapma\AppData\Local\Programs\Python\Python311\python.exe -m pytest tests/test_caspiana_inventory.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add core/caspiana/__init__.py core/caspiana/inventory.py tests/test_caspiana_inventory.py
git commit -m "feat(caspiana): add lease-folder inventory/manifest classifier"
```

---

## Task 2: OCR text extraction with on-disk cache

**Files:**
- Create: `core/caspiana/ocr_utils.py`
- Test: `tests/test_caspiana_ocr_utils.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `ocr_pdf_pages(pdf_path: Path, cache_dir: Path, dpi: int = 300) -> list[str]` — one OCR'd text string per page, cached to `cache_dir / f"{pdf_path.stem}__{pdf_path_hash}" / "page_N.txt"` so re-running the pipeline doesn't re-OCR ~200 multi-page PDFs every time.

- [ ] **Step 1: Write the failing test**

Uses a synthetically generated image (via PIL) so the test needs no real client scans and stays fast/deterministic.

```python
# tests/test_caspiana_ocr_utils.py
from pathlib import Path

from PIL import Image, ImageDraw

from core.caspiana.ocr_utils import _cache_key_for, ocr_pdf_pages


def _make_single_page_pdf(tmp_path: Path) -> Path:
    img = Image.new("RGB", (600, 200), "white")
    draw = ImageDraw.Draw(img)
    draw.text((20, 20), "LESSOR: JANE Q TESTOWNER", fill="black")
    draw.text((20, 60), "LEASE GROSS ACRES: 40.0000", fill="black")
    pdf_path = tmp_path / "sample.pdf"
    img.save(pdf_path, "PDF")
    return pdf_path


def test_cache_key_is_stable_for_same_file(tmp_path):
    pdf_path = _make_single_page_pdf(tmp_path)
    key1 = _cache_key_for(pdf_path)
    key2 = _cache_key_for(pdf_path)
    assert key1 == key2
    assert len(key1) == 16  # short hex digest, not the whole file


def test_ocr_pdf_pages_extracts_text_and_caches(tmp_path):
    pdf_path = _make_single_page_pdf(tmp_path)
    cache_dir = tmp_path / "ocr_cache"

    pages = ocr_pdf_pages(pdf_path, cache_dir)
    assert len(pages) == 1
    assert "LESSOR" in pages[0].upper()
    assert "40.0000" in pages[0]

    cache_files = list(cache_dir.rglob("page_*.txt"))
    assert len(cache_files) == 1

    # Second call must hit the cache, not re-OCR (cache file mtime unchanged).
    before = cache_files[0].stat().st_mtime
    ocr_pdf_pages(pdf_path, cache_dir)
    after = cache_files[0].stat().st_mtime
    assert before == after
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:\Users\mapma\AppData\Local\Programs\Python\Python311\python.exe -m pytest tests/test_caspiana_ocr_utils.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.caspiana.ocr_utils'`

- [ ] **Step 3: Write the implementation**

```python
# core/caspiana/ocr_utils.py
"""Page-level OCR for scanned lease PDFs, with an on-disk text cache so the
~200-file Caspiana batch isn't re-rasterized/re-OCR'd on every pipeline run.
Reuses the exact Tesseract/poppler setup validated in w1_intel.py."""
import hashlib
from pathlib import Path

import pytesseract
from pdf2image import convert_from_path

TESSERACT_EXE = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
POPPLER_PATH = (
    r"C:\Users\mapma\AppData\Local\Microsoft\WinGet\Packages"
    r"\oschwartz10612.Poppler_Microsoft.Winget.Source_8wekyb3d8bbwe\poppler-25.07.0\Library\bin"
)
pytesseract.pytesseract.tesseract_cmd = TESSERACT_EXE


def _cache_key_for(pdf_path: Path) -> str:
    """Short stable hash of path + size + mtime -- cheap to compute, changes
    if the source file is replaced/rescanned."""
    stat = pdf_path.stat()
    raw = f"{pdf_path.resolve()}|{stat.st_size}|{stat.st_mtime_ns}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def ocr_pdf_pages(pdf_path: Path, cache_dir: Path, dpi: int = 300) -> list[str]:
    """OCR every page of pdf_path and return one text string per page.
    Results are cached under cache_dir/<stem>__<hash>/page_N.txt."""
    key_dir = cache_dir / f"{pdf_path.stem}__{_cache_key_for(pdf_path)}"
    key_dir.mkdir(parents=True, exist_ok=True)

    cached = sorted(key_dir.glob("page_*.txt"))
    if cached:
        return [p.read_text(encoding="utf-8") for p in cached]

    images = convert_from_path(str(pdf_path), dpi=dpi, poppler_path=POPPLER_PATH)
    texts = []
    for i, img in enumerate(images, start=1):
        text = pytesseract.image_to_string(img)
        (key_dir / f"page_{i}.txt").write_text(text, encoding="utf-8")
        texts.append(text)
    return texts
```

- [ ] **Step 4: Run test to verify it passes**

Run: `C:\Users\mapma\AppData\Local\Programs\Python\Python311\python.exe -m pytest tests/test_caspiana_ocr_utils.py -v`
Expected: PASS (2 tests). If OCR text doesn't contain the expected strings, bump `dpi` to 300+ and confirm `TESSERACT_EXE`/`POPPLER_PATH` still match what's installed (`winget list` for both packages).

- [ ] **Step 5: Commit**

```bash
git add core/caspiana/ocr_utils.py tests/test_caspiana_ocr_utils.py
git commit -m "feat(caspiana): add cached page-level OCR extraction"
```

---

## Task 3: OGML Land Record Form parser

**Files:**
- Create: `core/caspiana/ogml_template.py`
- Test: `tests/test_caspiana_ogml_template.py`

**Interfaces:**
- Consumes: nothing (takes raw OCR text strings as input, decoupled from Task 2 so it's testable with fabricated text).
- Produces: `split_ogml_cards(page_text: str) -> list[str]` (a page can hold >1 card), `parse_ogml_card(card_text: str) -> dict` returning keys: `field`, `parish`, `state`, `unit_name`, `unit_no`, `lessor`, `lessee`, `lease_date`, `effective_date`, `expiration_date`, `term`, `royalty`, `lessors_mineral_interest`, `lease_gross_acres`, `lease_net_acres`, `lease_gross_acres_assigned`, `lease_net_acres_assigned`, `description`, `working_interest_owners` (`list[tuple[str, float]]`), `parse_warnings` (`list[str]`).

- [ ] **Step 1: Write the failing test**

The fixture text below mirrors the real form's field vocabulary (labels only — real form boilerplate, not confidential) with fabricated names/numbers, modeled on the two cards observed on the Sec 17 OGML sample.

```python
# tests/test_caspiana_ogml_template.py
from core.caspiana.ogml_template import parse_ogml_card, split_ogml_cards

SAMPLE_PAGE = """
LAND RECORD FORM
PAGE 1 OF 1
FIELD: EXAMPLE-PROSPECT COUNTY: SAMPLE STATE: LOUISIANA
UNIT NAME: EXAMPLE UNIT NO. 1 UNIT NO.: 100
LESSOR: JANE Q TESTOWNER
LESSEE: EXAMPLE PRODUCTION COMPANY, INC.
LEASE DATE: 01-15-60 EFFECTIVE DATE: EXPIRATION DATE: 01-15-65
TERM: 5 YRS. ROYALTY: 1/8 LESSOR'S MINERAL INTEREST: 1/2
LEASE GROSS ACRES: 640.000 LEASE NET ACRES: 40.00000
LEASE GROSS ACRES ASSIGNED: 40.0000 LEASE NET ACRES ASSIGNED: 20.0000
DESCRIPTION (ASSIGNED): N/2 NE/4 OF SECTION 1, T1N-R1W.
POOLING (Y/N): Y PUGH (Y/N): Y RIGHT TO FREE GAS (Y/N): Y
WORKING INTEREST OWNERS WORKING INTEREST IN UNIT
EXAMPLE OPERATOR CO .60000000
OTHER WORKING INTEREST OWNER .40000000
SURFACE OWNER: UNKNOWN DRILL SITE TRACT (Y/N): N
""".strip()


def test_split_ogml_cards_returns_single_card_for_single_page():
    cards = split_ogml_cards(SAMPLE_PAGE)
    assert len(cards) == 1


def test_parse_ogml_card_extracts_core_fields():
    record = parse_ogml_card(SAMPLE_PAGE)

    assert record["field"] == "EXAMPLE-PROSPECT"
    assert record["parish"] == "SAMPLE"
    assert record["unit_no"] == "100"
    assert record["lessor"] == "JANE Q TESTOWNER"
    assert record["lessee"] == "EXAMPLE PRODUCTION COMPANY, INC."
    assert record["royalty"] == "1/8"
    assert record["lessors_mineral_interest"] == "1/2"
    assert record["lease_gross_acres"] == 640.0
    assert record["lease_net_acres"] == 40.0
    assert record["lease_gross_acres_assigned"] == 40.0
    assert record["lease_net_acres_assigned"] == 20.0
    assert "N/2 NE/4" in record["description"]


def test_parse_ogml_card_extracts_working_interest_owners():
    record = parse_ogml_card(SAMPLE_PAGE)
    owners = record["working_interest_owners"]

    assert owners == [
        ("EXAMPLE OPERATOR CO", 0.6),
        ("OTHER WORKING INTEREST OWNER", 0.4),
    ]


def test_parse_ogml_card_flags_missing_acreage_as_warning():
    broken = "FIELD: X COUNTY: Y STATE: LOUISIANA\nLESSOR: NOBODY\nLESSEE: NOBODY INC"
    record = parse_ogml_card(broken)
    assert record["lease_net_acres"] is None
    assert any("lease_net_acres" in w for w in record["parse_warnings"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:\Users\mapma\AppData\Local\Programs\Python\Python311\python.exe -m pytest tests/test_caspiana_ogml_template.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.caspiana.ogml_template'`

- [ ] **Step 3: Write the implementation**

```python
# core/caspiana/ogml_template.py
"""Parser for the standardized OGML 'Land Record Form' landman abstract
card. A single OCR'd page can contain more than one card (one per
unit/lease assignment), so cards are split before field extraction."""
import re

_ACREAGE_FIELDS = [
    ("lease_gross_acres", r"LEASE GROSS ACRES:?\s*([\d,]+\.\d+)"),
    ("lease_net_acres", r"LEASE NET ACRES:?\s*([\d,]+\.\d+)"),
    ("lease_gross_acres_assigned", r"LEASE GROSS ACRES ASSIGNED:?\s*([\d,]+\.\d+)"),
    ("lease_net_acres_assigned", r"LEASE NET ACRES ASSIGNED:?\s*([\d,]+\.\d+)"),
]

_TEXT_FIELDS = [
    ("field", r"FIELD:?\s*([A-Z0-9 \-]+?)\s+(?:COUNTY|PARISH):"),
    ("parish", r"(?:COUNTY|PARISH):?\s*([A-Z0-9 &]+?)\s+STATE:"),
    ("state", r"STATE:?\s*([A-Z]+)"),
    ("unit_no", r"UNIT NO\.?:?\s*(\d+)"),
    ("lessor", r"LESSOR:?\s*(.+?)\s*(?:LESSEE:|\n)"),
    ("lessee", r"LESSEE:?\s*(.+?)\s*(?:LEASE DATE:|\n)"),
    ("term", r"TERM:?\s*([\d.]+\s*YRS?\.?)"),
    ("royalty", r"ROYALTY:?\s*(\d+/\d+)"),
    ("lessors_mineral_interest", r"LESSOR'?S MINERAL INTEREST:?\s*(\d+/\d+|FULL)"),
    ("description", r"DESCRIPTION \(ASSIGNED\):?\s*(.+?)(?:POOLING|$)"),
]

_CARD_SPLIT_RE = re.compile(r"(?=LAND RECORD FORM)")
_WI_LINE_RE = re.compile(r"^(.*?)([.\s]?\d\.\d{5,8})\s*$")


def split_ogml_cards(page_text: str) -> list[str]:
    """Split a page's OCR text into one chunk per 'LAND RECORD FORM' card."""
    chunks = [c.strip() for c in _CARD_SPLIT_RE.split(page_text) if c.strip()]
    return chunks if chunks else [page_text.strip()]


def _extract_float(pattern: str, text: str) -> float | None:
    m = re.search(pattern, text, re.IGNORECASE)
    if not m:
        return None
    return float(m.group(1).replace(",", ""))


def _extract_text(pattern: str, text: str) -> str | None:
    m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    if not m:
        return None
    return re.sub(r"\s+", " ", m.group(1)).strip()


def _parse_working_interest_owners(text: str) -> list[tuple[str, float]]:
    """Everything between 'WORKING INTEREST OWNERS' and 'SURFACE OWNER' is a
    small table of owner-name / WI-fraction lines. OCR loses the column
    layout, so each line is matched as '<name> <fraction>'."""
    m = re.search(
        r"WORKING INTEREST OWNERS.*?WORKING INTEREST IN UNIT\s*(.+?)(?:SURFACE OWNER|$)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if not m:
        return []
    owners = []
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line:
            continue
        wm = _WI_LINE_RE.match(line)
        if wm:
            name = wm.group(1).strip(" .")
            frac = float(wm.group(2).strip(" ."))
            if name:
                owners.append((name, frac))
    return owners


def parse_ogml_card(card_text: str) -> dict:
    record: dict = {}
    warnings: list[str] = []

    for key, pattern in _TEXT_FIELDS:
        record[key] = _extract_text(pattern, card_text)
        if record[key] is None:
            warnings.append(f"could not find {key}")

    for key, pattern in _ACREAGE_FIELDS:
        record[key] = _extract_float(pattern, card_text)
        if record[key] is None:
            warnings.append(f"could not find {key}")

    record["working_interest_owners"] = _parse_working_interest_owners(card_text)
    record["parse_warnings"] = warnings
    return record
```

- [ ] **Step 4: Run test to verify it passes**

Run: `C:\Users\mapma\AppData\Local\Programs\Python\Python311\python.exe -m pytest tests/test_caspiana_ogml_template.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add core/caspiana/ogml_template.py tests/test_caspiana_ogml_template.py
git commit -m "feat(caspiana): add OGML Land Record Form regex parser"
```

---

## Task 4: LPR Lease Transmittal parser

**Files:**
- Create: `core/caspiana/lpr_template.py`
- Test: `tests/test_caspiana_lpr_template.py`

**Interfaces:**
- Consumes: nothing (raw OCR text in, like Task 3).
- Produces: `parse_lpr_transmittal(page_text: str) -> dict` with keys: `lessor`, `lessee`, `lease_date`, `effective_date`, `expiration_date`, `term`, `royalty`, `gross_ac_total`, `net_acres_total`, `tract_lines` (`list[dict]` each with `location`, `tract_no`, `gross`, `interest`, `net`, `description`), `parse_warnings` (`list[str]`, includes a warning if the tract-line column counts don't reconcile with each other or with the totals).

- [ ] **Step 1: Write the failing test**

Fixture modeled on the real Lease Transmittal's numbered-field layout and its Legal Description table, using fabricated lessor/lessee/acreage.

```python
# tests/test_caspiana_lpr_template.py
from core.caspiana.lpr_template import parse_lpr_transmittal

SAMPLE_TRANSMITTAL = """
Lease Transmittal Page 1 of 2
1. Lessor Example Timber Company
41. Lessee Sample Energy E&P Company, L.L.C.
5. Date 03/01/2010
26. Effective 03/01/2010
25. Expires 03/01/2015
24. Term 5 years
33. Royalty 1/4th
8. Gross Ac 106.0000
9. Net Acres 106.0000
Legal Description
68. Location 69.Tract# 72. Gross 73. Interest 74. Net 75. Description
001N-001W,01
001N-001W,02
80.0000
26.0000
1.0000000
1.0000000
80.0000
26.0000
106.0000 106.0000
N/2 NW
FRACTIONAL E/2 OF N/2 N/2
Landman Approval
""".strip()


def test_parse_lpr_transmittal_extracts_header_fields():
    record = parse_lpr_transmittal(SAMPLE_TRANSMITTAL)

    assert record["lessor"] == "Example Timber Company"
    assert record["lessee"] == "Sample Energy E&P Company, L.L.C."
    assert record["royalty"] == "1/4th"
    assert record["gross_ac_total"] == 106.0
    assert record["net_acres_total"] == 106.0


def test_parse_lpr_transmittal_extracts_tract_lines_in_order():
    record = parse_lpr_transmittal(SAMPLE_TRANSMITTAL)
    lines = record["tract_lines"]

    assert len(lines) == 2
    assert lines[0]["location"] == "001N-001W,01"
    assert lines[0]["gross"] == 80.0
    assert lines[0]["interest"] == 1.0
    assert lines[0]["net"] == 80.0
    assert lines[0]["description"] == "N/2 NW"

    assert lines[1]["location"] == "001N-001W,02"
    assert lines[1]["net"] == 26.0
    assert "FRACTIONAL" in lines[1]["description"]
    assert record["parse_warnings"] == []


def test_parse_lpr_transmittal_warns_on_column_count_mismatch():
    broken = SAMPLE_TRANSMITTAL.replace("80.0000\n26.0000\n", "80.0000\n")
    record = parse_lpr_transmittal(broken)
    assert any("column count" in w for w in record["parse_warnings"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:\Users\mapma\AppData\Local\Programs\Python\Python311\python.exe -m pytest tests/test_caspiana_lpr_template.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.caspiana.lpr_template'`

- [ ] **Step 3: Write the implementation**

```python
# core/caspiana/lpr_template.py
"""Parser for the LPR 'Lease Transmittal' landman-software printout. The
Legal Description table's columns (Location / Tract# / Gross / Interest /
Net / Description) OCR in column-major reading order, not row-major, so
each column is located independently and then zipped back into rows --
zip is intentionally used so a count mismatch produces a short (not
misaligned) result, which the reconciliation check below catches."""
import re

_HEADER_FIELDS = [
    ("lessor", r"1\.\s*Lessor\s+(.+?)\s*(?:\n|$)"),
    ("lessee", r"41\.\s*Lessee\s+(.+?)\s*(?:\n|$)"),
    ("lease_date", r"5\.\s*Date\s+(\d{2}/\d{2}/\d{4})"),
    ("effective_date", r"26\.\s*Effective\s+(\d{2}/\d{2}/\d{4})"),
    ("expiration_date", r"25\.\s*Expires\s+(\d{2}/\d{2}/\d{4})"),
    ("term", r"24\.\s*Term\s+(.+?)\s*(?:\n|$)"),
    ("royalty", r"33\.\s*Royalty\s+(\S+)"),
]

_LOCATION_RE = re.compile(r"\b(\d{3}[NS]-\d{3}[EW],\d{1,2})\b")
_TOTALS_LINE_RE = re.compile(r"^\s*([\d,]+\.\d+)\s+([\d,]+\.\d+)\s*$", re.MULTILINE)


def _extract_text(pattern: str, text: str) -> str | None:
    m = re.search(pattern, text, re.IGNORECASE)
    return m.group(1).strip() if m else None


def _extract_float(pattern: str, text: str) -> float | None:
    m = re.search(pattern, text, re.IGNORECASE)
    return float(m.group(1).replace(",", "")) if m else None


def _legal_description_block(text: str) -> str:
    m = re.search(r"Legal Description\s*(.+?)Landman Approval", text, re.IGNORECASE | re.DOTALL)
    return m.group(1) if m else ""


def parse_lpr_transmittal(page_text: str) -> dict:
    record: dict = {}
    warnings: list[str] = []

    for key, pattern in _HEADER_FIELDS:
        record[key] = _extract_text(pattern, page_text)
        if record[key] is None:
            warnings.append(f"could not find {key}")

    record["gross_ac_total"] = _extract_float(r"8\.\s*Gross Ac\s+([\d,]+\.\d+)", page_text)
    record["net_acres_total"] = _extract_float(r"9\.\s*Net Acres\s+([\d,]+\.\d+)", page_text)

    block = _legal_description_block(page_text)
    locations = _LOCATION_RE.findall(block)

    numeric_lines = [
        float(n.replace(",", ""))
        for n in re.findall(r"^\s*([\d,]+\.\d+)\s*$", block, re.MULTILINE)
    ]
    # numeric_lines holds gross values, then interest values, then net
    # values, then one totals line (2 numbers) -- (len - 2) must divide by 3.
    n = len(locations)
    expected_numeric_count = 3 * n + 2
    description_lines = [
        line.strip() for line in block.splitlines()
        if line.strip() and not _LOCATION_RE.match(line.strip())
        and not re.match(r"^[\d,.\s]+$", line.strip())
        and "Location" not in line and "Description" not in line
    ]

    tract_lines = []
    if n > 0 and len(numeric_lines) == expected_numeric_count and len(description_lines) == n:
        gross_vals = numeric_lines[0:n]
        interest_vals = numeric_lines[n:2 * n]
        net_vals = numeric_lines[2 * n:3 * n]
        for i in range(n):
            tract_lines.append({
                "location": locations[i],
                "tract_no": str(i + 1),
                "gross": gross_vals[i],
                "interest": interest_vals[i],
                "net": net_vals[i],
                "description": description_lines[i],
            })
    else:
        warnings.append(
            f"tract-line column count mismatch: {n} locations, "
            f"{len(numeric_lines)} numeric values (expected {expected_numeric_count}), "
            f"{len(description_lines)} description lines"
        )

    record["tract_lines"] = tract_lines
    record["parse_warnings"] = warnings
    return record
```

- [ ] **Step 4: Run test to verify it passes**

Run: `C:\Users\mapma\AppData\Local\Programs\Python\Python311\python.exe -m pytest tests/test_caspiana_lpr_template.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add core/caspiana/lpr_template.py tests/test_caspiana_lpr_template.py
git commit -m "feat(caspiana): add LPR Lease Transmittal regex parser"
```

---

## Task 5: Row confidence scoring

**Files:**
- Create: `core/caspiana/confidence.py`
- Test: `tests/test_caspiana_confidence.py`

**Interfaces:**
- Consumes: the `parse_warnings` list and acreage/WI fields produced by Tasks 3 and 4's parsers (accessed as plain dict keys, no import coupling).
- Produces: `score_row(row: dict) -> str` returning `"High"` / `"Medium"` / `"Low"` / `"Needs Review"`. `REQUIRED_FOR_HIGH = ("gross_acres", "net_acres", "working_interest")` — the row-schema key names later tasks (Task 7's master-row builder) must populate before calling this.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_caspiana_confidence.py
from core.caspiana.confidence import score_row


def test_high_confidence_when_complete_and_no_warnings():
    row = {
        "gross_acres": 40.0,
        "net_acres": 20.0,
        "working_interest": 0.5,
        "source": "LPR",
        "parse_warnings": [],
    }
    assert score_row(row) == "High"


def test_medium_confidence_when_ogml_source_with_minor_warning():
    row = {
        "gross_acres": 40.0,
        "net_acres": 20.0,
        "working_interest": 0.5,
        "source": "OGML",
        "parse_warnings": ["could not find term"],
    }
    assert score_row(row) == "Medium"


def test_needs_review_when_core_acreage_field_missing():
    row = {
        "gross_acres": None,
        "net_acres": 20.0,
        "working_interest": 0.5,
        "source": "OGML",
        "parse_warnings": ["could not find lease_gross_acres"],
    }
    assert score_row(row) == "Needs Review"


def test_needs_review_when_source_is_raw():
    row = {
        "gross_acres": 40.0,
        "net_acres": 20.0,
        "working_interest": 0.5,
        "source": "Raw",
        "parse_warnings": [],
    }
    assert score_row(row) == "Needs Review"


def test_low_confidence_when_working_interest_fractions_dont_sum_near_one():
    row = {
        "gross_acres": 40.0,
        "net_acres": 20.0,
        "working_interest": 0.3,
        "working_interest_owners": [("A", 0.3), ("B", 0.3)],
        "source": "OGML",
        "parse_warnings": [],
    }
    assert score_row(row) == "Low"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:\Users\mapma\AppData\Local\Programs\Python\Python311\python.exe -m pytest tests/test_caspiana_confidence.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.caspiana.confidence'`

- [ ] **Step 3: Write the implementation**

```python
# core/caspiana/confidence.py
"""Scores how much a parsed row can be trusted, so the pipeline never
silently guesses at gross/net acres or working interest. Nothing here
mutates a row -- it only reads the fields the parsers/master-builder
already populated and returns a verdict."""

REQUIRED_FOR_HIGH = ("gross_acres", "net_acres", "working_interest")


def _wi_owners_reconcile(row: dict) -> bool:
    owners = row.get("working_interest_owners")
    if not owners:
        return True  # nothing to check
    total = sum(frac for _, frac in owners)
    return abs(total - 1.0) < 0.01


def score_row(row: dict) -> str:
    if row.get("source", "").lower() == "raw":
        # Raw legal instruments never carry an explicit acreage/WI field --
        # always route to manual/vision review rather than trust a regex
        # guess pulled out of free-form legal prose.
        return "Needs Review"

    missing_required = [f for f in REQUIRED_FOR_HIGH if row.get(f) is None]
    if missing_required:
        return "Needs Review"

    if not _wi_owners_reconcile(row):
        return "Low"

    warnings = row.get("parse_warnings") or []
    if not warnings:
        return "High"

    return "Medium"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `C:\Users\mapma\AppData\Local\Programs\Python\Python311\python.exe -m pytest tests/test_caspiana_confidence.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add core/caspiana/confidence.py tests/test_caspiana_confidence.py
git commit -m "feat(caspiana): add row confidence scoring"
```

---

## Task 6: PLSS aliquot subdivision geometry

**Files:**
- Create: `core/caspiana/plss.py`
- Test: `tests/test_caspiana_plss.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `subdivide_aliquot(section_polygon: shapely.geometry.Polygon, description: str) -> shapely.geometry.Polygon | None` (returns `None` for descriptions it can't confidently subdivide, e.g. metes-and-bounds or fractional/government-lot sections — caller must treat `None` as "needs manual/approximate placement", never silently draw a wrong box). `fetch_section_polygon(township_range: str, section: str, parish: str) -> shapely.geometry.Polygon` (queries the BLM CadNSDI REST service; network call, not unit tested here).

- [ ] **Step 1: Write the failing test**

Uses a plain unit-square fixture polygon (no real geography needed) to verify the aliquot-fraction math itself.

```python
# tests/test_caspiana_plss.py
from shapely.geometry import Polygon, box

from core.caspiana.plss import subdivide_aliquot

UNIT_SQUARE = box(0, 0, 1, 1)  # xmin, ymin, xmax, ymax


def test_half_subdivisions():
    n_half = subdivide_aliquot(UNIT_SQUARE, "N/2")
    assert n_half.bounds == (0, 0.5, 1, 1)

    s_half = subdivide_aliquot(UNIT_SQUARE, "S/2")
    assert s_half.bounds == (0, 0, 1, 0.5)

    e_half = subdivide_aliquot(UNIT_SQUARE, "E/2")
    assert e_half.bounds == (0.5, 0, 1, 1)

    w_half = subdivide_aliquot(UNIT_SQUARE, "W/2")
    assert w_half.bounds == (0, 0, 0.5, 1)


def test_quarter_subdivision():
    ne_quarter = subdivide_aliquot(UNIT_SQUARE, "NE/4")
    assert ne_quarter.bounds == (0.5, 0.5, 1, 1)


def test_compound_aliquot_subdivides_left_to_right():
    # N/2 N/2 NE/4 == take NE/4 first, then N/2 of that, then N/2 of that.
    result = subdivide_aliquot(UNIT_SQUARE, "N/2 N/2 NE/4")
    assert result.area == 1 / 16
    assert result.bounds == (0.75, 0.875, 1.0, 1.0)


def test_area_matches_acreage_fraction():
    result = subdivide_aliquot(UNIT_SQUARE, "SW/4")
    assert result.area == 0.25


def test_returns_none_for_unrecognized_description():
    assert subdivide_aliquot(UNIT_SQUARE, "Beginning at an iron pin thence N45E 200 ft") is None
    assert subdivide_aliquot(UNIT_SQUARE, "Lot 4, less 2.41 acres") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:\Users\mapma\AppData\Local\Programs\Python\Python311\python.exe -m pytest tests/test_caspiana_plss.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.caspiana.plss'`

- [ ] **Step 3: Write the implementation**

```python
# core/caspiana/plss.py
"""PLSS section polygon sourcing (BLM CadNSDI) and aliquot-description
subdivision. Only handles regular quarter/half aliquot descriptions
(N/2, SE/4, N/2 N/2 NE/4, ...) -- fractional sections, government lots,
and metes-and-bounds descriptions return None rather than a wrong
polygon, since the real Caspiana leases contain both (e.g. "fractional
section, containing 237.30 acres" observed in a raw amendment)."""
import re

import requests
from shapely.geometry import Polygon, box, shape

BLM_PLSS_MAPSERVER = (
    "https://gis.blm.gov/arcgis/rest/services/Cadastral/BLM_Natl_PLSS_CadNSDI/MapServer"
)
_SECTION_LAYER = 1  # "PLSSFirstDivision" (sections) in the BLM CadNSDI schema

_ALIQUOT_BOUNDS = {
    # fraction_token -> (xmin_frac, ymin_frac, xmax_frac, ymax_frac) within
    # whatever polygon it's applied to (always axis-aligned bounding box).
    "N/2": (0.0, 0.5, 1.0, 1.0),
    "S/2": (0.0, 0.0, 1.0, 0.5),
    "E/2": (0.5, 0.0, 1.0, 1.0),
    "W/2": (0.0, 0.0, 0.5, 1.0),
    "NE/4": (0.5, 0.5, 1.0, 1.0),
    "NW/4": (0.0, 0.5, 0.5, 1.0),
    "SE/4": (0.5, 0.0, 1.0, 0.5),
    "SW/4": (0.0, 0.0, 0.5, 0.5),
}
_TOKEN_RE = re.compile(r"\b([NSEW]{1,2}/[24])\b", re.IGNORECASE)


def _apply_fraction(poly: Polygon, token: str) -> Polygon:
    xmin, ymin, xmax, ymax = poly.bounds
    fx0, fy0, fx1, fy1 = _ALIQUOT_BOUNDS[token.upper()]
    w, h = xmax - xmin, ymax - ymin
    return box(xmin + fx0 * w, ymin + fy0 * h, xmin + fx1 * w, ymin + fy1 * h)


def subdivide_aliquot(section_polygon: Polygon, description: str) -> Polygon | None:
    tokens = _TOKEN_RE.findall(description)
    if not tokens:
        return None
    # Legal descriptions read outer-to-inner left-to-right (e.g. "N/2 N/2
    # NE/4" means "the N/2 of [the N/2 of [the NE/4]]"), so apply the
    # *last* token first, then work backwards.
    result = section_polygon
    for token in reversed(tokens):
        if token.upper() not in _ALIQUOT_BOUNDS:
            return None
        result = _apply_fraction(result, token)
    return result


def fetch_section_polygon(township_range: str, section: str, parish: str) -> Polygon:
    """Query BLM's public PLSS REST service for one section polygon.
    township_range like 'T14N R16W'. Not exercised by the unit test suite
    (network call) -- verified against real sections in Task 10."""
    t, r = township_range.upper().replace("T", "").replace("R", "").split("N ")
    where = f"TWNSHPNO={t} AND RANGENO={r.rstrip('W')} AND FRSTDIVNO='{section}'"
    resp = requests.get(
        f"{BLM_PLSS_MAPSERVER}/{_SECTION_LAYER}/query",
        params={"where": where, "outFields": "*", "f": "geojson"},
        timeout=30,
    )
    resp.raise_for_status()
    features = resp.json().get("features", [])
    if not features:
        raise ValueError(f"No BLM PLSS section found for {township_range} Sec {section}, {parish}")
    return shape(features[0]["geometry"])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `C:\Users\mapma\AppData\Local\Programs\Python\Python311\python.exe -m pytest tests/test_caspiana_plss.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add core/caspiana/plss.py tests/test_caspiana_plss.py
git commit -m "feat(caspiana): add PLSS aliquot subdivision and BLM section fetch"
```

---

## Task 7: Master dataset pipeline orchestrator

**Files:**
- Create: `core/caspiana/master_builder.py`
- Create: `scripts/caspiana_pipeline.py`
- Test: `tests/test_caspiana_master_builder.py`

**Interfaces:**
- Consumes: `build_manifest` (Task 1), `ocr_pdf_pages` (Task 2), `split_ogml_cards`/`parse_ogml_card` (Task 3), `parse_lpr_transmittal` (Task 4), `score_row` (Task 5).
- Produces: `build_master_rows(manifest: list[dict], cache_dir: Path) -> list[dict]` — one dict per output row with the full row schema: `section`, `township_range`, `parish`, `lessor`, `lessee`, `legal_description`, `gross_acres`, `net_acres`, `lessors_mineral_interest`, `working_interest_owners`, `royalty`, `lease_date`, `effective_date`, `expiration_date`, `unit_no`, `source`, `source_file`, `confidence`, `parse_warnings`, `superseded_by_lpr` (`bool` — `True` for OGML rows in a section that also has an LPR; those rows are kept for their working-interest-owner detail but must be excluded from acreage totals/GIS by every later task). This is the schema every later task (Excel, GIS join, dashboard) reads.

- [ ] **Step 1: Write the failing test**

Monkeypatches `ocr_pdf_pages` so the test doesn't touch real Tesseract/poppler — it only checks that manifest rows get routed to the right parser and turned into the master schema.

```python
# tests/test_caspiana_master_builder.py
from pathlib import Path

from core.caspiana import master_builder

OGML_TEXT = """
LAND RECORD FORM
FIELD: EXAMPLE COUNTY: SAMPLE STATE: LOUISIANA
UNIT NO.: 100
LESSOR: JANE Q TESTOWNER
LESSEE: EXAMPLE PRODUCTION COMPANY, INC.
TERM: 5 YRS. ROYALTY: 1/8 LESSOR'S MINERAL INTEREST: 1/2
LEASE GROSS ACRES: 40.0000 LEASE NET ACRES: 20.0000
LEASE GROSS ACRES ASSIGNED: 40.0000 LEASE NET ACRES ASSIGNED: 20.0000
DESCRIPTION (ASSIGNED): N/2 NE/4 OF SECTION 29, T14N-R16W.
WORKING INTEREST OWNERS WORKING INTEREST IN UNIT
EXAMPLE OPERATOR CO 1.00000000
SURFACE OWNER: UNKNOWN
""".strip()


def test_build_master_rows_routes_ogml_file_through_ogml_parser(tmp_path, monkeypatch):
    manifest = [{
        "section": "29", "township_range": "T14N R16W", "parish": "DeSoto",
        "doc_type": "OGML", "path": str(tmp_path / "card.pdf"),
    }]
    monkeypatch.setattr(master_builder, "ocr_pdf_pages", lambda path, cache_dir: [OGML_TEXT])

    rows = master_builder.build_master_rows(manifest, cache_dir=tmp_path / "cache")

    assert len(rows) == 1
    row = rows[0]
    assert row["source"] == "OGML"
    assert row["section"] == "29"
    assert row["lessor"] == "JANE Q TESTOWNER"
    assert row["gross_acres"] == 40.0
    assert row["net_acres"] == 20.0
    assert row["confidence"] in ("High", "Medium")
    assert row["source_file"] == str(tmp_path / "card.pdf")


def test_build_master_rows_flags_raw_docs_as_needs_review(tmp_path, monkeypatch):
    manifest = [{
        "section": "18", "township_range": "T14N R16W", "parish": "Caddo",
        "doc_type": "RAW", "path": str(tmp_path / "amendment.pdf"),
    }]
    monkeypatch.setattr(master_builder, "ocr_pdf_pages", lambda path, cache_dir: ["some legal prose"])

    rows = master_builder.build_master_rows(manifest, cache_dir=tmp_path / "cache")

    assert len(rows) == 1
    assert rows[0]["confidence"] == "Needs Review"
    assert rows[0]["source"] == "Raw"
    assert rows[0]["superseded_by_lpr"] is False


LPR_TEXT = """
Lease Transmittal
1. Lessor Example Timber Company
41. Lessee Sample Energy E&P Company, L.L.C.
33. Royalty 1/4th
8. Gross Ac 26.0000
9. Net Acres 26.0000
Legal Description
68. Location 69.Tract# 72. Gross 73. Interest 74. Net 75. Description
013N-016W,06
26.0000
1.0000000
26.0000
FRACTIONAL E/2 OF N/2 N/2
Landman Approval
""".strip()


def test_ogml_rows_flagged_superseded_when_section_also_has_lpr(tmp_path, monkeypatch):
    manifest = [
        {"section": "6", "township_range": "T13N R16W", "parish": "DeSoto",
         "doc_type": "LPR", "path": str(tmp_path / "transmittal.pdf")},
        {"section": "6", "township_range": "T13N R16W", "parish": "DeSoto",
         "doc_type": "OGML", "path": str(tmp_path / "card.pdf")},
    ]

    def fake_ocr(path, cache_dir):
        return [LPR_TEXT] if "transmittal" in str(path) else [OGML_TEXT]

    monkeypatch.setattr(master_builder, "ocr_pdf_pages", fake_ocr)

    rows = master_builder.build_master_rows(manifest, cache_dir=tmp_path / "cache")

    lpr_rows = [r for r in rows if r["source"] == "LPR"]
    ogml_rows = [r for r in rows if r["source"] == "OGML"]
    assert len(lpr_rows) == 1
    assert lpr_rows[0]["superseded_by_lpr"] is False
    assert len(ogml_rows) == 1
    assert ogml_rows[0]["superseded_by_lpr"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:\Users\mapma\AppData\Local\Programs\Python\Python311\python.exe -m pytest tests/test_caspiana_master_builder.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.caspiana.master_builder'`

- [ ] **Step 3: Write the implementation**

```python
# core/caspiana/master_builder.py
"""Ties inventory + OCR + template parsers + confidence scoring together
into the common master row schema every deliverable (Excel, GIS, web
dashboard) reads from."""
from pathlib import Path

from core.caspiana.confidence import score_row
from core.caspiana.lpr_template import parse_lpr_transmittal
from core.caspiana.ocr_utils import ocr_pdf_pages
from core.caspiana.ogml_template import parse_ogml_card, split_ogml_cards

MASTER_ROW_FIELDS = [
    "section", "township_range", "parish", "lessor", "lessee",
    "legal_description", "gross_acres", "net_acres",
    "lessors_mineral_interest", "working_interest_owners", "royalty",
    "lease_date", "effective_date", "expiration_date", "unit_no",
    "source", "source_file", "confidence", "parse_warnings",
    "superseded_by_lpr",
]


def _rows_from_ogml(manifest_entry: dict, page_text: str, superseded: bool) -> list[dict]:
    rows = []
    for card_text in split_ogml_cards(page_text):
        parsed = parse_ogml_card(card_text)
        row = {
            "section": manifest_entry["section"],
            "township_range": manifest_entry["township_range"],
            "parish": manifest_entry["parish"],
            "lessor": parsed.get("lessor"),
            "lessee": parsed.get("lessee"),
            "legal_description": parsed.get("description"),
            "gross_acres": parsed.get("lease_gross_acres_assigned") or parsed.get("lease_gross_acres"),
            "net_acres": parsed.get("lease_net_acres_assigned") or parsed.get("lease_net_acres"),
            "lessors_mineral_interest": parsed.get("lessors_mineral_interest"),
            "working_interest_owners": parsed.get("working_interest_owners"),
            "working_interest": (
                parsed["working_interest_owners"][0][1]
                if parsed.get("working_interest_owners") else None
            ),
            "royalty": parsed.get("royalty"),
            "lease_date": None, "effective_date": None, "expiration_date": None,
            "unit_no": parsed.get("unit_no"),
            "source": "OGML",
            "source_file": manifest_entry["path"],
            "parse_warnings": parsed.get("parse_warnings", []),
            "superseded_by_lpr": superseded,
        }
        row["confidence"] = score_row(row)
        rows.append(row)
    return rows


def _rows_from_lpr(manifest_entry: dict, page_text: str) -> list[dict]:
    parsed = parse_lpr_transmittal(page_text)
    rows = []
    for tract in parsed.get("tract_lines", []):
        row = {
            "section": manifest_entry["section"],
            "township_range": manifest_entry["township_range"],
            "parish": manifest_entry["parish"],
            "lessor": parsed.get("lessor"),
            "lessee": parsed.get("lessee"),
            "legal_description": tract.get("description"),
            "gross_acres": tract.get("gross"),
            "net_acres": tract.get("net"),
            "lessors_mineral_interest": None,
            "working_interest_owners": None,
            "working_interest": tract.get("interest"),
            "royalty": parsed.get("royalty"),
            "lease_date": parsed.get("lease_date"),
            "effective_date": parsed.get("effective_date"),
            "expiration_date": parsed.get("expiration_date"),
            "unit_no": None,
            "source": "LPR",
            "source_file": manifest_entry["path"],
            "parse_warnings": parsed.get("parse_warnings", []),
            "superseded_by_lpr": False,
        }
        row["confidence"] = score_row(row)
        rows.append(row)
    return rows


def _row_from_raw(manifest_entry: dict, page_text: str) -> dict:
    row = {
        "section": manifest_entry["section"],
        "township_range": manifest_entry["township_range"],
        "parish": manifest_entry["parish"],
        "lessor": None, "lessee": None, "legal_description": None,
        "gross_acres": None, "net_acres": None,
        "lessors_mineral_interest": None, "working_interest_owners": None,
        "working_interest": None, "royalty": None,
        "lease_date": None, "effective_date": None, "expiration_date": None,
        "unit_no": None,
        "source": "Raw",
        "source_file": manifest_entry["path"],
        "parse_warnings": ["raw support document -- needs manual/vision review"],
        "superseded_by_lpr": False,
    }
    row["confidence"] = score_row(row)
    return row


def build_master_rows(manifest: list[dict], cache_dir: Path) -> list[dict]:
    lpr_sections = {e["section"] for e in manifest if e["doc_type"] == "LPR"}

    rows: list[dict] = []
    for entry in manifest:
        pages = ocr_pdf_pages(Path(entry["path"]), cache_dir)
        full_text = "\n".join(pages)

        if entry["doc_type"] == "OGML":
            superseded = entry["section"] in lpr_sections
            rows.extend(_rows_from_ogml(entry, full_text, superseded))
        elif entry["doc_type"] == "LPR":
            rows.extend(_rows_from_lpr(entry, full_text))
        else:
            rows.append(_row_from_raw(entry, full_text))
    return rows
```

```python
# scripts/caspiana_pipeline.py
#!/usr/bin/env python
"""Run the full Caspiana Little Creek lease-abstraction OCR pipeline:
inventory -> OCR -> parse -> confidence score -> draft master dataset.

Run: C:\\Users\\mapma\\AppData\\Local\\Programs\\Python\\Python311\\python.exe scripts\\caspiana_pipeline.py
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.caspiana.inventory import build_manifest
from core.caspiana.master_builder import MASTER_ROW_FIELDS, build_master_rows

CASPIANA_ROOT = Path(r"C:\GIS\CLIENT\DOXA\SABINE\CASPIANA\Caspiana Little Creek T14-R16 & T13-R16")
DIVERSIFIED_ROOT = CASPIANA_ROOT / "Diversified File Downlaod"
DELIVERABLES_DIR = CASPIANA_ROOT / "Deliverables"
OCR_CACHE_DIR = DELIVERABLES_DIR / ".ocr_cache"


def main():
    DELIVERABLES_DIR.mkdir(exist_ok=True)
    OCR_CACHE_DIR.mkdir(exist_ok=True)

    manifest = build_manifest(DIVERSIFIED_ROOT)
    pd.DataFrame(manifest).to_csv(DELIVERABLES_DIR / "manifest.csv", index=False)
    print(f"Manifest: {len(manifest)} files "
          f"({sum(1 for m in manifest if m['doc_type'] == 'LPR')} LPR, "
          f"{sum(1 for m in manifest if m['doc_type'] == 'OGML')} OGML, "
          f"{sum(1 for m in manifest if m['doc_type'] == 'RAW')} Raw)")

    rows = build_master_rows(manifest, OCR_CACHE_DIR)
    df = pd.DataFrame(rows, columns=MASTER_ROW_FIELDS)
    df.to_csv(DELIVERABLES_DIR / "draft_master.csv", index=False)
    print(f"Draft master dataset: {len(df)} rows -> {DELIVERABLES_DIR / 'draft_master.csv'}")

    needs_qa = df[df["confidence"].isin(["Low", "Needs Review"])]
    needs_qa.to_csv(DELIVERABLES_DIR / "needs_vision_qa.csv", index=False)
    print(f"Flagged for vision QA: {len(needs_qa)} rows -> {DELIVERABLES_DIR / 'needs_vision_qa.csv'}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `C:\Users\mapma\AppData\Local\Programs\Python\Python311\python.exe -m pytest tests/test_caspiana_master_builder.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add core/caspiana/master_builder.py scripts/caspiana_pipeline.py tests/test_caspiana_master_builder.py
git commit -m "feat(caspiana): add master-dataset pipeline orchestrator"
```

---

## Task 8: Run the pipeline against the real Caspiana files

This is an execution/verification task against real client data, not a code-authoring task — nothing here is committed to git (outputs land only in `DELIVERABLES_DIR`, which is outside the repo).

- [ ] **Step 1: Run the pipeline**

Run: `C:\Users\mapma\AppData\Local\Programs\Python\Python311\python.exe scripts\caspiana_pipeline.py`

- [ ] **Step 2: Verify the manifest count matches the known file count**

The full section-by-section `Lease Agreement` file count gathered during design was 202 files (6+9+4+14+68+14+13+42+13+19 across Sec 17,18,19,20,29,30,31,32,5,6). Confirm `manifest.csv`'s row count is in that neighborhood — note it will be somewhat higher than 202 since `Payment`, `Title`, and `Plat` subfolders (outside `Lease Agreement`) also get swept in as `RAW`. Open `manifest.csv` and confirm `doc_type` counts: `LPR` should be exactly 2 (both from the shared Sec 5/Sec 6 file), `OGML` should be the bulk of rows.

- [ ] **Step 3: Verify no OCR crashes and inspect draft_master.csv**

Confirm `draft_master.csv` row count is close to but not lower than manifest's OGML+LPR-tract-line count (each OGML file can yield >1 row; each LPR tract line yields 1 row). Open it in Excel or `pandas.read_csv` and eyeball 5-10 rows for plausibility (real section numbers, real-looking lessor names, acreage numbers in a sane range for these sections).

- [ ] **Step 4: Inspect needs_vision_qa.csv size**

Note the row count — this is the queue for Task 9. If it's the large majority of rows (parsing mostly failing) rather than a minority, stop and debug the regex patterns against 3-4 real OCR'd pages before proceeding (`ocr_pdf_pages` output can be inspected directly per file to see what Tesseract actually produced vs. what the templates in Tasks 3/4 expect — real scans may need minor pattern adjustments the synthetic fixtures didn't surface).

---

## Task 9: Claude-vision QA pass on flagged rows

Agent-assisted, not scriptable — for each row in `needs_vision_qa.csv`:

- [ ] **Step 1:** Open `needs_vision_qa.csv`, group rows by `source_file` (multiple flagged rows often share one PDF).
- [ ] **Step 2:** For each distinct `source_file`, read the PDF with the Read tool (renders pages as images) and manually determine the correct values for whichever fields were flagged (`lessor`, `lessee`, `gross_acres`, `net_acres`, `working_interest`, `legal_description`, etc.), plus derive values for any `Raw`-sourced rows (leases with no LPR/OGML card) directly from the legal instrument text.
- [ ] **Step 3:** Apply the corrections into a copy of `draft_master.csv`, update `confidence` to `High` for corrected rows (or leave `Needs Review` with a note in a new `qa_note` column if the source document is genuinely ambiguous — never force a value that isn't actually supported by the document).
- [ ] **Step 3a (Sec 5 & 6 only):** These two sections have rows flagged `superseded_by_lpr=True` — the OGML card's `working_interest_owners` detail for a tract isn't captured by the LPR row for that same tract (LPR only carries the lessor's fractional interest, not a WI-owner breakdown). Where an OGML row's legal description matches an LPR row's legal description for the same section, copy the OGML row's `working_interest_owners` value onto the matching LPR row so the authoritative (LPR-sourced, non-superseded) row still carries WI-owner detail. Leave the OGML row itself in place (still `superseded_by_lpr=True`, excluded from totals) as the audit trail for that copy.
- [ ] **Step 4:** Save the corrected file as `DELIVERABLES_DIR / "master.csv"` — this is the final dataset every remaining task reads from.
- [ ] **Step 5:** Run the per-section reconciliation check: for each section, sum `net_acres` across its rows and compare against that section's total acreage from the `IPL Tract Folders` COT spreadsheets / `Plats`. Note any section where the sums are far off in a `reconciliation_notes.md` alongside `master.csv` — flag, don't silently adjust numbers to force a match.

---

## Task 10: GIS tract layer

**Files:**
- Create: `scripts/caspiana_gis_build.py`

- [ ] **Step 1: Write and run the GIS build script**

```python
# scripts/caspiana_gis_build.py
#!/usr/bin/env python
"""Build the Caspiana lease-tract GIS layer: one BLM PLSS section polygon
per section, subdivided per each master.csv row's legal description where
the aliquot parser (core.caspiana.plss) can resolve it.

Run: C:\\Users\\mapma\\AppData\\Local\\Programs\\Python\\Python311\\python.exe scripts\\caspiana_gis_build.py
"""
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.caspiana.plss import fetch_section_polygon, subdivide_aliquot

CASPIANA_ROOT = Path(r"C:\GIS\CLIENT\DOXA\SABINE\CASPIANA\Caspiana Little Creek T14-R16 & T13-R16")
DELIVERABLES_DIR = CASPIANA_ROOT / "Deliverables"


def main():
    master = pd.read_csv(DELIVERABLES_DIR / "master.csv")
    # OGML rows in a section that also has an LPR are kept in master.csv for
    # their working-interest detail but must not double up the LPR's tract
    # geometry/acreage -- see superseded_by_lpr in core.caspiana.master_builder.
    master = master[master["superseded_by_lpr"] != True]  # noqa: E712

    section_keys = master[["section", "township_range", "parish"]].drop_duplicates()
    section_polys = {}
    for _, row in section_keys.iterrows():
        key = (row["section"], row["township_range"])
        try:
            section_polys[key] = fetch_section_polygon(row["township_range"], row["section"], row["parish"])
        except Exception as exc:
            print(f"WARNING: could not fetch section polygon for {key}: {exc}")

    features = []
    unresolved = 0
    for _, row in master.iterrows():
        key = (row["section"], row["township_range"])
        section_poly = section_polys.get(key)
        if section_poly is None or pd.isna(row.get("legal_description")):
            unresolved += 1
            continue
        tract_poly = subdivide_aliquot(section_poly, str(row["legal_description"]))
        if tract_poly is None:
            unresolved += 1
            continue
        features.append({
            "geometry": tract_poly,
            "section": row["section"],
            "lessor": row["lessor"],
            "lessee": row["lessee"],
            "gross_ac": row["gross_acres"],
            "net_ac": row["net_acres"],
            "source": row["source"],
            "confidence": row["confidence"],
        })

    gdf = gpd.GeoDataFrame(features, crs=section_polys[next(iter(section_polys))].crs if section_polys else "EPSG:4326")
    out_path = DELIVERABLES_DIR / "lease_tracts.geojson"
    gdf.to_file(out_path, driver="GeoJSON")
    print(f"GIS layer: {len(gdf)} tract polygons resolved, {unresolved} rows unresolved "
          f"(fractional/metes-and-bounds descriptions, or missing section polygon) -> {out_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it and sanity-check output**

Run: `C:\Users\mapma\AppData\Local\Programs\Python\Python311\python.exe scripts\caspiana_gis_build.py`
Open `lease_tracts.geojson` in QGIS (or any GeoJSON viewer) and confirm the polygons fall within Caddo/DeSoto Parish, LA, roughly matching the section boxes visible in the existing `Plats/` PDFs. Cross-check the `unresolved` count against how many `master.csv` rows have non-simple-aliquot legal descriptions (fractional sections, metes-and-bounds) — those need a manual/approximate point placement noted in `reconciliation_notes.md` instead of a polygon.

- [ ] **Step 3: Commit only the script**

```bash
git add scripts/caspiana_gis_build.py
git commit -m "feat(caspiana): add GIS tract layer builder"
```

---

## Task 11: Excel workbook with native dashboard

**Files:**
- Create: `core/caspiana/excel_builder.py`
- Create: `scripts/caspiana_excel_build.py`
- Test: `tests/test_caspiana_excel_builder.py`

**Interfaces:**
- Consumes: a list of master-row dicts (Task 7's schema).
- Produces: `build_workbook(rows: list[dict]) -> openpyxl.Workbook` with a `Master Data` sheet (one row per lease/tract, formatted as an Excel Table for built-in filter dropdowns) and a `Dashboard` sheet (KPI summary cells + a PivotTable-ready cache, section/lessee/WI-owner breakdown via formulas since openpyxl can't script native PivotTables directly — see Step 3).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_caspiana_excel_builder.py
from core.caspiana.excel_builder import build_workbook

SAMPLE_ROWS = [
    {"section": "29", "township_range": "T14N R16W", "parish": "DeSoto",
     "lessor": "Jane Testowner", "lessee": "Example Production Co",
     "legal_description": "N/2 NE/4", "gross_acres": 40.0, "net_acres": 20.0,
     "working_interest": 1.0, "royalty": "1/8", "source": "OGML",
     "confidence": "High", "superseded_by_lpr": False},
    {"section": "29", "township_range": "T14N R16W", "parish": "DeSoto",
     "lessor": "Sam Otherowner", "lessee": "Example Production Co",
     "legal_description": "S/2 NE/4", "gross_acres": 40.0, "net_acres": 40.0,
     "working_interest": 0.5, "royalty": "1/4", "source": "LPR",
     "confidence": "High", "superseded_by_lpr": False},
    {"section": "29", "township_range": "T14N R16W", "parish": "DeSoto",
     "lessor": "Jane Testowner", "lessee": "Example Production Co",
     "legal_description": "N/2 NE/4", "gross_acres": 40.0, "net_acres": 20.0,
     "working_interest": 1.0, "royalty": "1/8", "source": "OGML",
     "confidence": "Medium", "superseded_by_lpr": True},
]


def test_build_workbook_has_master_and_dashboard_sheets():
    wb = build_workbook(SAMPLE_ROWS)
    assert "Master Data" in wb.sheetnames
    assert "Dashboard" in wb.sheetnames


def test_master_data_sheet_has_header_and_one_row_per_record():
    wb = build_workbook(SAMPLE_ROWS)
    ws = wb["Master Data"]
    header = [c.value for c in ws[1]]
    assert "lessor" in header
    assert "net_acres" in header
    assert ws.max_row == 1 + len(SAMPLE_ROWS)


def test_dashboard_sheet_has_correct_kpi_totals():
    # Row 3 of SAMPLE_ROWS is superseded_by_lpr=True (an OGML row kept only
    # for WI detail in a section that also has an LPR) -- it must be
    # excluded from the totals so LPR and OGML never double-count the same
    # tract's acreage.
    wb = build_workbook(SAMPLE_ROWS)
    ws = wb["Dashboard"]
    values = [c.value for row in ws.iter_rows() for c in row if c.value is not None]
    assert 80.0 in values  # total gross acres (40 + 40, excluding the superseded row's 40)
    assert 60.0 in values  # total net acres (20 + 40, excluding the superseded row's 20)


def test_master_data_sheet_includes_superseded_rows_for_reference():
    wb = build_workbook(SAMPLE_ROWS)
    ws = wb["Master Data"]
    assert ws.max_row == 1 + len(SAMPLE_ROWS)  # all 3 rows still listed, incl. the superseded one
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:\Users\mapma\AppData\Local\Programs\Python\Python311\python.exe -m pytest tests/test_caspiana_excel_builder.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.caspiana.excel_builder'`

Note: `test_master_data_sheet_has_header_and_one_row_per_record` (Step 1) and `test_master_data_sheet_includes_superseded_rows_for_reference` overlap slightly by design — both assert on row count from different angles; that's intentional, not a duplicate to remove.

- [ ] **Step 3: Write the implementation**

```python
# core/caspiana/excel_builder.py
"""Builds the Caspiana lease-abstract Excel workbook: a Master Data sheet
(one row per lease/tract, as a native Excel Table for filter dropdowns)
and a Dashboard sheet with KPI totals and section/lessee breakdown tables
(driven by formulas, since openpyxl cannot script a native PivotTable --
a person opening the file can still Insert > PivotTable off the Master
Data table for ad hoc slicing)."""
import openpyxl
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

MASTER_COLUMNS = [
    "section", "township_range", "parish", "lessor", "lessee",
    "legal_description", "gross_acres", "net_acres", "working_interest",
    "royalty", "source", "confidence", "superseded_by_lpr",
]


def _write_master_sheet(wb: openpyxl.Workbook, rows: list[dict]) -> None:
    ws = wb.active
    ws.title = "Master Data"
    ws.append(MASTER_COLUMNS)
    for row in rows:
        ws.append([row.get(col) for col in MASTER_COLUMNS])

    last_col = get_column_letter(len(MASTER_COLUMNS))
    last_row = 1 + len(rows)
    table = Table(displayName="LeaseMaster", ref=f"A1:{last_col}{last_row}")
    table.tableStyleInfo = TableStyleInfo(
        name="TableStyleMedium2", showRowStripes=True
    )
    ws.add_table(table)
    for col_idx in range(1, len(MASTER_COLUMNS) + 1):
        ws.column_dimensions[get_column_letter(col_idx)].width = 18


def _write_dashboard_sheet(wb: openpyxl.Workbook, rows: list[dict]) -> None:
    ws = wb.create_sheet("Dashboard")
    # Rows flagged superseded_by_lpr are kept in Master Data for their WI
    # detail but must not double-count acreage the LPR row already covers.
    countable = [r for r in rows if not r.get("superseded_by_lpr")]
    total_gross = sum(r.get("gross_acres") or 0 for r in countable)
    total_net = sum(r.get("net_acres") or 0 for r in countable)

    ws["A1"] = "Caspiana Little Creek -- Lease Abstract Summary"
    ws["A3"] = "Total Gross Acres"
    ws["B3"] = total_gross
    ws["A4"] = "Total Net Acres"
    ws["B4"] = total_net
    ws["A5"] = "Lease/Tract Rows (excl. superseded)"
    ws["B5"] = len(countable)

    ws["A7"] = "Net Acres by Section"
    ws["A8"], ws["B8"] = "Section", "Net Acres"
    by_section: dict[str, float] = {}
    for r in countable:
        by_section[r["section"]] = by_section.get(r["section"], 0) + (r.get("net_acres") or 0)
    for i, (section, net) in enumerate(sorted(by_section.items()), start=9):
        ws[f"A{i}"] = section
        ws[f"B{i}"] = net


def build_workbook(rows: list[dict]) -> openpyxl.Workbook:
    wb = openpyxl.Workbook()
    _write_master_sheet(wb, rows)
    _write_dashboard_sheet(wb, rows)
    return wb
```

```python
# scripts/caspiana_excel_build.py
#!/usr/bin/env python
"""Build the final Caspiana lease-abstract Excel workbook from master.csv.

Run: C:\\Users\\mapma\\AppData\\Local\\Programs\\Python\\Python311\\python.exe scripts\\caspiana_excel_build.py
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.caspiana.excel_builder import build_workbook

CASPIANA_ROOT = Path(r"C:\GIS\CLIENT\DOXA\SABINE\CASPIANA\Caspiana Little Creek T14-R16 & T13-R16")
DELIVERABLES_DIR = CASPIANA_ROOT / "Deliverables"


def main():
    df = pd.read_csv(DELIVERABLES_DIR / "master.csv")
    rows = df.to_dict(orient="records")
    wb = build_workbook(rows)
    out_path = DELIVERABLES_DIR / "Caspiana_Lease_Abstract.xlsx"
    wb.save(out_path)
    print(f"Workbook written: {out_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `C:\Users\mapma\AppData\Local\Programs\Python\Python311\python.exe -m pytest tests/test_caspiana_excel_builder.py -v`
Expected: PASS (4 tests). Then run `scripts\caspiana_excel_build.py` against the real `master.csv` from Task 9 and open the workbook in Excel to confirm the Table filter dropdowns work and add a native PivotTable + slicers off the `LeaseMaster` table for interactive section/lessee/WI-owner filtering (manual Excel step — openpyxl cannot create a live PivotTable object).

- [ ] **Step 5: Commit**

```bash
git add core/caspiana/excel_builder.py scripts/caspiana_excel_build.py tests/test_caspiana_excel_builder.py
git commit -m "feat(caspiana): add Excel workbook builder with dashboard sheet"
```

---

## Task 12: Web dashboard artifact

- [ ] **Step 1:** Load the `artifact-design` skill (and `dataviz` if charts are involved) before writing any HTML, per house rules for building Artifacts.
- [ ] **Step 2:** Write a self-contained HTML page embedding `master.csv` (converted to a JSON array) and `lease_tracts.geojson` as inline data, with a filterable/sortable table (by section, lessee, WI owner, confidence) and a simple map view rendering the tract polygons (inline SVG or Leaflet-free canvas rendering, since the Artifact CSP blocks external tile/script CDNs — render the tracts against a plain section-grid background rather than a basemap). Any KPI/summary totals shown on the page must exclude `superseded_by_lpr=True` rows, same as the Excel dashboard (Task 11) — those rows should still appear in the raw table for reference, just clearly labeled (e.g. a "superseded" badge) so they read as cross-check detail, not a second real lease.
- [ ] **Step 3:** Publish via the Artifact tool and send the user the link.

---

## Task 13: Final validation pass

- [ ] **Step 1:** Spot-check 10-15% of `master.csv` rows (weighted toward `Medium`/`High` confidence, since `Needs Review`/`Low` rows were already vision-corrected in Task 9) against a fresh direct read of their `source_file` PDF, to measure the pipeline's real-world accuracy rate on rows it trusted without a full manual pass.
- [ ] **Step 2:** Record the spot-check result (rows checked, rows correct, any corrections made) in `reconciliation_notes.md` in `DELIVERABLES_DIR`.
- [ ] **Step 3:** Confirm the per-section net-acreage reconciliation from Task 9 Step 5 is complete and any mismatches are documented, not silently resolved.
- [ ] **Step 4:** Send the user the three deliverables (`Caspiana_Lease_Abstract.xlsx`, `lease_tracts.geojson`, the web dashboard link) with a short summary of row counts by confidence level and any sections/leases still flagged for their manual review.
