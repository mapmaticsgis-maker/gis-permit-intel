#!/usr/bin/env python
"""
TX RRC W-1 permit plat early-signal intel.

User manually drops permit-plat PDFs into data/tx/w1/<YYYYMMDD>/ -- these
surface 1-2 days before the same permits show up in the daily daf420
approved-permit extract (confirmed 2026-07-29: 0/6 same-day plats were yet
in master.csv). Filenames follow RRC's convention:
    <permit_number>_Plat_<well/unit name>_<surveyor code>.pdf

Primary extraction is OCR (Tesseract + poppler, installed 2026-07-30):
plats are CAD-exported with outlined/vector text, so pdfplumber finds
zero extractable words -- the page has to be rasterized and read as an
image. Title blocks are often rotated 90/180 degrees along a page
margin (confirmed on a KSA-template plat), so each page is OCR'd at all
four rotations and results are merged. Validated against 12 real plats
across two days: 10/12 got both operator and county cleanly, the other
2 got one field each (never a wrong answer, matching the same
conservative philosophy as the fallback below).

Falls back to fuzzy-matching well-name tokens against historical
Lease_Name entries in master.csv when OCR finds nothing for a field --
weaker, but still useful when it clears MIN_MATCH_TOKENS. A single
coincidental token is not enough evidence to name an operator (confirmed
on real data: filename-only tokens once matched a well to a completely
unrelated Lewis Petro/Webb lease) -- better to say "unknown" than guess
wrong with a straight face.

Run: python w1_intel.py [YYYYMMDD]   (defaults to today)
"""
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import openpyxl
import pandas as pd
import pytesseract
import yaml
from pdf2image import convert_from_path

ROOT = Path(__file__).resolve().parent
CLIENT_WORKBOOK = Path(r"C:\GIS\Mapmatics_Client_Master_UPDATED.xlsx")

TESSERACT_EXE = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
POPPLER_PATH = (
    r"C:\Users\mapma\AppData\Local\Microsoft\WinGet\Packages"
    r"\oschwartz10612.Poppler_Microsoft.Winget.Source_8wekyb3d8bbwe\poppler-25.07.0\Library\bin"
)
pytesseract.pytesseract.tesseract_cmd = TESSERACT_EXE

STOPWORDS = {
    "unit", "gas", "well", "wells", "no", "trust", "plat", "final", "npz",
    "hs", "aw", "hh", "ltr", "lgr", "the", "of", "and", "et", "al", "ux",
    "h", "hc", "estate", "ranch", "farm", "farms", "heirs", "permit",
    "proposed", "location", "drilling", "survey", "texas", "county",
    "prepared", "for", "sheet", "job", "scale", "date", "revised",
    "rrc", "operating", "energy", "oil", "resources", "llc", "inc", "co",
    "operator", "operators", "company", "map", "maps",
}
MIN_MATCH_TOKENS = 2  # a single coincidental token isn't enough to attribute an operator

COUNTY_RE = re.compile(r"\b([A-Z]{2,}(?:[ \t]+[A-Z]{2,}){0,2})[ \t]+COUNTY,?[ \t]*TEXAS\b")
SOLE_USE_RE = re.compile(
    r"(?:sole use of|prepared for)[ \t]+([A-Z][A-Za-z0-9&\-'.]*(?:[ \t]+[A-Z][A-Za-z0-9&\-'.]*){0,5})",
    re.IGNORECASE,
)
SUFFIX_LINE_RE = re.compile(
    r"^([A-Z][A-Za-z0-9&\-'.]*(?:[ \t]+[A-Z][A-Za-z0-9&\-'.]*){0,5}),?[ \t]+"
    r"(INC\.?|LLC\.?|L\.L\.C\.?|LP\.?|L\.P\.?|LTD\.?|CORP\.?)$"
)
EXCLUDE_RE = re.compile(
    r"SURVEY|ENGINEERING|SURVEYOR|CIVIL|TBPLS|TBPE|RPLS|BOWMAN|KSA|CRAFTON",
    re.IGNORECASE,
)


def ocr_extract(pdf_path: Path, dpi: int = 200):
    """OCR the first page at 0/90/180/270 degrees and pull county + operator
    candidates from the combined text. Returns (county, operator) -- either
    may be None if not found."""
    pages = convert_from_path(str(pdf_path), dpi=dpi, poppler_path=POPPLER_PATH)
    img = pages[0]

    counties, operators = [], []
    for angle in (0, 90, 180, 270):
        rotated = img.rotate(angle, expand=True) if angle else img
        text = pytesseract.image_to_string(rotated)
        counties += [c.strip().upper() for c in COUNTY_RE.findall(text)]
        for line in text.splitlines():
            line = line.strip()
            if not line or EXCLUDE_RE.search(line):
                continue
            m = SOLE_USE_RE.search(line)
            if m:
                operators.append(m.group(1).strip().rstrip("."))
            if SUFFIX_LINE_RE.match(line):
                operators.append(line.rstrip("."))

    county = Counter(counties).most_common(1)[0][0] if counties else None
    operator = Counter(operators).most_common(1)[0][0] if operators else None
    return county, operator


def load_client_prospects():
    """Return [(client_name, status, jobs_text)] from the workbook."""
    if not CLIENT_WORKBOOK.exists():
        return []
    wb = openpyxl.load_workbook(CLIENT_WORKBOOK, data_only=True)
    ws = wb["Client Master"]
    rows = list(ws.iter_rows(min_row=2, values_only=True))
    return [(r[0], r[1], r[6]) for r in rows if r[0] and r[6]]


def load_operator_families():
    cfg = yaml.safe_load(open(ROOT / "config.yaml"))
    return cfg.get("operator_families", {})


def tokenize(name: str) -> set[str]:
    # Keep alphanumeric codes intact (F14D, 4HH, DS) -- splitting on digits
    # silently destroyed exactly the tokens most likely to be distinctive
    # well/unit identifiers, leaving only generic leftover words behind.
    words = re.findall(r"[A-Za-z0-9]+", name.upper())
    return {w.lower() for w in words if len(w) >= 3 and w.lower() not in STOPWORDS
            and not w.isdigit()}


def parse_filename(fname: str):
    """<permit>_Plat_<well name>_<code>.pdf -> (permit_number, well_name)."""
    stem = fname.rsplit(".", 1)[0]
    parts = stem.split("_", 2)
    if len(parts) < 3 or not parts[0].isdigit():
        return None, stem
    permit_raw, _plat, rest = parts
    well_name = re.sub(r"_(LGR|LTR)$", "", rest, flags=re.IGNORECASE)
    return permit_raw, well_name


def infer_operator_county_fallback(well_tokens: set[str], master: pd.DataFrame):
    """Fuzzy-match fallback for when OCR finds nothing. See module docstring
    for why this requires MIN_MATCH_TOKENS rather than any overlap at all."""
    if not well_tokens:
        return None, None, 0
    lease_tokens = master["Lease_Name"].fillna("").map(tokenize)
    overlap = lease_tokens.map(lambda t: len(t & well_tokens))
    if overlap.max() < MIN_MATCH_TOKENS:
        return None, None, int(overlap.max())
    hits = master[overlap == overlap.max()]
    ops = Counter(hits["Operator_Name"].dropna())
    counties = Counter(hits["County"].dropna())
    op = ops.most_common(1)[0][0] if ops else None
    county = counties.most_common(1)[0][0] if counties else None
    return op, county, int(overlap.max())


def family_of(operator: str, families: dict):
    if not operator:
        return None
    op_upper = operator.upper()
    for fam_data in families.values():
        if any(alias.upper() in op_upper for alias in fam_data["aliases"]):
            return fam_data["family"]
    return None


def match_clients(well_tokens: set[str], operator: str, county: str, prospects):
    """Fuzzy-match well tokens (and operator/county, if known) against each
    client's free-text Jobs/Prospect Names. Returns list of (client, status,
    matched_terms)."""
    hits = []
    for client, status, jobs_text in prospects:
        jobs_upper = jobs_text.upper()
        matched = {t for t in well_tokens if t.upper() in jobs_upper}
        if county and county.upper() in jobs_upper:
            matched.add(county)
        if operator:
            op_first_word = operator.split()[0].rstrip(",").upper()
            if len(op_first_word) >= 4 and op_first_word in jobs_upper:
                matched.add(operator.split()[0])
        if matched:
            hits.append((client, status, matched))
    return hits


def main():
    day = sys.argv[1] if len(sys.argv) > 1 else date.today().strftime("%Y%m%d")
    w1_dir = ROOT / "data" / "tx" / "w1" / day

    if not w1_dir.exists():
        print(f"No W-1 folder for {day} yet ({w1_dir}) -- nothing downloaded today.")
        return 0

    pdfs = sorted(w1_dir.glob("*.pdf"))
    if not pdfs:
        print(f"{w1_dir} exists but has no PDFs yet.")
        return 0

    master = pd.read_csv(ROOT / "data" / "tx" / "master.csv", dtype=str)
    known_permits = set(master["Permit_Number"].dropna())
    families = load_operator_families()
    prospects = load_client_prospects()

    lines = [f"# W-1 Early Intel — {day}\n", f"{len(pdfs)} plat(s) found.\n"]

    for pdf in pdfs:
        permit_raw, well_name = parse_filename(pdf.name)
        if permit_raw is None:
            lines.append(f"## {pdf.name}\n_Filename doesn't match expected pattern, skipped._\n")
            continue
        permit_padded = permit_raw.zfill(7)
        already_known = permit_padded in known_permits or permit_raw in known_permits

        try:
            county, op = ocr_extract(pdf)
        except Exception as e:
            county, op = None, None
            print(f"  [WARN] OCR failed for {pdf.name}: {e}", file=sys.stderr)
        source = "OCR" if (county or op) else None

        tokens = tokenize(well_name)
        if not op and not county:
            op, county, score = infer_operator_county_fallback(tokens, master)
            if op or county:
                source = f"fallback, {score} token overlap"
        elif not op or not county:
            fb_op, fb_county, score = infer_operator_county_fallback(tokens, master)
            op = op or fb_op
            county = county or fb_county

        fam = family_of(op, families)
        client_hits = match_clients(tokens, op, county, prospects)

        lines.append(f"## {well_name}  (Permit #{permit_raw})")
        lines.append(f"- **Status:** {'ALREADY in master.csv (not early anymore)' if already_known else '**NOT yet in master.csv — early signal**'}")
        if op or county:
            detail = f"{op or 'unknown operator'} ({county or 'unknown county'})"
            lines.append(f"- **Operator/county:** {detail}  _[source: {source}]_")
        else:
            lines.append("- **Operator/county:** unknown — OCR and filename inference both came up empty; needs manual check")
        if fam:
            lines.append(f"- **Watched family:** {fam}")
        if client_hits:
            for client, status, matched in client_hits:
                lines.append(f"- **Client match:** {client} [{status}] — matched on: {', '.join(sorted(matched))}")
        else:
            lines.append("- **Client match:** none found")
        lines.append("")

    digest = "\n".join(lines)
    out_path = w1_dir / "digest.md"
    out_path.write_text(digest, encoding="utf-8")
    print(digest)
    print(f"\nSaved: {out_path}")
    return 0


if __name__ == "__main__":
    exit(main())
