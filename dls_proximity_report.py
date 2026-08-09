#!/usr/bin/env python
"""
DLS proximity pilot: flags new TX RRC permits within 5 miles of DLS's actual
job-site boundaries, using real shapefile geometry rather than county-level
corridors. See docs/superpowers/specs/2026-08-09-dls-proximity-pilot-design.md.

Standalone report -- not wired into the daily email while unproven. Reads
already-computed data/tx/out/<date>/new_permits.csv rather than pulling new
data itself.

Run: python dls_proximity_report.py [YYYY-MM-DD]   (defaults to today)
"""
import json
import re
from pathlib import Path

NON_JOB_KEYWORDS = {"report", "dashboard", "update", "updates", "shapefile"}


def parse_dls_jobs(cell_text: str) -> list[str]:
    """Split DLS's workbook "Jobs / Prospect Names" cell into individual job
    names. Splits on top-level commas only -- a comma inside parentheses
    (e.g. "Lee Co (Giddings, Sage, Crescent Pass)") is a sub-area list for
    one job, not three separate jobs. Entries that look like report/
    deliverable descriptions rather than job names (containing any of
    NON_JOB_KEYWORDS) are dropped -- this is a narrow keyword rule, not a
    semantic judgment call, so a real job wrongly filtered later is a
    one-line fix to the keyword set."""
    jobs = []
    depth = 0
    current = []
    for ch in cell_text:
        if ch == "(":
            depth += 1
            current.append(ch)
        elif ch == ")":
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            jobs.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    if current:
        jobs.append("".join(current).strip())

    return [
        job for job in jobs
        if job and not any(re.search(rf"\b{kw}\b", job.lower()) for kw in NON_JOB_KEYWORDS)
    ]


def tokenize_for_match(name: str) -> set[str]:
    words = re.findall(r"[A-Za-z0-9]+", name.upper())
    return {w.lower() for w in words if len(w) >= 3}


def resolve_candidates(job_name: str, search_dir: Path, limit: int = 5) -> list[Path]:
    """Fuzzy-match a DLS job name against every .shp file under search_dir,
    scored by token overlap between the job name and the file's full path
    (so both folder and file names contribute -- FLATLAND_NORTH/AOI_NEW.shp
    matches "Flatland" via the folder name, not the filename)."""
    job_tokens = tokenize_for_match(job_name)
    if not job_tokens:
        return []

    scored = []
    for shp_path in search_dir.glob("**/*.shp"):
        path_tokens = tokenize_for_match(str(shp_path.relative_to(search_dir)))
        overlap = len(job_tokens & path_tokens)
        if overlap > 0:
            scored.append((overlap, shp_path))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [path for _, path in scored[:limit]]


def load_cache(cache_path: Path) -> dict:
    if not cache_path.exists():
        return {}
    return json.loads(cache_path.read_text(encoding="utf-8"))


def save_cache(cache_path: Path, cache: dict) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, indent=2, sort_keys=True), encoding="utf-8")


def update_cache_with_new_jobs(cache: dict, job_names: list[str], search_dir: Path) -> dict:
    for job_name in job_names:
        if job_name in cache:
            continue
        candidates = resolve_candidates(job_name, search_dir)
        cache[job_name] = {
            "status": "unconfirmed",
            "candidates": [str(p) for p in candidates],
        }
    return cache
