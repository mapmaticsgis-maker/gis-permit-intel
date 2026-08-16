"""
Picks up the intel-insight brief a cloud routine composed and commits it to
the inbox for emailing.

Split from intel_insight_evidence.py because the composing step runs as an
isolated cloud agent (Claude Code routine) with no access to this machine's
.env / SMTP credentials -- it can only commit the finished brief to the repo.
This script is the local half: pull, look for today's brief, email it, mark
it sent so a second run this machine does the same day doesn't double-send.

Expects the cloud routine to have written and pushed
data/intel_insight/<date>-brief.md (plain text, ready to email as-is).

Run: python send_intel_insight.py            (today's date)
     python send_intel_insight.py 2026-08-15 (backfill/testing)
"""
import subprocess
import sys
import datetime as dt
from pathlib import Path

import local_env
local_env.load_env()

import send_email

ROOT = Path(__file__).resolve().parent
INSIGHT_DIR = ROOT / "data" / "intel_insight"


def main():
    day = sys.argv[1] if len(sys.argv) > 1 else dt.date.today().isoformat()

    # The cloud routine pushes directly to origin/master; pull first so a
    # same-morning brief is actually visible before we go looking for it.
    subprocess.run(["git", "pull", "--quiet", "origin", "master"],
                    cwd=str(ROOT), check=False)

    brief_path = INSIGHT_DIR / f"{day}-brief.md"
    sent_marker = INSIGHT_DIR / f"{day}-brief.sent"

    if not brief_path.exists():
        print(f"No brief found at {brief_path} -- cloud routine may not have run yet, "
              f"or the day was skipped. Nothing to send.")
        return 0

    if sent_marker.exists():
        print(f"{brief_path} was already sent (marker present) -- not re-sending.")
        return 0

    body = brief_path.read_text(encoding="utf-8")
    send_email.send_insight_brief(body, day)
    sent_marker.write_text(f"sent {dt.datetime.now().isoformat()}\n", encoding="utf-8")
    print(f"Sent {brief_path} and wrote {sent_marker}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
