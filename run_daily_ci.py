r"""
GitHub Actions entry point. Mirrors run_daily.py's subprocess-per-state
pattern (proven locally) but adds: self-checks, email delivery (daily
brief + a separate failure alert), and an optional external heartbeat
ping — none of which make sense in the local Windows Task Scheduler
version, so that script is left alone; this is the CI-specific one.

Called by .github/workflows/daily-permit-intel.yml.
"""
import os
import re
import subprocess
import sys
import datetime as dt
from pathlib import Path

import pandas as pd
import requests

from common import load_cfg, load_master
import self_check
import send_email
import market_brief
from core.invariants import run_all as run_invariants
from core.outputs import read_skip_marker

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


def brief_section(label: str, ok: bool, digest: str, skip: dict | None) -> str:
    """One state's slice of the daily brief, always self-describing.

    An empty section used to be ambiguous: the pull could have failed, or it
    could have correctly skipped an unchanged source. The operator could not
    tell which, and on a skip tx_ok was True so no alert explained it.
    """
    if not ok:
        return (f"# {label}\n\n_The {label} pull FAILED this run — "
                f"see the alert email for details._")
    if skip:
        return self_check.skip_note(label, skip)
    if not digest.strip():
        return (f"# {label}\n\n_No digest was produced this run and no skip was "
                f"recorded — this is unexpected; check the run log._")
    return digest


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


W1_ATTACHMENT_BUDGET = 14 * 1024 * 1024  # base64 adds ~37% overhead (measured: 16.5MB raw -> 22.3MB encoded),
                                          # so 14MB raw stays well clear of Gmail's 25MB message cap

# Corridor counties worth attaching plats for. Narrows attachment volume to
# client-relevant areas -- both a Gmail-cap mitigation and a relevance filter,
# since most days' full plat set is well outside any watched corridor.
W1_ATTACH_COUNTIES = {
    "LEE", "LAVACA", "FAYETTE",  # Giddings
    "PANOLA", "RUSK", "HARRISON", "CHEROKEE", "SHELBY",
    "SAN AUGUSTINE", "SMITH", "NACOGDOCHES", "GREGG",  # East Texas
}


def _permit_counties_from_digest(digest_text: str) -> dict[str, str]:
    """Map permit number -> county (uppercased) from a W-1 digest.md's
    '**Operator/county:** OP (COUNTY)' lines. w1_intel.py's OCR only runs
    locally (not on GitHub Actions), so this reads its already-committed
    output rather than re-deriving county here.

    Permits where OCR/fallback couldn't resolve a county read as
    "unknown county" in the digest and are absent from the returned dict --
    those plats are excluded from attachment even if the well is plausibly
    in-corridor, since there's nothing here to check it against.
    """
    counties = {}
    for block in re.split(r"(?=^## )", digest_text, flags=re.MULTILINE):
        m_permit = re.search(r"\(Permit #(\d+)\)", block)
        if not m_permit:
            continue
        m_county = re.search(r"Operator/county:\*\*\s*[^(\n]*\(([^)]+)\)", block)
        if not m_county:
            continue
        county = m_county.group(1).strip().upper()
        if county != "UNKNOWN COUNTY":
            counties[m_permit.group(1)] = county
    return counties


def w1_plat_attachments(w1_dir: Path, digest_text: str = "") -> tuple[list[Path], str | None]:
    """Collect this run's plat drawings (not the generic AsApproved cover
    sheet) for email attachment, restricted to W1_ATTACH_COUNTIES. Filenames
    follow RRC's convention: <permit>_Plat_<well name>_<code>.<pdf|tif> --
    see w1_intel.py's docstring.

    Returns (files, skip_note). skip_note is set instead of files when the
    corridor-filtered plats still exceed W1_ATTACHMENT_BUDGET, so a heavy
    day degrades to "no attachments, here's why" rather than a failed or
    oversized send.
    """
    if not w1_dir.exists():
        return [], None
    plats = sorted(p for p in w1_dir.glob("**/*")
                    if p.is_file() and "_plat_" in p.name.lower())
    if not plats:
        return [], None

    permit_counties = _permit_counties_from_digest(digest_text)
    plats = [p for p in plats
             if permit_counties.get(p.name.split("_", 1)[0]) in W1_ATTACH_COUNTIES]
    if not plats:
        return [], None

    total = sum(p.stat().st_size for p in plats)
    if total > W1_ATTACHMENT_BUDGET:
        return [], (f"{len(plats)} corridor plat(s) found ({total / 1024 / 1024:.1f} MB) but skipped "
                    f"as email attachments -- over the {W1_ATTACHMENT_BUDGET / 1024 / 1024:.0f} MB budget. "
                    f"See {w1_dir} locally.")
    return plats, None


def la_recheck_list(cfg, root: Path, days: int = 14) -> str:
    """Wells flagged in the past N days, with SONRIS's doc-access link, so
    the user can quickly click through and see whether a plat/application
    has posted since. SONRIS's document-access page is CAPTCHA-gated --
    confirmed via a direct HTTP request (not just browser automation), so
    this can't be checked automatically. A compiled list with links is the
    honest alternative to pretending the status was verified."""
    la_out = root / cfg["data_dir"] / "la" / "out"
    cutoff = dt.date.today() - dt.timedelta(days=days)
    rows = []
    for day_dir in sorted(la_out.glob("2*")):
        try:
            day = dt.date.fromisoformat(day_dir.name)
        except ValueError:
            continue
        if day < cutoff:
            continue
        f = day_dir / "new_permits.csv"
        if not f.exists() or f.stat().st_size == 0:
            continue
        try:
            df = pd.read_csv(f, dtype=str)
        except pd.errors.EmptyDataError:
            continue
        for _, r in df.iterrows():
            link = r.get("DOC_ACCESS")
            if pd.isna(link) or not str(link).strip():
                continue
            rows.append({
                "date": day.isoformat(),
                "operator": r.get("operator", "") or "",
                "well": r.get("well", "") or "",
                "well_num": r.get("well_num", "") or "",
                "parish": str(r.get("parish", "") or "").title(),
                "link": link,
            })

    header = f"# LA Well-Docs Recheck List (past {days} days)\n"
    if not rows:
        return header + f"\n_No LA permits with doc-check links found in the past {days} days._"
    body = [
        "Wells flagged recently -- click to check if a plat/application has "
        "posted since (SONRIS is CAPTCHA-gated, so this can't be checked "
        "automatically):\n"
    ]
    for row in rows:
        body.append(f"- **{row['operator']}** — {row['well']} ({row['well_num']}), "
                     f"{row['parish']} — flagged {row['date']}")
        body.append(f"  {row['link']}")
    return header + "\n" + "\n".join(body)


def main():
    cfg = load_cfg()
    today = dt.date.today().isoformat()

    prev_tx_master = load_master(cfg, "tx")
    prev_la_master = load_master(cfg, "la")
    prev_tx_rows = len(prev_tx_master) if prev_tx_master is not None else 0
    prev_la_rows = len(prev_la_master) if prev_la_master is not None else 0

    tx_ok, tx_out = run_step([sys.executable, "tx_daf420.py"], "TX RRC pull")
    la_ok, la_out = run_step([sys.executable, "la_pull.py"], "LA SONRIS pull")

    # Generate market brief after both masters are updated
    brief_ok = False
    brief_out = ""
    if tx_ok:
        try:
            cfg = load_cfg()
            asof = pd.Timestamp(dt.date.today())
            brief_text = market_brief.build_brief(cfg, asof)
            outd_tx = ROOT / cfg["data_dir"] / "tx" / "out" / today
            outd_tx.mkdir(parents=True, exist_ok=True)
            brief_path = outd_tx / "market_brief.md"
            brief_path.write_text(brief_text, encoding="utf-8")
            brief_ok = True
            brief_out = f"Brief written to {brief_path}"
        except Exception as e:
            brief_ok = False
            brief_out = f"Market brief failed: {e}"
            print(f"--- Market Brief ---\n{brief_out}")

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

    # W-1 subscription digest: written locally by auto_download_subscriptions.py
    # (Playwright + OCR, can't run on GitHub Actions' runner) and committed
    # from there, so this step only has to read whatever landed in the repo.
    # Files posted today carry yesterday's date (RRC's own convention), so the
    # folder to check is dated yesterday, not today.
    yesterday_nodash = (dt.date.today() - dt.timedelta(days=1)).strftime("%Y%m%d")
    outd_w1 = ROOT / cfg["data_dir"] / "tx" / "w1" / yesterday_nodash
    w1_digest = self_check.read_digest(outd_w1)
    w1_attachments, w1_attach_skip_note = w1_plat_attachments(outd_w1, w1_digest)
    if w1_digest.strip():
        w1_section = f"# TX RRC W-1 Early Signal ({yesterday_nodash})\n\n{w1_digest}"
    else:
        w1_section = (
            f"# TX RRC W-1 Early Signal ({yesterday_nodash})\n\n"
            "_No W-1 subscription digest found for this date -- either RRC hadn't "
            "posted it yet, it's a Mon/Tue skip day, or the local download step "
            "didn't commit in time before this run._"
        )
    if w1_attachments:
        w1_section += f"\n\n_{len(w1_attachments)} plat drawing(s) attached to this email._"
    elif w1_attach_skip_note:
        w1_section += f"\n\n_{w1_attach_skip_note}_"

    # A skip marker only describes the day when the day has no new_permits.csv.
    # If an earlier run that day produced real output, that output is the truth
    # and a leftover marker must not override it.
    tx_skip = read_skip_marker(outd_tx) if (tx_ok and tx_new is None) else None
    la_skip = read_skip_marker(outd_la) if (la_ok and la_new is None) else None

    new_tx_master = load_master(cfg, "tx")
    new_la_master = load_master(cfg, "la")
    new_tx_rows = len(new_tx_master) if new_tx_master is not None else prev_tx_rows
    new_la_rows = len(new_la_master) if new_la_master is not None else prev_la_rows

    checks = []
    if tx_ok:
        checks.append(self_check.check_master_grew(prev_tx_rows, new_tx_rows, "tx"))
        checks.append(self_check.check_no_mojibake(tx_digest, "tx"))
        checks.append(self_check.check_volume_sane(tx_new, "tx", floor=0, ceiling=300,
                                                   skip=tx_skip))
    else:
        checks.append(("tx_pull_failed", False, tx_out[-500:]))
    if la_ok:
        checks.append(self_check.check_master_grew(prev_la_rows, new_la_rows, "la"))
        checks.append(self_check.check_no_mojibake(la_digest, "la"))
        checks.append(self_check.check_volume_sane(la_new, "la", floor=0, ceiling=50,
                                                   skip=la_skip))
    else:
        checks.append(("la_pull_failed", False, la_out[-500:]))
    checks.append(self_check.check_run_not_stale(RUN_LOG))

    checks.extend(collect_invariants(cfg["data_dir"], ("tx", "la"), dt.date.today()))

    failed = [c for c in checks if not c[1]]

    # Each section states its own status. The old text lumped "skipped" and
    # "failed" into one sentence for TX and said nothing at all for LA, so a
    # correctly-skipped weekend run produced a blank section the operator had
    # no way to interpret.
    brief = "\n\n---\n\n".join([
        brief_section("Texas RRC (daf420)", tx_ok, tx_digest, tx_skip),
        brief_section("Louisiana SONRIS", la_ok, la_digest, la_skip),
        w1_section,
        la_recheck_list(cfg, ROOT),
    ])
    send_email.send_daily_brief(brief, today, attachments=w1_attachments)
    if failed:
        send_email.send_failure_alert(checks, today)

    self_check.log_run(RUN_LOG, tx_new, la_new, checks,
                        status="OK" if not failed else "SOFT_FAIL")
    _ping()


if __name__ == "__main__":
    main()
