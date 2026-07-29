r"""
GitHub Actions entry point. Mirrors run_daily.py's subprocess-per-state
pattern (proven locally) but adds: self-checks, email delivery (daily
brief + a separate failure alert), and an optional external heartbeat
ping — none of which make sense in the local Windows Task Scheduler
version, so that script is left alone; this is the CI-specific one.

Called by .github/workflows/daily-permit-intel.yml.
"""
import os
import subprocess
import sys
import datetime as dt
from pathlib import Path

import requests

from common import load_cfg, load_master
import self_check
import send_email
from core.invariants import run_all as run_invariants

ROOT = Path(__file__).parent
RUN_LOG = ROOT / "data" / "run_log.csv"


def _ping(suffix: str = ""):
    """Optional healthchecks.io ping — the only thing that can ever catch
    GitHub Actions itself going silent (workflow disabled, billing lapse),
    since nothing running *inside* a stopped Action can detect that.
    Set HEALTHCHECK_URL as a repo secret to enable; no-ops otherwise."""
    url = os.environ.get("HEALTHCHECK_URL")
    if not url:
        return
    try:
        requests.get(f"{url}{suffix}", timeout=10)
    except Exception:
        pass


def run_step(cmd, label: str) -> tuple[bool, str]:
    try:
        r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=900)
        output = r.stdout + (("\nSTDERR:\n" + r.stderr) if r.stderr else "")
        print(f"--- {label} ---\n{output}")
        return r.returncode == 0, output
    except Exception as e:
        print(f"!!! {label} failed to launch: {e}")
        return False, str(e)


def collect_invariants(data_dir, states, today: dt.date) -> list:
    """Run each state's invariants, converting a crash into a failed check.

    The invariants are a sensor, and a sensor must not be able to take down
    the thing it monitors. This loop used to call run_invariants unguarded,
    and it runs BEFORE send_email.send_daily_brief. A ledger carrying a git
    conflict marker makes csv.DictReader yield a row whose ingested_at is
    None, and max(r["ingested_at"] ...) then raises TypeError straight out of
    main() -- so the operator got no brief, no failure alert, no log_run row
    and no healthcheck ping. The pipeline went silent in exactly the way this
    branch exists to prevent. Both CI and the local scheduler append to and
    commit data/<state>/ledger.csv, so conflicts are realistic.

    A broken sensor is now a failed check, which still alarms and still lets
    the brief go out, rather than an abort, which does neither.
    """
    out = []
    for state in states:
        try:
            results = run_invariants(data_dir, state, today)
        except Exception as e:
            results = [("invariants_crashed", False,
                        f"{type(e).__name__}: {e} -- ledger may be malformed; "
                        f"check data/{state}/ledger.csv for conflict markers")]
        for name, ok, detail in results:
            out.append((f"{state}_{name}", ok, detail))
    return out


def main():
    cfg = load_cfg()
    today = dt.date.today().isoformat()

    prev_tx_master = load_master(cfg, "tx")
    prev_la_master = load_master(cfg, "la")
    prev_tx_rows = len(prev_tx_master) if prev_tx_master is not None else 0
    prev_la_rows = len(prev_la_master) if prev_la_master is not None else 0

    tx_ok, tx_out = run_step([sys.executable, "tx_daf420.py"], "TX RRC pull")
    la_ok, la_out = run_step([sys.executable, "la_pull.py"], "LA SONRIS pull")

    if not tx_ok and not la_ok:
        # Both steps failed outright — hard crash, alert immediately and stop.
        send_email.send_failure_alert(
            [("tx_pull_crash", False, tx_out[-1500:]),
             ("la_pull_crash", False, la_out[-1500:])],
            today,
        )
        self_check.log_run(RUN_LOG, None, None, [("hard_crash", False, "both pulls failed")],
                            status="HARD_FAIL")
        _ping("/fail")
        sys.exit(1)

    outd_tx = ROOT / cfg["data_dir"] / "tx" / "out" / today
    outd_la = ROOT / cfg["data_dir"] / "la" / "out" / today
    tx_new = self_check.count_new(outd_tx) if tx_ok else None
    la_new = self_check.count_new(outd_la) if la_ok else None
    tx_digest = self_check.read_digest(outd_tx) if tx_ok else ""
    la_digest = self_check.read_digest(outd_la) if la_ok else ""

    new_tx_master = load_master(cfg, "tx")
    new_la_master = load_master(cfg, "la")
    new_tx_rows = len(new_tx_master) if new_tx_master is not None else prev_tx_rows
    new_la_rows = len(new_la_master) if new_la_master is not None else prev_la_rows

    checks = []
    if tx_ok:
        checks.append(self_check.check_master_grew(prev_tx_rows, new_tx_rows, "tx"))
        checks.append(self_check.check_no_mojibake(tx_digest, "tx"))
        checks.append(self_check.check_volume_sane(tx_new, "tx", floor=0, ceiling=300))
    else:
        checks.append(("tx_pull_failed", False, tx_out[-500:]))
    if la_ok:
        checks.append(self_check.check_master_grew(prev_la_rows, new_la_rows, "la"))
        checks.append(self_check.check_no_mojibake(la_digest, "la"))
        checks.append(self_check.check_volume_sane(la_new, "la", floor=0, ceiling=50))
    else:
        checks.append(("la_pull_failed", False, la_out[-500:]))
    checks.append(self_check.check_run_not_stale(RUN_LOG))

    checks.extend(collect_invariants(cfg["data_dir"], ("tx", "la"), dt.date.today()))

    failed = [c for c in checks if not c[1]]

    brief = f"{tx_digest}\n\n---\n\n{la_digest}" if tx_ok else (
        f"_TX pull skipped or failed this run — see alert email if one arrived._\n\n---\n\n{la_digest}"
    )
    send_email.send_daily_brief(brief, today)
    if failed:
        send_email.send_failure_alert(checks, today)

    self_check.log_run(RUN_LOG, tx_new, la_new, checks,
                        status="OK" if not failed else "SOFT_FAIL")
    _ping()


if __name__ == "__main__":
    main()
