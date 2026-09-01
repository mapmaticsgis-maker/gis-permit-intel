# Permit Market Brief — 2026-08-31

## Headline

*[Write this last. Two to three sentences on what today's activity means in context. If the day was unremarkable, say so plainly.]*

## Today

- Permits issued: **0** (30-day average 32/business day, baseline ~35)
- New spud postings dated today: **0**

No permits carry today's issue date. If the prior pull was identical, check tx_daf420.py's ingestion ledger — it already distinguishes a genuine RRC posting gap from a stale fetch; this brief does not re-derive that.

## Rolling week

- 7-day issuance: **91** (prior 7-day: 152, -40% vs prior week)

**Accelerating**

- BPX OPERATING COMPANY — 9 this week (+9)
- AETHON ENERGY OPERATING LLC — 7 this week (+7)
- U.S. ENERGY DEVELOPMENT CORP — 7 this week (+6)
- CONOCOPHILLIPS COMPANY — 5 this week (+5)
- CONTINENTAL RESOURCES, INC. — 5 this week (+5)

**Decelerating**

- OVINTIV USA INC. — 0 this week (-6)
- OCCIDENTAL PERMIAN LTD. — 0 this week (-7)
- VTX ENERGY OPERATING, LLC — 0 this week (-8)
- DIAMONDBACK E&P LLC — 1 this week (-11)
- PIONEER NATURAL RES. USA, INC. — 1 this week (-14)

**New entrants this week** (no permits in prior 30 days — check operator_families first; a rebrand or merged alias should not read as new)

- AETHON ENERGY OPERATING LLC (WASHINGTON)
- ATMOS PIPELINE - TEXAS (ECTOR)
- CHEVRON U. S. A. INC. (MIDLAND)
- CML EXPLORATION, LLC (ROBERTSON)
- CONOCOPHILLIPS COMPANY (REEVES)
- DRY CREEK OPERATING, LLC (JACK)
- DRY FORK PRODUCTION CO., LLC (SCHLEICHER)
- NECHES BEND RESOURCES, LLC (CHEROKEE)
- PETROPLEX ENERGY INC. (REEVES)
- SAGE NATURAL RESOURCES LLC (FAYETTE)

- Wells spudded this week: **3**, median permit-to-spud **18 days**

## Month to date

- MTD issuance: **669** over 21 business days, tracking to ~**669** (baseline ~750)
- Basin mix: Permian 62%, Eagle Ford 17%, Other 16%, East Texas gas 5%

**Watched families, MTD**

- EOG Resources: 18
- Adamas (ex-Aethon, Mitsubishi): 11
- Firebird Energy: 8
- Magnolia (EOG-contiguous, Lee Co): 7
- Sabine Energy: 4
- Apex (ex-Paloma, Citadel): 3
- Comstock (Jerry Jones): 2

**Spud conversion by issue cohort** *(floor, not a true rate — see Data notes)*

- 2026-04: 21/37 (57%)
- 2026-05: 28/84 (33%)
- 2026-06: 17/65 (26%)
- 2026-07: 34/693 (5%)
- 2026-08: 49/669 (7%)  *(inside spud-reporting lag)*

- Aging inventory: **534** permits issued 45+ days ago, still unspudded
- Ultra-deep (16,000'+) permits MTD: **29**

## Pattern candidates

*Machine-surfaced. Review before including — not all are meaningful.*

**Step-outs** — first permit in this county in 90+ days

- VERDUN OIL & GAS LLC → MCMULLEN (4 permit(s))
- SAGE NATURAL RESOURCES LLC → FAYETTE (2 permit(s))
- CML EXPLORATION, LLC → ROBERTSON (1 permit(s))
- ENERGY TRANSFER COMPANY → MITCHELL (1 permit(s))
- PALOMA OPERATING, LLC → WHARTON (1 permit(s))

**Permit banking candidates** — 90-day permits vs spuds *visible to this master*

> Floor, not a rate. Confirm against a direct well-status query before reporting a ratio to anyone.

- PIONEER NATURAL RES. USA, INC. — 114 permits, 17 spuds seen
- DIAMONDBACK E&P LLC — 70 permits, 4 spuds seen
- EOG RESOURCES, INC. — 46 permits, 0 spuds seen
- COG OPERATING LLC — 45 permits, 0 spuds seen
- CONTINENTAL RESOURCES, INC. — 38 permits, 0 spuds seen
- BPX OPERATING COMPANY — 32 permits, 0 spuds seen
- BURLINGTON RESOURCES O & G CO LP — 28 permits, 0 spuds seen
- OCCIDENTAL PERMIAN LTD. — 28 permits, 0 spuds seen

**Amendment clusters** — block-wide refiling often precedes drilling

- COTERRA ENERGY OPERATING CO. — FLYING EBONY 19-30 (8 permits refiled)
- CRESCENT ENERGY OPERATING, LLC — DK (7 permits refiled)
- KING OPERATING CORPORATION — BIVINS (2 permits refiled)

**Corridor — DLS / EOG — Giddings & Eastern Eagle Ford, trailing 90 days**

- MAGNOLIA OIL & GAS OPERATING LLC — 20 (FAYETTE, LEE, WASHINGTON)
- MARATHON OIL EF LLC — 8 (DEWITT, GONZALES)
- BURLINGTON RESOURCES O & G CO LP — 7 (DEWITT)
- DEVON ENERGY PRODUCTION CO, L.P. — 7 (DEWITT)
- FW EAGLE FORD I, LLC — 7 (GONZALES, LAVACA)
- AETHON ENERGY OPERATING LLC — 7 (WASHINGTON)
- SAGE NATURAL RESOURCES LLC — 4 (FAYETTE, LEE)
- ENSIGN NATURAL RESOURCES II LLC — 4 (DEWITT)
- BPX OPERATING COMPANY — 3 (DEWITT)
- ROYAL PRODUCTION COMPANY, INC. — 1 (LAVACA)
- IRONBLOOM OPERATING, LLC — 1 (LEE)
- ENHANCED ENERGY PARTNERS CORP — 1 (AUSTIN)
- LP OPERATING, LLC — 1 (GONZALES)
- WILDFIRE ENERGY OPERATING LLC — 1 (LEE)

New in this corridor this week: 14

**Corridor — DOXA / Sabine — East Texas, trailing 90 days**

- SABINE ENERGY INC. — 14 (HARRISON, PANOLA, RUSK)
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

New in this corridor this week: 2

**Corridor — DOXA / Firebird — Permian, trailing 90 days**

- PIONEER NATURAL RES. USA, INC. — 60 (ANDREWS, MIDLAND, UPTON)
- DIAMONDBACK E&P LLC — 48 (ECTOR, MIDLAND)
- COG OPERATING LLC — 45 (ANDREWS, MIDLAND)
- CONTINENTAL RESOURCES, INC. — 31 (ECTOR, MIDLAND, WINKLER)
- CHEVRON U. S. A. INC. — 21 (MIDLAND, UPTON)
- APACHE CORPORATION — 19 (MIDLAND, UPTON)
- FASKEN OIL AND RANCH, LTD. — 14 (ANDREWS)
- FIREBIRD ENERGY II LLC — 14 (ECTOR)
- SABALO II OPERATING, LLC — 12 (ANDREWS)
- ARRINGTON OIL&GAS OPERATING LLC — 12 (ECTOR)
- OVINTIV USA INC. — 11 (ANDREWS)
- BASIN OIL & GAS OPERATING, LLC — 9 (ECTOR, WINKLER)
- SUMMIT PETROLEUM LLC — 8 (UPTON)
- BLACKBEARD OPERATING, LLC — 7 (CRANE, WINKLER)
- RING ENERGY, INC. — 6 (CRANE)
- MEWBOURNE OIL COMPANY — 4 (WINKLER)
- BTA OIL PRODUCERS, LLC — 4 (CRANE)
- ADMIRAL PERMIAN OPERATING LLC — 3 (ANDREWS, UPTON)
- XRI DISPOSAL HOLDINGS, LLC — 3 (WINKLER)
- SM ENERGY COMPANY — 3 (CRANE)
- PERMIAN DEEP ROCK OIL CO., LLC — 3 (MIDLAND)
- DAVIS SOUTHERN OPERATING CO LLC — 2 (ECTOR)
- MID-STATES OPERATING COMPANY — 2 (MIDLAND)
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
- COMSTOCK OIL & GAS, LLC — 4 (LEON, ROBERTSON)
- ADAMAS ENERGY LLC — 2 (ROBERTSON)
- WILDFIRE ENERGY OPERATING LLC — 2 (ROBERTSON)
- MAXIMUS OPERATING, LTD. — 1 (LEON)
- CML EXPLORATION, LLC — 1 (ROBERTSON)

New in this corridor this week: 3

**Corridor — RROG + DOXA — NW Louisiana Haynesville, trailing 90 days**

- No permits in the trailing 90 days

## Data notes

- County labels check out against county_lookup.py (Mc-block self-check passed)
- 6 records excluded from cycle statistics (spud predates issue — wellbore re-entries)
- Newest issue date in master: 2026-08-28 (3 day(s) behind as-of date)
- Permits age out of the rolling daily source pull after ~30 days; a permit's disappearance from new activity is coverage boundary, not inactivity
- **Spud conversion and permit-banking figures are floors.** A permit that ages past the rolling window before spudding never posts its spud date back to the source, so every conversion figure here understates reality. Confirm against a direct well-status query before either reaches a client.
- Spud reporting lags ~21 days; silence inside that window is not a signal

## Louisiana

- 179 records in the LA master. Reported separately from TX by design — parish activity and Texas county activity are not directly comparable, and Haynesville spans the state line.
- *(Parish-level rolling/cohort analysis not yet built here — the LA REST layer per config.yaml has no BHL/line geometry, only surface points, so some of the TX-side metrics may not translate cleanly. Extend prep_tx's twin for LA's field names before relying on this.)*
