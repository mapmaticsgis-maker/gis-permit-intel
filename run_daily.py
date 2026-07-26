r"""Daily orchestrator for the permit intel pipeline.
Runs TX (if today's daf420 file has been downloaded) then LA (always, fully automatic via
SONRIS REST). Logs everything to logs\daily_YYYY-MM-DD.log so a scheduled run leaves a
record you can check without babysitting it.

Scheduled via Windows Task Scheduler at 08:30 local time (see instructions).
Place this file in C:\GIS\permit_intel alongside tx_daf420.py, la_pull.py, config.yaml.
"""
import subprocess, sys, os, pathlib, datetime as dt

ROOT = pathlib.Path(__file__).parent
LOGDIR = ROOT / "logs"
LOGDIR.mkdir(exist_ok=True)
today = dt.date.today()
logfile = LOGDIR / f"daily_{today.isoformat()}.log"
DOWNLOADS = pathlib.Path(os.path.expanduser("~")) / "Downloads"

def log(msg):
    line = f"[{dt.datetime.now():%H:%M:%S}] {msg}"
    print(line)
    with open(logfile, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def run(cmd, label):
    log(f"--- {label} ---")
    try:
        r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=900)
        with open(logfile, "a", encoding="utf-8") as f:
            f.write(r.stdout + "\n")
            if r.stderr:
                f.write("STDERR:\n" + r.stderr + "\n")
        print(r.stdout)
        if r.returncode != 0:
            log(f"!!! {label} exited with code {r.returncode} -- see log for details")
        else:
            log(f"{label} OK")
        return r.returncode == 0
    except Exception as e:
        log(f"!!! {label} failed to launch: {e}")
        return False

def main():
    log("=== Daily permit intel run starting ===")

    # --- TX: only runs if today's daf420 file is already sitting in Downloads ---
    expected = DOWNLOADS / f"daf420.dat.{today.month:02d}-{today.day:02d}-{today.year}"
    tx_file = expected if expected.exists() else None
    if tx_file is None:
        cands = sorted(DOWNLOADS.glob("daf420.dat.*"), key=lambda p: p.stat().st_mtime, reverse=True)
        if cands and dt.date.fromtimestamp(cands[0].stat().st_mtime) == today:
            tx_file = cands[0]

    if tx_file:
        log(f"TX file found: {tx_file}")
        run([sys.executable, "tx_daf420.py", str(tx_file)], "TX RRC pull")
    else:
        log(f"TX file NOT found for {today.isoformat()} in {DOWNLOADS} -- skipping TX this run. "
            f"Download daf420.dat.{today.month:02d}-{today.day:02d}-{today.year} from the RRC portal "
            f"and run: python tx_daf420.py \"<path>\" manually to backfill today.")

    # --- LA: always runs, no manual step needed ---
    run([sys.executable, "la_pull.py"], "LA SONRIS pull")

    log("=== Daily run complete ===")

if __name__ == "__main__":
    main()
