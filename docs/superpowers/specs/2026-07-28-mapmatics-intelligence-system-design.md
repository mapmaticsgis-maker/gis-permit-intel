# Mapmatics Intelligence System — Design

**Date:** 2026-07-28
**Status:** Approved for planning
**Supersedes:** ad-hoc daily digest in `run_daily.py` / `digest.py`

## Problem

The permit pipeline runs but produces nothing. Every daily `new_permits.csv` on record —
TX for 07-19, 07-20, 07-21, 07-26, 07-27, 07-28 and LA for 07-19, 07-20, 07-21, 07-27,
07-28 — contains a header row and no data, while the same TX digest reports 550 permits
issued month-to-date.

**Diagnosed 2026-07-28. The diff logic is correct and has been working.** An initial
hypothesis that master absorbed the day's records before comparison was investigated and
disproved: both `tx_daf420.py:267-268` and `la_pull.py:88-89` diff before updating master.
Two distinct bugs are responsible.

### Bug 1 — same-day re-runs overwrite the day's results with empties

Proven by consecutive commits on 2026-07-26:

```
c29c268b   data/tx/out/2026-07-26/new_permits.csv = 62 rows   master = 693
479da72d   data/tx/out/2026-07-26/new_permits.csv =  0 rows   master = 693
```

Run 1 correctly detected 62 new permits and updated master. A later run the same day
diffed against the updated master, correctly found zero, and wrote an empty
`new_permits.csv` over the good one. Outputs are keyed on `date.today()` and replaced
wholesale on every run.

The pipeline has three redundant triggers — Windows Task Scheduler, a GitHub Actions
workflow, and a local API trigger (`trigger_github_workflow.py`) — producing three "Daily
permit intel run" commits on 07-26 and three more on 07-27. The intelligence was computed
and then deleted, daily, by the pipeline's own redundancy.

The 62 permits from 07-26 are recoverable from git history.

### Bug 2 — the TX source has been frozen since 2026-07-26

`01` (permit header) record counts across the July inbox files:

```
07-03:  59   07-19: 502   07-24: 637
07-12: 348   07-21: 502   07-25: 669
07-16: 415   07-22: 567   07-26: 706
07-18: 478   07-23: 602   07-27: 706   ← byte-identical to 07-26
                          07-28: 706   ← only 14/15 coord records changed
```

The daf420 extract is month-to-date cumulative and resets at month start (59 permits on
07-03, climbing to 706 by 07-26). It then stopped advancing. Only coordinate records are
still changing, and issue dates stop at 2026-07-24 in a file dated 07-28. Either the MFT
link in `texas.fetch_url` no longer refreshes, or the downloader is being served a cached
copy.

Note that the flat stretches at 07-19/07-20 (502, 502) and 07-13/07-14 (348, 348) show the
source has legitimately-flat days, so freshness detection must tolerate short plateaus
without tolerating indefinite ones.

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

The pack is also the eventual dashboard's data source (see *Future surface*), so it stays
**presentation-neutral**: no brief-specific shaping, ordering, or phrasing leaks into it.
Anything the brief states must be *derivable from the pack*, never computed only during
composition — otherwise a second surface cannot reproduce it.

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

The existing diff logic is correct and is retained. It is consolidated out of
`tx_daf420.py:diff_master` and `common.py:diff` into one tested `core/diff.py` — not
because it is broken, but because two near-duplicate implementations with different
change-column sets and different resurfaced-handling is a latent divergence:

```
diff(today_records, master, key, change_cols) → {new, amended, resurfaced}
```

### Ingestion ledger — the fix for Bug 1

The real defect is that ingestion is not idempotent. An **ingestion ledger** at
`data/<state>/ledger.csv` records one row per ingested source:

```
source_name, sha256, ingested_at, records_parsed, new, amended, resurfaced
```

Before ingesting, hash the source. Two rules follow:

- **Already-ingested content is never re-ingested.** If the hash is in the ledger, the run
  exits reporting "source unchanged since `<ingested_at>`" and **touches no outputs.** This
  makes redundant triggers harmless, which matters because the three existing triggers are
  not going away.
- **Outputs are never replaced by an emptier result.** Writing `new_permits.csv` for a date
  that already holds more rows than the incoming result is an error condition, not a
  silent overwrite.

The same hash check is the Bug 2 detector: an unchanged source hash across consecutive
days *is* the freshness alarm, so one mechanism covers both defects.

**The diff key is the business key, never `OBJECTID`.** TX keys on `STATUS_NUMBER`, LA on
`WELL_SERIAL_NUM`. The LA master currently carries both `OBJECTID` and `id`; SONRIS
assigns `OBJECTID` server-side and it can shift between queries, which is a likely
contributor to the duplicate accumulation patched in `4ee4a75`. Key uniqueness and
non-nullity are asserted before the diff runs.

### Backfill

No signal is lost. `data/tx/inbox/` retains 29 daily `daf420.dat` files back to
2026-07-01, so TX replays completely: rebuild master from empty, walk files in date
order, regenerate every missed day. LA retains no raw files but SONRIS is queryable by
`PERMIT_DATE`, so LA rebuilds from source. The 62 permits detected on 07-26 and
subsequently overwritten are additionally recoverable from commit `c29c268b`.

**The replay must handle the month boundary.** The extract is month-to-date cumulative and
resets at month start: `07-01` and `07-02` carry June's accumulation (974 and 1009 permit
headers), then `07-03` resets to 59. A replay that treats the series as monotonic will
misclassify the entire June carry-over. Replay starts at `07-03`; the `07-01`/`07-02`
files belong to June's cycle.

**Acceptance test.** Replaying `07-03` through `07-28` from an empty master must yield a
master of exactly **693 unique permits**, and the per-day `new` counts must sum to 693.
This is exact and mechanically checkable, and the current pipeline fails it by producing
zeros from `07-27` onward.

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

- **Source hash unchanged for 3 consecutive days** — the Bug 2 detector. Threshold is 3,
  not 2, because the source has legitimately-flat days (07-19/07-20 both 502 headers,
  07-13/07-14 both 348). Three days spans a weekend plateau without tolerating a freeze.
- **Source content advanced but zero new permits detected** — contradiction; the diff or
  the parser is wrong. This is the check that catches a genuine diff regression.
- **An output file would shrink** — refuse to write `new_permits.csv` for a date that
  already holds more rows. The Bug 1 backstop.
- Master row count flat across a rolling week
- Expected `daf420` file absent for the run date
- Any record with a null or duplicate business key — alert, never silently drop
- Workbook snapshot older than 7 days

Both bugs found on 2026-07-28 would have fired within 72 hours under these rules.

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

1. **Fix the sensor.** Ingestion ledger and idempotent outputs (Bug 1), source-freshness
   alarms (Bug 2), consolidated `core/diff.py`, July replay and backfill. Delivers real
   daily signal and stops the bleeding. Everything else depends on this.
   *Bug 2 additionally requires an out-of-band fix — confirming whether the RRC MFT link
   still refreshes — which is investigation, not code, and is tracked separately.*
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

## Future surface — dashboard

The intended end state is a dashboard the user can check from anywhere, at any time. It is
**not built in this spec.** The brief runs in Claude Cowork until it proves itself, and
only then does a persistent surface get built.

Three constraints this imposes on the work we do now, so the dashboard is not a rewrite:

1. **The evidence pack is the API.** Brief and dashboard are both consumers of the same
   presentation-neutral pack. Keeping composition logic out of the pack is what makes a
   second surface cheap.
2. **Briefs are persisted, not just sent.** Each brief is written to `data/briefs/<date>.md`
   in addition to being emailed. A dashboard needs history to render, and a brief that only
   exists in an inbox has none. This costs nothing now and is unrecoverable later.
3. **Two dashboards, not one.** Zach's existing dashboard consumes
   `data/<state>/out/<date>/` and that contract is unchanged. The intel dashboard is a
   separate, second consumer reading the evidence pack. They are not merged.

**Promotion criterion.** "Proves successful" needs a definition before it can be met.
Proposed: the brief runs unattended for four consecutive weeks with no silent-failure
alarms, and the user acts on it — opens a client conversation, adjusts a job, or catches a
permit they would otherwise have missed — at least weekly. To be confirmed by the user.

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
