#!/usr/bin/env python
"""
Automated RRC daf420 download via headless browser (Playwright).

The RRC GoDrive portal (PrimeFaces/JSF app) requires a real click on the
row checkbox to register server-side selection state before the Download
button's form-submit will produce a file. A plain HTTP GET on the "link"
URL just returns the HTML file browser page, not the data -- this is why
requests.get() always returned HTML. The Download button POSTs the form
and returns a ZIP (named documents_YYYYMMDD.zip) containing the single
file daf420.dat.

Row 0 in the file list is always the current/latest daf420.dat.

Runs via Windows Task Scheduler (see setup_task_scheduler.ps1).
Logs: logs/rrc_download.log
"""

import asyncio
import io
import logging
import os
import subprocess
import sys
import traceback
import zipfile
from datetime import datetime
from pathlib import Path

import yaml

# Task Scheduler doesn't reliably honor -WorkingDirectory the way an
# interactive shell does; anchor everything to this file's location so
# config.yaml and the git repo are always found regardless of launch context.
SCRIPT_DIR = Path(__file__).resolve().parent
os.chdir(SCRIPT_DIR)

log_dir = SCRIPT_DIR / "logs"
log_dir.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(log_dir / "rrc_download.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

GODRIVE_URL = "https://mft.rrc.texas.gov/link/5f07cc72-2e79-4df8-ade1-9aeb792e03fc"
MIN_SIZE_BYTES = 200_000  # daf420.dat is normally 1-3 MB; guard against garbage/empty files

# Chrome executable, installed to a project-local folder rather than the
# default %LOCALAPPDATA%\ms-playwright. Under Task Scheduler's S4U logon
# session, launching a browser from the user's AppData profile path
# reproducibly fails with a bogus "Executable doesn't exist" -- even though
# the file is present and reads fine interactively -- while this repo
# directory (which the S4U token already needs for git operations) works
# without issue. Install with:
#   $env:PLAYWRIGHT_BROWSERS_PATH = 'C:\GIS\permit_intel\.playwright-browsers'
#   python -m playwright install chromium
CHROMIUM_EXE = str(SCRIPT_DIR / ".playwright-browsers" / "chromium-1228" / "chrome-win64" / "chrome.exe")


async def download_daf420(watch_dir: Path) -> Path | None:
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, executable_path=CHROMIUM_EXE)
        page = await browser.new_page(accept_downloads=True)
        try:
            logger.info("Opening RRC GoDrive portal...")
            await page.goto(GODRIVE_URL, wait_until="load", timeout=60000)
            await page.wait_for_timeout(2000)

            # Row 0 is always the current daf420.dat (top of the list, sorted by Last Modified desc)
            logger.info("Selecting current file (row 0)...")
            await page.locator('tr[data-ri="0"] .ui-chkbox-box').click()
            await page.wait_for_timeout(1000)

            selected = await page.eval_on_selector(
                'tr[data-ri="0"]', 'el => el.getAttribute("aria-selected")'
            )
            if selected != "true":
                logger.error("Row selection did not register -- page structure may have changed")
                return None

            logger.info("Triggering download...")
            async with page.expect_download(timeout=45000) as dl_info:
                await page.click("text=Download")
            download = await dl_info.value

            zip_bytes = Path(await download.path()).read_bytes()
            logger.info(f"Downloaded ZIP: {len(zip_bytes)/1024:.0f} KB")

        finally:
            await browser.close()

        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
            names = z.namelist()
            if "daf420.dat" not in names:
                logger.error(f"Expected daf420.dat in zip, found: {names}")
                return None
            data = z.read("daf420.dat")

        if len(data) < MIN_SIZE_BYTES:
            logger.error(f"daf420.dat too small ({len(data)} bytes) -- likely bad/empty file, discarding")
            return None

        today = datetime.now().date()
        dest = watch_dir / f"daf420.dat.{today.month:02d}-{today.day:02d}-{today.year}"
        watch_dir.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        logger.info(f"Saved: {dest} ({len(data)/1024/1024:.2f} MB)")
        return dest


def git_commit_and_push(file_path: Path) -> bool:
    try:
        subprocess.run(["git", "add", str(file_path)], check=True, capture_output=True, timeout=30)
        result = subprocess.run(["git", "diff", "--staged", "--quiet"], capture_output=True, timeout=10)
        if result.returncode == 0:
            logger.info("Nothing new to commit (file unchanged or already committed)")
            return True
        subprocess.run(
            ["git", "commit", "-m", f"Daily TX data: {file_path.name} (auto-downloaded)"],
            check=True, capture_output=True, timeout=30,
        )
        subprocess.run(["git", "push"], check=True, capture_output=True, timeout=60)
        logger.info("Committed and pushed to GitHub")
        return True
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode(errors="replace") if e.stderr else str(e)
        logger.error(f"Git operation failed: {stderr}")
        return False


def main() -> int:
    logger.info("=" * 80)
    logger.info("RRC daf420 Automated Download")
    logger.info("=" * 80)

    cfg = yaml.safe_load(open("config.yaml"))
    watch_dir = Path(cfg["texas"]["watch_dir"])

    today = datetime.now().date()
    existing = watch_dir / f"daf420.dat.{today.month:02d}-{today.day:02d}-{today.year}"
    if existing.exists():
        logger.info(f"{existing.name} already present, skipping download")
        return 0

    dest = asyncio.run(download_daf420(watch_dir))
    if not dest:
        logger.warning("Download failed -- GitHub Actions will fall back to the last committed file")
        return 1

    if git_commit_and_push(dest):
        logger.info("SUCCESS -- file will be picked up by the 9:00 AM workflow run")
        return 0
    return 1


if __name__ == "__main__":
    try:
        exit(main())
    except Exception:
        logger.error("Unhandled exception:\n" + traceback.format_exc())
        exit(1)
