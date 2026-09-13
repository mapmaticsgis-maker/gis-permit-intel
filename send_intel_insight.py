"""
Picks up cloud-routine-composed briefs and emails them.

Split from the composing steps (intel_insight_evidence.py / the Play Intel
Briefing cloud routine) because composing runs as an isolated cloud agent
(a Claude Code routine) with no access to this machine's .env / SMTP
credentials -- it can only commit the finished brief to the repo. This
script is the local half: pull, look for today's brief(s), email whichever
exist, mark each sent so a second run this machine does the same day
doesn't double-send.

Two brief types share this one script and one Task Scheduler entry rather
than each getting their own -- they're the same pattern (cloud routine
composes + commits, this emails), just different directories/cadences:
  - data/intel_insight/<date>-brief.md      -- daily
  - data/play_intel/<date>-brief.md         -- Mon/Thu only (a Play Intel
    Briefing routine on a Tue/Wed/Fri/weekend run of this script simply
    finds no file for that brief type and skips it -- no harm in checking
    daily for a twice-weekly brief.

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

BRIEFS = [
    ("data/intel_insight", send_email.send_insight_brief),
    ("data/play_intel", send_email.send_play_intel_brief),
]


def send_if_ready(dir_path: Path, day: str, send_fn) -> None:
    brief_path = dir_path / f"{day}-brief.md"
    sent_marker = dir_path / f"{day}-brief.sent"

    if not brief_path.exists():
        print(f"No brief found at {brief_path} -- cloud routine may not have run yet, "
              f"or the day was skipped. Nothing to send.")
        return

    if sent_marker.exists():
        print(f"{brief_path} was already sent (marker present) -- not re-sending.")
        return

    body = brief_path.read_text(encoding="utf-8")
    send_fn(body, day)
    sent_marker.write_text(f"sent {dt.datetime.now().isoformat()}\n", encoding="utf-8")
    print(f"Sent {brief_path} and wrote {sent_marker}.")


def main():
    day = sys.argv[1] if len(sys.argv) > 1 else dt.date.today().isoformat()

    # Cloud routines push directly to origin/master; pull first so a
    # same-morning brief is actually visible before we go looking for it.
    subprocess.run(["git", "pull", "--quiet", "origin", "master"],
                    cwd=str(ROOT), check=False)

    for dir_name, send_fn in BRIEFS:
        send_if_ready(ROOT / dir_name, day, send_fn)
    return 0


if __name__ == "__main__":
    sys.exit(main())
