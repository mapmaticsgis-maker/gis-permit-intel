#!/usr/bin/env python
"""
Daily 8:45 AM CST check: did the automated RRC download (auto_download_rrc.py,
runs at 8:30 AM) succeed?

Silent on success -- only sends an email if today's daf420 file is missing
or wasn't pushed to GitHub, so you know to grab it manually before the
9:00 AM workflow run.

Must run AFTER auto_download_rrc.py's scheduled time, with enough buffer
for it to complete -- confirmed via logs that a same-time-or-earlier check
produces a false "ACTION NEEDED" alert every day even when the download
succeeds moments later (e.g. 2026-08-01: reminder fired 08:33:16, download
succeeded 08:33:18 -- 2 seconds afterward). This is not a duplicate
process; it's this same task racing the download it's meant to verify.

Runs via Windows Task Scheduler.
"""

import os
import smtplib
import subprocess
import sys
import traceback
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import logging
from pathlib import Path

# Task Scheduler doesn't guarantee the -WorkingDirectory is honored the same
# way an interactive shell does; anchor everything to this file's location.
SCRIPT_DIR = Path(__file__).resolve().parent
os.chdir(SCRIPT_DIR)

from local_env import load_env
load_env()

log_dir = SCRIPT_DIR / "logs"
log_dir.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    handlers=[logging.FileHandler(log_dir / "daily_reminder.log", encoding="utf-8")],
)
logger = logging.getLogger(__name__)


def today_file_exists_locally() -> Path | None:
    today = datetime.now().date()
    expected = Path("data/tx/inbox") / f"daf420.dat.{today.month:02d}-{today.day:02d}-{today.year}"
    return expected if expected.exists() else None


def today_file_pushed_to_github(file_path: Path) -> bool:
    """Check the file is committed AND that commit has been pushed (not just staged locally)."""
    try:
        # Is it tracked/committed at all?
        result = subprocess.run(
            ["git", "log", "-1", "--format=%H", "--", str(file_path)],
            capture_output=True, text=True, timeout=15,
        )
        if not result.stdout.strip():
            return False

        # Is the local branch even with (or ahead is fine, behind is not) origin?
        subprocess.run(["git", "fetch", "origin"], capture_output=True, timeout=30)
        behind = subprocess.run(
            ["git", "rev-list", "--count", "HEAD..origin/master"],
            capture_output=True, text=True, timeout=15,
        )
        # If local is behind origin that's fine (someone else pushed); we only
        # care that our commit isn't sitting local-only, unpushed.
        ahead = subprocess.run(
            ["git", "log", "--format=%H", "origin/master..HEAD", "--", str(file_path)],
            capture_output=True, text=True, timeout=15,
        )
        if ahead.stdout.strip():
            return False  # commit touching this file exists locally but not on origin
        return True
    except Exception as e:
        logger.warning(f"Could not verify push status: {e}")
        return True  # don't false-alarm on a git-check failure alone


def send_alert(subject: str, body: str):
    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER", "mapmatics.gis@gmail.com")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    recipient = os.environ.get("ALERT_TO_EMAIL", "mapmatics.gis@gmail.com")

    if not smtp_password:
        logger.error("SMTP_PASSWORD not set in environment; cannot send alert")
        return False

    msg = MIMEMultipart("alternative")
    msg["From"] = smtp_user
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        server = smtplib.SMTP(smtp_host, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(msg)
        server.quit()
        logger.info(f"Alert sent to {recipient}: {subject}")
        return True
    except Exception as e:
        logger.error(f"Failed to send alert: {e}")
        return False


def main():
    logger.info("Checking auto-download status...")

    file_path = today_file_exists_locally()

    if not file_path:
        logger.warning("No daf420 file found for today -- auto-download likely failed")
        send_alert(
            "ACTION NEEDED: RRC auto-download failed",
            "The 8:30 AM automated download did not produce today's daf420 file.\n\n"
            "Grab it manually before 9:00 AM:\n"
            "1. https://mft.rrc.texas.gov/link/5f07cc72-2e79-4df8-ade1-9aeb792e03fc\n"
            "2. Download today's file, drop into C:\\GIS\\permit_intel\\data\\tx\\inbox\\\n"
            "   (auto-commits within 15 min) or upload via GitHub web UI:\n"
            "   https://github.com/mapmaticsgis-maker/gis-permit-intel\n\n"
            "Check logs\\rrc_download.log on the PC for the failure reason.\n",
        )
        return

    if not today_file_pushed_to_github(file_path):
        logger.warning(f"{file_path.name} exists locally but wasn't pushed to GitHub")
        send_alert(
            "ACTION NEEDED: RRC file downloaded but not pushed",
            f"{file_path.name} was downloaded but the commit never reached GitHub "
            "(auto_download_rrc.py's git push likely failed -- network issue?).\n\n"
            "From the PC, run:\n"
            "  cd C:\\GIS\\permit_intel\n"
            "  git add data\\tx\\inbox\\" + file_path.name + "\n"
            "  git commit -m \"Daily TX data: " + file_path.name + "\"\n"
            "  git push\n",
        )
        return

    logger.info(f"{file_path.name} downloaded and pushed successfully -- no alert needed")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.error("Unhandled exception:\n" + traceback.format_exc())
        sys.exit(1)
