# Permit Market Brief — 2026-09-05

## Headline

*[Write this last. Two to three sentences on what today's activity means in context. If the day was unremarkable, say so plainly.]*

## Today

- Permits issued: **0** (30-day average 31/business day, baseline ~35)
- New spud postings dated today: **0**

No permits carry today's issue date. If the prior pull was identical, check tx_daf420.py's ingestion ledger — it already distinguishes a genuine RRC posting gap from a stale fetch; this brief does not re-derive that.

## Rolling week

- 7-day issuance: **133** (prior 7-day: 118, +13% vs prior week)

**Accelerating**

- OXYROCK OPERATING, LLC — 14 this week (+14)
- ANADARKO E&P ONSHORE LLC — 9 this week (+9)
- DE V OPERATING, LLC — 6 this week (+6)
- EOG RESOURCES, INC. — 6 this week (+6)
- DIAMONDBACK E&P LLC — 7 this week (+6)

**Decelerating**

- CONTINENTAL RESOURCES, INC. — 0 this week (-5)
- CONOCOPHILLIPS COMPANY — 0 this week (-5)
- U.S. ENERGY DEVELOPMENT CORP — 2 this week (-6)
- COTERRA ENERGY OPERATING CO. — 0 this week (-8)
- BPX OPERATING COMPANY — 1 this week (-8)

**New entrants this week** (no permits in prior 30 days — check operator_families first; a rebrand or merged alias should not read as new)

- ACTIVE IRON ENERGY, LLC (GAINES)
- ANADARKO E&P ONSHORE LLC (LOVING)
- BLACKBEARD OPERATING, LLC (CRANE)
- COTULA OIL & GAS CO., INC. (CALLAHAN)
- CYTEX SOUTH TEXAS OPERATING LLC (MADISON)
- DE V OPERATING, LLC (GLASSCOCK)
- DEVON ENERGY PRODUCTION CO, L.P. (KARNES)
- EXCEL OPERATING, LLC (CALDWELL)
- HALLIBURTON ENERGY SERVICES, INC (MILAM)
- HALLIBURTON OPERATING COMPANY (KING)

- Wells spudded this week: **5**, median permit-to-spud **19 days**

## Month to date

- MTD issuance: **107** over 4 business days, tracking to ~**588** (baseline ~750)
- Basin mix: Permian 73%, Eagle Ford 17%, Other 7%, East Texas gas 3%

**Watched families, MTD**

- EOG Resources: 6
- Comstock (Jerry Jones): 1
- Sabine Energy: 1
- Adamas (ex-Aethon, Mitsubishi): 1

**Spud conversion by issue cohort** *(floor, not a true rate — see Data notes)*

- 2026-05: 29/85 (34%)
- 2026-06: 17/67 (25%)
- 2026-07: 35/693 (5%)
- 2026-08: 56/695 (8%)  *(inside spud-reporting lag)*
- 2026-09: 0/107 (0%)  *(inside spud-reporting lag)*

- Aging inventory: **641** permits issued 45+ days ago, still unspudded
- Ultra-deep (16,000'+) permits MTD: **1**

## Pattern candidates

*Machine-surfaced. Review before including — not all are meaningful.*

**Step-outs** — first permit in this county in 90+ days

- DEVON ENERGY PRODUCTION CO, L.P. → KARNES (3 permit(s))
- HIBERNIA RESOURCES IV, LLC → IRION (2 permit(s))
- ATMOS PIPELINE - TEXAS → COLLIN (1 permit(s))
- ATMOS PIPELINE - TEXAS → NAVARRO (1 permit(s))
- COMSTOCK OIL & GAS, LLC → FREESTONE (1 permit(s))
- CRESCENT ENERGY OPERATING, LLC → WARD (1 permit(s))
- CYTEX SOUTH TEXAS OPERATING LLC → MADISON (1 permit(s))
- ENSIGN NATURAL RESOURCES II LLC → GONZALES (1 permit(s))
- ROSE CITY RESOURCES, LLC → MARION (1 permit(s))
- ROYAL PRODUCTION COMPANY, INC. → HIDALGO (1 permit(s))

**Permit banking candidates** — 90-day permits vs spuds *visible to this master*

> Floor, not a rate. Confirm against a direct well-status query before reporting a ratio to anyone.

- PIONEER NATURAL RES. USA, INC. — 116 permits, 19 spuds seen
- DIAMONDBACK E&P LLC — 71 permits, 9 spuds seen
- EOG RESOURCES, INC. — 52 permits, 0 spuds seen
- COG OPERATING LLC — 45 permits, 0 spuds seen
- CONTINENTAL RESOURCES, INC. — 38 permits, 0 spuds seen
- OCCIDENTAL PERMIAN LTD. — 35 permits, 0 spuds seen
- BPX OPERATING COMPANY — 33 permits, 0 spuds seen
- BURLINGTON RESOURCES O & G CO LP — 29 permits, 0 spuds seen

**Corridor — DLS / EOG — Giddings & Eastern Eagle Ford, trailing 90 days**

- MAGNOLIA OIL & GAS OPERATING LLC — 20 (FAYETTE, LEE, WASHINGTON)
- AETHON ENERGY OPERATING LLC — 16 (WASHINGTON)
- FW EAGLE FORD I, LLC — 9 (GONZALES, LAVACA)
- MARATHON OIL EF LLC — 8 (DEWITT, GONZALES)
- BURLINGTON RESOURCES O & G CO LP — 7 (DEWITT)
- DEVON ENERGY PRODUCTION CO, L.P. — 7 (DEWITT)
- ENSIGN NATURAL RESOURCES II LLC — 5 (DEWITT, GONZALES)
- SAGE NATURAL RESOURCES LLC — 4 (FAYETTE, LEE)
- BPX OPERATING COMPANY — 4 (DEWITT)
- ROYAL PRODUCTION COMPANY, INC. — 1 (LAVACA)
- IRONBLOOM OPERATING, LLC — 1 (LEE)
- ENHANCED ENERGY PARTNERS CORP — 1 (AUSTIN)
- STRAND ENERGY, L.C. — 1 (COLORADO)
- LP OPERATING, LLC — 1 (GONZALES)
- WILDFIRE ENERGY OPERATING LLC — 1 (LEE)

New in this corridor this week: 14

**Corridor — DOXA / Sabine — East Texas, trailing 90 days**

- SABINE ENERGY INC. — 17 (HARRISON, PANOLA, RUSK)
- TGNR PANOLA LLC — 9 (PANOLA)
- BUFFCO PRODUCTION INC. — 7 (HARRISON, PANOLA, RUSK)
- TGNR EAST TEXAS II LLC — 5 (PANOLA)
- PWEP OPERATING, LLC — 4 (HARRISON)
- R. LACY SERVICES, LTD. — 3 (PANOLA)
- FAULCONER ENERGY, LLC — 3 (GREGG, SMITH)
- COMSTOCK OIL & GAS, LLC — 2 (HARRISON)
- REVENANT ENERGY OPERATING LLC — 2 (NACOGDOCHES)
- AGIS ENERGY LLC — 2 (PANOLA)
- TANOS EXPLORATION IV, LLC — 2 (RUSK)
- SILVER HILL ENERGY OPERATING LLC — 2 (SHELBY)
- BUCKHORN OPERATING LLC — 2 (RUSK)
- SELECT WATER SOLUTIONS, LLC — 1 (SHELBY)
- NECHES BEND RESOURCES, LLC — 1 (CHEROKEE)
- SONERRA RESOURCES CORPORATION — 1 (NACOGDOCHES)
- VALENCE OPERATING COMPANY — 1 (RUSK)
- XTO ENERGY INC. — 1 (SHELBY)

New in this corridor this week: 3

**Corridor — DOXA / Firebird — Permian, trailing 90 days**

- PIONEER NATURAL RES. USA, INC. — 62 (ANDREWS, MIDLAND, UPTON)
- DIAMONDBACK E&P LLC — 50 (ECTOR, MIDLAND)
- COG OPERATING LLC — 45 (ANDREWS, MIDLAND)
- CONTINENTAL RESOURCES, INC. — 31 (ECTOR, MIDLAND, WINKLER)
- CHEVRON U. S. A. INC. — 21 (MIDLAND, UPTON)
- APACHE CORPORATION — 19 (MIDLAND, UPTON)
- FASKEN OIL AND RANCH, LTD. — 14 (ANDREWS)
- FIREBIRD ENERGY II LLC — 14 (ECTOR)
- SABALO II OPERATING, LLC — 12 (ANDREWS)
- ARRINGTON OIL&GAS OPERATING LLC — 12 (ECTOR)
- OVINTIV USA INC. — 11 (ANDREWS)
- BLACKBEARD OPERATING, LLC — 10 (CRANE, WINKLER)
- RING ENERGY, INC. — 10 (CRANE)
- BASIN OIL & GAS OPERATING, LLC — 9 (ECTOR, WINKLER)
- SUMMIT PETROLEUM LLC — 8 (UPTON)
- MEWBOURNE OIL COMPANY — 4 (WINKLER)
- BTA OIL PRODUCERS, LLC — 4 (CRANE)
- ADMIRAL PERMIAN OPERATING LLC — 3 (ANDREWS, UPTON)
- XRI DISPOSAL HOLDINGS, LLC — 3 (WINKLER)
- SM ENERGY COMPANY — 3 (CRANE)
- PERMIAN DEEP ROCK OIL CO., LLC — 3 (MIDLAND)
- DAVIS SOUTHERN OPERATING CO LLC — 2 (ECTOR)
- MID-STATES OPERATING COMPANY — 2 (MIDLAND)
- LAGUNA PETROLEUM CORPORATION — 2 (ECTOR)
- OLSEN ENERGY INC. — 1 (ANDREWS)
- GREEN CENTURY EXP & PROD, LLC — 1 (CRANE)
- DISCOVERY OPERATING, INC. — 1 (MIDLAND)
- BOSQUE TEXAS OIL LLC — 1 (WINKLER)
- HILCORP ENERGY COMPANY — 1 (ANDREWS)
- MONTARE OPERATING, LTD. — 1 (ANDREWS)
- TEXLAND PETROLEUM, L.P. — 1 (ANDREWS)
- ATMOS PIPELINE - TEXAS — 1 (ECTOR)
- OVERFLOW ENERGY PERMIAN, LLC — 1 (MIDLAND)
- AQUA TERRA PERMIAN, LLC — 1 (UPTON)
- PETX OPERATING LLC — 1 (UPTON)
- ZARVONA ENERGY LLC — 1 (UPTON)

New in this corridor this week: 17

**Corridor — West Haynesville watch, trailing 90 days**

- HILCORP ENERGY COMPANY — 9 (FREESTONE, ROBERTSON)
- EMPIRE TEXAS OPERATING LLC — 5 (HOUSTON, MADISON)
- COMSTOCK OIL & GAS, LLC — 5 (FREESTONE, LEON, ROBERTSON)
- WILDFIRE ENERGY OPERATING LLC — 2 (ROBERTSON)
- MAXIMUS OPERATING, LTD. — 1 (LEON)
- CML EXPLORATION, LLC — 1 (ROBERTSON)
- CYTEX SOUTH TEXAS OPERATING LLC — 1 (MADISON)

New in this corridor this week: 2

**Corridor — RROG + DOXA — NW Louisiana Haynesville, trailing 90 days**

- No permits in the trailing 90 days

## Data notes

- County labels check out against county_lookup.py (Mc-block self-check passed)
- 7 records excluded from cycle statistics (spud predates issue — wellbore re-entries)
- Newest issue date in master: 2026-09-03 (2 day(s) behind as-of date)
- Permits age out of the rolling daily source pull after ~30 days; a permit's disappearance from new activity is coverage boundary, not inactivity
- **Spud conversion and permit-banking figures are floors.** A permit that ages past the rolling window before spudding never posts its spud date back to the source, so every conversion figure here understates reality. Confirm against a direct well-status query before either reaches a client.
- Spud reporting lags ~21 days; silence inside that window is not a signal

## Louisiana

- 184 records in the LA master. Reported separately from TX by design — parish activity and Texas county activity are not directly comparable, and Haynesville spans the state line.
- *(Parish-level rolling/cohort analysis not yet built here — the LA REST layer per config.yaml has no BHL/line geometry, only surface points, so some of the TX-side metrics may not translate cleanly. Extend prep_tx's twin for LA's field names before relying on this.)*
