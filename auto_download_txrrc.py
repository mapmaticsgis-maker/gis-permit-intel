#!/usr/bin/env python
"""
Automated daily TX RRC daf420 download + commit via Windows Task Scheduler.
Runs at 8:00 AM, downloads today's file, commits to GitHub.

Methods tried (in order):
  1. RRC fetch_url (with retries + proper headers)
  2. GoDrive folder (if folder ID configured)
  3. Graceful skip if all fail (workflow uses last known good file)

Logs to: logs/txrrc_download.log
"""

import requests
import subprocess
import logging
import yaml
import time
from pathlib import Path
from datetime import datetime
import sys

# Configure logging
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)
log_file = log_dir / "txrrc_download.log"

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def download_from_rrc_url(cfg, today):
    """Download from RRC's fetch_url with retries and proper headers."""
    try:
        url = cfg.get("texas", {}).get("fetch_url")
        if not url:
            logger.info("RRC fetch_url not configured, skipping")
            return None

        headers = {
            "User-Agent": "permit-intel-bot (github.com/mapmaticsgis-maker/gis-permit-intel)",
            "Accept": "*/*"
        }

        logger.info(f"Attempting RRC fetch_url (retries: 3)...")

        for attempt in range(1, 4):
            try:
                resp = requests.get(url, headers=headers, timeout=120)
                resp.raise_for_status()

                content_type = resp.headers.get("Content-Type", "")

                # Guard against HTML error/login pages
                if "text/html" in content_type:
                    logger.warning("fetch_url returned HTML (login/error page), not binary data")
                    if attempt < 3:
                        time.sleep(2 ** attempt)
                        continue
                    return None

                # Check file size (daf420 files are typically 1-3 MB)
                if len(resp.content) < 200000:
                    logger.warning(f"Downloaded file too small ({len(resp.content)/1024:.0f} KB), likely wrong file")
                    if attempt < 3:
                        time.sleep(2 ** attempt)
                        continue
                    return None

                # Success!
                dest = Path(cfg["texas"]["watch_dir"]) / f"daf420.dat.{today.month:02d}-{today.day:02d}-{today.year}"
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(resp.content)

                size_mb = len(resp.content) / 1024 / 1024
                logger.info(f"[RRC fetch_url] SUCCESS: Downloaded {dest.name} ({size_mb:.1f} MB)")
                return dest

            except requests.exceptions.RequestException as e:
                logger.warning(f"Attempt {attempt}/3 failed: {e}")
                if attempt < 3:
                    wait = 2 ** attempt
                    logger.info(f"Retrying in {wait}s...")
                    time.sleep(wait)

        logger.warning("RRC fetch_url failed after 3 attempts")
        return None

    except Exception as e:
        logger.error(f"RRC fetch_url error: {e}", exc_info=True)
        return None


def download_from_godrive(cfg, today):
    """Download from GoDrive folder if folder_id is configured."""
    try:
        folder_id = cfg.get("texas", {}).get("godrive_folder_id")
        if not folder_id:
            logger.debug("GoDrive folder_id not configured, skipping")
            return None

        logger.info(f"Attempting GoDrive folder download...")
        today_str = f"{today.month:02d}-{today.day:02d}-{today.year}"

        # List files in the folder (via shared folder view)
        folder_url = f"https://drive.google.com/drive/folders/{folder_id}"

        resp = requests.get(folder_url, timeout=30)
        resp.raise_for_status()

        # Parse HTML for file ID matching today's date
        import re
        # Look for Google Drive file references in the page HTML
        # Google Drive embeds file IDs in the page source
        pattern = rf'\"([a-zA-Z0-9_-]{{20,}})\",\"[^\"]*daf420\.dat\.{re.escape(today_str)}'

        match = re.search(pattern, resp.text)
        if not match:
            logger.warning(f"Could not find daf420.dat.{today_str} in GoDrive folder HTML")
            return None

        file_id = match.group(1)
        download_url = f"https://drive.google.com/uc?id={file_id}&export=download"

        logger.info(f"Found file in GoDrive, downloading...")

        r = requests.get(download_url, timeout=120)
        r.raise_for_status()

        if len(r.content) < 200000:
            logger.warning(f"Downloaded file too small ({len(r.content)/1024:.0f} KB)")
            return None

        dest = Path(cfg["texas"]["watch_dir"]) / f"daf420.dat.{today_str}"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(r.content)

        size_mb = len(r.content) / 1024 / 1024
        logger.info(f"[GoDrive] SUCCESS: Downloaded {dest.name} ({size_mb:.1f} MB)")
        return dest

    except Exception as e:
        logger.warning(f"GoDrive download failed: {e}")
        return None


def git_commit_and_push(file_path):
    """Commit and push the file to GitHub."""
    try:
        logger.info(f"Committing {file_path.name} to git...")

        # Stage file
        subprocess.run(
            ["git", "add", str(file_path)],
            cwd=".",
            check=True,
            capture_output=True,
            timeout=30
        )

        # Check if there's anything staged
        result = subprocess.run(
            ["git", "diff", "--staged", "--quiet"],
            cwd=".",
            capture_output=True,
            timeout=10
        )

        if result.returncode == 0:
            logger.info("No changes to commit (file may already exist)")
            return True

        # Commit
        subprocess.run(
            ["git", "commit", "-m", f"Daily TX data: {file_path.name}"],
            cwd=".",
            check=True,
            capture_output=True,
            timeout=30
        )
        logger.info("Commit successful")

        # Push
        subprocess.run(
            ["git", "push"],
            cwd=".",
            check=True,
            capture_output=True,
            timeout=60
        )
        logger.info("Push successful")

        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"Git operation failed: {e.stderr.decode() if e.stderr else str(e)}")
        return False
    except Exception as e:
        logger.error(f"Git error: {e}", exc_info=True)
        return False


def main():
    """Main entry point."""
    today = datetime.now().date()
    logger.info("=" * 80)
    logger.info(f"TX RRC Daily Auto-Download Started ({today})")
    logger.info("=" * 80)

    # Load config
    try:
        cfg = yaml.safe_load(open("config.yaml"))
    except Exception as e:
        logger.error(f"Failed to load config.yaml: {e}")
        return 1

    file_path = None

    # Try download methods
    logger.info("Attempting download methods...")

    # Method 1: RRC fetch_url
    file_path = download_from_rrc_url(cfg, today)

    # Method 2: GoDrive folder (if configured)
    if not file_path:
        file_path = download_from_godrive(cfg, today)

    # If we got a file, commit it
    if file_path:
        logger.info("Download successful, attempting git commit...")
        if git_commit_and_push(file_path):
            logger.info("=" * 80)
            logger.info(f"SUCCESS: {file_path.name} downloaded and pushed to GitHub")
            logger.info("GitHub Actions will pick it up in the 10:15 AM run")
            logger.info("=" * 80)
            return 0
        else:
            logger.warning("=" * 80)
            logger.warning("Downloaded file but failed to commit. Manual intervention may be needed.")
            logger.warning("=" * 80)
            return 1
    else:
        logger.warning("=" * 80)
        logger.warning("All download methods failed")
        logger.warning("GitHub Actions will use the last known good file from watch_dir")
        logger.warning("This is OK for now, but you may want to investigate if this persists")
        logger.warning("=" * 80)
        return 1


if __name__ == "__main__":
    exit(main())
