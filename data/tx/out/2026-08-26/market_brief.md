# Permit Market Brief — 2026-08-26

## Headline

*[Write this last. Two to three sentences on what today's activity means in context. If the day was unremarkable, say so plainly.]*

## Today

- Permits issued: **0** (30-day average 31/business day, baseline ~35)
- New spud postings dated today: **0**

No permits carry today's issue date. If the prior pull was identical, check tx_daf420.py's ingestion ledger — it already distinguishes a genuine RRC posting gap from a stale fetch; this brief does not re-derive that.

## Rolling week

- 7-day issuance: **76** (prior 7-day: 197, -61% vs prior week)

**Accelerating**

- VTX ENERGY OPERATING, LLC — 8 this week (+8)
- BTA OIL PRODUCERS, LLC — 4 this week (+4)
- HILCORP ENERGY COMPANY — 3 this week (+3)
- PERUN ENERGY LLC — 3 this week (+3)
- JAVELIN ENERGY PARTNERS MGMT LLC — 3 this week (+3)

**Decelerating**

- FASKEN OIL AND RANCH, LTD. — 0 this week (-8)
- SM ENERGY COMPANY — 0 this week (-9)
- OCCIDENTAL PERMIAN LTD. — 2 this week (-10)
- EOG RESOURCES, INC. — 1 this week (-11)
- PIONEER NATURAL RES. USA, INC. — 4 this week (-18)

**New entrants this week** (no permits in prior 30 days — check operator_families first; a rebrand or merged alias should not read as new)

- ENSIGN NATURAL RESOURCES II LLC (DEWITT)
- HIBERNIA RESOURCES IV, LLC (DAWSON)
- KODIAK OIL & GAS, INC. (WICHITA)
- PDEH LLC (LOVING)
- RISING STAR ENERGY PARTNERS II, (REFUGIO)
- SEABOARD OPERATING CO. (BORDEN)
- SONERRA RESOURCES CORPORATION (NACOGDOCHES)
- TANOS EXPLORATION IV, LLC (RUSK)
- TEXXOL OPERATING COMPANY, INC. (MONTAGUE)
- UPSTREAM RESOURCE PARTNERS, LLC (ANDERSON)

- Wells spudded this week: **17**, median permit-to-spud **16 days**

## Month to date

- MTD issuance: **568** over 18 business days, tracking to ~**663** (baseline ~750)
- Basin mix: Permian 64%, Other 17%, Eagle Ford 15%, East Texas gas 4%

**Watched families, MTD**

- EOG Resources: 18
- Magnolia (EOG-contiguous, Lee Co): 7
- Firebird Energy: 6
- Adamas (ex-Aethon, Mitsubishi): 4
- Sabine Energy: 3
- Apex (ex-Paloma, Citadel): 2
- Comstock (Jerry Jones): 1

**Spud conversion by issue cohort** *(floor, not a true rate — see Data notes)*

- 2026-04: 21/36 (58%)
- 2026-05: 21/76 (28%)
- 2026-06: 15/62 (24%)
- 2026-07: 33/693 (5%)
- 2026-08: 25/568 (4%)  *(inside spud-reporting lag)*

- Aging inventory: **423** permits issued 45+ days ago, still unspudded
- Ultra-deep (16,000'+) permits MTD: **26**

## Pattern candidates

*Machine-surfaced. Review before including — not all are meaningful.*

**Step-outs** — first permit in this county in 90+ days

- JAVELIN ENERGY PARTNERS MGMT LLC → DIMMIT (3 permit(s))
- ADMIRAL PERMIAN OPERATING LLC → ANDREWS (2 permit(s))
- BORDERLINE OPERATING CORP. → YOUNG (1 permit(s))
- COMSTOCK OIL & GAS, LLC → ROBERTSON (1 permit(s))
- HILCORP ENERGY COMPANY → ANDREWS (1 permit(s))
- RING ENERGY, INC. → YOAKUM (1 permit(s))
- WILDFIRE ENERGY OPERATING LLC → LEE (1 permit(s))

**Permit banking candidates** — 90-day permits vs spuds *visible to this master*

> Floor, not a rate. Confirm against a direct well-status query before reporting a ratio to anyone.

- PIONEER NATURAL RES. USA, INC. — 113 permits, 15 spuds seen
- DIAMONDBACK E&P LLC — 69 permits, 3 spuds seen
- EOG RESOURCES, INC. — 46 permits, 0 spuds seen
- COG OPERATING LLC — 45 permits, 0 spuds seen
- CONTINENTAL RESOURCES, INC. — 33 permits, 0 spuds seen
- DE CENTRAL OPERATING, LLC — 32 permits, 2 spuds seen
- BURLINGTON RESOURCES O & G CO LP — 28 permits, 0 spuds seen
- MEWBOURNE OIL COMPANY — 25 permits, 1 spuds seen

**Amendment clusters** — block-wide refiling often precedes drilling

- COTERRA ENERGY OPERATING CO. — STATE WINNING COLORS (9 permits refiled)
- COTERRA ENERGY OPERATING CO. — STATE WINTERGREEN (8 permits refiled)
- COTERRA ENERGY OPERATING CO. — STATE SECRETARIAT (7 permits refiled)
- COTERRA ENERGY OPERATING CO. — STATE CHARISMATIC 5-8 (6 permits refiled)
- COTERRA ENERGY OPERATING CO. — STATE KINGMAN (4 permits refiled)
- COTERRA ENERGY OPERATING CO. — CITATION 41-32 (3 permits refiled)
- COTERRA ENERGY OPERATING CO. — FOOLISH PLEASURE 43-6 (3 permits refiled)
- COTERRA ENERGY OPERATING CO. — NEEDLES 39 (2 permits refiled)

**Corridor — DLS / EOG — Giddings & Eastern Eagle Ford, trailing 90 days**

- MAGNOLIA OIL & GAS OPERATING LLC — 20 (FAYETTE, LEE, WASHINGTON)
- MARATHON OIL EF LLC — 8 (DEWITT, GONZALES)
- BURLINGTON RESOURCES O & G CO LP — 7 (DEWITT)
- DEVON ENERGY PRODUCTION CO, L.P. — 7 (DEWITT)
- FW EAGLE FORD I, LLC — 7 (GONZALES, LAVACA)
- SAGE NATURAL RESOURCES LLC — 2 (LEE)
- ENSIGN NATURAL RESOURCES II LLC — 2 (DEWITT)
- ROYAL PRODUCTION COMPANY, INC. — 1 (LAVACA)
- IRONBLOOM OPERATING, LLC — 1 (LEE)
- ENHANCED ENERGY PARTNERS CORP — 1 (AUSTIN)
- LP OPERATING, LLC — 1 (GONZALES)
- WILDFIRE ENERGY OPERATING LLC — 1 (LEE)

New in this corridor this week: 3

**Corridor — DOXA / Sabine — East Texas, trailing 90 days**

- SABINE ENERGY INC. — 13 (HARRISON, PANOLA, RUSK)
- TGNR PANOLA LLC — 9 (PANOLA)
- BUFFCO PRODUCTION INC. — 7 (HARRISON, PANOLA, RUSK)
- TGNR EAST TEXAS II LLC — 5 (PANOLA)
- R. LACY SERVICES, LTD. — 3 (PANOLA)
- FAULCONER ENERGY, LLC — 3 (GREGG, SMITH)
- PWEP OPERATING, LLC — 3 (HARRISON)
- COMSTOCK OIL & GAS, LLC — 2 (HARRISON)
- REVENANT ENERGY OPERATING LLC — 2 (NACOGDOCHES)
- AGIS ENERGY LLC — 2 (PANOLA)
- TANOS EXPLORATION IV, LLC — 2 (RUSK)
- SILVER HILL ENERGY OPERATING LLC — 2 (SHELBY)
- BUCKHORN OPERATING LLC — 1 (RUSK)
- SELECT WATER SOLUTIONS, LLC — 1 (SHELBY)
- SONERRA RESOURCES CORPORATION — 1 (NACOGDOCHES)
- XTO ENERGY INC. — 1 (SHELBY)

New in this corridor this week: 2

**Corridor — DOXA / Firebird — Permian, trailing 90 days**

- PIONEER NATURAL RES. USA, INC. — 59 (ANDREWS, MIDLAND, UPTON)
- DIAMONDBACK E&P LLC — 47 (ECTOR, MIDLAND)
- COG OPERATING LLC — 45 (ANDREWS, MIDLAND)
- CONTINENTAL RESOURCES, INC. — 26 (ECTOR, MIDLAND, WINKLER)
- APACHE CORPORATION — 19 (MIDLAND, UPTON)
- CHEVRON U. S. A. INC. — 18 (UPTON)
- FASKEN OIL AND RANCH, LTD. — 14 (ANDREWS)
- SABALO II OPERATING, LLC — 12 (ANDREWS)
- FIREBIRD ENERGY II LLC — 12 (ECTOR)
- OVINTIV USA INC. — 11 (ANDREWS)
- ARRINGTON OIL&GAS OPERATING LLC — 10 (ECTOR)
- BASIN OIL & GAS OPERATING, LLC — 9 (ECTOR, WINKLER)
- SUMMIT PETROLEUM LLC — 8 (UPTON)
- BLACKBEARD OPERATING, LLC — 7 (CRANE, WINKLER)
- MEWBOURNE OIL COMPANY — 4 (WINKLER)
- BTA OIL PRODUCERS, LLC — 4 (CRANE)
- RING ENERGY, INC. — 4 (CRANE)
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
- OVERFLOW ENERGY PERMIAN, LLC — 1 (MIDLAND)
- AQUA TERRA PERMIAN, LLC — 1 (UPTON)
- PETX OPERATING LLC — 1 (UPTON)
- ZARVONA ENERGY LLC — 1 (UPTON)

New in this corridor this week: 17

**Corridor — West Haynesville watch, trailing 90 days**

- HILCORP ENERGY COMPANY — 9 (FREESTONE, ROBERTSON)
- EMPIRE TEXAS OPERATING LLC — 5 (HOUSTON, MADISON)
- COMSTOCK OIL & GAS, LLC — 3 (LEON, ROBERTSON)
- ADAMAS ENERGY LLC — 2 (ROBERTSON)
- MAXIMUS OPERATING, LTD. — 1 (LEON)
- WILDFIRE ENERGY OPERATING LLC — 1 (ROBERTSON)

New in this corridor this week: 3

**Corridor — RROG + DOXA — NW Louisiana Haynesville, trailing 90 days**

- No permits in the trailing 90 days

## Data notes

- County labels check out against county_lookup.py (Mc-block self-check passed)
- 4 records excluded from cycle statistics (spud predates issue — wellbore re-entries)
- Newest issue date in master: 2026-08-24 (2 day(s) behind as-of date)
- Permits age out of the rolling daily source pull after ~30 days; a permit's disappearance from new activity is coverage boundary, not inactivity
- **Spud conversion and permit-banking figures are floors.** A permit that ages past the rolling window before spudding never posts its spud date back to the source, so every conversion figure here understates reality. Confirm against a direct well-status query before either reaches a client.
- Spud reporting lags ~21 days; silence inside that window is not a signal

## Louisiana

- 172 records in the LA master. Reported separately from TX by design — parish activity and Texas county activity are not directly comparable, and Haynesville spans the state line.
- *(Parish-level rolling/cohort analysis not yet built here — the LA REST layer per config.yaml has no BHL/line geometry, only surface points, so some of the TX-side metrics may not translate cleanly. Extend prep_tx's twin for LA's field names before relying on this.)*
