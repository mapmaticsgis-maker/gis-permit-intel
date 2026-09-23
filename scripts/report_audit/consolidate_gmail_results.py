"""One-off consolidation of the Gmail sent-mail search result files pulled
during Task 3 into data/report_audit/gmail_sent_pdfs.json. Not part of the
regular pipeline -- Stage C's search results are gathered by hand each time
via the Gmail MCP tools (see plan Task 3), this just merges this run's dump.
"""
import datetime
import json
from pathlib import Path

RESULT_FILES = {
    "RROG": [
        r"C:\Users\mapma\.claude\projects\C--GIS-permit-intel\b894fd3a-5dfe-4978-a329-f37f0959f64e\tool-results\mcp-6d65b25b-51dd-42bd-9fff-ef796a4809f1-search_threads-1790203509916.txt",
        r"C:\Users\mapma\.claude\projects\C--GIS-permit-intel\b894fd3a-5dfe-4978-a329-f37f0959f64e\tool-results\mcp-6d65b25b-51dd-42bd-9fff-ef796a4809f1-search_threads-1790203547054.txt",
    ],
    "DOXA": [
        r"C:\Users\mapma\.claude\projects\C--GIS-permit-intel\b894fd3a-5dfe-4978-a329-f37f0959f64e\tool-results\mcp-6d65b25b-51dd-42bd-9fff-ef796a4809f1-search_threads-1790203560712.txt",
        r"C:\Users\mapma\.claude\projects\C--GIS-permit-intel\b894fd3a-5dfe-4978-a329-f37f0959f64e\tool-results\mcp-6d65b25b-51dd-42bd-9fff-ef796a4809f1-search_threads-1790203569341.txt",
        r"C:\Users\mapma\.claude\projects\C--GIS-permit-intel\b894fd3a-5dfe-4978-a329-f37f0959f64e\tool-results\mcp-6d65b25b-51dd-42bd-9fff-ef796a4809f1-search_threads-1790203581603.txt",
    ],
}

OUTPUT_PATH = Path("data/report_audit/gmail_sent_pdfs.json")


def main():
    sent_pdfs = []
    seen = set()
    for client, paths in RESULT_FILES.items():
        for path in paths:
            data = json.loads(Path(path).read_text(encoding="utf-8", errors="replace"))
            for thread in data.get("threads", []):
                for msg in thread.get("messages", []):
                    if "SENT" not in msg.get("labelIds", []):
                        continue
                    key = (client, msg["id"])
                    if key in seen:
                        continue
                    seen.add(key)
                    sent_pdfs.append({
                        "client": client,
                        "date": msg["date"][:10],
                        "subject": msg.get("subject", ""),
                    })

    output = {
        "generated_date": datetime.date.today().isoformat(),
        "window_days": 365,
        "note": "subject-based (attachment filenames not cheaply available in bulk); matched via the same token/digit logic as filesystem matching",
        "sent_pdfs": sent_pdfs,
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, indent=2))
    print(f"Wrote {len(sent_pdfs)} sent-mail entries to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
