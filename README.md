# Permit Intel — TX RRC + LA SONRIS daily automation

Automates the manual daily pull: fetch -> diff vs master -> classify -> corridor digest
(+ CSV / GeoJSON for Arc, + amendments, + new-operator flags).

## Setup (once)
    pip install pandas requests pyyaml openpyxl
    mkdir data\tx\inbox data\la\inbox   (Windows)

## Day one (works immediately, no URL config)
1. Do your normal manual RRC download; drop the file into data/tx/inbox/.
2. `python tx_pull.py`  -> first run builds the master; from run 2 you get real diffs.
3. Same idea for LA: export a SONRIS permits CSV into data/la/inbox/, `python la_pull.py`.

## Automating the fetch (the goal)
- TEXAS: paste the URL of the daily file you download into config.yaml -> texas.fetch_url.
  (Your existing RRC MFT link pattern works here.) Then tx_pull.py is hands-off.
- LOUISIANA: verify the DNR/SONRIS ArcGIS REST wells layer in a browser
  (start at https://gis.dnr.louisiana.gov/arcgis/rest/services, find the wells/permits
  layer, click "Query" to test) and set louisiana.rest_url + date_field. The script
  pulls everything permitted since your last run, geometry included, in NAD27 (outSR=4267).
- Field names in config.fields must match the source headers — run once, look at the
  error/columns, adjust config. Ten-minute job.

## Scheduling (Windows)
Task Scheduler -> Create Task -> Daily 09:45 ->
    Program: python   Arguments: run_daily.py   Start in: <this folder>
Zach's dashboard can read data/*/out/<date>/ directly - same shape every day.

## Outputs per day (data/<state>/out/<YYYY-MM-DD>/)
- new_permits.csv   (first_seen column flags brand-new operators = new entrants)
- amendments.csv    (same id, changed operator/depth/wellbore = amendment activity)
- new_permits.geojson  (drop into ArcGIS Pro; NAD27 geographic for LA REST pulls)
- digest.md         (corridor-grouped intel note: DLS/EOG, DOXA/Sabine, Firebird,
                     West Haynesville, NW LA - with operator-family tags like
                     "Adamas (ex-Aethon, Mitsubishi)")

## Notes
- Corridors + operator families are yours to edit in config.yaml - that's the
  intelligence layer (counties/parishes per client, corporate genealogy tags).
- LA units: next module joins LA permits to your HA RA SU* unit shapefiles
  (spatial join in Arc or geopandas) so each permit lands in a named unit.
- The SONRIS "Permit to Drill Applications" queue (pre-issuance) is a separate
  scrape - phase 2, gives you lead time TX can't.

## v2 — tx_daf420.py (the real TX pipeline)
Uses Jason's proven daf420 parser + coordinate cache + GDB build, with the diff/intel
engine on top. Run daily (arg optional; otherwise newest daf420* in data/tx/inbox):

    python tx_daf420.py C:\Users\mapma\Downloads\daf420.dat.07-19-2026

Per run: new_permits.csv / amendments.csv / resurfaced.csv / digest.md
(corridor hits, watched-family tags, resurfaced older files, month-to-date rollup
with hot-cycle spud tracking). Inside ArcGIS Pro's python it ALSO builds the GDB:
your usual FULL table + surface/BHL points + wellbore lines, PLUS "NEW"-tagged
feature classes containing only today's adds/amendments - so yesterday-vs-today
is a layer, not a memory exercise. Set gdb/coord_cache paths in config.yaml
(defaults match your current C:\GIS\RRC_Permits setup).

Replaces the daily copy-paste-into-Claude step: the day-over-day and MTD arithmetic
is all in digest.md; save Claude for the judgment calls on top.
