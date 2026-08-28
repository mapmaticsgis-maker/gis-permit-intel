# Shelby North Area 1 Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `Shelby_North_Area1_Dashboard.html` — a single self-contained page showing Sabine's Shelby North Area 1 leasing and title position, organized around the title→leasing handoff.

**Architecture:** A small Python package reads two visually-formatted Excel status reports and five shapefiles, merges them on the `DOXA_TN` tract key (via a composite-key expander), computes six pipeline buckets plus four analytics payloads, and substitutes everything as JSON literals into an HTML template that inlines Leaflet. Output is one static file that opens by double-click.

**Tech Stack:** ArcGIS Pro Python 3 (`osgeo`/ogr+osr, `pandas`, `openpyxl`, `PIL`, `fontTools`+`brotli`), Leaflet 1.9.4, vanilla JS/CSS.

## Global Constraints

- **Interpreter:** `C:\Program Files\ArcGIS\Pro\bin\Python\envs\arcgispro-py3\python.exe`. The system Python 3.14 has a broken `openpyxl`/`numpy` import chain and no GDAL. Never `pip install` anything.
- **Working dir:** `C:\GIS\CLIENT\DOXA\SABINE\SHELBY\DASHBOARD\`.
- **Never name a scratch file `inspect.py`** — it shadows stdlib `inspect` and breaks the `numpy` import chain with a confusing circular-import error.
- **Basemaps: keyless sources only.** OSM, Esri World Imagery, Esri World Topo, None. `basemaps.cartocdn.com` returns "API KEY REQUIRED" placeholder tiles.
- **Workbook columns `H`–`O` and `W`–`AD` are a visual scale bar, not data.** Their values are not row-aligned to the tract block they describe. Never parse them. Column `A` is the authoritative status.
- **`Rejected` lease stage is suppressed** per client direction.
- **Doxa brand burgundy is exactly `#651C32`.**
- **Output must open offline.** No external requests except basemap tiles.
- Every geometry layer reprojects to EPSG:4326, `SimplifyPreserveTopology` at `0.00003`, coordinates rounded to 6 dp.

---

## File Structure

```
C:\GIS\CLIENT\DOXA\SABINE\SHELBY\DASHBOARD\
├── build_shelby_dashboard.py   # orchestration + assertions + template substitution
├── shelby/
│   ├── __init__.py
│   ├── reports.py              # workbook parsing, composite expansion, merge, pipeline buckets
│   ├── analytics.py            # funnel, title ladder, runner workload, area cross-tab, owners
│   ├── change.py               # prior-week diff (optional)
│   ├── geo.py                  # ogr loaders, reprojection, GeoJSON emit
│   └── assets.py               # logo data URIs, Gotham woff2 subset
├── tests/
│   ├── test_reports.py
│   ├── test_analytics.py
│   └── test_change.py
├── template.html
└── vendor/
    ├── leaflet.css
    ├── leaflet.js
    └── mm_logo.png
```

**Deviation from the Flatland build, deliberate:** Flatland is one 400-line script. This build has materially more parsing logic (two workbooks, composite key expansion, an optional week-over-week diff), and the expander is the one place a silent miss produces a wrong-but-plausible dashboard. Splitting it into a package makes that logic unit-testable. `geo.py` is lifted almost verbatim from Flatland.

---

### Task 1: Scaffold and vendor assets

**Files:**
- Create: `DASHBOARD/shelby/__init__.py`, `DASHBOARD/shelby/assets.py`
- Create: `DASHBOARD/tests/test_assets.py`
- Copy: `vendor/leaflet.css`, `vendor/leaflet.js`, `vendor/mm_logo.png` from `C:\GIS\CLIENT\DLS\DASHBOARD\vendor\`

**Interfaces:**
- Consumes: nothing
- Produces: `png_data_uri(path, width=None) -> str`, `gotham_woff2_data_uri(otf_path) -> str`, `sabine_logo_uri() -> str`, `doxa_logo_uri() -> str`, `mapmatics_logo_uri() -> str`

- [ ] **Step 1: Create the directory tree and copy vendor assets**

```bash
mkdir -p "C:/GIS/CLIENT/DOXA/SABINE/SHELBY/DASHBOARD/shelby" \
         "C:/GIS/CLIENT/DOXA/SABINE/SHELBY/DASHBOARD/tests" \
         "C:/GIS/CLIENT/DOXA/SABINE/SHELBY/DASHBOARD/vendor"
cp "C:/GIS/CLIENT/DLS/DASHBOARD/vendor/leaflet.css" \
   "C:/GIS/CLIENT/DLS/DASHBOARD/vendor/leaflet.js" \
   "C:/GIS/CLIENT/DLS/DASHBOARD/vendor/mm_logo.png" \
   "C:/GIS/CLIENT/DOXA/SABINE/SHELBY/DASHBOARD/vendor/"
touch "C:/GIS/CLIENT/DOXA/SABINE/SHELBY/DASHBOARD/shelby/__init__.py"
```

- [ ] **Step 2: Write the failing test**

`tests/test_assets.py`:

```python
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shelby import assets


def test_doxa_logo_is_png_data_uri():
    uri = assets.doxa_logo_uri()
    assert uri.startswith("data:image/png;base64,")
    assert len(uri) > 2000


def test_sabine_logo_is_png_data_uri():
    uri = assets.sabine_logo_uri()
    assert uri.startswith("data:image/png;base64,")
    assert len(uri) > 2000


def test_mapmatics_logo_is_png_data_uri():
    assert assets.mapmatics_logo_uri().startswith("data:image/png;base64,")


def test_gotham_subset_is_woff2_and_small():
    uri = assets.gotham_woff2_data_uri(assets.GOTHAM_BOOK)
    assert uri.startswith("data:font/woff2;base64,")
    # a Latin-basic subset of one weight should land well under 40 KB of base64
    assert len(uri) < 40000
```

- [ ] **Step 3: Run test to verify it fails**

Run:
```bash
cd "C:/GIS/CLIENT/DOXA/SABINE/SHELBY/DASHBOARD" && "C:/Program Files/ArcGIS/Pro/bin/Python/envs/arcgispro-py3/python.exe" -m pytest tests/test_assets.py -v
```
Expected: FAIL, `ModuleNotFoundError: No module named 'shelby.assets'`

- [ ] **Step 4: Implement `shelby/assets.py`**

```python
# -*- coding: utf-8 -*-
"""Logo and font embedding for the Shelby dashboard."""

import base64
import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
VENDOR = os.path.join(HERE, "..", "vendor")

DOXA_ASSETS = r"C:\Users\mapma\Downloads\DOXA_LogoAssets_SHARE\Assets"
DOXA_WHT = os.path.join(DOXA_ASSETS, "DOXA_Logo_Full_WHT.png")
GOTHAM_BOOK = os.path.join(DOXA_ASSETS, "Gotham-Book.otf")
GOTHAM_MEDIUM = os.path.join(DOXA_ASSETS, "Gotham-Medium.otf")
GOTHAM_BOLD = os.path.join(DOXA_ASSETS, "Gotham-Bold.otf")
SABINE_JPG = r"C:\GIS\LOGO\SABINE.jpg"
MM_LOGO = os.path.join(VENDOR, "mm_logo.png")

# Latin basic + the punctuation the page actually uses.
SUBSET_CHARS = (
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789"
    " .,:;!?%&()[]{}/\\-–—_'\"+#*=<>@|"
)


def _png_uri(raw):
    return "data:image/png;base64," + base64.b64encode(raw).decode("ascii")


def png_data_uri(path, width=None):
    """Load an image, optionally downscale to *width* px, return a PNG data URI."""
    from PIL import Image
    im = Image.open(path).convert("RGBA")
    if width and im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="PNG", optimize=True)
    return _png_uri(buf.getvalue())


def doxa_logo_uri():
    """White Doxa wordmark, for the burgundy header bar."""
    return png_data_uri(DOXA_WHT, width=420)


def sabine_logo_uri():
    """Sabine mark. The source is a JPEG of the logo on white; the mark has blue
    gradients that fringe badly if the white is keyed out, so it is composited
    onto an opaque white chip and the chip is styled with a border in CSS."""
    from PIL import Image
    im = Image.open(SABINE_JPG).convert("RGB")
    # crop away the JPEG's generous white margin before downscaling
    bg = Image.new("RGB", im.size, (255, 255, 255))
    from PIL import ImageChops
    diff = ImageChops.difference(im, bg).convert("L")
    box = diff.getbbox()
    if box:
        im = im.crop(box)
    w = 300
    im = im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="PNG", optimize=True)
    return _png_uri(buf.getvalue())


def mapmatics_logo_uri():
    return png_data_uri(MM_LOGO, width=260)


def gotham_woff2_data_uri(otf_path):
    """Subset one Gotham weight to Latin basic and return it as a woff2 data URI."""
    from fontTools.subset import Subsetter, Options
    from fontTools.ttLib import TTFont

    font = TTFont(otf_path)
    opts = Options()
    opts.layout_features = ["kern", "liga"]
    opts.desubroutinize = True
    opts.notdef_outline = True
    sub = Subsetter(options=opts)
    sub.populate(text=SUBSET_CHARS)
    sub.subset(font)

    font.flavor = "woff2"
    buf = io.BytesIO()
    font.save(buf)
    font.close()
    return "data:font/woff2;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
```

- [ ] **Step 5: Run tests to verify they pass**

Run:
```bash
cd "C:/GIS/CLIENT/DOXA/SABINE/SHELBY/DASHBOARD" && "C:/Program Files/ArcGIS/Pro/bin/Python/envs/arcgispro-py3/python.exe" -m pytest tests/test_assets.py -v
```
Expected: 4 passed.

If `test_gotham_subset_is_woff2_and_small` fails on size, print `len(uri)` and check whether `opts.desubroutinize` is set — an unsubroutinized CFF is several times larger.

- [ ] **Step 6: Commit**

```bash
cd "C:/GIS/permit_intel" && git add -A && git commit -m "Shelby dashboard: scaffold + logo/font embedding"
```

---

### Task 2: Workbook parser

**Files:**
- Create: `DASHBOARD/shelby/reports.py`
- Create: `DASHBOARD/tests/test_reports.py`

**Interfaces:**
- Consumes: nothing
- Produces: `parse_workbook(path) -> "OrderedDict[str, dict]"` keyed by the raw workbook tract key. Each record: `{"key": str, "status": str, "gma": str, "mi": str, "nma": str, "ttl_com": str, "lse_com": str, "owners": [{"name": str, "addr": str}]}`. Also `clean(v) -> str`.

- [ ] **Step 1: Write the failing test**

`tests/test_reports.py`:

```python
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shelby import reports

CONSOLIDATED = (r"C:\Users\mapma\Downloads"
                r"\20260820 CONSOLIDATED BUYERS-Lease Status Report-Shelby NTH Area 1.xlsx")
TITLE = (r"C:\Users\mapma\Downloads"
         r"\20260820 TITLE WORK-Lease Status Report-Shelby NTH Area 1.xlsx")


def test_clean_normalizes_blanks_and_newlines():
    assert reports.clean(None) == ""
    assert reports.clean("  ") == ""
    assert reports.clean("nan") == ""
    assert reports.clean("Title\n26%-75%") == "Title 26%-75%"


def test_consolidated_yields_161_tract_keys():
    recs = reports.parse_workbook(CONSOLIDATED)
    assert len(recs) == 161


def test_title_yields_161_tract_keys():
    recs = reports.parse_workbook(TITLE)
    assert len(recs) == 161


def test_first_tract_block_captures_status_gma_and_all_owners():
    recs = reports.parse_workbook(CONSOLIDATED)
    r = recs["163-001"]
    assert r["status"] == "Negotiating"
    assert r["gma"] == "87.12"
    assert len(r["owners"]) == 5
    assert r["owners"][0]["name"] == "Michael Shane Powdrill"
    assert "Joaquin, TX 75954" in r["owners"][0]["addr"]


def test_title_workbook_captures_runner_in_comments_column():
    recs = reports.parse_workbook(TITLE)
    r = recs["284-001"]
    assert r["status"] == "Title 76%-99%"
    assert r["ttl_com"] == "Kevin Running"


def test_scale_bar_columns_are_not_parsed():
    """Cols H-O / W-AD are a visual bar whose values are not row-aligned to the
    block they describe; tract 163-002's bar value sits two rows above its block.
    Status must come from column A only."""
    recs = reports.parse_workbook(CONSOLIDATED)
    assert recs["163-002"]["status"] == "Attempting to Contact"
    assert recs["163-001"]["status"] == "Negotiating"
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
cd "C:/GIS/CLIENT/DOXA/SABINE/SHELBY/DASHBOARD" && "C:/Program Files/ArcGIS/Pro/bin/Python/envs/arcgispro-py3/python.exe" -m pytest tests/test_reports.py -v
```
Expected: FAIL, `ModuleNotFoundError: No module named 'shelby.reports'`

- [ ] **Step 3: Implement the parser in `shelby/reports.py`**

```python
# -*- coding: utf-8 -*-
"""Parsing and merging of the two Shelby North Area 1 status workbooks.

Both workbooks are visually formatted, not tabular:
  row 1  title
  row 2  status colour key
  row 4  column header
  row 6+ data

Columns: A STATUS | B TRACT NO. | C MINERAL OWNER | D ADDRESS | E TRACT GMA'S
         F MINERAL INTEREST | G LESSOR NMA'S | AF TITLE COMMENTS | AG LEASE COMMENTS

Columns H-O and W-AD are a visual scale bar. Their values are NOT reliably
row-aligned to the tract block they describe -- tract 163-002's bar value lands
two rows above its own block -- so they are never parsed. Column A is the
authoritative status.
"""

from collections import OrderedDict

DATA_START_ROW = 6

COL_STATUS, COL_TRACT, COL_OWNER, COL_ADDR = 1, 2, 3, 4
COL_GMA, COL_MI, COL_NMA = 5, 6, 7
COL_TTL_COM, COL_LSE_COM = 32, 33


def clean(v):
    """Normalize a cell to a stripped single-line string; blanks become ''."""
    if v is None:
        return ""
    s = str(v).replace("\n", " ").strip()
    while "  " in s:
        s = s.replace("  ", " ")
    return "" if s.lower() in ("nan", "nat", "none") else s


def parse_workbook(path):
    """Return OrderedDict {raw workbook tract key: record}.

    A tract block starts on any row where column B is non-empty. Owner rows
    follow beneath it with only C/D populated. Blocks are separated by a blank row.
    """
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.active

    tracts = OrderedDict()
    cur = None
    for row in range(DATA_START_ROW, ws.max_row + 1):
        def g(col):
            return clean(ws.cell(row, col).value)

        key = g(COL_TRACT)
        if key:
            cur = {
                "key": key,
                "status": g(COL_STATUS),
                "gma": g(COL_GMA),
                "mi": g(COL_MI),
                "nma": g(COL_NMA),
                "ttl_com": g(COL_TTL_COM),
                "lse_com": g(COL_LSE_COM),
                "owners": [],
            }
            tracts[key] = cur
        if cur is not None:
            name = g(COL_OWNER)
            if name:
                cur["owners"].append({"name": name, "addr": g(COL_ADDR)})
    wb.close()
    return tracts
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
cd "C:/GIS/CLIENT/DOXA/SABINE/SHELBY/DASHBOARD" && "C:/Program Files/ArcGIS/Pro/bin/Python/envs/arcgispro-py3/python.exe" -m pytest tests/test_reports.py -v
```
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
cd "C:/GIS/permit_intel" && git add -A && git commit -m "Shelby dashboard: workbook parser"
```

---

### Task 3: Composite key expander

This is the highest-risk function in the build. A miss here produces a dashboard that looks right but silently drops tracts.

**Files:**
- Modify: `DASHBOARD/shelby/reports.py`
- Modify: `DASHBOARD/tests/test_reports.py`

**Interfaces:**
- Consumes: nothing
- Produces: `expand_key(key, known) -> list[str]` where `known` is a set/dict of valid `DOXA_TN` values.

- [ ] **Step 1: Write the failing test — all 11 known composite strings**

Append to `tests/test_reports.py`:

```python
# The 161 real DOXA_TN values are the authority for what a key may expand to.
KNOWN = set()
for _fam, _n in [("163", 15), ("230", 3), ("284", 8), ("459", 52),
                 ("520", 11), ("521", 2), ("738", 2), ("840", 6)]:
    KNOWN |= {"%s-%03d" % (_fam, i) for i in range(1, _n + 1)}
KNOWN |= {"631-%03d" % i for i in range(1, 49)} - {"631-043"}
KNOWN |= {"365-274-%03d" % i for i in range(1, 9)}
KNOWN |= {"365-592-%03d" % i for i in range(1, 8)}


def test_plain_key_passes_through():
    assert reports.expand_key("163-001", KNOWN) == ["163-001"]


def test_two_part_family_key_passes_through():
    assert reports.expand_key("365-274-001", KNOWN) == ["365-274-001"]


def test_expands_ampersand_and_comma_list():
    assert reports.expand_key("163-002 & 004,007,008,009", KNOWN) == [
        "163-002", "163-004", "163-007", "163-008", "163-009"]


def test_expands_includes_phrasing():
    assert reports.expand_key("230-001 includes 230-002 & 230-003", KNOWN) == [
        "230-001", "230-002", "230-003"]


def test_expands_parenthetical_backreference():
    assert reports.expand_key("230-002 (with 230-001)", KNOWN) == ["230-002", "230-001"]


def test_expands_also_part_of_phrasing():
    assert reports.expand_key("459-006 also part of 459-003", KNOWN) == [
        "459-006", "459-003"]


def test_expands_five_tract_title_package():
    assert reports.expand_key("459-015 & 018,034,038,051", KNOWN) == [
        "459-015", "459-018", "459-034", "459-038", "459-051"]


def test_expands_seven_tract_leasing_package():
    assert reports.expand_key("520-001, 004, 005, 006, 008, 010 & 011", KNOWN) == [
        "520-001", "520-004", "520-005", "520-006", "520-008", "520-010", "520-011"]


def test_expands_four_tract_package():
    assert reports.expand_key("520-002, 005, 007 & 009", KNOWN) == [
        "520-002", "520-005", "520-007", "520-009"]


def test_expands_package_with_partial_tract_notation():
    assert reports.expand_key("520-003 & 004, pt 005, 006, 008, 010, 011", KNOWN) == [
        "520-003", "520-004", "520-005", "520-006", "520-008", "520-010", "520-011"]


def test_expands_pt_suffix_key():
    assert reports.expand_key("520-005 pt", KNOWN) == ["520-005"]


def test_expands_key_that_does_not_start_with_its_family():
    """'Partial Tract Comprised of 520-001 & 002' -- the family prefix must be
    taken from the first full tract ID found anywhere in the string, not from
    the string's leading characters."""
    assert reports.expand_key("Partial Tract Comprised of 520-001 & 002", KNOWN) == [
        "520-001", "520-002"]


def test_unresolvable_key_returns_empty():
    assert reports.expand_key("no tract here", KNOWN) == []


def test_every_workbook_key_resolves():
    """Both workbooks must expand to 161/161 coverage with nothing unresolved."""
    for path in (CONSOLIDATED, TITLE):
        recs = reports.parse_workbook(path)
        unresolved = [k for k in recs if not reports.expand_key(k, KNOWN)]
        assert unresolved == [], "unresolved keys in %s: %s" % (path, unresolved)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
cd "C:/GIS/CLIENT/DOXA/SABINE/SHELBY/DASHBOARD" && "C:/Program Files/ArcGIS/Pro/bin/Python/envs/arcgispro-py3/python.exe" -m pytest tests/test_reports.py -v -k expand
```
Expected: FAIL, `AttributeError: module 'shelby.reports' has no attribute 'expand_key'`

- [ ] **Step 3: Implement `expand_key`**

Add to `shelby/reports.py`:

```python
import re

# 459-012 or the two-part 365-274-001
FULL_TN_RE = re.compile(r"\b(\d{3}(?:-\d{3})?)-(\d{3})\b")
BARE_NUM_RE = re.compile(r"\b(\d{3})\b")


def expand_key(key, known):
    """Expand a workbook tract key into the list of real DOXA_TN values it names.

    11 of the 161 workbook keys name several tracts at once, because title work
    and leasing are assigned in packages:

        '163-002 & 004,007,008,009'
        '520-003 & 004, pt 005, 006, 008, 010, 011'
        'Partial Tract Comprised of 520-001 & 002'

    Rule, in order:
      1. If the key is already a DOXA_TN, return it.
      2. Find the FIRST full tract ID anywhere in the string. Its leading
         portion is the family prefix. Taking the family from the first full ID
         rather than from the string's leading characters is what makes
         'Partial Tract Comprised of 520-001 & 002' resolve -- that key does not
         begin with its family.
      3. Collect every bare 3-digit number in the string, prefix each with the
         family, keep those that exist, preserving order and de-duplicating.
    """
    k = (key or "").strip()
    if k in known:
        return [k]

    m = FULL_TN_RE.search(k)
    if not m:
        return []
    family = m.group(1)

    out = []
    for num in BARE_NUM_RE.findall(k):
        cand = "%s-%s" % (family, num)
        if cand in known and cand not in out:
            out.append(cand)
    return out
```

Note on why `BARE_NUM_RE` over the whole string is safe: the family segment of a
full ID is 3 digits too, so `520-001` yields both `520` and `001`. Prefixing
`520` gives `520-520`, which is not in `known` and is dropped. The filter against
`known` is what makes the loose scan correct.

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
cd "C:/GIS/CLIENT/DOXA/SABINE/SHELBY/DASHBOARD" && "C:/Program Files/ArcGIS/Pro/bin/Python/envs/arcgispro-py3/python.exe" -m pytest tests/test_reports.py -v
```
Expected: 20 passed.

- [ ] **Step 5: Commit**

```bash
cd "C:/GIS/permit_intel" && git add -A && git commit -m "Shelby dashboard: composite tract key expander + full test coverage"
```

---

### Task 4: Merge and pipeline bucketing

**Files:**
- Modify: `DASHBOARD/shelby/reports.py`
- Modify: `DASHBOARD/tests/test_reports.py`

**Interfaces:**
- Consumes: `parse_workbook`, `expand_key`
- Produces:
  - `LEASE_LABEL: dict[str, str]`, `TITLE_LABEL: dict[str, str]`, `SPLIT_STATUS: dict[str, tuple[str, str]]`
  - `merge(shp_attrs, consolidated, title) -> dict[str, dict]` — one record per `DOXA_TN`, keys: `tn area ac lse_code ttl_code lse_status ttl_status runner gma owners ttl_com lse_com bucket`
  - `pipeline_bucket(rec) -> str` returning one of the six `BUCKET_*` constants
  - `strip_runner(s) -> str`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_reports.py`:

```python
def test_strip_runner_removes_trailing_running():
    assert reports.strip_runner("Patrick Running") == "Patrick"
    assert reports.strip_runner("Luke running") == "Luke"
    assert reports.strip_runner("Philip running") == "Philip"
    assert reports.strip_runner("") == ""


def _fake(**kw):
    base = dict(tn="X-001", area="OPEN", ac=10.0, lse_code=None, ttl_code=None,
                lse_status="", ttl_status="", runner="", gma="", owners=[],
                ttl_com="", lse_com="")
    base.update(kw)
    return base


def test_bucket_untouched():
    assert reports.pipeline_bucket(_fake()) == reports.BUCKET_UNTOUCHED


def test_bucket_ready_to_lease_when_title_done_and_no_leasing():
    r = _fake(ttl_code="76", ttl_status="Title 76%-99%")
    assert reports.pipeline_bucket(r) == reports.BUCKET_READY


def test_bucket_title_on_hold_wins_over_everything():
    r = _fake(ttl_code="RT", lse_status="Negotiating", lse_code="NEG_AC")
    assert reports.pipeline_bucket(r) == reports.BUCKET_ON_HOLD


def test_bucket_leasing_without_current_title_assignment():
    r = _fake(lse_code="NEG", lse_status="Negotiating")
    assert reports.pipeline_bucket(r) == reports.BUCKET_LEASE_NO_TITLE


def test_bucket_both_active():
    r = _fake(lse_code="NEG", lse_status="Negotiating",
              ttl_code="76", ttl_status="Title 76%-99%")
    assert reports.pipeline_bucket(r) == reports.BUCKET_BOTH


def test_bucket_title_in_progress_below_76():
    r = _fake(ttl_code="26", ttl_status="Title 26%-75%")
    assert reports.pipeline_bucket(r) == reports.BUCKET_TITLE_WIP
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
cd "C:/GIS/CLIENT/DOXA/SABINE/SHELBY/DASHBOARD" && "C:/Program Files/ArcGIS/Pro/bin/Python/envs/arcgispro-py3/python.exe" -m pytest tests/test_reports.py -v -k "bucket or runner"
```
Expected: FAIL, `AttributeError: module 'shelby.reports' has no attribute 'strip_runner'`

- [ ] **Step 3: Implement merge + bucketing**

Add to `shelby/reports.py`:

```python
# ---------------------------------------------------------------- vocabulary --
# Fills come from the workbook colour key (row 2) so the dashboard, the
# workbooks and the two PDF status maps read identically.
LEASE_LABEL = {
    "AC": "Attempting to Contact",
    "CM": "Contact Made",
    "NEG": "Negotiating",
    "COMM": "Committed",
    "SIGN": "Signed",
    "LIH": "Lease in Hand",
    "LPR": "LPR Complete",
    "RT": "Title On Hold",
}
LEASE_FILL = {
    "Attempting to Contact": "#CCECFF",
    "Contact Made": "#66CCFF",
    "Negotiating": "#FFC000",
    "Committed": "#00FF00",
    "Signed": "#FFFF66",
    "Lease in Hand": "#9CE89C",
    "LPR Complete": "#4FBF4F",
    "Title On Hold": "#FFA07A",
}
# Full runway shown in the funnel; unused stages render greyed.
# 'Rejected' exists in the workbook key but is suppressed per client direction.
LEASE_STAGES = ["Attempting to Contact", "Contact Made", "Negotiating",
                "Committed", "Signed", "Lease in Hand", "LPR Complete"]

TITLE_LABEL = {"RT": "Title On Hold", "0": "Title 0%-25%", "26": "Title 26%-75%",
               "76": "Title 76%-99%", "100": "Title 100%"}
TITLE_FILL = {"Title On Hold": "#FFA07A", "Title 0%-25%": "#FF66CC",
              "Title 26%-75%": "#00CCFF", "Title 76%-99%": "#99FF99",
              "Title 100%": "#1B7A1B"}
TITLE_STAGES = ["Title On Hold", "Title 0%-25%", "Title 26%-75%",
                "Title 76%-99%", "Title 100%"]

# Tracts carrying two statuses at once -> diagonal hatch of the two fills,
# matching how they read on the ArcMap exports.
SPLIT_STATUS = {
    "NEG_OPEN": ("Negotiating", None),
    "NEG_AC": ("Negotiating", "Attempting to Contact"),
    "COMM_RC_AC": ("Committed", "Attempting to Contact"),
}

AREA_FILL = {
    "OPEN": "#8CC63F",
    "POTENTIAL DEEP RIGHTS OPEN": "#E8C39E",
    "UNIT W LAPSED PRODUCTION": "#B5A8D5",
}

# --------------------------------------------------------------- pipeline -----
BUCKET_UNTOUCHED = "Untouched - no title, no leasing"
BUCKET_TITLE_WIP = "Title in progress (<76%), no leasing"
BUCKET_READY = "Ready to lease - title >=76%, leasing not started"
BUCKET_BOTH = "Title running + leasing active"
BUCKET_LEASE_NO_TITLE = "Leasing, no current title assignment"
BUCKET_ON_HOLD = "Blocked - title on hold"

BUCKET_ORDER = [BUCKET_UNTOUCHED, BUCKET_TITLE_WIP, BUCKET_READY,
                BUCKET_BOTH, BUCKET_LEASE_NO_TITLE, BUCKET_ON_HOLD]

BUCKET_FILL = {
    BUCKET_UNTOUCHED: "#D8D8D8",
    BUCKET_TITLE_WIP: "#00CCFF",
    BUCKET_READY: "#00B050",
    BUCKET_BOTH: "#FFC000",
    BUCKET_LEASE_NO_TITLE: "#B48EAD",
    BUCKET_ON_HOLD: "#FFA07A",
}

TITLE_DONE_STATUSES = {"Title 76%-99%", "Title 100%", "Open"}
RUNNER_RE = re.compile(r"\s*running\s*$", re.I)


def strip_runner(s):
    """'Patrick Running' -> 'Patrick'."""
    return RUNNER_RE.sub("", (s or "").strip()).strip()


def _on_hold(r):
    return (r["ttl_code"] == "RT" or r["lse_code"] == "RT"
            or r["ttl_status"] == "Title On Hold" or r["lse_status"] == "Title On Hold")


def _has_title(r):
    return bool(r["ttl_status"]) or r["ttl_code"] in ("0", "26", "76", "100", "RT")


def _title_done(r):
    return r["ttl_code"] in ("76", "100") or r["ttl_status"] in TITLE_DONE_STATUSES


def _has_lease(r):
    return bool(r["lse_status"]) or bool(r["lse_code"])


def pipeline_bucket(r):
    """Place a merged tract record into exactly one of the six pipeline buckets.

    Order matters: 'on hold' is checked first because a blocked tract is blocked
    regardless of what else is recorded against it.
    """
    if _on_hold(r):
        return BUCKET_ON_HOLD
    if _title_done(r) and not _has_lease(r):
        return BUCKET_READY
    if _has_lease(r) and not _has_title(r):
        return BUCKET_LEASE_NO_TITLE
    if _has_lease(r) and _has_title(r):
        return BUCKET_BOTH
    if _has_title(r):
        return BUCKET_TITLE_WIP
    return BUCKET_UNTOUCHED


def merge(shp_attrs, consolidated, title):
    """Combine shapefile attributes with both workbooks into one record per tract.

    *shp_attrs* is {DOXA_TN: {"area":..., "ac":..., "lse_code":..., "ttl_code":...}}.
    Statuses on a composite key apply to every tract that key expands to.
    """
    known = set(shp_attrs)
    out = {}
    for tn, a in shp_attrs.items():
        out[tn] = {
            "tn": tn, "area": a["area"], "ac": a["ac"],
            "lse_code": a["lse_code"], "ttl_code": a["ttl_code"],
            "lse_status": "", "ttl_status": "", "runner": "",
            "gma": "", "owners": [], "ttl_com": "", "lse_com": "",
            "ttl_group": "", "lse_group": "",
        }

    for key, rec in consolidated.items():
        for tn in expand_key(key, known):
            r = out[tn]
            if rec["status"]:
                r["lse_status"] = rec["status"]
            if rec["owners"] and len(rec["owners"]) > len(r["owners"]):
                r["owners"] = rec["owners"]
            if rec["gma"] and not r["gma"]:
                r["gma"] = rec["gma"]
            if rec["lse_com"]:
                r["lse_com"] = rec["lse_com"]
            if rec["ttl_com"]:
                r["ttl_com"] = rec["ttl_com"]
            if key != tn:
                r["lse_group"] = key

    for key, rec in title.items():
        for tn in expand_key(key, known):
            r = out[tn]
            if rec["status"]:
                r["ttl_status"] = rec["status"]
            if rec["ttl_com"]:
                r["runner"] = strip_runner(rec["ttl_com"])
            if key != tn:
                r["ttl_group"] = key

    for r in out.values():
        r["bucket"] = pipeline_bucket(r)
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
cd "C:/GIS/CLIENT/DOXA/SABINE/SHELBY/DASHBOARD" && "C:/Program Files/ArcGIS/Pro/bin/Python/envs/arcgispro-py3/python.exe" -m pytest tests/test_reports.py -v
```
Expected: 27 passed.

- [ ] **Step 5: Commit**

```bash
cd "C:/GIS/permit_intel" && git add -A && git commit -m "Shelby dashboard: status vocabulary, merge, pipeline bucketing"
```

---

### Task 5: Geometry loaders

**Files:**
- Create: `DASHBOARD/shelby/geo.py`

**Interfaces:**
- Consumes: nothing
- Produces: `transform_to_wgs84(layer)`, `geom_to_geojson(geom, ct)`, `load_features(path, layer_name=None, prop_map=None, keep=None, where=None, bbox=None) -> list[dict]`, `load_tract_attrs(path) -> dict`, `bounds_of(features) -> [xmin, ymin, xmax, ymax]`, `fc(features)`, `minjson(obj)`

- [ ] **Step 1: Implement `shelby/geo.py`**

Lifted from `C:\GIS\CLIENT\DLS\DASHBOARD\build_flatland_dashboard.py` with a
`bbox` filter added for the 39,028-feature statewide abstract layer.

```python
# -*- coding: utf-8 -*-
"""Shapefile loading, reprojection and GeoJSON emission."""

import json
from osgeo import ogr, osr

ogr.UseExceptions()
osr.UseExceptions()

SIMPLIFY_DEG = 0.00003   # ~3 m, topology preserving
COORD_PREC = 6


def _wgs84():
    sr = osr.SpatialReference()
    sr.ImportFromEPSG(4326)
    sr.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)   # lon, lat
    return sr


WGS84 = _wgs84()


def transform_to_wgs84(layer):
    src = layer.GetSpatialRef()
    if src is None:
        raise RuntimeError("layer has no spatial reference: " + layer.GetName())
    src = src.Clone()
    src.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    if src.IsSame(WGS84):
        return None
    return osr.CoordinateTransformation(src, WGS84)


def geom_to_geojson(geom, ct):
    g = geom.Clone()
    if ct is not None:
        g.Transform(ct)
    if SIMPLIFY_DEG:
        s = g.SimplifyPreserveTopology(SIMPLIFY_DEG)
        if s is not None and not s.IsEmpty():
            g = s
    return json.loads(g.ExportToJson(options=["COORDINATE_PRECISION=%d" % COORD_PREC]))


def _clean(v):
    if v is None:
        return ""
    return str(v).strip() if isinstance(v, str) else v


def load_features(path, layer_name=None, prop_map=None, keep=None,
                  where=None, bbox=None):
    """Load a layer -> list of GeoJSON features in WGS84.

    bbox is (minx, miny, maxx, maxy) in the LAYER's own CRS; it is applied as a
    spatial filter before reprojection, which is what keeps the 39,028-feature
    statewide abstract layer manageable.
    """
    ds = ogr.Open(path)
    if ds is None:
        raise RuntimeError("cannot open " + path)
    layer = ds.GetLayerByName(layer_name) if layer_name else ds.GetLayer(0)
    if where:
        layer.SetAttributeFilter(where)
    if bbox:
        layer.SetSpatialFilterRect(*bbox)
    ct = transform_to_wgs84(layer)
    defn = layer.GetLayerDefn()
    src_fields = [defn.GetFieldDefn(i).GetName() for i in range(defn.GetFieldCount())]

    feats = []
    for feat in layer:
        g = feat.GetGeometryRef()
        if g is None or g.IsEmpty():
            continue
        props = {}
        if prop_map:
            for sf, ok in prop_map.items():
                if sf in src_fields:
                    props[ok] = _clean(feat.GetField(sf))
        if keep and not keep(props):
            continue
        feats.append({"type": "Feature", "properties": props,
                      "geometry": geom_to_geojson(g, ct)})
    ds = None
    return feats


def load_tract_attrs(path):
    """DOXA_TRACTS.shp -> ({DOXA_TN: attrs}, {DOXA_TN: geometry})."""
    ds = ogr.Open(path)
    if ds is None:
        raise RuntimeError("cannot open " + path)
    layer = ds.GetLayer(0)
    ct = transform_to_wgs84(layer)
    attrs, geoms = {}, {}
    for feat in layer:
        g = feat.GetGeometryRef()
        if g is None or g.IsEmpty():
            continue
        tn = _clean(feat.GetField("DOXA_TN"))
        if not tn:
            continue
        attrs[tn] = {
            "area": _clean(feat.GetField("AREA")),
            "ac": round(feat.GetField("GIS_AREA") or 0.0, 2),
            "legal_ac": feat.GetField("LEGAL_AREA"),
            "surface_owner": _clean(feat.GetField("OWNER_NAME")),
            "legal_desc": _clean(feat.GetField("LEGAL_DESC")),
            "lse_code": feat.GetField("LSE_STAT"),
            "ttl_code": feat.GetField("STATUS"),
        }
        geoms[tn] = geom_to_geojson(g, ct)
    ds = None
    return attrs, geoms


def bounds_of(features):
    xmin = ymin = 1e18
    xmax = ymax = -1e18

    def walk(coords):
        nonlocal xmin, ymin, xmax, ymax
        if not coords:
            return
        if isinstance(coords[0], (int, float)):
            x, y = coords[0], coords[1]
            xmin, xmax = min(xmin, x), max(xmax, x)
            ymin, ymax = min(ymin, y), max(ymax, y)
        else:
            for c in coords:
                walk(c)

    for f in features:
        g = f.get("geometry")
        if g:
            walk(g.get("coordinates"))
    return [xmin, ymin, xmax, ymax]


def fc(features):
    return {"type": "FeatureCollection", "features": features}


def minjson(obj):
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)
```

- [ ] **Step 2: Verify the loaders against the real data**

Run (save as `tests/smoke_geo.py`, not `inspect.py`):

```bash
cd "C:/GIS/CLIENT/DOXA/SABINE/SHELBY/DASHBOARD" && "C:/Program Files/ArcGIS/Pro/bin/Python/envs/arcgispro-py3/python.exe" -c "
import sys; sys.path.insert(0,'.')
from shelby import geo
a,g = geo.load_tract_attrs(r'C:\GIS\CLIENT\DOXA\SABINE\SHELBY\DOXA_TRACTS.shp')
print('tracts', len(a), len(g))
print('bounds', [round(x,4) for x in geo.bounds_of([{'geometry':v} for v in g.values()])])
u = geo.load_features(r'C:\GIS\CLIENT\DOXA\SABINE\SHELBY\SHELBY_UNITS.shp',
                      prop_map={'unit_nm':'unit_nm','operator':'operator','wellstat':'wellstat','acres':'acres'})
print('units', len(u))
"
```
Expected: `tracts 161 161`, a bounds box around `[-94.15, 31.85, -94.02, 31.98]`, `units 20`.

- [ ] **Step 3: Commit**

```bash
cd "C:/GIS/permit_intel" && git add -A && git commit -m "Shelby dashboard: geometry loaders"
```

---

### Task 6: Analytics payloads

**Files:**
- Create: `DASHBOARD/shelby/analytics.py`
- Create: `DASHBOARD/tests/test_analytics.py`

**Interfaces:**
- Consumes: `reports.merge` output, `reports.BUCKET_*`, `reports.LEASE_STAGES`, `reports.TITLE_STAGES`
- Produces: `build_payload(merged) -> dict` with keys `pipeline`, `funnel`, `title_ladder`, `runners`, `areas`, `owners`, `totals`

- [ ] **Step 1: Write the failing test — against the real merged data**

`tests/test_analytics.py`:

```python
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shelby import analytics, geo, reports

SHP = r"C:\GIS\CLIENT\DOXA\SABINE\SHELBY\DOXA_TRACTS.shp"
CONSOLIDATED = (r"C:\Users\mapma\Downloads"
                r"\20260820 CONSOLIDATED BUYERS-Lease Status Report-Shelby NTH Area 1.xlsx")
TITLE = (r"C:\Users\mapma\Downloads"
         r"\20260820 TITLE WORK-Lease Status Report-Shelby NTH Area 1.xlsx")


def _merged():
    attrs, _ = geo.load_tract_attrs(SHP)
    return reports.merge(attrs, reports.parse_workbook(CONSOLIDATED),
                         reports.parse_workbook(TITLE))


def test_all_161_tracts_merge():
    assert len(_merged()) == 161


def test_pipeline_bucket_counts_match_the_spec():
    p = {row["bucket"]: row for row in analytics.build_payload(_merged())["pipeline"]}
    assert p[reports.BUCKET_UNTOUCHED]["tracts"] == 101
    assert p[reports.BUCKET_TITLE_WIP]["tracts"] == 4
    assert p[reports.BUCKET_READY]["tracts"] == 9
    assert p[reports.BUCKET_BOTH]["tracts"] == 10
    assert p[reports.BUCKET_LEASE_NO_TITLE]["tracts"] == 31
    assert p[reports.BUCKET_ON_HOLD]["tracts"] == 6


def test_ready_to_lease_queue_names_its_nine_tracts():
    p = {row["bucket"]: row for row in analytics.build_payload(_merged())["pipeline"]}
    ready = p[reports.BUCKET_READY]
    assert sorted(ready["tns"]) == [
        "284-001", "284-002", "284-003", "284-004", "284-005",
        "284-006", "284-007", "284-008", "365-274-001"]
    assert round(ready["ac"]) == 237


def test_blocked_queue_names_its_six_tracts():
    p = {row["bucket"]: row for row in analytics.build_payload(_merged())["pipeline"]}
    assert sorted(p[reports.BUCKET_ON_HOLD]["tns"]) == [
        "163-006", "459-015", "459-018", "459-034", "459-038", "459-051"]


def test_area_cross_tab_matches_the_master_map():
    areas = {a["area"]: a for a in analytics.build_payload(_merged())["areas"]}
    assert areas["OPEN"]["tracts"] == 57
    assert areas["POTENTIAL DEEP RIGHTS OPEN"]["tracts"] == 33
    assert areas["UNIT W LAPSED PRODUCTION"]["tracts"] == 71
    assert areas["OPEN"]["engaged_tracts"] == 2
    assert areas["UNIT W LAPSED PRODUCTION"]["engaged_tracts"] == 38


def test_runner_workload():
    runners = {r["name"]: r for r in analytics.build_payload(_merged())["runners"]}
    assert runners["Kevin"]["tracts"] == 8
    assert runners["Richard"]["tracts"] == 7
    assert runners["Patrick"]["tracts"] == 5
    assert runners["Luke"]["tracts"] == 5
    assert runners["Philip"]["tracts"] == 1


def test_funnel_shows_every_stage_including_unused_ones():
    funnel = analytics.build_payload(_merged())["funnel"]
    assert [s["stage"] for s in funnel] == reports.LEASE_STAGES
    unused = [s for s in funnel if s["stage"] == "Lease in Hand"][0]
    assert unused["tracts"] == 0


def test_rejected_stage_is_suppressed():
    stages = [s["stage"] for s in analytics.build_payload(_merged())["funnel"]]
    assert "Rejected" not in stages


def test_owner_roster_totals_128_records():
    owners = analytics.build_payload(_merged())["owners"]
    assert sum(len(t["owners"]) for t in owners) == 128
    first = [t for t in owners if t["tn"] == "163-001"][0]
    assert len(first["owners"]) == 5


def test_totals():
    t = analytics.build_payload(_merged())["totals"]
    assert t["tracts"] == 161
    assert round(t["ac"]) == 4237
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
cd "C:/GIS/CLIENT/DOXA/SABINE/SHELBY/DASHBOARD" && "C:/Program Files/ArcGIS/Pro/bin/Python/envs/arcgispro-py3/python.exe" -m pytest tests/test_analytics.py -v
```
Expected: FAIL, `ModuleNotFoundError: No module named 'shelby.analytics'`

- [ ] **Step 3: Implement `shelby/analytics.py`**

```python
# -*- coding: utf-8 -*-
"""Analytics payloads for the five dashboard tabs."""

from collections import defaultdict

from . import reports


def _engaged(r):
    return bool(r["lse_status"]) or bool(r["lse_code"])


def _pipeline(merged):
    by = defaultdict(list)
    for r in merged.values():
        by[r["bucket"]].append(r)
    rows = []
    for b in reports.BUCKET_ORDER:
        sel = by.get(b, [])
        rows.append({
            "bucket": b,
            "tracts": len(sel),
            "ac": round(sum(r["ac"] for r in sel), 1),
            "fill": reports.BUCKET_FILL[b],
            # The short, actionable queues name their members inline; the long
            # ones would just be a wall of tract numbers.
            "tns": sorted(r["tn"] for r in sel)
                   if b in (reports.BUCKET_READY, reports.BUCKET_ON_HOLD,
                            reports.BUCKET_TITLE_WIP) else [],
        })
    return rows


def _funnel(merged):
    counts = defaultdict(lambda: [0, 0.0])
    for r in merged.values():
        label = r["lse_status"] or reports.LEASE_LABEL.get(r["lse_code"], "")
        # A split code like NEG_AC counts under its primary stage.
        if not label and r["lse_code"] in reports.SPLIT_STATUS:
            label = reports.SPLIT_STATUS[r["lse_code"]][0]
        if label in reports.LEASE_FILL and label != "Title On Hold":
            counts[label][0] += 1
            counts[label][1] += float(r["gma"] or 0) or r["ac"]
    return [{"stage": s, "tracts": counts[s][0], "ac": round(counts[s][1], 1),
             "fill": reports.LEASE_FILL[s], "unused": counts[s][0] == 0}
            for s in reports.LEASE_STAGES]


def _title_ladder(merged):
    counts = defaultdict(lambda: [0, 0.0])
    for r in merged.values():
        label = r["ttl_status"] or reports.TITLE_LABEL.get(r["ttl_code"], "")
        if label in reports.TITLE_FILL:
            counts[label][0] += 1
            counts[label][1] += r["ac"]
    return [{"stage": s, "tracts": counts[s][0], "ac": round(counts[s][1], 1),
             "fill": reports.TITLE_FILL[s]} for s in reports.TITLE_STAGES]


def _runners(merged):
    agg = defaultdict(lambda: {"tracts": 0, "ac": 0.0, "tns": [], "groups": set()})
    for r in merged.values():
        if not r["runner"]:
            continue
        a = agg[r["runner"]]
        a["tracts"] += 1
        a["ac"] += r["ac"]
        a["tns"].append(r["tn"])
        if r["ttl_group"]:
            a["groups"].add(r["ttl_group"])
    return sorted(
        [{"name": k, "tracts": v["tracts"], "ac": round(v["ac"], 1),
          "tns": sorted(v["tns"]), "groups": sorted(v["groups"])}
         for k, v in agg.items()],
        key=lambda x: -x["ac"])


def _areas(merged):
    agg = defaultdict(lambda: {"tracts": 0, "ac": 0.0, "et": 0, "eac": 0.0})
    for r in merged.values():
        a = agg[r["area"] or "UNCLASSIFIED"]
        a["tracts"] += 1
        a["ac"] += r["ac"]
        if _engaged(r):
            a["et"] += 1
            a["eac"] += r["ac"]
    return sorted(
        [{"area": k, "tracts": v["tracts"], "ac": round(v["ac"], 1),
          "engaged_tracts": v["et"], "engaged_ac": round(v["eac"], 1),
          "fill": reports.AREA_FILL.get(k, "#CCCCCC")} for k, v in agg.items()],
        key=lambda x: -x["ac"])


def _owners(merged):
    out = []
    for r in sorted(merged.values(), key=lambda x: x["tn"]):
        if r["owners"]:
            out.append({"tn": r["tn"], "area": r["area"],
                        "lse_status": r["lse_status"], "owners": r["owners"]})
    return out


def build_payload(merged):
    return {
        "pipeline": _pipeline(merged),
        "funnel": _funnel(merged),
        "title_ladder": _title_ladder(merged),
        "runners": _runners(merged),
        "areas": _areas(merged),
        "owners": _owners(merged),
        "totals": {
            "tracts": len(merged),
            "ac": round(sum(r["ac"] for r in merged.values()), 1),
            "engaged": sum(1 for r in merged.values() if _engaged(r)),
            "owner_records": sum(len(r["owners"]) for r in merged.values()),
        },
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
cd "C:/GIS/CLIENT/DOXA/SABINE/SHELBY/DASHBOARD" && "C:/Program Files/ArcGIS/Pro/bin/Python/envs/arcgispro-py3/python.exe" -m pytest tests/ -v
```
Expected: 41 passed (4 assets + 27 reports + 10 analytics).

If `test_owner_roster_totals_128_records` fails, the likely cause is `merge`
overwriting an owner list from a composite key with a shorter one — check the
`len(rec["owners"]) > len(r["owners"])` guard.

- [ ] **Step 5: Commit**

```bash
cd "C:/GIS/permit_intel" && git add -A && git commit -m "Shelby dashboard: analytics payloads for all five tabs"
```

---

### Task 7: Week-over-week change diff

**Files:**
- Create: `DASHBOARD/shelby/change.py`
- Create: `DASHBOARD/tests/test_change.py`

**Interfaces:**
- Consumes: `reports.parse_workbook`, `reports.merge`, `reports.LEASE_STAGES`, `reports.TITLE_STAGES`
- Produces: `build_change(current_merged, prior_consolidated_path, prior_title_path, shp_attrs) -> dict | None` with keys `as_of`, `advanced`, `title_moved`, `added`, `removed`, `regressed`

- [ ] **Step 1: Write the failing test — synthetic, so it runs without last week's files**

`tests/test_change.py`:

```python
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shelby import change, reports


def _rec(tn, lse="", ttl="", runner="", ac=10.0):
    return {"tn": tn, "area": "OPEN", "ac": ac, "lse_code": None, "ttl_code": None,
            "lse_status": lse, "ttl_status": ttl, "runner": runner, "gma": "",
            "owners": [], "ttl_com": "", "lse_com": "", "ttl_group": "",
            "lse_group": "", "bucket": ""}


def test_no_prior_snapshot_returns_none():
    assert change.build_change({}, None, None, {}) is None
    assert change.build_change({}, "does/not/exist.xlsx", "also/not.xlsx", {}) is None


def test_advanced_detects_forward_lease_movement():
    prior = {"A-001": _rec("A-001", lse="Attempting to Contact")}
    cur = {"A-001": _rec("A-001", lse="Negotiating")}
    d = change.diff(cur, prior)
    assert d["advanced"] == [{"tn": "A-001", "field": "lease", "ac": 10.0,
                              "was": "Attempting to Contact", "now": "Negotiating"}]
    assert d["regressed"] == []


def test_regressed_detects_backward_lease_movement():
    prior = {"A-001": _rec("A-001", lse="Committed")}
    cur = {"A-001": _rec("A-001", lse="Negotiating")}
    d = change.diff(cur, prior)
    assert d["regressed"][0]["now"] == "Negotiating"
    assert d["advanced"] == []


def test_title_movement_is_reported_separately():
    prior = {"A-001": _rec("A-001", ttl="Title 26%-75%")}
    cur = {"A-001": _rec("A-001", ttl="Title 76%-99%")}
    d = change.diff(cur, prior)
    assert d["title_moved"][0]["now"] == "Title 76%-99%"


def test_added_and_removed_tracts():
    prior = {"A-001": _rec("A-001")}
    cur = {"A-002": _rec("A-002")}
    d = change.diff(cur, prior)
    assert [x["tn"] for x in d["added"]] == ["A-002"]
    assert [x["tn"] for x in d["removed"]] == ["A-001"]


def test_starting_leasing_from_nothing_counts_as_advanced():
    prior = {"A-001": _rec("A-001")}
    cur = {"A-001": _rec("A-001", lse="Attempting to Contact")}
    d = change.diff(cur, prior)
    assert d["advanced"][0]["was"] == "(none)"


def test_unchanged_tracts_produce_no_rows():
    prior = {"A-001": _rec("A-001", lse="Negotiating", ttl="Title 26%-75%")}
    cur = {"A-001": _rec("A-001", lse="Negotiating", ttl="Title 26%-75%")}
    d = change.diff(cur, prior)
    assert d["advanced"] == [] and d["regressed"] == [] and d["title_moved"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
cd "C:/GIS/CLIENT/DOXA/SABINE/SHELBY/DASHBOARD" && "C:/Program Files/ArcGIS/Pro/bin/Python/envs/arcgispro-py3/python.exe" -m pytest tests/test_change.py -v
```
Expected: FAIL, `ModuleNotFoundError: No module named 'shelby.change'`

- [ ] **Step 3: Implement `shelby/change.py`**

```python
# -*- coding: utf-8 -*-
"""Week-over-week diff against the prior report pair.

Optional by design: the prior workbooks may not exist on any given cycle, and
the build must not depend on them. When absent, build_change returns None and
the template hides the CHANGE tab.
"""

import os

from . import reports

LEASE_RANK = {s: i + 1 for i, s in enumerate(reports.LEASE_STAGES)}
TITLE_RANK = {s: i for i, s in enumerate(reports.TITLE_STAGES)}


def _lease_rank(s):
    # 'Title On Hold' is a block, not a pipeline position; treat as unranked.
    return LEASE_RANK.get(s, 0)


def _row(tn, field, was, now, ac):
    return {"tn": tn, "field": field, "was": was or "(none)",
            "now": now or "(none)", "ac": ac}


def diff(current, prior):
    """Compare two merged {tn: record} maps."""
    out = {"advanced": [], "regressed": [], "title_moved": [],
           "added": [], "removed": []}

    for tn in sorted(set(current) - set(prior)):
        r = current[tn]
        out["added"].append({"tn": tn, "ac": r["ac"], "area": r["area"]})
    for tn in sorted(set(prior) - set(current)):
        r = prior[tn]
        out["removed"].append({"tn": tn, "ac": r["ac"], "area": r["area"]})

    for tn in sorted(set(current) & set(prior)):
        c, p = current[tn], prior[tn]
        if c["lse_status"] != p["lse_status"]:
            row = _row(tn, "lease", p["lse_status"], c["lse_status"], c["ac"])
            if _lease_rank(c["lse_status"]) >= _lease_rank(p["lse_status"]):
                out["advanced"].append(row)
            else:
                out["regressed"].append(row)
        if c["ttl_status"] != p["ttl_status"]:
            out["title_moved"].append(
                _row(tn, "title", p["ttl_status"], c["ttl_status"], c["ac"]))
    return out


def build_change(current_merged, prior_consolidated, prior_title, shp_attrs):
    """Parse the prior pair with the SAME parser and expander as the current
    pair -- no second code path -- then diff. Returns None when unavailable."""
    if not prior_consolidated or not prior_title:
        return None
    if not (os.path.exists(prior_consolidated) and os.path.exists(prior_title)):
        return None

    prior_merged = reports.merge(shp_attrs,
                                 reports.parse_workbook(prior_consolidated),
                                 reports.parse_workbook(prior_title))
    d = diff(current_merged, prior_merged)
    d["as_of"] = os.path.basename(prior_consolidated)[:8]
    return d
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
cd "C:/GIS/CLIENT/DOXA/SABINE/SHELBY/DASHBOARD" && "C:/Program Files/ArcGIS/Pro/bin/Python/envs/arcgispro-py3/python.exe" -m pytest tests/ -v
```
Expected: 48 passed (4 assets + 27 reports + 10 analytics + 7 change).

- [ ] **Step 5: Commit**

```bash
cd "C:/GIS/permit_intel" && git add -A && git commit -m "Shelby dashboard: week-over-week change diff (optional prior snapshot)"
```

---

### Task 8: HTML template

**Files:**
- Create: `DASHBOARD/template.html`

**Reference:** `C:\GIS\CLIENT\DLS\DASHBOARD\template.html` (1,388 lines) for the shell, splitter, theme toggle and map wiring. Reuse its CSS structure and Leaflet setup; replace the header and all tab content.

**Note on this task's specificity:** this is the largest task and the only one
whose steps are part prose rather than wholly code -- a complete 1,400-line
template inline in a plan is not useful. The parts given as literal code are the
ones where a wrong guess costs real time: the brand tokens, the Leaflet
renderer/hit-testing rules, the caveat markup, and the change-tab removal. Tab
body rendering is ordinary DOM work against payload shapes that Task 6's tests
already pin down. Build it against `payload` keys exactly as
`analytics.build_payload` emits them.

**Placeholders the build substitutes:**
`__LEAFLET_CSS__` `__LEAFLET_JS__` `__GOTHAM_BOOK__` `__GOTHAM_MEDIUM__` `__GOTHAM_BOLD__` `__DOXA_LOGO__` `__SABINE_LOGO__` `__MM_LOGO__` `__TRACTS_GEO__` `__UNITS_GEO__` `__AOI_GEO__` `__DEEPRIGHTS_GEO__` `__ABSTRACTS_GEO__` `__COUNTIES_GEO__` `__PAYLOAD__` `__CHANGE__` `__EXTENT__` `__GENERATED__`

- [ ] **Step 1: Build the shell — header, splitter, theme toggle**

Header markup, burgundy bar:

```html
<header class="hdr">
  <img class="doxa" src="__DOXA_LOGO__" alt="Doxa Land Management">
  <span class="prep">prepared for</span>
  <img class="sabine" src="__SABINE_LOGO__" alt="Sabine Oil &amp; Gas">
  <div class="titles">
    <h1>Shelby North Area 1</h1>
    <div class="sub">Shelby County, Texas &middot; leasing &amp; title status
      as of 08/17&ndash;18/2026 &middot; built __GENERATED__</div>
  </div>
  <a class="mm" href="https://mapmatics.co" target="_blank" rel="noopener">
    <span>via</span><img src="__MM_LOGO__" alt="Mapmatics"></a>
</header>
```

Font faces and brand tokens:

```css
@font-face{font-family:Gotham;font-weight:400;font-display:swap;
  src:url(__GOTHAM_BOOK__) format('woff2')}
@font-face{font-family:Gotham;font-weight:500;font-display:swap;
  src:url(__GOTHAM_MEDIUM__) format('woff2')}
@font-face{font-family:Gotham;font-weight:700;font-display:swap;
  src:url(__GOTHAM_BOLD__) format('woff2')}
:root{
  --burgundy:#651C32; --burgundy-lt:#8A2A47;
  --bg:#f4f4f6; --panel:#fff; --ink:#1a1a1c; --muted:#6b6b73; --line:#dcdce2;
  font-family:Gotham,Montserrat,system-ui,sans-serif;
}
:root[data-theme=dark]{
  --bg:#161619; --panel:#1e1e22; --ink:#ececed; --muted:#9a9aa2; --line:#33333a;
}
.hdr{background:var(--burgundy);color:#fff;display:flex;align-items:center;
  gap:18px;padding:10px 18px}
.hdr .doxa{height:30px}
.hdr .prep{font-size:11px;letter-spacing:.08em;text-transform:uppercase;opacity:.75}
/* the Sabine mark is on an opaque white chip -- it is a JPEG with gradients
   that fringe if keyed out, so give it a rounded white pad instead */
.hdr .sabine{height:34px;background:#fff;border-radius:4px;padding:3px 7px}
.hdr .titles{margin-left:auto;text-align:right}
```

- [ ] **Step 2: Build the five tabs**

Tab bar: `PIPELINE` (default) · `TITLE` · `AREAS` · `OWNERS` · `CHANGE`.

PIPELINE renders `payload.pipeline` as six clickable rows (bucket name, tract
count, acres, a proportional bar in `row.fill`). Rows carrying `tns` expand to
list them. Below it, `payload.funnel` as horizontal bars; rows with
`unused:true` render at 35% opacity with a "no tracts yet" note.

The caveat is required page furniture, not a tooltip — render it directly
beneath the `Leasing, no current title assignment` row:

```html
<p class="caveat">
  The TITLE WORK report carries only <em>currently assigned</em> work and appears
  to drop tracts once complete &mdash; 631-006 reads title 100% in GIS but
  &ldquo;Open&rdquo; in the workbook. These tracts have no <em>current</em> title
  assignment, which is not the same as title not being done.
</p>
```

TITLE renders `payload.title_ladder` then `payload.runners` (name, tracts,
acres, and the package strings from `groups`).

AREAS renders `payload.areas` as three rows: total tracts/acres with an
engaged-portion overlay bar.

OWNERS renders `payload.owners` grouped by tract with a search box filtering on
owner name, tract, and city. Show the owners-per-tract count as a badge.

CHANGE renders `changeData` sections; if `changeData` is null, remove the tab
button and panel at init:

```js
if (!changeData) {
  document.querySelector('[data-tab=change]').remove();
  document.getElementById('tab-change').remove();
}
```

- [ ] **Step 3: Wire the map with the Flatland mechanics**

These rules are the fixes for bugs already paid for once in the Flatland build:

```js
// ONE shared canvas renderer across all hit-testable tract layers. Each
// L.canvas creates a full-map-sized <canvas> with pointer-events:auto, so
// only the topmost canvas receives clicks -- per-layer canvases silently
// break selection.
const tractRenderer = L.canvas({ padding: 0.15 });

// SVG for layers that must let clicks fall through to the tracts beneath.
const outlineRenderer = L.svg({ padding: 0.15 });

// Highlights must never intercept pointer events.
const highlight = L.geoJSON(null, {
  interactive: false,
  style: { color: '#651C32', weight: 3, fill: false }
}).addTo(map);

// Pan only if off-screen. NEVER change zoom on select -- a fitBounds zoom
// jump was the cause of the "map jams on select" stall in Flatland.
function revealTract(layer) {
  const b = layer.getBounds();
  if (!map.getBounds().contains(b)) map.panTo(b.getCenter(), { animate: true });
}

// uid -> feature lookups via Map, not Array.find().
const byTn = new Map(tractsGeo.features.map(f => [f.properties.tn, f]));
```

Four mutually exclusive tract fill layers as radio options — *Lease status*
(default), *Title status*, *Area classification*, *Pipeline stage* — each
recolouring the same GeoJSON layer rather than adding a second one. Split
statuses render as a diagonal hatch built from a `<pattern>`-backed canvas fill.

Basemaps, keyless only:

```js
const basemaps = {
  'OpenStreetMap': L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    { maxZoom: 19, attribution: '&copy; OpenStreetMap' }),
  'Esri Imagery': L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    { maxZoom: 19, attribution: 'Esri' }),
  'Esri Topo': L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}',
    { maxZoom: 19, attribution: 'Esri' }),
  'None': L.tileLayer('')
};
```

Overlays: units (outlined, labelled `unit_nm`), abstracts (labelled
`SURVEY A-###`), deep rights (off by default), AOI (red dashed, matching the
PDF maps), counties.

- [ ] **Step 4: Commit**

```bash
cd "C:/GIS/permit_intel" && git add -A && git commit -m "Shelby dashboard: HTML template with five tabs and Doxa/Sabine branding"
```

---

### Task 9: Build orchestration

**Files:**
- Create: `DASHBOARD/build_shelby_dashboard.py`

**Interfaces:**
- Consumes: everything above
- Produces: `Shelby_North_Area1_Dashboard.html`

- [ ] **Step 1: Implement the build script**

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
build_shelby_dashboard.py
=========================
Regenerates Shelby_North_Area1_Dashboard.html -- a single self-contained page:
  left  = tabbed analytics of the two weekly Shelby North Area 1 status reports
  right = interactive Leaflet lease/title/area/pipeline map

Run with the ArcGIS Pro python (has osgeo + openpyxl + PIL + fontTools):

  "C:\\Program Files\\ArcGIS\\Pro\\bin\\Python\\envs\\arcgispro-py3\\python.exe" build_shelby_dashboard.py

The system Python 3.14 on this machine will NOT work: broken openpyxl/numpy
import chain, no GDAL.
"""

import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from shelby import analytics, assets, change, geo, reports

HERE = os.path.dirname(os.path.abspath(__file__))
GIS = r"C:\GIS\CLIENT\DOXA\SABINE\SHELBY"
DL = r"C:\Users\mapma\Downloads"

# ---------------------------------------------------------------- inputs -----
CONSOLIDATED = os.path.join(
    DL, "20260820 CONSOLIDATED BUYERS-Lease Status Report-Shelby NTH Area 1.xlsx")
TITLE = os.path.join(
    DL, "20260820 TITLE WORK-Lease Status Report-Shelby NTH Area 1.xlsx")

# Prior-week pair for the CHANGE tab. Leave as None until they are available;
# the build logs a line and hides the tab rather than failing.
PRIOR_CONSOLIDATED = None
PRIOR_TITLE = None

TRACT_SHP = os.path.join(GIS, "DOXA_TRACTS.shp")
UNIT_SHP = os.path.join(GIS, "SHELBY_UNITS.shp")
AOI_SHP = os.path.join(GIS, "AOI.shp")
DEEP_SHP = os.path.join(GIS, "DEEP_RIGHTS_TOTAL.shp")
ABSTRACT_SHP = r"C:\GIS\BOUNDARY\ETX_SURVEY\ETX_CO_ABSTR.shp"
COUNTY_SHP = r"C:\GIS\BOUNDARY\COUNTY\tl_2024_us_county.shp"

TEMPLATE = os.path.join(HERE, "template.html")
OUTPUT = os.path.join(HERE, "Shelby_North_Area1_Dashboard.html")
VENDOR = os.path.join(HERE, "vendor")

EXPECTED_TRACTS = 161


def main():
    print("parsing workbooks ...")
    consolidated = reports.parse_workbook(CONSOLIDATED)
    title = reports.parse_workbook(TITLE)
    print("  consolidated keys: %d | title keys: %d" % (len(consolidated), len(title)))

    print("loading tract polygons ...")
    attrs, geoms = geo.load_tract_attrs(TRACT_SHP)
    print("  tract polygons: %d" % len(attrs))

    print("merging ...")
    merged = reports.merge(attrs, consolidated, title)

    # The composite-key expander is the one place a parsing miss produces a
    # plausible-looking but wrong dashboard. Fail loudly rather than ship it.
    if len(merged) != EXPECTED_TRACTS:
        raise SystemExit("FATAL: merged %d tracts, expected %d"
                         % (len(merged), EXPECTED_TRACTS))
    known = set(attrs)
    unresolved = [k for k in list(consolidated) + list(title)
                  if not reports.expand_key(k, known)]
    if unresolved:
        raise SystemExit("FATAL: workbook keys that resolve to no tract: %s"
                         % unresolved)
    print("  merged %d/%d tracts, all workbook keys resolved"
          % (len(merged), EXPECTED_TRACTS))

    payload = analytics.build_payload(merged)
    for row in payload["pipeline"]:
        print("    %-52s %4d tr  %9.1f ac"
              % (row["bucket"], row["tracts"], row["ac"]))

    print("building change view ...")
    change_data = change.build_change(merged, PRIOR_CONSOLIDATED, PRIOR_TITLE, attrs)
    if change_data is None:
        print("  no prior snapshot -- CHANGE tab hidden")
    else:
        print("  advanced %d | title moved %d | added %d | removed %d | regressed %d"
              % (len(change_data["advanced"]), len(change_data["title_moved"]),
                 len(change_data["added"]), len(change_data["removed"]),
                 len(change_data["regressed"])))

    print("assembling tract features ...")
    tract_features = [
        {"type": "Feature", "properties": merged[tn], "geometry": geoms[tn]}
        for tn in sorted(merged) if tn in geoms]

    extent = geo.bounds_of(tract_features)
    pad_x = (extent[2] - extent[0]) * 0.06
    pad_y = (extent[3] - extent[1]) * 0.06
    extent = [extent[0] - pad_x, extent[1] - pad_y,
              extent[2] + pad_x, extent[3] + pad_y]

    print("loading context layers ...")
    units = geo.load_features(UNIT_SHP, prop_map={
        "unit_nm": "unit_nm", "operator": "operator", "wellstat": "wellstat",
        "abstract": "abstract", "acres": "acres"})
    aoi = geo.load_features(AOI_SHP, prop_map={"acres": "acres"})
    deep = geo.load_features(DEEP_SHP, prop_map={
        "DOXA_TN": "tn", "AREA": "area", "GIS_AREA": "ac"})
    counties = geo.load_features(COUNTY_SHP, prop_map={"NAME": "name"},
                                 keep=lambda p: p.get("name") in
                                 {"Shelby", "Panola", "Nacogdoches", "San Augustine",
                                  "Rusk", "Sabine"})
    # The abstract layer is 39,028 features statewide; clip to the AOI first.
    abstracts = geo.load_features(
        ABSTRACT_SHP,
        prop_map={"ABSTRACT_L": "abstract_label", "LEVEL1_SUR": "survey_name"},
        bbox=(extent[0] - 0.05, extent[1] - 0.05, extent[2] + 0.05, extent[3] + 0.05))
    print("  units %d | aoi %d | deep %d | counties %d | abstracts %d"
          % (len(units), len(aoi), len(deep), len(counties), len(abstracts)))

    print("rendering template ...")
    with open(TEMPLATE, "r", encoding="utf-8") as fh:
        html = fh.read()
    with open(os.path.join(VENDOR, "leaflet.css"), "r", encoding="utf-8") as fh:
        leaflet_css = fh.read()
    with open(os.path.join(VENDOR, "leaflet.js"), "r", encoding="utf-8") as fh:
        leaflet_js = fh.read()
    # Leaflet's stylesheet points at marker PNGs we don't ship; neutralise those
    # url() refs so an offline open doesn't 404 for images nothing uses.
    leaflet_css = leaflet_css.replace("url(images/", "url(data:,")

    subs = {
        "__LEAFLET_CSS__": leaflet_css,
        "__LEAFLET_JS__": leaflet_js,
        "__GOTHAM_BOOK__": assets.gotham_woff2_data_uri(assets.GOTHAM_BOOK),
        "__GOTHAM_MEDIUM__": assets.gotham_woff2_data_uri(assets.GOTHAM_MEDIUM),
        "__GOTHAM_BOLD__": assets.gotham_woff2_data_uri(assets.GOTHAM_BOLD),
        "__DOXA_LOGO__": assets.doxa_logo_uri(),
        "__SABINE_LOGO__": assets.sabine_logo_uri(),
        "__MM_LOGO__": assets.mapmatics_logo_uri(),
        "__TRACTS_GEO__": geo.minjson(geo.fc(tract_features)),
        "__UNITS_GEO__": geo.minjson(geo.fc(units)),
        "__AOI_GEO__": geo.minjson(geo.fc(aoi)),
        "__DEEPRIGHTS_GEO__": geo.minjson(geo.fc(deep)),
        "__ABSTRACTS_GEO__": geo.minjson(geo.fc(abstracts)),
        "__COUNTIES_GEO__": geo.minjson(geo.fc(counties)),
        "__PAYLOAD__": geo.minjson(payload),
        "__CHANGE__": geo.minjson(change_data),
        "__EXTENT__": geo.minjson(extent),
        "__GENERATED__": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    missing = [k for k in subs if k not in html]
    if missing:
        raise SystemExit("FATAL: template is missing placeholders: %s" % missing)
    for k, v in subs.items():
        html = html.replace(k, v)

    with open(OUTPUT, "w", encoding="utf-8") as fh:
        fh.write(html)
    mb = os.path.getsize(OUTPUT) / (1024 * 1024)
    print("\nwrote %s  (%.1f MB)" % (OUTPUT, mb))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the build**

Run:
```bash
cd "C:/GIS/CLIENT/DOXA/SABINE/SHELBY/DASHBOARD" && "C:/Program Files/ArcGIS/Pro/bin/Python/envs/arcgispro-py3/python.exe" build_shelby_dashboard.py
```

Expected output includes:
```
  merged 161/161 tracts, all workbook keys resolved
    Untouched - no title, no leasing                      101 tr     2585.9 ac
    Ready to lease - title >=76%, leasing not started       9 tr      236.7 ac
    Blocked - title on hold                                 6 tr       90.7 ac
  no prior snapshot -- CHANGE tab hidden
wrote ...Shelby_North_Area1_Dashboard.html  (2.x MB)
```

- [ ] **Step 3: Run the full test suite**

Run:
```bash
cd "C:/GIS/CLIENT/DOXA/SABINE/SHELBY/DASHBOARD" && "C:/Program Files/ArcGIS/Pro/bin/Python/envs/arcgispro-py3/python.exe" -m pytest tests/ -v
```
Expected: 48 passed (4 assets + 27 reports + 10 analytics + 7 change).

- [ ] **Step 4: Commit**

```bash
cd "C:/GIS/permit_intel" && git add -A && git commit -m "Shelby dashboard: build orchestration with 161/161 join assertion"
```

---

### Task 10: Visual verification against the source maps

The build asserting 161/161 proves the join, not that the page is *right*. This
task checks it against the three PDFs Doxa already sends.

**Files:** none created; may produce fixes to `template.html`.

- [ ] **Step 1: Open the dashboard in the browser pane**

Use `mcp__Claude_Browser__preview_start` with the `file://` URL of the output.

- [ ] **Step 2: Check each success criterion from spec §11**

For each, screenshot and compare:

1. Tract count in the header reads 161; no tract renders unfilled on the Area layer.
2. **Lease status layer vs `20260819_TX-SHELBY-LEASE_STATUS.pdf`** — the orange
   Negotiating block through the 163/459 tracts, the green Committed cluster at
   459-001/003/007/010/019, the light-blue Attempting to Contact run through
   840-002…006 and the 520s.
3. **Title status layer vs `20260819_TX-SHELBY-TITLE_STATUS.pdf`** — the pale
   green 284 block in the north, the dark green 631-006, the cyan 163/520 block
   in the south, salmon on 459-015/018/034/038.
4. **Area layer vs `20260715_TX-SHELBY_TRACTS.pdf`** — green OPEN in the north
   and east, tan deep-rights through the middle, purple lapsed-unit in the west.
5. PIPELINE ready-to-lease row lists 9 tracts totalling 237 ac.
6. The "no current title assignment" caveat is visible on the PIPELINE tab
   without hovering anything.
7. Clicking a tract selects it without a zoom jump; clicking a second tract
   while the first is selected still works (canvas hit-testing).
8. Owner search filters; typing `Joaquin` returns tracts, typing `Beckham`
   returns 163-004.
9. Theme toggle: both themes legible, Sabine chip readable on dark.
10. CHANGE tab is absent (no prior snapshot configured).

- [ ] **Step 3: Verify it opens offline**

Disconnect or block network, reopen the file, confirm the page renders with
polygons, labels and all tabs functional; only basemap tiles should be missing.

- [ ] **Step 4: Fix anything found, then commit**

```bash
cd "C:/GIS/permit_intel" && git add -A && git commit -m "Shelby dashboard: visual verification fixes"
```

---

## Deferred — activate when last week's reports arrive

Set `PRIOR_CONSOLIDATED` and `PRIOR_TITLE` at the top of
`build_shelby_dashboard.py` to the prior-week pair and re-run. The CHANGE tab
appears automatically. Confirm:

- The advanced/regressed split reads correctly against what actually moved.
- No tract appears in both `added` and `removed`.
- If the prior workbooks use a different tract-key spelling, the expander test
  in `tests/test_reports.py` gains those strings as new cases first.

## Out of scope

- Wells and production data (the DI shapefiles are present but nothing in these
  two reports references them).
- Any editing, write-back, or server component.
- Bonus, spend, velocity, expiration runway — no source data exists.
- Automating the weekly rebuild.
