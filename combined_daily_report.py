#!/usr/bin/env python
"""
Combined daily intel report: confirmed TX/LA permits + W-1 early signal,
in one file instead of three separate digests.

Auto-detects the most recent dated folder under each of:
  data/tx/out/<YYYY-MM-DD>/digest.md   (daf420 -- confirmed TX permits)
  data/la/out/<YYYY-MM-DD>/digest.md   (SONRIS -- confirmed LA permits)
  data/tx/w1/<YYYYMMDD>/digest.md      (subscriptions -- W-1 early signal)

These three sources naturally land on different calendar dates (LA/TX
publish same-day, W-1 subscriptions lag a day), so each section is
labeled with its own date rather than forcing one shared date.

W-1 entries are deduplicated by permit number -- the subscription ZIPs
include a "Plat" drawing, an "AsApproved" cover sheet, and sometimes a
revision PDF per permit, and w1_intel.py treats each as a separate list
item. This collapses them to one entry per permit, preferring whichever
had a successful OCR read over the "unknown" ones.

Run: python combined_daily_report.py
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def latest_dir(base: Path, pattern: str):
    """Return the most recent (by name, which sorts chronologically) dir
    under base matching pattern that actually has a digest.md."""
    candidates = sorted(
        (d for d in base.glob(pattern) if (d / "digest.md").exists()),
        key=lambda d: d.name,
    )
    return candidates[-1] if candidates else None


def dedupe_w1(digest_text: str) -> str:
    """Collapse W-1 entries with the same permit number to one, preferring
    entries where OCR/fallback actually resolved something over 'unknown'."""
    blocks = re.split(r"(?=^## )", digest_text, flags=re.MULTILINE)
    header, entries = blocks[0], blocks[1:]

    by_permit = {}
    order = []
    for block in entries:
        m = re.search(r"\(Permit #(\d+)\)", block)
        if not m:
            continue
        permit = m.group(1)
        if permit not in by_permit:
            by_permit[permit] = block
            order.append(permit)
        else:
            # Prefer a block with a resolved operator over "unknown"
            existing_unknown = "unknown" in by_permit[permit].lower().split("operator/county:")[1][:60] if "operator/county:" in by_permit[permit].lower() else True
            new_unknown = "unknown" in block.lower().split("operator/county:")[1][:60] if "operator/county:" in block.lower() else True
            if existing_unknown and not new_unknown:
                by_permit[permit] = block

    return header + "".join(by_permit[p] for p in order)


def main():
    tx_dir = latest_dir(ROOT / "data" / "tx" / "out", "2*")
    la_dir = latest_dir(ROOT / "data" / "la" / "out", "2*")
    w1_dir = latest_dir(ROOT / "data" / "tx" / "w1", "2*")

    sections = ["# Combined Daily Permit Intel\n"]

    sections.append("## Confirmed New Permits -- Texas RRC\n")
    if tx_dir:
        text = (tx_dir / "digest.md").read_text(encoding="utf-8")
        sections.append(f"_Source: {tx_dir.name}_\n\n{text}\n")
    else:
        sections.append("_No TX digest found._\n")

    sections.append("\n## Confirmed New Permits -- Louisiana SONRIS\n")
    if la_dir:
        text = (la_dir / "digest.md").read_text(encoding="utf-8")
        sections.append(f"_Source: {la_dir.name}_\n\n{text}\n")
    else:
        sections.append("_No LA digest found._\n")

    sections.append("\n## Early Signal -- W-1 Plats (1-2 days ahead of RRC approval)\n")
    if w1_dir:
        text = (w1_dir / "digest.md").read_text(encoding="utf-8")
        deduped = dedupe_w1(text)
        sections.append(f"_Source: {w1_dir.name}_\n\n{deduped}\n")
    else:
        sections.append("_No W-1 digest found._\n")

    report = "\n".join(sections)

    out_path = ROOT / "combined_daily_report.md"
    out_path.write_text(report, encoding="utf-8")
    print(report)
    print(f"\nSaved: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
