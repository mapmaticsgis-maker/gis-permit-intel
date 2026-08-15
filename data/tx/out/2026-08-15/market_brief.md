# Permit Market Brief — 2026-08-15

## Headline

*[Write this last. Two to three sentences on what today's activity means in context. If the day was unremarkable, say so plainly.]*

## Today

- Permits issued: **0** (30-day average 32/business day, baseline ~35)
- New spud postings dated today: **0**

No permits carry today's issue date. If the prior pull was identical, check tx_daf420.py's ingestion ledger — it already distinguishes a genuine RRC posting gap from a stale fetch; this brief does not re-derive that.

## Rolling week

- 7-day issuance: **156** (prior 7-day: 186, -16% vs prior week)

**Accelerating**

- DIAMONDBACK E&P LLC — 31 this week (+24)
- DE CENTRAL OPERATING, LLC — 12 this week (+11)
- EOG RESOURCES, INC. — 9 this week (+6)
- OCCIDENTAL PERMIAN LTD. — 7 this week (+6)
- TGNR EAST TEXAS II LLC — 5 this week (+5)

**Decelerating**

- APACHE CORPORATION — 0 this week (-5)
- BPX OPERATING COMPANY — 1 this week (-6)
- L.C.S. PRODUCTION COMPANY — 0 this week (-6)
- CONTINENTAL RESOURCES, INC. — 0 this week (-8)
- BURLINGTON RESOURCES O & G CO LP — 0 this week (-9)

**New entrants this week** (no permits in prior 30 days — check operator_families first; a rebrand or merged alias should not read as new)

- ADAMAS ENERGY LLC (SAN AUGUSTINE)
- BASA RESOURCES, INC. (VAN ZANDT)
- DISCOVERY NATURAL RESOURCES LLC (REAGAN)
- ENHANCED ENERGY PARTNERS CORP (AUSTIN)
- FAIR OIL, LTD. (WOOD)
- FORMENTERA OPERATIONS LLC (FRIO)
- G & F OIL, INC. (PALO PINTO)
- KEBO OIL & GAS, INC. (VICTORIA)
- MONTARE OPERATING, LTD. (ANDREWS)
- NODDING DONKEY RESOURCES LLC (RUNNELS)

- Wells spudded this week: **3**, median permit-to-spud **5 days**

## Month to date

- MTD issuance: **342** over 10 business days, tracking to ~**718** (baseline ~750)
- Basin mix: Permian 61%, Other 20%, Eagle Ford 14%, East Texas gas 5%

**Watched families, MTD**

- EOG Resources: 12
- Magnolia (EOG-contiguous, Lee Co): 4
- Sabine Energy: 2
- Adamas (ex-Aethon, Mitsubishi): 2
- Apex (ex-Paloma, Citadel): 1

**Spud conversion by issue cohort** *(floor, not a true rate — see Data notes)*

- 2026-04: 13/28 (46%)
- 2026-05: 8/56 (14%)
- 2026-06: 9/42 (21%)
- 2026-07: 30/693 (4%)  *(inside spud-reporting lag)*
- 2026-08: 4/342 (1%)  *(inside spud-reporting lag)*

- Aging inventory: **166** permits issued 45+ days ago, still unspudded
- Ultra-deep (16,000'+) permits MTD: **22**

## Pattern candidates

*Machine-surfaced. Review before including — not all are meaningful.*

**Step-outs** — first permit in this county in 90+ days

- EOG RESOURCES, INC. → WEBB (9 permit(s))
- TGNR EAST TEXAS II LLC → PANOLA (5 permit(s))
- SILVER HILL ENERGY OPERATING LLC → LA SALLE (4 permit(s))
- OCCIDENTAL PERMIAN LTD. → SCURRY (2 permit(s))
- BKV BARNETT, LLC → WISE (1 permit(s))
- FX ENERGY OPERATING, LLC → HEMPHILL (1 permit(s))
- HILCORP ENERGY COMPANY → ROBERTSON (1 permit(s))
- MONTARE OPERATING, LTD. → ANDREWS (1 permit(s))

**Permit banking candidates** — 90-day permits vs spuds *visible to this master*

> Floor, not a rate. Confirm against a direct well-status query before reporting a ratio to anyone.

- PIONEER NATURAL RES. USA, INC. — 97 permits, 8 spuds seen
- DIAMONDBACK E&P LLC — 57 permits, 0 spuds seen
- COG OPERATING LLC — 45 permits, 0 spuds seen
- EOG RESOURCES, INC. — 40 permits, 0 spuds seen
- CONTINENTAL RESOURCES, INC. — 33 permits, 0 spuds seen
- DE CENTRAL OPERATING, LLC — 32 permits, 1 spuds seen
- BURLINGTON RESOURCES O & G CO LP — 28 permits, 0 spuds seen
- BPX OPERATING COMPANY — 23 permits, 0 spuds seen

**Amendment clusters** — block-wide refiling often precedes drilling

- COTERRA ENERGY OPERATING CO. — VAGRANT 38 FEE (4 permits refiled)
- ANADARKO E&P ONSHORE LLC — GOLEM STATE 56-2-43-13 (2 permits refiled)

**Corridor — DLS / EOG — Giddings & Eastern Eagle Ford, trailing 90 days**

- MAGNOLIA OIL & GAS OPERATING LLC — 17 (FAYETTE, LEE, WASHINGTON)
- MARATHON OIL EF LLC — 8 (DEWITT, GONZALES)
- BURLINGTON RESOURCES O & G CO LP — 7 (DEWITT)
- DEVON ENERGY PRODUCTION CO, L.P. — 7 (DEWITT)
- FW EAGLE FORD I, LLC — 7 (GONZALES, LAVACA)
- SAGE NATURAL RESOURCES LLC — 2 (LEE)
- ROYAL PRODUCTION COMPANY, INC. — 1 (LAVACA)
- IRONBLOOM OPERATING, LLC — 1 (LEE)
- ENHANCED ENERGY PARTNERS CORP — 1 (AUSTIN)
- LP OPERATING, LLC — 1 (GONZALES)

New in this corridor this week: 5

**Corridor — DOXA / Sabine — East Texas, trailing 90 days**

- SABINE ENERGY INC. — 14 (HARRISON, PANOLA, RUSK)
- TGNR PANOLA LLC — 9 (PANOLA)
- BUFFCO PRODUCTION INC. — 7 (HARRISON, PANOLA, RUSK)
- TGNR EAST TEXAS II LLC — 6 (HARRISON, PANOLA)
- SILVER HILL ENERGY OPERATING LLC — 4 (SHELBY)
- PWEP OPERATING, LLC — 3 (HARRISON)
- R. LACY SERVICES, LTD. — 3 (PANOLA)
- FAULCONER ENERGY, LLC — 3 (GREGG, SMITH)
- COMSTOCK OIL & GAS, LLC — 2 (HARRISON)
- ARENOS ENERGY — 2 (NACOGDOCHES)
- REVENANT ENERGY OPERATING LLC — 2 (NACOGDOCHES)
- AGIS ENERGY LLC — 2 (PANOLA)
- BUCKHORN OPERATING LLC — 1 (RUSK)
- TANOS EXPLORATION IV, LLC — 1 (RUSK)
- SELECT WATER SOLUTIONS, LLC — 1 (SHELBY)
- XTO ENERGY INC. — 1 (SHELBY)

New in this corridor this week: 8

**Corridor — DOXA / Firebird — Permian, trailing 90 days**

- COG OPERATING LLC — 45 (ANDREWS, MIDLAND)
- PIONEER NATURAL RES. USA, INC. — 45 (MIDLAND, UPTON)
- DIAMONDBACK E&P LLC — 35 (ECTOR, MIDLAND)
- CONTINENTAL RESOURCES, INC. — 26 (ECTOR, MIDLAND, WINKLER)
- CHEVRON U. S. A. INC. — 18 (UPTON)
- APACHE CORPORATION — 12 (MIDLAND, UPTON)
- ARRINGTON OIL&GAS OPERATING LLC — 10 (ECTOR)
- BASIN OIL & GAS OPERATING, LLC — 9 (ECTOR, WINKLER)
- SUMMIT PETROLEUM LLC — 8 (UPTON)
- SABALO II OPERATING, LLC — 7 (ANDREWS)
- FASKEN OIL AND RANCH, LTD. — 6 (ANDREWS)
- BLACKBEARD OPERATING, LLC — 6 (CRANE, WINKLER)
- FIREBIRD ENERGY II LLC — 6 (ECTOR)
- MEWBOURNE OIL COMPANY — 5 (WINKLER)
- OVINTIV USA INC. — 5 (ANDREWS)
- XRI DISPOSAL HOLDINGS, LLC — 3 (WINKLER)
- SM ENERGY COMPANY — 3 (CRANE)
- BTA OIL PRODUCERS, LLC — 2 (CRANE)
- RING ENERGY, INC. — 2 (CRANE)
- PERMIAN DEEP ROCK OIL CO., LLC — 2 (MIDLAND)
- OLSEN ENERGY INC. — 1 (ANDREWS)
- GREEN CENTURY EXP & PROD, LLC — 1 (CRANE)
- DISCOVERY OPERATING, INC. — 1 (MIDLAND)
- ADMIRAL PERMIAN OPERATING LLC — 1 (UPTON)
- BOSQUE TEXAS OIL LLC — 1 (WINKLER)
- MONTARE OPERATING, LTD. — 1 (ANDREWS)
- PETX OPERATING LLC — 1 (UPTON)
- ZARVONA ENERGY LLC — 1 (UPTON)

New in this corridor this week: 35

**Corridor — West Haynesville watch, trailing 90 days**

- HILCORP ENERGY COMPANY — 7 (FREESTONE, ROBERTSON)
- EMPIRE TEXAS OPERATING LLC — 5 (HOUSTON, MADISON)
- COMSTOCK OIL & GAS, LLC — 2 (LEON)
- ADAMAS ENERGY LLC — 2 (ROBERTSON)
- MAXIMUS OPERATING, LTD. — 1 (LEON)

New in this corridor this week: 1

**Corridor — RROG + DOXA — NW Louisiana Haynesville, trailing 90 days**

- No permits in the trailing 90 days

## Data notes

- County labels check out against county_lookup.py (Mc-block self-check passed)
- 4 records excluded from cycle statistics (spud predates issue — wellbore re-entries)
- Newest issue date in master: 2026-08-13 (2 day(s) behind as-of date)
- Permits age out of the rolling daily source pull after ~30 days; a permit's disappearance from new activity is coverage boundary, not inactivity
- **Spud conversion and permit-banking figures are floors.** A permit that ages past the rolling window before spudding never posts its spud date back to the source, so every conversion figure here understates reality. Confirm against a direct well-status query before either reaches a client.
- Spud reporting lags ~21 days; silence inside that window is not a signal

## Louisiana

- 149 records in the LA master. Reported separately from TX by design — parish activity and Texas county activity are not directly comparable, and Haynesville spans the state line.
- *(Parish-level rolling/cohort analysis not yet built here — the LA REST layer per config.yaml has no BHL/line geometry, only surface points, so some of the TX-side metrics may not translate cleanly. Extend prep_tx's twin for LA's field names before relying on this.)*
