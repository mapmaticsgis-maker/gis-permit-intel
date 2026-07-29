#!/usr/bin/env python
"""
TX RRC W-1 permit plat early-signal intel.

User manually drops permit-plat PDFs into data/tx/w1/<YYYYMMDD>/ -- these
surface 1-2 days before the same permits show up in the daily daf420
approved-permit extract (confirmed 2026-07-29: 0/6 same-day plats were yet
in master.csv). Filenames follow RRC's convention:
    <permit_number>_Plat_<well/unit name>_<surveyor code>.pdf

The plats themselves are CAD-exported with outlined/vector text (no
extractable text layer -- pdfplumber finds zero words), so this doesn't
attempt to read the PDF content. Instead it works from the filename
(permit number + well/unit name are always present and reliable) and
infers operator/county by fuzzy-matching well-name tokens against
historical Lease_Name entries in master.csv. This is a real limitation:
inference, not a read of the document. A brand-new operator/area with no
matching history in master.csv will come back "unknown" rather than a
guess -- OCR (Tesseract+poppler) would remove this gap but isn't
installed on this machine as of 2026-07-29.

Run: python w1_intel.py [YYYYMMDD]   (defaults to today)
"""
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import openpyxl
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent
CLIENT_WORKBOOK = Path(r"C:\GIS\Mapmatics_Client_Master_UPDATED.xlsx")

STOPWORDS = {
    "unit", "gas", "well", "wells", "no", "trust", "plat", "final", "npz",
    "hs", "aw", "hh", "ltr", "lgr", "the", "of", "and", "et", "al", "ux",
    "h", "hc", "estate", "ranch", "farm", "farms", "heirs", "permit",
    "proposed", "location", "drilling", "survey", "texas", "county",
    "prepared", "for", "sheet", "job", "scale", "date", "revised",
}
MIN_MATCH_TOKENS = 2  # a single coincidental token (e.g. a county-ish word) isn't enough to attribute an operator


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
    # strip a trailing surveyor code segment like "_LGR" or "_LTR" if present
    well_name = re.sub(r"_(LGR|LTR)$", "", rest, flags=re.IGNORECASE)
    return permit_raw, well_name


def infer_operator_county(well_tokens: set[str], master: pd.DataFrame):
    """Score master.csv leases by token overlap with the well name; return
    the (operator, county, match_count) of the strongest match, or
    (None, None, 0) if nothing clears MIN_MATCH_TOKENS. A single coincidental
    token (confirmed on real data: "mesa" alone matched an unrelated Lewis
    Petro/Webb lease, misattributing a Panola/TGNR well) is not enough
    evidence to name an operator -- better to say "unknown" than guess wrong
    with a straight face."""
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

        tokens = tokenize(well_name)
        op, county, score = infer_operator_county(tokens, master)
        fam = family_of(op, families)
        client_hits = match_clients(tokens, op, county, prospects)

        lines.append(f"## {well_name}  (Permit #{permit_raw})")
        lines.append(f"- **Status:** {'ALREADY in master.csv (not early anymore)' if already_known else '**NOT yet in master.csv — early signal**'}")
        if op:
            conf = "strong" if score >= 3 else "weak" if score >= 1 else "none"
            lines.append(f"- **Inferred operator:** {op} ({county})  _[match confidence: {conf}, {score} token overlap]_")
        else:
            lines.append("- **Inferred operator:** unknown — no historical lease-name match; needs manual check")
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
