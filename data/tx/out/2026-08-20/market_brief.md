# Permit Market Brief — 2026-08-20

## Headline

*[Write this last. Two to three sentences on what today's activity means in context. If the day was unremarkable, say so plainly.]*

## Today

- Permits issued: **0** (30-day average 31/business day, baseline ~35)
- New spud postings dated today: **0**

No permits carry today's issue date. If the prior pull was identical, check tx_daf420.py's ingestion ledger — it already distinguishes a genuine RRC posting gap from a stale fetch; this brief does not re-derive that.

## Rolling week

- 7-day issuance: **115** (prior 7-day: 195, -41% vs prior week)

**Accelerating**

- COTERRA ENERGY OPERATING CO. — 8 this week (+8)
- FASKEN OIL AND RANCH, LTD. — 8 this week (+8)
- MEWBOURNE OIL COMPANY — 6 this week (+5)
- MCM OPERATING, LLC — 5 this week (+5)
- SABALO II OPERATING, LLC — 5 this week (+5)

**Decelerating**

- TGNR EAST TEXAS II LLC — 0 this week (-5)
- BPX OPERATING COMPANY — 0 this week (-8)
- DE CENTRAL OPERATING, LLC — 0 this week (-12)
- DIAMONDBACK E&P LLC — 6 this week (-25)
- PIONEER NATURAL RES. USA, INC. — 2 this week (-26)

**New entrants this week** (no permits in prior 30 days — check operator_families first; a rebrand or merged alias should not read as new)

- AQUA TERRA PERMIAN, LLC (UPTON)
- ARROW OIL & GAS, LLC (OLDHAM)
- CARSON BUCKLES EXPLORATION LLC (OCHILTREE)
- COTERRA ENERGY OPERATING CO. (CULBERSON)
- CRESCENT ENERGY OPERATING, LLC (WEBB)
- DELEK CRUDE LOGISTICS, LLC (TAYLOR)
- FIREBIRD ENERGY II LLC (ECTOR)
- HANNATHON PETROLEUM II, LLC (REAGAN)
- INEOS USA OIL & GAS LLC (LA SALLE)
- LAGUNA TEXAS RESOURCES, LLC (DAWSON)

- Wells spudded this week: **2**, median permit-to-spud **8 days**

## Month to date

- MTD issuance: **457** over 14 business days, tracking to ~**686** (baseline ~750)
- Basin mix: Permian 62%, Other 18%, Eagle Ford 16%, East Texas gas 4%

**Watched families, MTD**

- EOG Resources: 17
- Magnolia (EOG-contiguous, Lee Co): 7
- Firebird Energy: 4
- Sabine Energy: 3
- Apex (ex-Paloma, Citadel): 2
- Adamas (ex-Aethon, Mitsubishi): 2

**Spud conversion by issue cohort** *(floor, not a true rate — see Data notes)*

- 2026-04: 18/33 (55%)
- 2026-05: 9/62 (15%)
- 2026-06: 13/52 (25%)
- 2026-07: 30/693 (4%)  *(inside spud-reporting lag)*
- 2026-08: 6/457 (1%)  *(inside spud-reporting lag)*

- Aging inventory: **257** permits issued 45+ days ago, still unspudded
- Ultra-deep (16,000'+) permits MTD: **22**

## Pattern candidates

*Machine-surfaced. Review before including — not all are meaningful.*

**Step-outs** — first permit in this county in 90+ days

- SILVER HILL ENERGY OPERATING LLC → KARNES (3 permit(s))
- AQUA TERRA PERMIAN, LLC → UPTON (1 permit(s))
- B.O.L.D. OIL AND GAS, LLC → JACK (1 permit(s))
- DAVIS SOUTHERN OPERATING CO LLC → JASPER (1 permit(s))
- TEXLAND PETROLEUM, L.P. → ANDREWS (1 permit(s))
- WHITEHEAD RESOURCES, LTD. → HARDIN (1 permit(s))
- WILDFIRE ENERGY OPERATING LLC → ROBERTSON (1 permit(s))

**Permit banking candidates** — 90-day permits vs spuds *visible to this master*

> Floor, not a rate. Confirm against a direct well-status query before reporting a ratio to anyone.

- PIONEER NATURAL RES. USA, INC. — 99 permits, 8 spuds seen
- DIAMONDBACK E&P LLC — 63 permits, 0 spuds seen
- COG OPERATING LLC — 45 permits, 0 spuds seen
- EOG RESOURCES, INC. — 45 permits, 0 spuds seen
- CONTINENTAL RESOURCES, INC. — 33 permits, 0 spuds seen
- DE CENTRAL OPERATING, LLC — 32 permits, 1 spuds seen
- BURLINGTON RESOURCES O & G CO LP — 28 permits, 0 spuds seen
- MEWBOURNE OIL COMPANY — 25 permits, 1 spuds seen

**Amendment clusters** — block-wide refiling often precedes drilling

- COTERRA ENERGY OPERATING CO. — STREET SENSE 40 (4 permits refiled)

**Corridor — DLS / EOG — Giddings & Eastern Eagle Ford, trailing 90 days**

- MAGNOLIA OIL & GAS OPERATING LLC — 20 (FAYETTE, LEE, WASHINGTON)
- MARATHON OIL EF LLC — 8 (DEWITT, GONZALES)
- BURLINGTON RESOURCES O & G CO LP — 7 (DEWITT)
- DEVON ENERGY PRODUCTION CO, L.P. — 7 (DEWITT)
- FW EAGLE FORD I, LLC — 7 (GONZALES, LAVACA)
- SAGE NATURAL RESOURCES LLC — 2 (LEE)
- ROYAL PRODUCTION COMPANY, INC. — 1 (LAVACA)
- IRONBLOOM OPERATING, LLC — 1 (LEE)
- ENHANCED ENERGY PARTNERS CORP — 1 (AUSTIN)
- LP OPERATING, LLC — 1 (GONZALES)

New in this corridor this week: 3

**Corridor — DOXA / Sabine — East Texas, trailing 90 days**

- SABINE ENERGY INC. — 13 (HARRISON, PANOLA, RUSK)
- TGNR PANOLA LLC — 9 (PANOLA)
- BUFFCO PRODUCTION INC. — 7 (HARRISON, PANOLA, RUSK)
- TGNR EAST TEXAS II LLC — 5 (PANOLA)
- PWEP OPERATING, LLC — 3 (HARRISON)
- R. LACY SERVICES, LTD. — 3 (PANOLA)
- FAULCONER ENERGY, LLC — 3 (GREGG, SMITH)
- COMSTOCK OIL & GAS, LLC — 2 (HARRISON)
- REVENANT ENERGY OPERATING LLC — 2 (NACOGDOCHES)
- AGIS ENERGY LLC — 2 (PANOLA)
- SILVER HILL ENERGY OPERATING LLC — 2 (SHELBY)
- ARENOS ENERGY — 2 (NACOGDOCHES)
- BUCKHORN OPERATING LLC — 1 (RUSK)
- TANOS EXPLORATION IV, LLC — 1 (RUSK)
- SELECT WATER SOLUTIONS, LLC — 1 (SHELBY)
- XTO ENERGY INC. — 1 (SHELBY)

New in this corridor this week: 1

**Corridor — DOXA / Firebird — Permian, trailing 90 days**

- COG OPERATING LLC — 45 (ANDREWS, MIDLAND)
- PIONEER NATURAL RES. USA, INC. — 45 (MIDLAND, UPTON)
- DIAMONDBACK E&P LLC — 40 (ECTOR, MIDLAND)
- CONTINENTAL RESOURCES, INC. — 26 (ECTOR, MIDLAND, WINKLER)
- CHEVRON U. S. A. INC. — 18 (UPTON)
- APACHE CORPORATION — 15 (MIDLAND, UPTON)
- FASKEN OIL AND RANCH, LTD. — 14 (ANDREWS)
- SABALO II OPERATING, LLC — 12 (ANDREWS)
- ARRINGTON OIL&GAS OPERATING LLC — 10 (ECTOR)
- FIREBIRD ENERGY II LLC — 10 (ECTOR)
- BASIN OIL & GAS OPERATING, LLC — 9 (ECTOR, WINKLER)
- SUMMIT PETROLEUM LLC — 8 (UPTON)
- OVINTIV USA INC. — 7 (ANDREWS)
- BLACKBEARD OPERATING, LLC — 6 (CRANE, WINKLER)
- MEWBOURNE OIL COMPANY — 4 (WINKLER)
- RING ENERGY, INC. — 4 (CRANE)
- XRI DISPOSAL HOLDINGS, LLC — 3 (WINKLER)
- SM ENERGY COMPANY — 3 (CRANE)
- BTA OIL PRODUCERS, LLC — 2 (CRANE)
- MID-STATES OPERATING COMPANY — 2 (MIDLAND)
- PERMIAN DEEP ROCK OIL CO., LLC — 2 (MIDLAND)
- OLSEN ENERGY INC. — 1 (ANDREWS)
- GREEN CENTURY EXP & PROD, LLC — 1 (CRANE)
- DISCOVERY OPERATING, INC. — 1 (MIDLAND)
- ADMIRAL PERMIAN OPERATING LLC — 1 (UPTON)
- BOSQUE TEXAS OIL LLC — 1 (WINKLER)
- MONTARE OPERATING, LTD. — 1 (ANDREWS)
- TEXLAND PETROLEUM, L.P. — 1 (ANDREWS)
- AQUA TERRA PERMIAN, LLC — 1 (UPTON)
- PETX OPERATING LLC — 1 (UPTON)
- ZARVONA ENERGY LLC — 1 (UPTON)

New in this corridor this week: 31

**Corridor — West Haynesville watch, trailing 90 days**

- HILCORP ENERGY COMPANY — 7 (FREESTONE, ROBERTSON)
- EMPIRE TEXAS OPERATING LLC — 5 (HOUSTON, MADISON)
- COMSTOCK OIL & GAS, LLC — 2 (LEON)
- ADAMAS ENERGY LLC — 2 (ROBERTSON)
- MAXIMUS OPERATING, LTD. — 1 (LEON)
- WILDFIRE ENERGY OPERATING LLC — 1 (ROBERTSON)

New in this corridor this week: 1

**Corridor — RROG + DOXA — NW Louisiana Haynesville, trailing 90 days**

- No permits in the trailing 90 days

## Data notes

- County labels check out against county_lookup.py (Mc-block self-check passed)
- 3 records excluded from cycle statistics (spud predates issue — wellbore re-entries)
- Newest issue date in master: 2026-08-18 (2 day(s) behind as-of date)
- Permits age out of the rolling daily source pull after ~30 days; a permit's disappearance from new activity is coverage boundary, not inactivity
- **Spud conversion and permit-banking figures are floors.** A permit that ages past the rolling window before spudding never posts its spud date back to the source, so every conversion figure here understates reality. Confirm against a direct well-status query before either reaches a client.
- Spud reporting lags ~21 days; silence inside that window is not a signal

## Louisiana

- 168 records in the LA master. Reported separately from TX by design — parish activity and Texas county activity are not directly comparable, and Haynesville spans the state line.
- *(Parish-level rolling/cohort analysis not yet built here — the LA REST layer per config.yaml has no BHL/line geometry, only surface points, so some of the TX-side metrics may not translate cleanly. Extend prep_tx's twin for LA's field names before relying on this.)*
