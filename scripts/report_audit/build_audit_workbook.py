import json
import os
from pathlib import Path

from openpyxl import Workbook

from scripts.report_audit.matching import match_candidate

HEADERS = [
    "Client", "MXD", "MXD Last Modified", "Matched PDF(s)", "PDF Date(s)",
    "Report Candidate(s)", "Report Date(s)", "Gmail Confirmation", "Confidence",
]

FILESYSTEM_PATH = Path("data/report_audit/filesystem_matches.json")
GMAIL_PATH = Path("data/report_audit/gmail_sent_pdfs.json")
OUTPUT_PATH = Path(r"C:\GIS\CLIENT\RROG_DOXA_Report_PDF_Email_Audit.xlsx")


def find_gmail_confirmation(mxd_basename, sent_pdfs):
    for entry in sent_pdfs:
        if match_candidate(mxd_basename, entry["subject"]):
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

        client_sent_pdfs = [s for s in sent_pdfs if s["client"] == row["client"]]
        confirmation = find_gmail_confirmation(row["mxd_basename"], client_sent_pdfs)

        confidence = _best_confidence(pdf_matches + report_candidates)

        ws.append([
            row["client"],
            row["mxd_path"],
            row["mxd_modified"],
            "; ".join(os.path.basename(m["path"]) for m in pdf_matches) or None,
            "; ".join(m["date"] for m in pdf_matches) or None,
            "; ".join(os.path.basename(c["path"]) for c in report_candidates) or None,
            "; ".join(c["date"] for c in report_candidates) or None,
            confirmation,
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
