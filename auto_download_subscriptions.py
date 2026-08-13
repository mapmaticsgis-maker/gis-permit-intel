#!/usr/bin/env python
"""
Download RRC subscription W-1 ZIP files (district 3 & 6) from GoDrive portal.

Files post daily ~10:30 AM (skip Mon/Tue). Downloaded via headless Playwright
from https://mft.rrc.texas.gov/link/f11363bb-8120-4e8c-bbc0-a253ec0a85d4,
unzipped to data/tx/w1/<YYYYMMDD>/, then analyzed via w1_intel.py.

Logs: logs/subscriptions_download.log
"""

import logging
import os
import shutil
import subprocess
import sys
import traceback
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path

from playwright.sync_api import sync_playwright

SCRIPT_DIR = Path(__file__).resolve().parent
os.chdir(SCRIPT_DIR)

log_dir = SCRIPT_DIR / "logs"
log_dir.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(log_dir / "subscriptions_download.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

PORTAL_URL = "https://mft.rrc.texas.gov/link/f11363bb-8120-4e8c-bbc0-a253ec0a85d4"
DISTRICTS = ["03", "06"]

# Task Scheduler's S4U logon session can't resolve %LOCALAPPDATA%\ms-playwright
# the way an interactive session does, so the default browser install is
# invisible to it (same issue solved for auto_download_rrc.py). Use the
# project-local Chromium install instead, which S4U already has access to.
CHROMIUM_EXE = str(SCRIPT_DIR / ".playwright-browsers" / "chromium-1228" / "chrome-win64" / "chrome.exe")


def should_run_today():
    """Skip Monday (0) and Tuesday (1) -- no filings over weekend."""
    return date.today().weekday() not in (0, 1)


KNOWN_DRIFT_PATHS = ["data/tx/master.csv", "data/tx/ledger.csv",
                      "data/la/master.csv", "data/la/ledger.csv"]


def _clear_known_local_drift():
    """A separate local task (PermitIntelDaily, an arcpy GDB builder) pulls
    the same TX/LA source data independently and routinely leaves these
    specific files locally modified -- confirmed safe to discard throughout
    manual operation all project: same underlying source, not separate
    work. Left uncleared, this blocks `git pull` outright (confirmed
    2026-08-13: this script's push retry failed and the digest sat
    unpushed all day, alongside the same failure in auto_download_rrc.py),
    which is a stronger failure than the non-fast-forward case this retry
    was originally built for -- a blocked pull never even reaches the
    retry push."""
    subprocess.run(["git", "checkout", "--", *KNOWN_DRIFT_PATHS],
                    capture_output=True, timeout=30)


def git_commit_and_push(file_path: Path) -> bool:
    try:
        subprocess.run(["git", "add", str(file_path)], check=True, capture_output=True, timeout=30)
        result = subprocess.run(["git", "diff", "--staged", "--quiet"], capture_output=True, timeout=10)
        if result.returncode == 0:
            logger.info("Nothing new to commit (digest unchanged or already committed)")
            return True
        subprocess.run(
            ["git", "commit", "-m", f"W-1 early signal: {file_path.parent.name} (auto-downloaded)"],
            check=True, capture_output=True, timeout=30,
        )
        try:
            subprocess.run(["git", "push"], check=True, capture_output=True, timeout=60)
        except subprocess.CalledProcessError:
            # Same non-fast-forward pattern as auto_download_rrc.py -- GitHub
            # Actions' own commit routinely lands on origin first. Merge pull
            # resolves the common case; a real conflict still raises.
            logger.warning("Push rejected (likely non-fast-forward) -- clearing known local drift and retrying")
            _clear_known_local_drift()
            subprocess.run(["git", "pull", "--no-edit"], check=True, capture_output=True, timeout=60)
            subprocess.run(["git", "push"], check=True, capture_output=True, timeout=60)
        return True
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode(errors="replace") if e.stderr else str(e)
        logger.error(f"Git operation failed: {stderr}")
        return False


def download_files(page, target_date_str: str, download_dir: Path):
    """
    Find and download district 3 & 6 files for a given date from the sorted portal.
    Returns dict of {district: file_path}.
    """
    logger.info(f"Navigating to portal (target date: {target_date_str})")
    page.goto(PORTAL_URL, wait_until="networkidle")
    page.wait_for_timeout(3000)

    # Click "Last Modified" column header twice: first to sort ascending, second to sort descending (newest first)
    modified_header = page.locator('[role="columnheader"]:has-text("Last Modified")')
    if modified_header.count() > 0:
        logger.info("Sorting by Last Modified (newest first)")
        modified_header.first.click()
        page.wait_for_timeout(1500)
        modified_header.first.click()  # Second click for descending order
        page.wait_for_timeout(1500)
    else:
        logger.warning("Could not find Last Modified header")

    downloaded = {}

    # Find all ZIP file links visible on the page
    zip_links = page.locator('a:has-text(".zip")')
    count = zip_links.count()
    logger.info(f"Found {count} ZIP file links on portal")

    # Look for the target date's district 3 & 6 files
    for district in DISTRICTS:
        target_filename = f"subscriptions_{target_date_str}_district{district}.zip"
        logger.info(f"Looking for: {target_filename}")

        found = False
        for i in range(min(count, 50)):  # Check first 50 links
            link_text = zip_links.nth(i).inner_text()
            if target_filename in link_text or (
                target_date_str in link_text and f"district{district}" in link_text
            ):
                logger.info(f"  Found link for district {district}")
                # Set up download handler before clicking
                with page.expect_download() as download_info:
                    zip_links.nth(i).click()
                    download = download_info.value
                    dest = download_dir / download.suggested_filename
                    download.save_as(dest)
                    downloaded[district] = dest
                    logger.info(f"  Downloaded: {dest.name} ({dest.stat().st_size / 1024 / 1024:.1f} MB)")
                found = True
                break

        if not found:
            logger.warning(f"  District {district} file not found for {target_date_str}")

    return downloaded


def unzip_to_w1(zip_files: dict, today_str: str):
    """Unzip district files to data/tx/w1/<date>/."""
    w1_dir = SCRIPT_DIR / "data" / "tx" / "w1" / today_str
    w1_dir.mkdir(parents=True, exist_ok=True)

    for district, zip_path in zip_files.items():
        logger.info(f"Unzipping district {district} to {w1_dir}")
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(w1_dir)
            logger.info(f"  Extracted {len(zf.namelist())} files")
        except Exception as e:
            logger.error(f"  Failed to unzip: {e}")
            raise

    return w1_dir


def main() -> int:
    logger.info("=" * 80)
    logger.info("RRC Subscription (W-1) Automated Download")
    logger.info("=" * 80)

    if not should_run_today():
        day_name = date.today().strftime("%A")
        logger.info(f"Skipping {day_name} (no filings over weekend)")
        return 0

    # Files posted today contain YESTERDAY's W-1 data. The RRC filename uses
    # dashed dates (subscriptions_2026-07-30_district03.zip), but the shared
    # W-1 folder convention -- used by manual drops and w1_intel.py's own
    # default -- is undashed YYYYMMDD. Keep both: dashed for the portal
    # search, undashed for anywhere the two sources need to land in the
    # same per-day folder.
    yesterday = date.today() - timedelta(days=1)
    yesterday_str = yesterday.strftime("%Y-%m-%d")
    yesterday_nodash = yesterday.strftime("%Y%m%d")

    download_dir = Path(SCRIPT_DIR / ".subscriptions_temp")
    download_dir.mkdir(exist_ok=True)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, executable_path=CHROMIUM_EXE)
            page = browser.new_page()
            page.on("download", lambda download: None)  # Let expect_download handle it

            # Download yesterday's files (posted today)
            zip_files = download_files(page, yesterday_str, download_dir)
            browser.close()

            if not zip_files:
                logger.warning(f"No district 3 or 6 files found for {yesterday_str}")
                return 0

            w1_dir = unzip_to_w1(zip_files, yesterday_nodash)
            logger.info(f"All files extracted to {w1_dir}")

            # List extracted plats
            plat_files = list(w1_dir.glob("**/*.pdf"))
            logger.info(f"Found {len(plat_files)} PDF files in subscription zips")

            if plat_files:
                logger.info(f"SUCCESS -- running W-1 analysis on {len(plat_files)} plats")
                # Run W-1 intel analysis on the extracted files
                result = subprocess.run(
                    [sys.executable, "w1_intel.py", yesterday_nodash],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    logger.info("W-1 analysis completed successfully")
                    # Print the analysis output
                    if result.stdout:
                        for line in result.stdout.split('\n')[:20]:  # First 20 lines
                            if line.strip():
                                logger.info(f"  {line}")
                else:
                    logger.error(f"W-1 analysis failed: {result.stderr}")
                    return 1

                # Without this, the digest sat local-only every day and never
                # reached the repo -- GitHub Actions runs remotely and builds
                # the email from committed files, so a local-only digest is
                # invisible to it no matter how correct the local run was.
                digest_path = w1_dir / "digest.md"
                if digest_path.exists() and git_commit_and_push(digest_path):
                    logger.info("W-1 digest committed and pushed")
                else:
                    logger.error("W-1 digest was NOT committed -- today's email will not include it")
                    return 1
                return 0
            else:
                logger.warning("No PDF files found in downloaded ZIPs")
                return 0

    except Exception as e:
        logger.error("Unhandled exception:\n" + traceback.format_exc())
        return 1

    finally:
        # Clean up temp ZIP files
        if download_dir.exists():
            shutil.rmtree(download_dir, ignore_errors=True)


if __name__ == "__main__":
    exit(main())
