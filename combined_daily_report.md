# Combined Daily Permit Intel

## Market Brief

# Permit Market Brief — 2026-08-14

## Headline

*[Write this last. Two to three sentences on what today's activity means in context. If the day was unremarkable, say so plainly.]*

## Today

- Permits issued: **0** (30-day average 28/business day, baseline ~35)
- New spud postings dated today: **0**

No permits carry today's issue date. If the prior pull was identical, check tx_daf420.py's ingestion ledger — it already distinguishes a genuine RRC posting gap from a stale fetch; this brief does not re-derive that.

## Rolling week

- 7-day issuance: **77** (prior 7-day: 186, -59% vs prior week)

**Accelerating**

- DIAMONDBACK E&P LLC — 24 this week (+17)
- DE CENTRAL OPERATING, LLC — 12 this week (+11)
- TGNR EAST TEXAS II LLC — 5 this week (+5)
- SILVER HILL ENERGY OPERATING LLC — 4 this week (+4)
- EL TORO RESOURCES LLC — 3 this week (+3)

**Decelerating**

- BURK ROYALTY CO., LTD. — 0 this week (-6)
- L.C.S. PRODUCTION COMPANY — 0 this week (-6)
- CONTINENTAL RESOURCES, INC. — 0 this week (-8)
- BURLINGTON RESOURCES O & G CO LP — 0 this week (-9)
- PIONEER NATURAL RES. USA, INC. — 6 this week (-15)

**New entrants this week** (no permits in prior 30 days — check operator_families first; a rebrand or merged alias should not read as new)

- ADAMAS ENERGY LLC (SAN AUGUSTINE)
- BASA RESOURCES, INC. (VAN ZANDT)
- DISCOVERY NATURAL RESOURCES LLC (REAGAN)
- MONTARE OPERATING, LTD. (ANDREWS)
- PALADIN PETROLEUM III, L.L.C. (JIM WELLS)
- RISE PETROLEUM INVESTMENTS LLC (HARRIS)
- TGNR EAST TEXAS II LLC (PANOLA)

- Wells spudded this week: **1**, median permit-to-spud **5 days**

## Month to date

- MTD issuance: **263** over 10 business days, tracking to ~**552** (baseline ~750)
- Basin mix: Permian 61%, Other 21%, Eagle Ford 13%, East Texas gas 5%

**Watched families, MTD**

- EOG Resources: 4
- Adamas (ex-Aethon, Mitsubishi): 2
- Apex (ex-Paloma, Citadel): 1

**Spud conversion by issue cohort** *(floor, not a true rate — see Data notes)*

- 2026-04: 13/28 (46%)
- 2026-05: 8/52 (15%)
- 2026-06: 7/40 (18%)
- 2026-07: 30/693 (4%)  *(inside spud-reporting lag)*
- 2026-08: 2/263 (1%)  *(inside spud-reporting lag)*

- Aging inventory: **132** permits issued 45+ days ago, still unspudded
- Ultra-deep (16,000'+) permits MTD: **22**

## Pattern candidates

*Machine-surfaced. Review before including — not all are meaningful.*

**Step-outs** — first permit in this county in 90+ days

- TGNR EAST TEXAS II LLC → PANOLA (5 permit(s))
- SILVER HILL ENERGY OPERATING LLC → LA SALLE (4 permit(s))
- OCCIDENTAL PERMIAN LTD. → SCURRY (2 permit(s))
- EOG RESOURCES, INC. → WEBB (1 permit(s))
- FX ENERGY OPERATING, LLC → HEMPHILL (1 permit(s))
- HILCORP ENERGY COMPANY → ROBERTSON (1 permit(s))
- MONTARE OPERATING, LTD. → ANDREWS (1 permit(s))

**Permit banking candidates** — 90-day permits vs spuds *visible to this master*

> Floor, not a rate. Confirm against a direct well-status query before reporting a ratio to anyone.

- PIONEER NATURAL RES. USA, INC. — 81 permits, 8 spuds seen
- DIAMONDBACK E&P LLC — 50 permits, 0 spuds seen
- COG OPERATING LLC — 42 permits, 0 spuds seen
- CONTINENTAL RESOURCES, INC. — 33 permits, 0 spuds seen
- DE CENTRAL OPERATING, LLC — 32 permits, 0 spuds seen
- EOG RESOURCES, INC. — 32 permits, 0 spuds seen
- BURLINGTON RESOURCES O & G CO LP — 28 permits, 0 spuds seen
- BPX OPERATING COMPANY — 23 permits, 0 spuds seen

**Amendment clusters** — block-wide refiling often precedes drilling

- COTERRA ENERGY OPERATING CO. — VAGRANT 38 FEE (4 permits refiled)

**Corridor — DLS / EOG — Giddings & Eastern Eagle Ford, trailing 90 days**

- MAGNOLIA OIL & GAS OPERATING LLC — 13 (FAYETTE, LEE, WASHINGTON)
- MARATHON OIL EF LLC — 8 (DEWITT, GONZALES)
- BURLINGTON RESOURCES O & G CO LP — 7 (DEWITT)
- DEVON ENERGY PRODUCTION CO, L.P. — 7 (DEWITT)
- FW EAGLE FORD I, LLC — 7 (GONZALES, LAVACA)
- SAGE NATURAL RESOURCES LLC — 2 (LEE)
- ROYAL PRODUCTION COMPANY, INC. — 1 (LAVACA)
- IRONBLOOM OPERATING, LLC — 1 (LEE)
- LP OPERATING, LLC — 1 (GONZALES)

New in this corridor this week: 0

**Corridor — DOXA / Sabine — East Texas, trailing 90 days**

- SABINE ENERGY INC. — 12 (HARRISON, PANOLA, RUSK)
- TGNR PANOLA LLC — 9 (PANOLA)
- BUFFCO PRODUCTION INC. — 6 (HARRISON, PANOLA, RUSK)
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

New in this corridor this week: 5

**Corridor — DOXA / Firebird — Permian, trailing 90 days**

- COG OPERATING LLC — 42 (ANDREWS, MIDLAND)
- PIONEER NATURAL RES. USA, INC. — 37 (MIDLAND, UPTON)
- DIAMONDBACK E&P LLC — 30 (ECTOR, MIDLAND)
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
- PERMIAN DEEP ROCK OIL CO., LLC — 2 (MIDLAND)
- OLSEN ENERGY INC. — 1 (ANDREWS)
- GREEN CENTURY EXP & PROD, LLC — 1 (CRANE)
- DISCOVERY OPERATING, INC. — 1 (MIDLAND)
- ADMIRAL PERMIAN OPERATING LLC — 1 (UPTON)
- BOSQUE TEXAS OIL LLC — 1 (WINKLER)
- MONTARE OPERATING, LTD. — 1 (ANDREWS)
- RING ENERGY, INC. — 1 (CRANE)
- PETX OPERATING LLC — 1 (UPTON)
- ZARVONA ENERGY LLC — 1 (UPTON)

New in this corridor this week: 19

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
- 3 records excluded from cycle statistics (spud predates issue — wellbore re-entries)
- Newest issue date in master: 2026-08-11 (3 day(s) behind as-of date)
- Permits age out of the rolling daily source pull after ~30 days; a permit's disappearance from new activity is coverage boundary, not inactivity
- **Spud conversion and permit-banking figures are floors.** A permit that ages past the rolling window before spudding never posts its spud date back to the source, so every conversion figure here understates reality. Confirm against a direct well-status query before either reaches a client.
- Spud reporting lags ~21 days; silence inside that window is not a signal

## Louisiana

- 149 records in the LA master. Reported separately from TX by design — parish activity and Texas county activity are not directly comparable, and Haynesville spans the state line.
- *(Parish-level rolling/cohort analysis not yet built here — the LA REST layer per config.yaml has no BHL/line geometry, only surface points, so some of the TX-side metrics may not translate cleanly. Extend prep_tx's twin for LA's field names before relying on this.)*



## Confirmed New Permits -- Texas RRC

_Source: 2026-08-13_

# Texas RRC (daf420) Permit Intel — Thu Aug 13 2026

**77 new** | **4 amended** vs master.

## Corridor hits (client-relevant)

### DOXA / Firebird — Permian
- **DIAMONDBACK E&P LLC** — RIVERCREST 2-11 A: 2 wells (1JM, 1WA) (Midland, 12500' TD)
- **DIAMONDBACK E&P LLC** — RIVERCREST 2-11 B: 2 wells (1LS, 1WD) (Midland, 12500' TD)
- **DIAMONDBACK E&P LLC** — RIVERCREST 2-11 C (Midland, 12500' TD)
- **DIAMONDBACK E&P LLC** — RIVERCREST 2-11 E: 2 wells (3JM, 3WA) (Midland, 12500' TD)
- **DIAMONDBACK E&P LLC** — RIVERCREST 2-11 F: 2 wells (3LS, 3WB) (Midland, 12500' TD)
- **DIAMONDBACK E&P LLC** — RIVERCREST 2-11 G (Midland, 12500' TD)
- **DIAMONDBACK E&P LLC** — SHERIFF 2-38 C (Ector, 13000' TD)
- **DIAMONDBACK E&P LLC** — SHERIFF 2-38 D (Ector, 13000' TD)
- **MONTARE OPERATING, LTD.** — UNIVERSITY 13-45 (Andrews, 11370' TD)
- **PIONEER NATURAL RES. USA, INC.** — BROOKS-CRESPI 30M (Midland, 10424' TD)
- **PIONEER NATURAL RES. USA, INC.** — NEAL 9C (Upton, 10381' TD)
- **PIONEER NATURAL RES. USA, INC.** — SHAUNA-WINDHAM 42I (Upton, 10931' TD)
- **PIONEER NATURAL RES. USA, INC.** — SHAUNA-WINDHAM 42J (Midland, 10931' TD)
- **PIONEER NATURAL RES. USA, INC.** — TURNER EC42C (Midland, 10326' TD)
- **PIONEER NATURAL RES. USA, INC.** — TURNER EC42DD (Midland, 10326' TD)

### DOXA / Sabine — East Texas
- **TGNR EAST TEXAS II LLC** — G11A WINSTON AN (Panola, 22000' TD)
- **TGNR EAST TEXAS II LLC** — G11A WINSTON BN (Panola, 22000' TD)
- **TGNR EAST TEXAS II LLC** — G11A WINSTON CN (Panola, 22000' TD)
- **TGNR EAST TEXAS II LLC** — G11A WINSTON DN (Panola, 22000' TD)
- **TGNR EAST TEXAS II LLC** — G11A WINSTON EN (Panola, 22000' TD)

### West Haynesville watch
- **HILCORP ENERGY COMPANY** — BUCHANAN SWD (Robertson, 13278' TD)

## Watched-family activity outside corridors
- Adamas (ex-Aethon, Mitsubishi): ADAMAS ENERGY LLC — San Augustine: 2 wells (1H, 2HB)
- EOG Resources: EOG RESOURCES, INC. — Webb

## All new permits by county

### Andrews (1)
- MONTARE OPERATING, LTD. — UNIVERSITY 13-45 (16)

### Angelina (1)
- CATURUS ENERGY, LLC — STURGEON (1HB)

### Baylor (2)
- WAGGONER OPERATING, L.L.C. — WAGGONER DNTK (247DN)
- WAGGONER OPERATING, L.L.C. — WAGGONER DNTK (248DN)

### Borden (1)
- SURGE OPERATING, LLC — CHIMERA UNIT B 07-18 (4NH)

### Deaf Smith (1)
- NORTH TEXAS CARBON, LLC — BRAVO (4)

### Dimmit (3)
- EL TORO RESOURCES LLC — YETT RANCH (8231H)
- EL TORO RESOURCES LLC — YETT RANCH (8232H)
- EL TORO RESOURCES LLC — YETT RANCH (8233H)

### Ector (2)
- DIAMONDBACK E&P LLC — SHERIFF 2-38 C (3BN)
- DIAMONDBACK E&P LLC — SHERIFF 2-38 D (4BN)

### Harris (1)
- RISE PETROLEUM INVESTMENTS LLC — JC STRIBLING (2)

### Hemphill (1)
- FX ENERGY OPERATING, LLC — YOUNG -2- (1)

### Howard (1)
- SM ENERGY COMPANY — WACO KID MARION RAVENWOOD A (0781WD)

### Jim Wells (1)
- PALADIN PETROLEUM III, L.L.C. — RUSSELL (8)

### La Salle (4)
- SILVER HILL ENERGY OPERATING LLC — FLORES (3H)
- SILVER HILL ENERGY OPERATING LLC — FLORES (4H)
- SILVER HILL ENERGY OPERATING LLC — FLORES (5H)
- SILVER HILL ENERGY OPERATING LLC — FLORES (6H)

### Loving (1)
- WATERBRIDGE STATELINE LLC — FPW SWD (4)

### Maverick (12)
- DIAMONDBACK E&P LLC — STANTON 28-16 C (4WA)
- DIAMONDBACK E&P LLC — STANTON 28-16 D (4LS)
- DIAMONDBACK E&P LLC — STANTON 28-16 D (4WB)
- DIAMONDBACK E&P LLC — STANTON 28-16 E (2LS)
- DIAMONDBACK E&P LLC — STANTON 28-16 E (2WB)
- DIAMONDBACK E&P LLC — STANTON 28-16 G (1LS)
- DIAMONDBACK E&P LLC — STANTON 28-16 G (1WB)
- DIAMONDBACK E&P LLC — STANTON 28-16 H (3WA)
- DIAMONDBACK E&P LLC — STANTON 28-16 I (2JM)
- DIAMONDBACK E&P LLC — STANTON 28-16 I (2WA)
- DIAMONDBACK E&P LLC — STANTON 28-16 J (3LS)
- DIAMONDBACK E&P LLC — STANTON 28-16 J (3WB)

### Midland (14)
- DIAMONDBACK E&P LLC — RIVERCREST 2-11 A (1JM)
- DIAMONDBACK E&P LLC — RIVERCREST 2-11 A (1WA)
- DIAMONDBACK E&P LLC — RIVERCREST 2-11 B (1LS)
- DIAMONDBACK E&P LLC — RIVERCREST 2-11 B (1WD)
- DIAMONDBACK E&P LLC — RIVERCREST 2-11 C (2WD)
- DIAMONDBACK E&P LLC — RIVERCREST 2-11 E (3JM)
- DIAMONDBACK E&P LLC — RIVERCREST 2-11 E (3WA)
- DIAMONDBACK E&P LLC — RIVERCREST 2-11 F (3LS)
- DIAMONDBACK E&P LLC — RIVERCREST 2-11 F (3WB)
- DIAMONDBACK E&P LLC — RIVERCREST 2-11 G (2JM)
- PIONEER NATURAL RES. USA, INC. — BROOKS-CRESPI 30M (13H)
- PIONEER NATURAL RES. USA, INC. — SHAUNA-WINDHAM 42J (210H)
- PIONEER NATURAL RES. USA, INC. — TURNER EC42C (103H)
- PIONEER NATURAL RES. USA, INC. — TURNER EC42DD (104H)

### Panola (5)
- TGNR EAST TEXAS II LLC — G11A WINSTON AN (1HH)
- TGNR EAST TEXAS II LLC — G11A WINSTON BN (2HH)
- TGNR EAST TEXAS II LLC — G11A WINSTON CN (3HH)
- TGNR EAST TEXAS II LLC — G11A WINSTON DN (4HH)
- TGNR EAST TEXAS II LLC — G11A WINSTON EN (5HH)

### Reagan (13)
- DE CENTRAL OPERATING, LLC — SIDEWINDER EAST I 12-8 (4209H)
- DE CENTRAL OPERATING, LLC — SIDEWINDER EAST I 12-8 (4409H)
- DE CENTRAL OPERATING, LLC — SIDEWINDER EAST K 12-8 (4311H)
- DE CENTRAL OPERATING, LLC — SIDEWINDER EAST M 12-8 (4213H)
- DE CENTRAL OPERATING, LLC — SIDEWINDER EAST M 12-8 (4413H)
- DE CENTRAL OPERATING, LLC — SIDEWINDER EAST O 12-8 (4315H)
- DE CENTRAL OPERATING, LLC — SIDEWINDER WEST A 12-8 (4201H)
- DE CENTRAL OPERATING, LLC — SIDEWINDER WEST A 12-8 (4401H)
- DE CENTRAL OPERATING, LLC — SIDEWINDER WEST C 12-8 (4303H)
- DE CENTRAL OPERATING, LLC — SIDEWINDER WEST E 12-8 (4205H)
- DE CENTRAL OPERATING, LLC — SIDEWINDER WEST E 12-8 (4405H)
- DE CENTRAL OPERATING, LLC — SIDEWINDER WEST G 12-8 (4307H)
- DISCOVERY NATURAL RESOURCES LLC — BULLHEAD (0472DC)

### Reeves (1)
- BPX OPERATING COMPANY — STATE CARSON 57-T3-8X20 A (W101H)

### Roberts (1)
- SUMMIT PETROLEUM LLC — MAYO CLINIC (4133H)

### Robertson (1)
- HILCORP ENERGY COMPANY — BUCHANAN SWD (2)

### San Augustine (2)
- ADAMAS ENERGY LLC — LEON VALLEY EAST (1H)
- ADAMAS ENERGY LLC — LEON VALLEY EAST (2HB)

### Scurry (2)
- OCCIDENTAL PERMIAN LTD. — FULLER (6018)
- OCCIDENTAL PERMIAN LTD. — FULLER (6053)

### Upton (2)
- PIONEER NATURAL RES. USA, INC. — NEAL 9C (103H)
- PIONEER NATURAL RES. USA, INC. — SHAUNA-WINDHAM 42I (209H)

### Van Zandt (1)
- BASA RESOURCES, INC. — CENTRAL VAN WOODBINE UNIT (437)

### Ward (2)
- PITTS ENERGY CO. — C. W. EDWARDS ET AL (8)
- PITTS ENERGY CO. — EDWARDS, C. W. ET AL (9)

### Webb (1)
- EOG RESOURCES, INC. — CODIGO (23H)

## Amendments
- WBI ENERGY MIDSTREAM, LLC — HF SINCLAIR (Baylor)
- HIGHPEAK ENERGY HOLDINGS, LLC — THE PEAKS 29-17 B UNIT (Howard)
- SM ENERGY COMPANY — WACO KID MARION RAVENWOOD AA (Howard)
- PERMIAN DEEP ROCK OIL CO., LLC — BULLDOG B (Midland)

---
_New-entrant check: any operator above with no prior record in master is flagged NEW OPERATOR in new_permits.csv (col: first_seen)._

## Resurfaced older files (issue date >7d old, new to master)
- COTERRA ENERGY OPERATING CO. — NEEDLES 39 UNIT 14H (Culberson), issued 2025-01-16
- COTERRA ENERGY OPERATING CO. — NEEDLES 39 UNIT 16H (Culberson), issued 2025-01-16
- COTERRA ENERGY OPERATING CO. — VAGRANT 38 FEE UNIT 12H (Culberson), issued 2024-12-10
- COTERRA ENERGY OPERATING CO. — VAGRANT 38 FEE UNIT 13H (Culberson), issued 2024-12-10
- COTERRA ENERGY OPERATING CO. — VAGRANT 38 FEE UNIT 14H (Culberson), issued 2024-12-10
- COTERRA ENERGY OPERATING CO. — VAGRANT 38 FEE UNIT 15H (Culberson), issued 2024-12-10
- VERDUN OIL & GAS LLC — TROMMELFEUER UNIT 1H (Dimmit), issued 2025-06-17
- MARATHON OIL EF LLC — BARNHART (EF) 98H (Gonzales), issued 2024-04-25
- SILVER HILL ENERGY OPERATING LLC — USA LARK 2DH (Live Oak), issued 2025-08-22
- APACHE CORPORATION — BOB 2HM (Midland), issued 2026-06-25
- COTERRA ENERGY OPERATING CO. — TELLURIDE STATE 29-32 UNIT H 8H (Reeves), issued 2025-02-24
- COTERRA ENERGY OPERATING CO. — TELLURIDE STATE 29-32 UNIT I 9H (Reeves), issued 2025-02-24
- COTERRA ENERGY OPERATING CO. — TELLURIDE STATE 29-32 UNIT J 10H (Reeves), issued 2025-02-24
- GREENLAKE ENERGY OPERATING, LLC — MIKE JONES 4102H (Reeves), issued 2025-07-15
- APACHE CORPORATION — CC 4243 E 10HU (Upton), issued 2026-03-26
- APACHE CORPORATION — CC 4243 F 9HS (Upton), issued 2026-03-27

## Month-to-date (August 2026) — 263 permits issued

**By county (top 12):**
- Reagan: 28
- Reeves: 20
- Midland: 19
- Maverick: 18
- Upton: 17
- Webb: 12
- Andrews: 9
- Ector: 9
- Wilbarger: 7
- Yoakum: 7
- Crane: 6
- Taylor: 6

**By operator (top 12):**
- DIAMONDBACK E&P LLC: 31
- PIONEER NATURAL RES. USA, INC.: 27
- DE CENTRAL OPERATING, LLC: 13
- BURLINGTON RESOURCES O & G CO LP: 9
- CONTINENTAL RESOURCES, INC.: 8
- BPX OPERATING COMPANY: 8
- SM ENERGY COMPANY: 7
- PERMIAN RESOURCES OPERATING, LLC: 6
- L.C.S. PRODUCTION COMPANY: 6
- BURK ROYALTY CO., LTD.: 6
- OVINTIV USA INC.: 5
- CATURUS ENERGY, LLC: 5

**Watched families MTD:**
- EOG Resources: 4
- Adamas (ex-Aethon, Mitsubishi): 2
- Apex (ex-Paloma, Citadel): 1

**Hot cycles (spud <=14 days after issue):**
- WBI ENERGY MIDSTREAM, LLC — HF SINCLAIR T006MP (Baylor): issued 08/05, spud 08/10 (5d)
- L.C.S. PRODUCTION COMPANY — KISSELL UNIT 29 (Taylor): issued 08/04, spud 08/07 (3d)


## Confirmed New Permits -- Louisiana SONRIS

_Source: 2026-08-13_

# Louisiana SONRIS Permit Intel — Thu Aug 13 2026

**1 new** | **0 amended** vs master.


## All new permits by parish

### Beauregard (1)
- FONTAINEBLEAU OPERATING, LLC — COLUMBIA LAND 27 (002)
  _API 17011213080000  Sec 027-06S-13W  Field: BANCROFT, SOUTH  
  Well profile: https://sonlite.dnr.state.la.us/ords/apex/r/sonris_pub/sonris_data_portal/well-profile?clear=CR,9000&ig[ig_master]_well_serial_num=255803  
  Well docs (check back -- often not posted yet at permit time): https://sonlite.dnr.state.la.us/ords/r/sonris/ucmsearch/finddocuments?qtype=eq&idx=xwellserialnumber&val=255803_

---
_New-entrant check: any operator above with no prior record in master is flagged NEW OPERATOR in new_permits.csv (col: first_seen)._


## Early Signal -- W-1 Plats (1-2 days ahead of RRC approval)

_Source: 20260812_

# W-1 Early Intel — 20260812

13 plat(s) found across 4 permits.

## Fisher-Duncan_1B_PLAT_20260730_final  (Permit #905153)
- **Status:** **NOT yet in master.csv — early signal**
- **Operator/county:** CRATON OPERATING LLC (GREGG)  _[source: OCR/fallback merged from multiple plat documents]_
- **Client match:** none found

## MAGNOLIA_MAC ARTHUR TWO H 02_PERMIT PLAT_FINAL (08-05-26)  (Permit #917730)
- **Status:** **NOT yet in master.csv — early signal**
- **Operator/county:** OPERATING LLC (WASHINGTON)  _[source: OCR/fallback merged from multiple plat documents]_
- **Client match:** none found

## MAGNOLIA_MAC ARTHUR H 06_PERMIT PLAT_FINAL (08-06-26)  (Permit #917731)
- **Status:** **NOT yet in master.csv — early signal**
- **Operator/county:** OPERATING LLC (WASHINGTON)  _[source: OCR/fallback merged from multiple plat documents]_
- **Client match:** none found

## MAGNOLIA_TRUMAN SEVEN H 07 TM_PERMIT PLAT_FINAL (08-06-26)  (Permit #917733)
- **Status:** **NOT yet in master.csv — early signal**
- **Operator/county:** OPERATING LLC (WASHINGTON)  _[source: OCR/fallback merged from multiple plat documents]_
- **Client match:** none found

