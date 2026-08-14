# Consolidation map — permit_intel vs permit-market-brief

Written after reading `tx_daf420.py`, `county_lookup.py`, and `config.yaml`.

## Short version

`permit_intel` is more mature than what I built alongside it. Most of my `permit-market-brief` scaffolding duplicates work already done better there and should be retired rather than run in parallel. Three things I built are genuinely additive and should be folded in.

## What permit_intel already does better

| Capability | permit_intel | my version | Verdict |
|---|---|---|---|
| Persistent master | `common.load_master` / `save_master` | `ingest.py` writes a CSV | **Theirs.** Mine reinvents it. |
| Duplicate-pull detection | SHA-256 ingestion ledger + skip marker distinguishing "correctly skipped" from "run failed" | prints a NOTE if nothing new | **Theirs, decisively.** I spent three briefs guessing whether identical pulls were an RRC gap or a broken fetch; the ledger answers it. |
| Twice-daily RRC publishing | `union_write_csv` unions the day's output | not handled | **Theirs.** I did not know this happened. |
| Change classification | new / amended / **resurfaced** (`resurfaced_after_days=7`) | new / new-spud | **Theirs.** "Resurfaced" is a category I was describing in prose without naming. |
| Leading-zero preservation | explicit `ID_COLS` dtype map, with a comment explaining 693/693 permits affected | none — my CSV round-trip would strip them | **Theirs.** Real bug I would have reintroduced. |
| ArcGIS write path | `da.InsertCursor`, bypassing ERROR 161025 on this machine, with pyshp shapefile fallback | GP tools (`TableToTable`, `XYTableToPoint`) | **Theirs.** My corrected script uses exactly the GP tools documented as broken there. |
| Corridors | five named corridors with client tags, TX + LA, in config | `CORRIDOR = {LAVACA, FAYETTE, LEE}` hardcoded | **Theirs.** |
| Operator families | alias map handling rebrands and mergers | none | **Theirs.** Solves the "is this a new entrant or a rename?" problem I flagged as open. |

## What I built that is additive

### 1. The county fix — both copies

`county_lookup.py` has the identical Mc-block shift as the ArcGIS script. Nine codes, 307–323, each two slots off. Corrected drop-in provided; only those nine keys change.

This is the highest-priority item. Until it lands, every corridor rollup that touches Martin, McMullen, Madison, Mason, Matagorda, or Maverick is wrong — and `config.yaml` does not currently include any of those six counties in a corridor, which is precisely why it went unnoticed.

### 2. Extended daf420 fields

`tx_daf420.py`'s `parse_rrc` is byte-identical in behavior to the ArcGIS script's — same four record types, same 16 fields. The layout guide (OGA049M) documents 15 segments; Tier 1 additions are in `references/daf420-field-map.md`.

The two that most change what the digest can report:

- **Application status** (record 01, pos 101) exposes *pending* applications, plus withdrawals and denials. Everything the pipeline currently sees is post-approval.
- **Type of application** (record 02, pos 68) separates genuine new drills from re-entries, recompletions, and reclasses. Permit counts arguably should exclude codes 14 and 15.

Offsets are unverified — I have no raw `.dat`. Patch and run with `--verify` before trusting.

### 3. The analytical layer

`digest.py` + `mtd_rollup` covers daily deltas, MTD by county/operator/family, and hot cycles. Not covered:

- rolling 7-day vs prior 7-day, with operator momentum
- basin mix (Permian / Eagle Ford / East Texas gas)
- spud conversion by issue cohort
- aging inventory (45+ days issued, unspudded)
- step-outs — first permit in a county in 90+ days
- permit banking candidates
- amendment clusters — block-wide refiling ahead of drilling

These belong in a `market_brief.py` that reads the **existing** master and config, not a second pipeline.

### 4. The spud-visibility caveat

Any conversion or banking figure computed from this data is a **floor**, not a rate. Permits leave the rolling pull after roughly 30 days; only 59% of spuds occur inside that window, so ~40% never post back. Measured against 83 snapshots: 691 spudded wells, median permit-to-spud 24 days, p75 51 days.

Left unguarded this metric labels every large operator a permit banker. EOG reads "145 permits, 0 spuds" while two Lavaca wells demonstrably spudded. Worth carrying into `mtd_rollup` as well — its hot-cycle list is sound, but any ratio built on the same data needs the caveat.

## Retire

- `permit-market-brief/scripts/ingest.py` — superseded
- `permit-market-brief/scripts/rrc_parse.py` as a standalone — the county fix and extended fields should be patched into `tx_daf420.py`; the corrected ArcGIS script stays only as the manual Pro-side tool
- `references/github-actions-example.yml`'s fetch step — see below

## Corrections to my own reference docs

**The fetch endpoint.** `references/data-sources.md` describes a "constant-filename daf420" URL as the automation target. `config.yaml` shows something different: an MFT share link (`mft.rrc.texas.gov/link/...`) with Playwright handling session and redirects, plus a watch-dir fallback for manual drops. Playwright means the fetch step needs a browser in the runner — a materially different Actions setup than a `curl`. I asserted the constant-filename approach without checking; the config is authoritative.

**Dead config.** `texas.fields` maps names like `STATUS_NUMBER`, `API_NO`, `WELLBORE_PROFILE`, `AMEND_FLAG`, `SHL_LAT`. Those are RRC query/GIS export names, not daf420 fields, and `tx_daf420.py` uses its own hardcoded names instead. That block appears vestigial from an earlier design. Worth deleting or annotating so it doesn't mislead later.

**Corridor scope.** My analyze.py treats the corridor as three counties. Config defines it as nine: LEE, FAYETTE, BASTROP, WASHINGTON, GONZALES, LAVACA, DEWITT, AUSTIN, COLORADO. Several briefs I wrote reported "corridor activity" against the narrower set.

## Order of work

1. Drop in corrected `county_lookup.py`. Rebuild affected digests if any covered the Mc-block counties.
2. Patch extended fields into `tx_daf420.py`'s `parse_rrc`; run `--verify` against one real `.dat`.
3. Add `market_brief.py` reading the existing master + config.
4. Delete my `ingest.py`; keep `rrc_parse.py` only as the Pro-side manual tool.
5. Reconcile the Actions fetch step against the actual Playwright/MFT flow.
