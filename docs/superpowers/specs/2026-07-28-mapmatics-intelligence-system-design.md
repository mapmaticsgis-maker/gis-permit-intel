# Mapmatics Intelligence System — Design

**Date:** 2026-07-28
**Status:** Approved for planning
**Supersedes:** ad-hoc daily digest in `run_daily.py` / `digest.py`

## Problem

The permit pipeline runs but produces nothing. Every daily `new_permits.csv` on record —
TX for 07-19, 07-20, 07-21, 07-26, 07-27, 07-28 and LA for 07-19, 07-20, 07-21, 07-27,
07-28 — contains a header row and no data, while the same TX digest reports 550 permits
issued month-to-date. Fetch, parse, master accumulation, MTD rollup, scheduling and email
delivery all work. The diff does not, and it has failed silently for at least ten days.

Separately, the pipeline produces counts, not intelligence. It cannot say which permits
matter, because nothing in the RRC or SONRIS feed knows where Mapmatics has work.

## Goal

A single ranked morning brief that tells Jason what changed overnight that affects his
clients, combining permit movement with job state, delivered before the workday starts.

Three organs, one loop:

1. **Sensor** — daily TX RRC + LA SONRIS permit capture and change detection
2. **Analyst** — client job state and opportunity signals from labeled email
3. **Repertoire** — the mechanism by which GIS knowledge accretes into the system

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Ranking driver | Client / job proximity | Chosen by user over operator-anomaly, corridor momentum, BD targets |
| Architecture | Deterministic core, Claude at the edge | Numbers stay auditable; judgment stays capable |
| Client registry | Existing workbook, read-only | User explicitly rejected maintaining a new config shape |
| Open Items updates | Proposed in brief, never written back | User keeps ownership of the CRM |
| Brief structure | Client-keyed | Both ranking driver and email content key on client |

## Architecture

```
DETERMINISTIC (Python — no LLM, fully testable)
  fetch → parse → diff → update master → spatial join
                                             ↓
                              data/evidence/<date>.json      ← the seam
                                             ↓
              ┌──────────────────────────────┴───────────────┐
              ↓                                              ↓
  JUDGMENT (Claude)                              FALLBACK (Python)
  evidence pack + workbook snapshot              renders pack as plain
  + labeled Gmail → ranked brief                 brief if Claude step fails
              └──────────────────────────────┬───────────────┘
                                             ↓
                                  morning brief → inbox
                              CSV / GeoJSON → Zach's dashboard
```

The **evidence pack** is the contract between halves. Deterministic side writes facts
only, no prose. Claude side reads it and composes. The seam is what makes the system
testable without an LLM and degradable when the LLM step fails.

Governing rule: **anything that might be shown to a client is computed deterministically;
anything that is a judgment call is Claude's.**

### Repo layout

```
permit_intel/
  config.yaml                 # sources, corridors  (operator_families block REMOVED)
  core/
    sources/                  # tx_daf420.py, la_pull.py  (existing, relocated)
    diff.py                   # NEW — change detection as a pure function
    spatial.py                # NEW — permit → client AOI distance
    registry.py               # NEW — reads the client workbook snapshot
    evidence.py               # NEW — assembles the evidence pack
    invariants.py             # NEW — silent-failure alarms
  brief/
    fallback.py               # NEW — evidence pack → plain brief, no LLM
  repertoire/
    INBOX.md  ACTIVE.md  REJECTED.md
  .claude/skills/
    compose-morning-brief/
  data/
    <state>/master.csv
    <state>/out/<date>/       # existing dashboard contract — unchanged
    evidence/<date>.json
    registry/Mapmatics_Client_Master_v2.xlsx    # snapshot, committed
```

## Component 1 — The sensor

### Change detection

Extracted from the pull scripts into a pure function:

```
diff(today_records, master, key) → {new, amended, resurfaced}
```

No file I/O, no side effects, no master mutation. The caller updates master *after*
consuming the result. This structurally prevents the current failure, in which master
absorbs the day's records before comparison so nothing is ever new.

**The diff key is the business key, never `OBJECTID`.** TX keys on `STATUS_NUMBER`, LA on
`WELL_SERIAL_NUM`. The LA master currently carries both `OBJECTID` and `id`; SONRIS
assigns `OBJECTID` server-side and it can shift between queries, which is a likely
contributor to the duplicate accumulation patched in `4ee4a75`. Key uniqueness and
non-nullity are asserted before the diff runs.

### Backfill

No signal is lost. `data/tx/inbox/` retains 29 daily `daf420.dat` files back to
2026-07-01, so TX replays completely: rebuild master from empty, walk files in date
order, regenerate every missed day. LA retains no raw files but SONRIS is queryable by
`PERMIT_DATE`, so LA rebuilds from source.

The replay doubles as the acceptance test: replaying July 2026 must yield a new-permit
count equal to the MTD total the digest independently computes for the same period (550
as of 07-28), reconciled exactly rather than approximately. The current implementation
yields zero.

### Spatial join

TX `daf420` carries both surface (`Surface_Lat/Lon`) and bottomhole (`BHL_Lat/Lon`)
coordinates. Distance is computed to the **wellbore segment** (SHL→BHL), not the surface
point — a Haynesville or Permian lateral can bottom two miles from where it surfaces,
and surface-only proximity is wrong in exactly the cases that matter most.

The LA SONRIS service (`DNRSvc/OC/MapServer/0`) is surface-only with no BHL or line
geometry. LA degrades to surface-point distance, and the brief states this rather than
implying precision it does not have.

Distances computed in **EPSG:5070 (NAD83 / CONUS Albers)** — covers TX and LA in one CRS
with negligible distortion at miles-scale, avoiding per-zone UTM bookkeeping.

## Component 2 — The client registry

Source of truth: `C:\Users\mapma\Desktop\ADMIN\Mapmatics_Client_Master_v2.xlsx`
(22 clients, 5 sheets). **Read-only.** No new config shape is introduced.

Each run copies the workbook into `data/registry/` and reads the copy. Excel holds a lock
while the file is open; the run must not fail because the workbook was left open. On copy
failure the last good snapshot is used and the brief says so in its header. The snapshot
is committed, giving the CRM version history as a side effect.

Sheets consumed:

- **Client Master** — `Status` filters the brief to Active clients; `Gmail Label` is the
  join key to email; `Jobs / Prospect Names` seeds geometry resolution.
- **Label Key** — Gmail label → client, and equally important, which labels are Personal
  (`Xbox/MS/EA`) or Internal. The privacy boundary comes from the user's own file.
- **Open Items** — the job-status model. Not re-modelled elsewhere.
- **Corporate Intel & Notes** — canonical operator genealogy.
- **Contacts Directory** — contact attribution for threads.

### Operator genealogy consolidation

`config.yaml`'s `operator_families` block duplicates the Corporate Intel tab (Adamas /
Aethon / Mitsubishi, Apex / Paloma / Citadel, Expand / CHK+SWN / Indigo, Diversified /
Oaktree). Two sources of truth will drift. The workbook becomes canonical — it carries
the narrative and the *why* — and the `operator_families` block is removed from
`config.yaml`, with the pipeline reading families from the workbook.

### Job-name → geometry resolution

The workbook names jobs (Flatland, Turnpike, Lee Co, Paxton, Shelby North) but holds no
coordinates. Those names map onto folders under `C:\GIS\CLIENT\<CLIENT>\` — e.g.
`CLIENT/DLS/FLATLAND_NORTH`, `CLIENT/DLS/TURNPIKE_2025.gdb`, `CLIENT/DOXA/DESOTO_IPL`.

A resolver proposes matches by scanning client folders; the user confirms the list once
and it is cached in the repo. This is the **only** new artifact requiring user
maintenance, and it is a one-time confirmation rather than an ongoing shape. Clients with
no resolved geometry fall back to county-level matching, flagged as coarse in the brief.

Per-client proximity radius is required because a Permian client and a Haynesville client
do not care at the same range. Default 5 miles, stored alongside the resolved geometry.

## Component 3 — The email analyst

Scoped entirely by the `Label Key` sheet. For each Active client, read that client's
labeled threads over a rolling 14-day window and produce:

1. **Job status delta** — what moved, who owes whom, what has gone quiet
2. **Opportunity signals** — business-shaped threads with no client label (how Dorada
   entered), plus existing clients mentioning new areas or projects

Labels marked Personal are never read. Labels marked Internal are read only for
admin-relevant signals (invoices, 1099s), not summarized as client work.

Explicitly out of scope: inbox triage / "threads needing a response." The user wants
intelligence, not task management.

## Component 4 — The brief

Client-keyed, ranked, single document, delivered to the user's inbox each morning.

```
Mapmatics Morning Brief — <date>

NEEDS YOU TODAY          overdue open items, time-sensitive commitments
BY CLIENT (active)       job status + permits near AOI, one block per client
OPPORTUNITY SIGNALS      unlabeled business threads, new-area mentions
SUGGESTED OPEN ITEMS     proposed edits for the user to apply by hand
CORRIDOR ROLLUP          MTD counts and corridor stats (existing digest content)
```

Client sort order: permits landed near AOI, then overdue open items, then recency.
Dormant clients are excluded, except in a monthly reactivation note (the workbook already
flags Brookston as a good A&D-news target).

## Error handling — the actual failure mode

The system did not crash. It produced confident, empty output for ten days. Error
handling is therefore about detecting *plausible* wrongness, not exceptions.

**Invariants that alarm:**

- Zero new permits across both states for 2 consecutive days (would have fired 2026-07-20)
- Master row count flat across a rolling week
- Expected `daf420` file absent for the run date
- Any record with a null or duplicate business key — alert, never silently drop
- Workbook snapshot older than 7 days

**The provably-empty rule.** An empty brief must state the evidence for its emptiness —
"0 new permits, verified against N master records and today's daf420" — or state that it
could not verify. There is no third case in which silence is rendered as success.

Existing `self_check.py` is extended rather than replaced.

## Testing

In priority order:

1. **`diff()` against the July replay.** Must reproduce ~550 TX permits across July 2026.
   This is the acceptance test for the entire fix.
2. **Spatial join** against hand-verified distances on a known DLS tract, including a
   horizontal well where SHL and BHL differ materially.
3. **Evidence pack schema** — contract test at the seam, since both halves depend on it.
4. **Fallback renderer** — must produce a readable brief from a pack with no LLM involved.
5. **Registry reader** — tolerates a locked workbook, missing sheets, renamed columns.

## Component 5 — The repertoire

The mechanism by which GIS knowledge from outside sources enters the system.

```
repertoire/
  INBOX.md      ← unstructured drop point. links, tools, techniques, half-thoughts.
  ACTIVE.md     ← adopted, with where it was wired in
  REJECTED.md   ← evaluated and declined, with the reason
```

Zero friction in, structure on the way out. Every `INBOX.md` entry is triaged into exactly
one of four outcomes: wired into the pipeline (commit noted in `ACTIVE.md`), graduated to
a `.claude/skills/` entry, saved as a reference memory, or declined with a written reason.

**Nothing remains in INBOX.** Triage runs at the start of any session where the inbox is
non-empty. `REJECTED.md` prevents re-evaluating the same tool in six months.

### The feedback loop

The expertise layer is a `compose-morning-brief` skill plus memory. When the user corrects
a brief — "that Adamas permit was the only thing that mattered" — the correction becomes a
memory that changes subsequent ranking. User corrections are the training signal, and they
persist across sessions. This is the same mechanism that captured the RROG principal
correction (John Bowman sole principal; Brad Ryan contractor, not principal).

## Implementation phasing

This spec covers five components and is too large for a single implementation plan. It
decomposes into four phases, each independently valuable and separately plannable:

1. **Fix the sensor.** `diff.py` as a pure function, business-key assertions, July replay
   and backfill, invariants and alarms. Delivers real daily signal and stops the bleeding.
   Everything else depends on this.
2. **Registry + spatial.** Workbook snapshot reader, job-name → geometry resolution, the
   spatial join, evidence pack. Delivers proximity-ranked permits with no email involved.
3. **Analyst + brief.** Email layer, `compose-morning-brief` skill, fallback renderer,
   delivery. Delivers the brief as specified.
4. **Repertoire.** Inbox, triage workflow, feedback loop into memory.

Phase 1 is the only one that is urgent; each subsequent phase is additive.

## Assumptions to confirm

- **Client-keyed brief structure** was inferred, not explicitly chosen — both the ranking
  driver and the email content key on client, so it follows, but the user did not select
  it directly when offered.
- **Delivery at 08:00 CST by email**, reusing existing `send_email.py` and Task Scheduler.
- **Rolling email window** of 14 days for job-status derivation.

## Deferred, deliberately

Designed so these slot in without rework:

- **Operator-anomaly ranking** as a secondary brief section. Proximity is a rearview
  mirror — it surfaces places work already exists and will never surface a corridor
  Mapmatics is not yet in, which is where being first with a correct call is made.
- **Corridor momentum** (rate-of-change over a rolling window) and **BD target watchlist**.
- **Publishable weekly corridor note** — the reputation artifact, building on the existing
  `weekly_intelligence.py`. The current system terminates at a CSV; distinction requires it
  to terminate at something publishable on a cadence.

## Out of scope

- Rebuilding Zach's dashboard. The `data/<state>/out/<date>/` contract is unchanged and
  treated as a first-class output.
- Any write to the client workbook.
- Inbox triage or task management.
