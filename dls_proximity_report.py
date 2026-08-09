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

from core.geometry import GeometryLoadError, distance_miles, load_shapefile_rings, reproject_points

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


# RRC's public daf420 extract is standard NAD83 geographic -- assumed, not
# verified against an authoritative RRC source. If proximity results look
# systematically off by a small but consistent amount, this is the first
# thing to check.
PERMIT_CRS_WKT = (
    'GEOGCS["NAD83",DATUM["North_American_Datum_1983",'
    'SPHEROID["GRS 1980",6378137,298.257222101]],'
    'PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433]]'
)


def load_confirmed_geometries(cache: dict) -> dict:
    geometries = {}
    for job_name, entry in cache.items():
        if entry.get("status") != "confirmed":
            continue
        try:
            geometries[job_name] = load_shapefile_rings(Path(entry["shapefile_path"]))
        except GeometryLoadError:
            continue
    return geometries


def nearest_job_distances(permit_row: dict, geometries: dict) -> list[tuple[str, float]]:
    surface_lon, surface_lat = float(permit_row["Surface_Lon"]), float(permit_row["Surface_Lat"])
    bhl_lon, bhl_lat = float(permit_row["BHL_Lon"]), float(permit_row["BHL_Lat"])
    (sx, sy), (bx, by) = reproject_points(
        [(surface_lon, surface_lat), (bhl_lon, bhl_lat)], PERMIT_CRS_WKT
    )

    results = []
    for job_name, geometry in geometries.items():
        d = min(distance_miles(sx, sy, geometry), distance_miles(bx, by, geometry))
        results.append((job_name, d))

    results.sort(key=lambda pair: pair[1])
    return results
