"""
Load .env into os.environ for scripts run via Windows Task Scheduler.

Task Scheduler processes don't inherit interactive shell env vars (the
SMTP_PASSWORD set via $env: in a PowerShell session is gone once that
window closes) -- .env is the persistent, git-ignored substitute.
Existing os.environ values always win, so GitHub Actions (which sets
these via repo Secrets) is unaffected.
"""

from pathlib import Path


def load_env(path: Path | None = None) -> None:
    import os

    env_path = path or (Path(__file__).parent / ".env")
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())
