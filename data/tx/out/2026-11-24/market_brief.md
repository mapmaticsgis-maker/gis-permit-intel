# Permit Market Brief — 2026-11-24

## Headline

*[Write this last. Two to three sentences on what today's activity means in context. If the day was unremarkable, say so plainly.]*

## Today

- Permits issued: **0** (30-day average 0/business day, baseline ~35)
- New spud postings dated today: **0**

No permits carry today's issue date. If the prior pull was identical, check tx_daf420.py's ingestion ledger — it already distinguishes a genuine RRC posting gap from a stale fetch; this brief does not re-derive that.

## Rolling week

- 7-day issuance: **0** (prior 7-day: 0)

## Month to date

- MTD issuance: **0** over 17 business days, tracking to ~**0** (baseline ~750)

**Spud conversion by issue cohort** *(floor, not a true rate — see Data notes)*

- 2026-05: 29/85 (34%)
- 2026-06: 19/72 (26%)
- 2026-07: 35/693 (5%)
- 2026-08: 58/695 (8%)
- 2026-09: 0/156 (0%)

- Aging inventory: **1635** permits issued 45+ days ago, still unspudded
- Ultra-deep (16,000'+) permits MTD: **0**

## Pattern candidates

*Machine-surfaced. Review before including — not all are meaningful.*

**Permit banking candidates** — 90-day permits vs spuds *visible to this master*

> Floor, not a rate. Confirm against a direct well-status query before reporting a ratio to anyone.

- OXYROCK OPERATING, LLC — 14 permits, 0 spuds seen
- AETHON ENERGY OPERATING LLC — 12 permits, 0 spuds seen
- DE CENTRAL OPERATING, LLC — 12 permits, 0 spuds seen
- DIAMONDBACK E&P LLC — 12 permits, 0 spuds seen
- OCCIDENTAL PERMIAN LTD. — 10 permits, 0 spuds seen
- ANADARKO E&P ONSHORE LLC — 9 permits, 0 spuds seen
- BLACKBEARD OPERATING, LLC — 8 permits, 0 spuds seen
- U.S. ENERGY DEVELOPMENT CORP — 8 permits, 0 spuds seen

**Corridor — DLS / EOG — Giddings & Eastern Eagle Ford, trailing 90 days**

- AETHON ENERGY OPERATING LLC — 12 (WASHINGTON)
- ENSIGN NATURAL RESOURCES II LLC — 3 (DEWITT, GONZALES)
- SAGE NATURAL RESOURCES LLC — 2 (FAYETTE)
- FW EAGLE FORD I, LLC — 2 (GONZALES)
- STRAND ENERGY, L.C. — 1 (COLORADO)
- BPX OPERATING COMPANY — 1 (DEWITT)

New in this corridor this week: 0

**Corridor — DOXA / Sabine — East Texas, trailing 90 days**

- SABINE ENERGY INC. — 4 (HARRISON, PANOLA)
- REVENANT ENERGY OPERATING LLC — 2 (NACOGDOCHES)
- NECHES BEND RESOURCES, LLC — 1 (CHEROKEE)
- BROOKSTON ENERGY, INC. — 1 (HARRISON)

New in this corridor this week: 0

**Corridor — DOXA / Firebird — Permian, trailing 90 days**

- BLACKBEARD OPERATING, LLC — 8 (CRANE)
- DIAMONDBACK E&P LLC — 7 (MIDLAND)
- RING ENERGY, INC. — 5 (CRANE)
- PIONEER NATURAL RES. USA, INC. — 5 (MIDLAND)
- CONTINENTAL RESOURCES, INC. — 4 (ECTOR)
- CHEVRON U. S. A. INC. — 3 (MIDLAND)
- ARRINGTON OIL&GAS OPERATING LLC — 2 (ECTOR)
- FIREBIRD ENERGY II LLC — 2 (ECTOR)
- APACHE CORPORATION — 2 (UPTON)
- LAGUNA PETROLEUM CORPORATION — 2 (ECTOR)

New in this corridor this week: 0

**Corridor — West Haynesville watch, trailing 90 days**

- CYTEX SOUTH TEXAS OPERATING LLC — 2 (MADISON)
- CML EXPLORATION, LLC — 1 (ROBERTSON)
- WILDFIRE ENERGY OPERATING LLC — 1 (ROBERTSON)
- COMSTOCK OIL & GAS, LLC — 1 (FREESTONE)

New in this corridor this week: 0

**Corridor — RROG + DOXA — NW Louisiana Haynesville, trailing 90 days**

- No permits in the trailing 90 days

## Data notes

- County labels check out against county_lookup.py (Mc-block self-check passed)
- 10 records excluded from cycle statistics (spud predates issue — wellbore re-entries)
- Newest issue date in master: 2026-09-04 (81 day(s) behind as-of date)
- Permits age out of the rolling daily source pull after ~30 days; a permit's disappearance from new activity is coverage boundary, not inactivity
- **Spud conversion and permit-banking figures are floors.** A permit that ages past the rolling window before spudding never posts its spud date back to the source, so every conversion figure here understates reality. Confirm against a direct well-status query before either reaches a client.
- Spud reporting lags ~21 days; silence inside that window is not a signal

## Louisiana

- 264 records in the LA master. Reported separately from TX by design — parish activity and Texas county activity are not directly comparable, and Haynesville spans the state line.
- *(Parish-level rolling/cohort analysis not yet built here — the LA REST layer per config.yaml has no BHL/line geometry, only surface points, so some of the TX-side metrics may not translate cleanly. Extend prep_tx's twin for LA's field names before relying on this.)*
