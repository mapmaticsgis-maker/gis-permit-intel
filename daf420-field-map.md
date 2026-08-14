# daf420 field map — what the file carries that we aren't reading

Source: RRC publication **OGA049M**, *Drilling Permit Master Plus Latitudes and Longitudes, Magnetic Tape User's Guide* (First Edition July 14, 2004).
https://www.rrc.texas.gov/media/zgccdjpi/drillingpermitmasterpluslatitudeslongitudes_oga049m_july1.pdf

## Offset calibration — read this before adding any field

The guide's byte positions are 1-indexed. Two different conversions apply depending on record type:

| Record | Conversion to Python slice start | Basis |
|---|---|---|
| **01** (DAROOT) | `pos - 1` | Matches the existing parser exactly |
| **02** (DAPERMIT) | `pos - 3` | Existing parser sits 2 bytes earlier than documented |

The record-02 discrepancy comes from the guide printing a doubled 2-byte record-ID header for that segment that the real file does not contain. The current parser's offsets are validated against 83 snapshots of real output, so they are the ground truth — the documented positions are what needs adjusting, not the code.

Verify each conversion against a real `.dat` before trusting it. Every offset marked **UNVERIFIED** below is derived from the guide, not observed.

## Record segments present in the file

| ID | Segment | Contents | Currently read |
|---|---|---|---|
| 01 | DAROOT | Application status, county, lease, operator, received date | Partial |
| 02 | DAPERMIT | Permit master — dates, depth, well type, location, API | Partial |
| 03 | DAFIELD | Target field(s), well purpose, completion | No |
| 04 | DAFLDSPC | Per-field district/depth/lease/acres | No |
| 05 | DAFLDBHL | Per-field bottom-hole survey description | No |
| 06–09 | Restrictions | Canned and free-form permit restrictions | No |
| 10 | DAPMTBHL | Permit bottom-hole survey description | No |
| 11 | DAALTADD | Alternate address | No |
| 12 | DAREMARK | Permit remarks | No |
| 13 | DACHECK | Check register | No |
| 14 | DAW999A1 | GIS surface coordinates | Yes |
| 15 | DAW999B1 | GIS bottom-hole coordinates | Yes |

---

## Tier 1 — add these; they change what the brief can say

### Application status flag — record 01, position 101 → `line[100:101]` **UNVERIFIED**

`P` pending · `A` approved · `W` withdrawn · `D` dismissed · `E` denied · `C` closed · `O` other · `X` deleted · `Z` cancelled

**Why it matters most:** the brief currently sees only issued permits. This flag exposes *pending applications* — activity that has been filed but not yet approved. That is a genuine leading indicator, visible days or weeks before issuance. It also surfaces withdrawals and denials, which are currently invisible; an operator pulling applications is a signal we have no way to detect today.

### Type of application — record 02, position 68 → `line[65:67]` **UNVERIFIED**

`01` drill · `05` other · `07` re-enter · `09` field transfer · `14` recompletion · `15` reclass
(pre-1995 files also use 02–04, 06, 08, 10–13)

Replaces the current heuristic of inferring re-entries from a spud date preceding the issue date. That heuristic catches only re-entries where an old spud is carried forward; this field is definitive and also separates recompletions and field transfers from genuine new drills. Permit counts should arguably exclude `14` and `15` entirely.

### Permit expired date — record 02, position 181 → `line[178:186]` **UNVERIFIED**

Directly answers the permit-life question raised on the Firebird Julie 2535 block — eight permits filed February 2025 and still undrilled. Rather than inferring expiry risk from age, the file states the date.

### Well status + status date — record 02, positions 172 and 173 → `line[169:170]`, `line[170:178]` **UNVERIFIED**

`W` final completion · `D` dry hole · `A` long-string casing · `N` intermediate casing · `T` cathodic protection · plus ~20 more (guide Appendix B).

This is the missing half of the lifecycle. The master currently tracks permit → spud and stops. Well status carries the well through to completion or dry hole, which is what actually determines whether an operator's inventory converted.

### Horizontal / directional / sidetrack flags — record 02, positions 496, 484, 485 → `line[493:494]`, `line[481:482]`, `line[482:483]` **UNVERIFIED**

The brief currently infers horizontals from an `H` in the well number, which is a naming convention, not data. These are explicit.

### API number — record 02, position 505 → `line[502:510]` **UNVERIFIED**

The join key to every other RRC dataset — production, completions, well status. Without it the permit master is a closed island. With it the brief could eventually report actual production outcomes on wells it tracked from permit.

---

## Tier 2 — directly useful for the land and title work

### Surface legal description — record 02 **UNVERIFIED**

Only populated when the location-format flag at position 245 (`line[242:243]`) is `N`:

| Field | Position | Slice |
|---|---|---|
| Section | 246 | `line[243:251]` |
| Block | 254 | `line[251:261]` |
| Survey | 264 | `line[261:316]` |
| Abstract | 319 | `line[316:322]` |

Abstract and survey are the identifiers a landman actually works from. Having them in the master means corridor activity can be reported by survey and abstract rather than only by coordinate — considerably more useful to Daniels than a lat/long.

### Bottom-hole legal description — record 10 (DAPMTBHL) **UNVERIFIED**

Section, block, abstract, survey, acres, and perpendicular distances to the two nearest lease and survey lines. Same value as above, for the bottom hole.

### Surface acres and nearest city — record 02, positions 328 and 348 **UNVERIFIED**

Acreage assigned to the lease, plus nearest town with distance and direction. Acreage would let the brief report acres permitted rather than well counts, which is a better measure of commitment.

### Amended and extended dates — record 02, positions 140 and 148 **UNVERIFIED**

Explicit amendment and extension dates. The brief currently detects amendments by watching `Received_Date` change between snapshots — workable but indirect, and it misses amendments that land between pulls.

### Amendment sequence number — record 01, position 10 → `line[9:11]` **UNVERIFIED**

`99` is the original filing; each amendment decrements (98, 97, 96…). Gives amendment *depth* directly. A permit at 95 has been amended four times — usually a sign of a contested or repeatedly revised location.

### Well purpose — record 03, position 11 **UNVERIFIED, and record 03 offsets are not calibrated**

`O` oil · `G` gas · `B` both · `I` injection · `D` saltwater disposal · `S` service · `V` water supply · `T` exploratory · `C` cathodic protection

Would cleanly separate SWDs and injection wells from producers. The brief currently mixes them, which inflates counts in water-heavy counties like Loving and Reeves.

Record 03 offsets have not been checked against the file. Record 01 needed no adjustment and record 02 needed −2; record 03 may need its own. Verify before use.

### Rule 37 case number — record 02, position 231 → `line[228:235]` **UNVERIFIED**

A Rule 37 exception means a spacing hearing — the well is closer to a lease line than standard spacing allows. That is a title-relevant flag and often correlates with contested acreage.

---

## Tier 3 — situational

- **Field number** (record 03, position 3). Eight digits; first five identify the field, last three the reservoir. Needs an RRC field-name lookup table to be readable.
- **Permit restrictions** (records 06–09). Canned restriction codes plus free-form text. Occasionally contains the actual reason a permit was conditioned.
- **Cancellation reason** (record 02, position 197, 30 chars free-form).
- **Problem flags** (record 01, positions 102–112): money, P-5, P-12, plat, W-1A, Rule 37/38/39. Mostly RRC-internal workflow noise.
- **Nearest well distance and direction** (record 02, position 445).
- **Zip code** (record 02, position 106) — operator location, marginal.

---

## Suggested verification procedure

Run the parser with `--verify` against one real `.dat`, which prints the raw slice and parsed value for each new field on the first several records. Check that:

1. Application-status values fall in the documented code set, not random characters.
2. Type-of-application values are mostly `01`, with a scattering of `07`, `14`, `15`.
3. Dates parse as plausible dates rather than zeros or garbage.
4. The horizontal flag is `Y` on wells whose number ends in `H`, and `N` on those that do not — a self-check against the existing convention.
5. API numbers are 8 digits beginning with the county code.

If a field comes back as garbage, the offset is wrong by a fixed amount — shift and retry rather than abandoning the field.
