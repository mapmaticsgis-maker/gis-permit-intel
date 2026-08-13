#!/usr/bin/env python
"""
Monitor data/tx/inbox/ for new daf420.dat files and auto-commit them.
Runs via Windows Task Scheduler every 15 minutes (or on-demand).

This is simpler than trying to automate the download (RRC link doesn't work headlessly).
User downloads the file to inbox (from phone, laptop, Dropbox sync, etc), script commits it.
"""

import subprocess
import logging
from pathlib import Path
from datetime import datetime
import sys

# Configure logging
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)
log_file = log_dir / "inbox_commit.log"

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def git_status():
    """Check git status for untracked .dat files in inbox."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=".",
            check=True,
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.stdout
    except Exception as e:
        logger.error(f"git status failed: {e}")
        return ""


def find_uncommitted_dat_files():
    """Find new .dat files in inbox that aren't committed."""
    try:
        status = git_status()
        uncommitted = []

        for line in status.split("\n"):
            # Look for untracked or modified files in data/tx/inbox/
            if "data/tx/inbox/daf420.dat" in line:
                # Line format: "?? path/to/file" or " M path/to/file"
                file_path = line[3:].strip()
                if file_path:
                    uncommitted.append(file_path)

        return uncommitted
    except Exception as e:
        logger.error(f"Failed to find uncommitted files: {e}")
        return []


KNOWN_DRIFT_PATHS = ["data/tx/master.csv", "data/tx/ledger.csv",
                      "data/la/master.csv", "data/la/ledger.csv"]


def _clear_known_local_drift():
    """A separate local task (PermitIntelDaily, an arcpy GDB builder) pulls
    the same TX/LA source data independently and routinely leaves these
    specific files locally modified -- confirmed safe to discard throughout
    manual operation all project: same underlying source, not separate
    work. This script runs every 15 minutes, more often than any other
    committer here, so it's the most likely to hit this and previously had
    no self-heal at all (confirmed 2026-08-13: two sibling scripts with a
    pull-retry still failed the same morning because the retry itself
    didn't clear this drift first)."""
    subprocess.run(["git", "checkout", "--", *KNOWN_DRIFT_PATHS],
                    cwd=".", capture_output=True, timeout=30)


def git_commit_and_push(file_paths):
    """Commit and push file(s) to GitHub."""
    try:
        if not file_paths:
            logger.info("No new files to commit")
            return True

        logger.info(f"Found {len(file_paths)} new file(s) to commit")

        # Stage files
        for file_path in file_paths:
            subprocess.run(
                ["git", "add", file_path],
                cwd=".",
                check=True,
                capture_output=True,
                timeout=30
            )
            logger.info(f"  Staged: {file_path}")

        # Commit
        msg = f"Daily TX data: {', '.join([Path(f).name for f in file_paths])}"
        subprocess.run(
            ["git", "commit", "-m", msg],
            cwd=".",
            check=True,
            capture_output=True,
            timeout=30
        )
        logger.info(f"Committed: {msg}")

        # Push
        try:
            subprocess.run(
                ["git", "push"],
                cwd=".",
                check=True,
                capture_output=True,
                timeout=60
            )
        except subprocess.CalledProcessError:
            logger.warning("Push rejected -- clearing known local drift and retrying")
            _clear_known_local_drift()
            subprocess.run(["git", "pull", "--no-edit"], cwd=".", check=True,
                            capture_output=True, timeout=60)
            subprocess.run(["git", "push"], cwd=".", check=True,
                            capture_output=True, timeout=60)
        logger.info("Pushed to GitHub")

        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"Git operation failed: {e.stderr.decode() if e.stderr else str(e)}")
        return False
    except Exception as e:
        logger.error(f"Git error: {e}", exc_info=True)
        return False


def main():
    """Main entry point."""
    logger.info("TX Inbox Auto-Commit Monitor")

    # Find new files
    new_files = find_uncommitted_dat_files()

    if not new_files:
        logger.debug("No new files to commit")
        return 0

    # Commit and push
    if git_commit_and_push(new_files):
        logger.info(f"SUCCESS: {len(new_files)} file(s) committed and pushed")
        return 0
    else:
        logger.warning("Failed to commit files")
        return 1


if __name__ == "__main__":
    exit(main())
