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
