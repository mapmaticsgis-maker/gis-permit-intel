#!/usr/bin/env python
"""
Trigger the Daily Permit Intel GitHub Actions workflow via the REST API
(workflow_dispatch), instead of relying on GitHub's own cron scheduler.

Why: GitHub deprioritizes scheduled (cron) workflow runs, especially on
lower-traffic repos -- observed a 2h25m delay on 2026-07-27 despite a
correctly configured 9:00 AM cron. This PC's Task Scheduler has proven
reliable (auto_download_rrc.py fires within seconds of its scheduled
time), so it triggers the run directly instead.

Runs via Windows Task Scheduler at 9:00 AM CST, after the 7:50 AM
auto-download has had time to complete.
Logs: logs/github_trigger.log
"""

import logging
import os
import sys
import traceback
from pathlib import Path

import requests

SCRIPT_DIR = Path(__file__).resolve().parent
os.chdir(SCRIPT_DIR)

from local_env import load_env
load_env()

log_dir = SCRIPT_DIR / "logs"
log_dir.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(log_dir / "github_trigger.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

OWNER = "mapmaticsgis-maker"
REPO = "gis-permit-intel"
WORKFLOW_FILE = "daily-permit-intel.yml"
BRANCH = "master"


def main() -> int:
    logger.info("=" * 80)
    logger.info("Triggering Daily Permit Intel workflow via GitHub API")
    logger.info("=" * 80)

    token = os.environ.get("GITHUB_PAT")
    if not token:
        logger.error("GITHUB_PAT not set (check .env)")
        return 1

    url = f"https://api.github.com/repos/{OWNER}/{REPO}/actions/workflows/{WORKFLOW_FILE}/dispatches"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    payload = {"ref": BRANCH}

    resp = requests.post(url, headers=headers, json=payload, timeout=30)

    if resp.status_code == 204:
        logger.info("SUCCESS: workflow run dispatched")
        return 0
    else:
        logger.error(f"FAILED: HTTP {resp.status_code} -- {resp.text}")
        return 1


if __name__ == "__main__":
    try:
        exit(main())
    except Exception:
        logger.error("Unhandled exception:\n" + traceback.format_exc())
        exit(1)
