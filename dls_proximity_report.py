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
import datetime as dt
import json
import re
import sys
from pathlib import Path

import openpyxl
import pandas as pd

from core.geometry import GeometryLoadError, distance_miles, load_shapefile_rings, reproject_points

NON_JOB_KEYWORDS = {"report", "dashboard", "update", "updates", "shapefile"}

RADIUS_MILES = 5.0

ROOT = Path(__file__).resolve().parent
CACHE_PATH = ROOT / "data" / "registry" / "dls_geometry_confirmed.json"
DLS_SEARCH_DIR = Path(r"C:\GIS\CLIENT\DLS")
CLIENT_WORKBOOK = Path(r"C:\GIS\Mapmatics_Client_Master_UPDATED.xlsx")


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


def load_confirmed_geometries(cache: dict) -> tuple[dict, list[str]]:
    """Returns (geometries, failed_job_names). A job marked "confirmed" whose
    shapefile can't actually be loaded (missing file, bad/missing
    shapefile_path, etc.) must not just vanish -- it's reported separately in
    failed_job_names so the report can call it out instead of silently
    checking permits against nothing for that job."""
    geometries = {}
    failed_job_names = []
    for job_name, entry in cache.items():
        if entry.get("status") != "confirmed":
            continue
        try:
            geometries[job_name] = load_shapefile_rings(Path(entry["shapefile_path"]))
        except (GeometryLoadError, KeyError, TypeError):
            failed_job_names.append(job_name)
            continue
    return geometries, failed_job_names


def _parse_coord(value) -> float | None:
    try:
        if value is None or (isinstance(value, float) and value != value):  # NaN check without pandas import
            return None
        f = float(value)
        return f
    except (TypeError, ValueError):
        return None


def nearest_job_distances(permit_row: dict, geometries: dict) -> list[tuple[str, float]]:
    candidate_points = []
    surface_lon, surface_lat = _parse_coord(permit_row.get("Surface_Lon")), _parse_coord(permit_row.get("Surface_Lat"))
    if surface_lon is not None and surface_lat is not None:
        candidate_points.append((surface_lon, surface_lat))
    bhl_lon, bhl_lat = _parse_coord(permit_row.get("BHL_Lon")), _parse_coord(permit_row.get("BHL_Lat"))
    if bhl_lon is not None and bhl_lat is not None:
        candidate_points.append((bhl_lon, bhl_lat))

    if not candidate_points:
        return []

    projected_points = reproject_points(candidate_points, PERMIT_CRS_WKT)

    results = []
    for job_name, geometry in geometries.items():
        d = min(distance_miles(x, y, geometry) for x, y in projected_points)
        results.append((job_name, d))

    results.sort(key=lambda pair: pair[1])
    return results


def build_report(
    day: str,
    unresolved_jobs: list[str],
    hits: list[dict],
    failed_to_load_jobs: list[str] | None = None,
    permits_file_found: bool = True,
    no_coords_count: int = 0,
    total_permits: int = 0,
) -> str:
    failed_to_load_jobs = failed_to_load_jobs or []
    lines = [f"# DLS Proximity Report — {day}\n"]

    if unresolved_jobs:
        lines.append("## Unresolved jobs (no confirmed geometry -- edit the cache file)\n")
        for job in unresolved_jobs:
            lines.append(f"- {job}")
        lines.append("")

    if failed_to_load_jobs:
        # Kept visually separate from "Unresolved jobs" (finding #2): these
        # jobs ARE confirmed in the cache, but their shapefile couldn't
        # actually be loaded -- a different failure mode that would
        # otherwise silently vanish from the report entirely.
        lines.append("## Confirmed but failed to load (shapefile unreadable -- check the cache entry)\n")
        for job in failed_to_load_jobs:
            lines.append(f"- {job}")
        lines.append("")

    if not permits_file_found:
        # Finding #3: distinguish "we checked and found nothing" from "we
        # never checked because the permits file wasn't there."
        lines.append(f"No TX permit file found for {day} -- nothing was checked.")
        return "\n".join(lines)

    if no_coords_count:
        # Finding #4: permits with no usable coordinates are skipped by
        # nearest_job_distances without being counted anywhere -- surface
        # that count instead of letting it disappear silently.
        lines.append(
            f"{no_coords_count} of {total_permits} permits had no usable coordinates "
            "and could not be checked.\n"
        )

    if not hits:
        lines.append(f"No new permits found within {RADIUS_MILES} miles of a confirmed DLS job today.")
        return "\n".join(lines)

    lines.append(f"## Permits within {RADIUS_MILES} miles of a DLS job\n")
    by_job: dict[str, list[dict]] = {}
    for hit in hits:
        by_job.setdefault(hit["job_name"], []).append(hit)

    # Finding #13: sort job groups themselves by their nearest hit, not
    # insertion order -- the design spec calls for "sorted nearest first."
    sorted_job_groups = sorted(
        by_job.items(), key=lambda pair: min(h["distance"] for h in pair[1])
    )
    for job_name, job_hits in sorted_job_groups:
        lines.append(f"### {job_name}")
        for hit in sorted(job_hits, key=lambda h: h["distance"]):
            lines.append(f"- {hit['operator']} — Permit #{hit['permit']} ({hit['distance']:.1f} mi)")
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    day = sys.argv[1] if len(sys.argv) > 1 else dt.date.today().isoformat()

    wb = openpyxl.load_workbook(CLIENT_WORKBOOK, data_only=True)
    ws = wb["Client Master"]
    # Column 2 (0-indexed): "Gmail Label" -- identifies the DLS client row.
    dls_row = next(r for r in ws.iter_rows(min_row=2, values_only=True) if r[2] == "DLS")
    # Column 6 (0-indexed): "Jobs / Prospect Names".
    jobs_cell = dls_row[6]

    job_names = parse_dls_jobs(jobs_cell) if jobs_cell else []
    if not jobs_cell or not job_names:
        # Finding #7: r[2] == "DLS" and dls_row[6] have no defensive check --
        # if the workbook's column layout ever changes, this would silently
        # proceed as if DLS simply has zero jobs instead of surfacing the
        # real problem.
        raise RuntimeError(
            "DLS row found but Jobs/Prospect Names cell is empty or unparseable -- "
            "check workbook column layout hasn't changed"
        )

    cache = load_cache(CACHE_PATH)
    cache = update_cache_with_new_jobs(cache, job_names, DLS_SEARCH_DIR)
    save_cache(CACHE_PATH, cache)

    unresolved = [j for j in job_names if cache.get(j, {}).get("status") != "confirmed"]
    geometries, failed_to_load_jobs = load_confirmed_geometries(cache)

    permits_path = ROOT / "data" / "tx" / "out" / day / "new_permits.csv"
    hits = []
    permits_file_found = permits_path.exists()
    no_coords_count = 0
    total_permits = 0
    if permits_file_found:
        permits = pd.read_csv(permits_path, dtype=str)
        total_permits = len(permits)
        for _, row in permits.iterrows():
            # No pre-filter on missing lat/lon here: nearest_job_distances
            # (Task 7, fixed after a reviewer found it crashing on the 47%
            # of a real day's TX permits missing BHL) already handles a
            # permit with only one usable point, returning [] only when
            # NEITHER point parses. Filtering here on "either missing" would
            # silently discard exactly the permits that fix was built to
            # still process.
            distances = nearest_job_distances(row.to_dict(), geometries)
            if not distances and geometries:
                # [] here means both points were unparseable -- if geometries
                # were empty instead, that's a different, already-visible
                # situation (surfaced via the unresolved/failed-to-load job
                # lists), not a coordinate problem (finding #4).
                no_coords_count += 1
            for job_name, distance in distances:
                if distance <= RADIUS_MILES:
                    hits.append({
                        "permit": row["Permit_Number"],
                        "operator": row["Operator_Name"],
                        "job_name": job_name,
                        "distance": distance,
                    })

    report = build_report(
        day,
        unresolved,
        hits,
        failed_to_load_jobs=failed_to_load_jobs,
        permits_file_found=permits_file_found,
        no_coords_count=no_coords_count,
        total_permits=total_permits,
    )
    out_path = ROOT / "data" / "dls_proximity" / f"{day}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")
    print(report)
    print(f"\nSaved: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
