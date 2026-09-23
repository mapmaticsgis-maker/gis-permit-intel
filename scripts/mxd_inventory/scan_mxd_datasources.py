# Driver: run with C:\Python27\ArcGIS10.8\python.exe scan_mxd_datasources.py
#
# Enumerates every .mxd under CLIENT_ROOTS and scans each one in its own
# subprocess (via scan_one_mxd.py) so a per-file arcpy/COM crash only loses
# that one file, not the whole batch. Writes progress incrementally to
# PROGRESS_PATH so a driver-level crash (or Ctrl-C) can resume where it left
# off -- re-running skips mxds already recorded there.
import datetime
import json
import os
import subprocess
import sys

CLIENT_ROOTS = {
    "RROG": r"C:\GIS\CLIENT\RROG",
    "DOXA": r"C:\GIS\CLIENT\DOXA",
}

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
WORKER_PATH = os.path.join(THIS_DIR, "scan_one_mxd.py")
PYTHON_EXE = sys.executable

OUTPUT_PATH = r"C:\GIS\permit_intel\data\mxd_inventory\raw_inventory.json"
PROGRESS_PATH = r"C:\GIS\permit_intel\data\mxd_inventory\scan_progress.jsonl"


def find_mxds(root):
    matches = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            if name.lower().endswith(".mxd"):
                matches.append(os.path.join(dirpath, name))
    return matches


def already_scanned(progress_path):
    scanned = set()
    if not os.path.exists(progress_path):
        return scanned
    with open(progress_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            scanned.add(entry["mxd_path"])
    return scanned


def run_worker(client, mxd_path):
    try:
        proc = subprocess.Popen(
            [PYTHON_EXE, WORKER_PATH, client, mxd_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = proc.communicate()
    except Exception as exc:
        return {"mxd_path": mxd_path, "error": "subprocess launch failed: {0}".format(exc)}

    if proc.returncode != 0:
        tail = stderr.strip().splitlines()[-1] if stderr.strip() else "exit code {0}".format(proc.returncode)
        return {"mxd_path": mxd_path, "error": "worker failed: {0}".format(tail)}

    try:
        return json.loads(stdout.strip().splitlines()[-1])
    except Exception as exc:
        return {"mxd_path": mxd_path, "error": "could not parse worker output: {0}".format(exc)}


def scan_all():
    output_dir = os.path.dirname(OUTPUT_PATH)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    skip = already_scanned(PROGRESS_PATH)
    if skip:
        print("Resuming: {0} mxds already scanned, skipping those.".format(len(skip)))

    progress_file = open(PROGRESS_PATH, "a")
    try:
        for client, root in CLIENT_ROOTS.items():
            for mxd_path in find_mxds(root):
                if mxd_path in skip:
                    continue
                entry = run_worker(client, mxd_path)
                progress_file.write(json.dumps(entry) + "\n")
                progress_file.flush()
                os.fsync(progress_file.fileno())
                status = "error: {0}".format(entry["error"]) if "error" in entry else "{0} layers".format(len(entry["records"]))
                print("{0} -> {1}".format(mxd_path, status))
    finally:
        progress_file.close()


def assemble_output():
    records = []
    errors = []
    with open(PROGRESS_PATH, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            if "error" in entry:
                errors.append({"mxd_path": entry["mxd_path"], "error": entry["error"]})
            else:
                records.extend(entry["records"])

    output = {
        "generated_date": datetime.date.today().isoformat(),
        "client_roots": CLIENT_ROOTS,
        "records": records,
        "errors": errors,
    }
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)

    print("Assembled {0} records, {1} errors. Wrote {2}".format(len(records), len(errors), OUTPUT_PATH))


def main():
    scan_all()
    assemble_output()


if __name__ == "__main__":
    main()
