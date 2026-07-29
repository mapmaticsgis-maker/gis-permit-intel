# RRC source freeze: diagnosis

**Investigated:** 2026-07-29, ~07:25 CDT, from worktree `phase1-sensor-fix`.
**Revised:** 2026-07-29, later same day, after code review returned five Critical findings
on the first draft. Corrections below are folded in; the 740-vs-706 permit-count evidence
from the original investigation is unchanged and reproduced verbatim.

## Finding

RRC has continued to publish new permit data — the source is **not** frozen upstream, and
`auto_download_rrc.py` is **not** writing stale content. Every morning automation trigger on
this machine (download 07:50, local ArcGIS pipeline 08:30, GitHub Actions dispatch 09:00)
runs before RRC's daily refresh, so each day's capture is one publish-cycle behind — not
just the download step. This is compounded by RRC not publishing over the weekend: 2026-07-26
was a Sunday, so the file RRC served that morning was unchanged from Saturday, and Monday
07-27's 07:50 capture returned the exact same bytes as Sunday's. That is why 07-26 and 07-27
are byte-identical (confirmed below) — it is the schedule-vs-refresh gap *plus* a real
non-publishing day landing on top of it, not the schedule gap alone.

As of this check (before today's 07:50 run), RRC's server already carries 34 more permit
headers than the committed `daf420.dat.07-28-2026` (issue dates extending to 2026-07-27
instead of 2026-07-24) — direct evidence the upstream source is alive and moving.

Separately: `setup_task_scheduler.ps1` in this repo does **not** describe the scheduled
tasks actually running on this machine. It registers `TX-RRC-Daily-Download` at 08:00
AM pointing at `auto_download_txrrc.py` — a script that does not exist anywhere in this
repository. The task that is actually live and running (`TX-RRC-Auto-Download`, confirmed
via `Get-ScheduledTask` below) runs `auto_download_rrc.py` — the real, present script — at
07:50, not 08:00. The checked-in setup script is stale and would not be the right place to
apply a schedule fix; that is itself a finding worth recording, not just a footnote.

## Observed vs. inferred

To keep this note honest about what was actually measured versus generalized:

**Observed directly (this investigation, with quoted command output):**
- Plain GET on `fetch_url` returns HTML (200, ~298 KB) — not a data feed.
- A full Playwright click-and-download replay of `auto_download_rrc.py`'s flow succeeds and
  returns a `daf420.dat` with 740 `01`-records / issue dates through 2026-07-27 — more than
  the stored 07-28 file's 706 records / issue dates through 2026-07-24.
- `data/tx/inbox/daf420.dat.07-26-2026` and `daf420.dat.07-27-2026` are byte-identical
  (same length, same sha256) — verified directly, shown below.
- The live Windows Task Scheduler configuration (`Get-ScheduledTask`), showing the actual
  running triggers and actions, not the checked-in setup script's version.
- `auto_download_txrrc.py`, the script `setup_task_scheduler.ps1` registers, does not exist
  in this repository (`find . -iname auto_download_txrrc.py` returns nothing).
- The portal's "Last Modified" column for the live `daf420.dat` reads `7/28/26 9:45:44 AM`,
  read at two points ~6h43m apart on 2026-07-29 (00:42 and ~07:25), both identical.
- `core.invariants.check_records_advancing`'s alarm date, computed directly against the
  known header-count history.

**Inferred, not observed, and labeled as such:**
- "RRC refreshes daily at approximately 9:45 AM." This is a generalization from **one**
  file mtime (`7/28/26 9:45:44 AM`), observed twice on the same calendar day against the
  same unchanged file — not two independent daily observations. It has not been confirmed
  that this mtime will advance again on 07-29 or that 9:45 AM is a fixed daily time rather
  than a one-off. What would confirm it: observing the live mtime advance across two or
  more consecutive days, ideally bracketing each morning trigger to see which side of the
  refresh each one lands on.
- That the weekend explains the 07-26/07-27 identity (RRC not publishing on Sunday) is a
  reasonable calendar-based inference (07-26 is a Sunday) but was not confirmed by finding
  an explicit "no new data on weekends" statement from RRC — it is consistent with the
  data and is the simplest explanation, not an independently verified policy.

## Evidence

### 1. Plain GET on the configured `fetch_url` returns the portal page, not data (expected)

```
$ python -c "import hashlib,requests,yaml; u=yaml.safe_load(open('config.yaml'))['texas']['fetch_url']; r=requests.get(u,timeout=120); print(r.status_code, len(r.content), hashlib.sha256(r.content).hexdigest()[:16], r.headers.get('last-modified'), r.headers.get('content-type'))"
200 298699 f250668fa35fb408 None text/html;charset=UTF-8
```

This is the GoDrive file-listing HTML page (~298 KB), consistent with the comment at the
top of `auto_download_rrc.py` ("A plain HTTP GET on the link URL just returns the HTML file
browser page, not the data"). This is normal behavior for this endpoint, not evidence of an
expired/auth-gated link — the link only "fails" a plain GET because it was never meant to
be fetched that way.

### 2. Replicating the downloader's actual click-and-download flow succeeds and returns NEW content

Read-only Playwright script pointed at the same `.playwright-browsers` Chromium the real
downloader uses, performing the identical row-select + Download click sequence as
`auto_download_rrc.py::download_daf420`, saving only to a scratch temp path (never
`data/tx/inbox/`):

```
Navigating to https://mft.rrc.texas.gov/link/5f07cc72-2e79-4df8-ade1-9aeb792e03fc
HTTP status: 200
Title: RRC Web Client - GoDrive
Found 250 rows
--- row 0 ---
        daf420.dat  7/28/26 9:45:44 AM  1.89 MB
```

```
Opening RRC GoDrive portal...
Selecting current file (row 0)...
Row 0 aria-selected: true
Triggering download...
Downloaded ZIP: 1936.7 KB
Zip contents: ['daf420.dat']
daf420.dat: 1983045 bytes, sha256[:16]=dbd9df0189dc8c23
```

The link works, requires no additional auth beyond the browser flow the script already
performs, and returns a valid `daf420.dat` — ruling out "link expired / needs a session."

### 3. The served file differs from the stored file, and it is *larger*, not corrupted

```
$ python -c "
import hashlib
stored = open('data/tx/inbox/daf420.dat.07-28-2026','rb').read()
live = open(r'...\daf420.dat.live-check','rb').read()
print('stored len', len(stored), 'sha', hashlib.sha256(stored).hexdigest()[:16])
print('live   len', len(live), 'sha', hashlib.sha256(live).hexdigest()[:16])
print('stored 01-count', sum(1 for l in stored.splitlines() if l.startswith(b'01')))
print('live   01-count', sum(1 for l in live.splitlines() if l.startswith(b'01')))
"
stored len 1900001 sha f2d19627afc91656
live   len 1983045 sha dbd9df0189dc8c23
stored 01-count 706
live   01-count 740
```

Parsing both files with the repo's own `tx_daf420.parse_rrc`:

```
live rows: 740
stored rows: 706

live Issue_Date value_counts, last 6 of 15 dates printed (full output ran
`.value_counts(dropna=False).sort_index().tail(15)`):
2026-07-20    51
2026-07-21    28
2026-07-22    29
2026-07-23    26
2026-07-24    36
2026-07-27    27
Name: count, dtype: int64

stored Issue_Date value_counts, last 5 of 15 dates printed:
2026-07-20    51
2026-07-21    28
2026-07-22    29
2026-07-23    26
2026-07-24    36
Name: count, dtype: int64
```

The live, currently-served file already contains 27 permits issued 2026-07-27 that are
absent from the stored 07-28 file (which tops out at 2026-07-24, matching the header
counts given in the task brief: 07-25:669, 07-26:706, 07-27:706, 07-28:706). No permits
appear for 2026-07-25/26 (Saturday/Sunday) in either file, consistent with RRC not issuing
permits on weekends.

### 4. The downloader's own run log shows it correctly captured whatever was live at run time

From `C:\GIS\permit_intel\logs\rrc_download.log` (this worktree has no `logs/`; the log
lives in the main checkout the scheduled task runs from):

```
[2026-07-27 09:15:33,365] INFO: RRC daf420 Automated Download
[2026-07-27 09:15:34,456] INFO: Opening RRC GoDrive portal...
[2026-07-27 09:15:39,826] INFO: Downloaded ZIP: 1854 KB
[2026-07-27 09:15:39,995] INFO: Saved: data\tx\inbox\daf420.dat.07-27-2026 (1.81 MB)
[2026-07-27 09:15:40,128] INFO: Nothing new to commit (file unchanged or already committed)

[2026-07-28 07:50:02,430] INFO: RRC daf420 Automated Download
[2026-07-28 07:50:04,665] INFO: Opening RRC GoDrive portal...
[2026-07-28 07:50:10,235] INFO: Saved: data\tx\inbox\daf420.dat.07-28-2026 (1.81 MB)
[2026-07-28 07:50:13,280] INFO: Committed and pushed to GitHub
```

Both runs succeeded (after unrelated earlier Playwright-executable errors on 07-27 were
retried), produced normally-sized zips, and their "1.81 MB" size labels match the stored
files' actual byte counts — there is no sign of a caching or stale-write bug in
`auto_download_rrc.py`; it wrote exactly what the server returned to it at that moment. The
07-27 log entry shows a run at 09:15 (a retry, after earlier same-morning Playwright
executable-path failures also in that log, not reproduced here) rather than the scheduled
07:50 — meaning even the *later* 07-27 attempt still returned the same 706-count content,
which the weekend explanation (next point) accounts for independent of exact run time.

### 5. The live scheduled-task configuration, its mismatch with the checked-in script, and the weekend explanation

**5a. The live Task Scheduler configuration** (`Get-ScheduledTask`, read-only, run during
this investigation):

```
Name    : PermitIntelDaily
State   : Ready
Trigger : 2026-07-19T08:30:00
Action  : "C:\Program Files\ArcGIS\Pro\bin\Python\envs\arcgispro-py3\python.exe" "C:\GIS\permit_intel\run_daily.py"

Name    : TX-RRC-Auto-Download
State   : Ready
Trigger : 2026-07-26T07:50:00-05:00
Action  : C:\Users\mapma\AppData\Local\Programs\Python\Python314\python.exe C:\GIS\permit_intel\auto_download_rrc.py

Name    : TX-RRC-Daily-Reminder
State   : Ready
Trigger : 2026-07-26T08:00:00-05:00
Action  : C:\Users\mapma\AppData\Local\Programs\Python\Python314\python.exe C:\GIS\permit_intel\send_daily_reminder.py

Name    : TX-RRC-GitHub-Trigger
State   : Ready
Trigger : 2026-07-27T09:00:00-05:00
Action  : C:\Users\mapma\AppData\Local\Programs\Python\Python314\python.exe C:\GIS\permit_intel\trigger_github_workflow.py

Name    : TX-RRC-Inbox-AutoCommit
State   : Ready
Trigger : 2026-07-26T14:31:15-05:00
Action  : C:\Users\mapma\AppData\Local\Programs\Python\Python314\python.exe C:\GIS\permit_intel\auto_commit_inbox.py
```

So the download runs at **07:50**, the local ArcGIS pipeline (`PermitIntelDaily` →
`run_daily.py`) at **08:30**, and the GitHub Actions dispatch (`TX-RRC-GitHub-Trigger` →
`trigger_github_workflow.py`, which fires `.github/workflows/daily-permit-intel.yml`) at
**09:00** — all three of the morning triggers that touch TX data run before the file's
observed `9:45:44 AM` modification time. Fixing only the download step would leave the
08:30 local pipeline and 09:00 GitHub Actions dispatch still processing a stale inbox on
the morning it runs early.

**5b. `setup_task_scheduler.ps1` does not match this.** Line 66 registers:

```
$trigger2 = New-ScheduledTaskTrigger -Daily -At "08:00 AM"
```

against `auto_download_txrrc.py` (line 59), a filename that does not exist in this repo —
only `auto_download_rrc.py` does. The live `TX-RRC-Auto-Download` task runs the real script
at 07:50, not 08:00, and was evidently registered some other way (by hand, or by an earlier
version of the setup script) — not by the version currently checked in. Editing
`setup_task_scheduler.ps1` and re-running it would not change the schedule that is actually
executing; it targets a script and a time neither of which describe the live task.

**5c. The 07-26/07-27 byte-identical pair is a weekend, not an anomaly.** 2026-07-26 was a
Sunday and 2026-07-27 a Monday (calendar: 07-24 Fri, 07-25 Sat, 07-26 Sun, 07-27 Mon, 07-28
Tue). Direct hash comparison of the four most recent inbox files:

```
$ python -c "
import hashlib
for d in ['07-25','07-26','07-27','07-28']:
    p = f'data/tx/inbox/daf420.dat.{d}-2026'
    data = open(p,'rb').read()
    print(d, len(data), hashlib.sha256(data).hexdigest()[:16])
"
07-25 1802398 ee0ff0e3efb3ed46
07-26 1898578 3c1ec0be06714ee4
07-27 1898578 3c1ec0be06714ee4
07-28 1900001 f2d19627afc91656
```

07-26 and 07-27 are exactly the same file (identical length and sha256); 07-25 and 07-28
each differ from their neighbors. If the schedule-vs-refresh gap were the only mechanism,
each day's early capture should still differ slightly day to day (new coordinate records at
minimum). The exact identity of the 07-26/07-27 pair specifically is explained by RRC simply
not having anything new to publish over the Sunday-into-Monday window — the schedule gap
explains why every capture is one cycle behind; the weekend explains why two of those
captures, specifically, came back byte-for-byte the same.

## Remedy

- **No RRC portal/share-link action needed.** The link is valid and functioning; ruling out
  bucket 1's remedy (reissuing the MFT share link).
- **No downloader code fix needed.** `auto_download_rrc.py` is not caching or writing stale
  content; ruling out bucket 2's remedy — it correctly wrote whatever the server returned
  at the moment each run fired.
- **This requires re-registering scheduled tasks on the Windows machine, as Administrator —
  an out-of-band action the repo owner must perform, not a code fix.** Because the live
  tasks were not created by the checked-in `setup_task_scheduler.ps1` (it points at a
  nonexistent script and a different time than what's running), changing a trigger time
  cannot be done by editing a file in this repo and committing it. Someone with admin
  access to that machine needs to:
  1. Move (or duplicate with a later time) `TX-RRC-Auto-Download`, currently 07:50, to run
     after RRC's refresh.
  2. Move `PermitIntelDaily` (`run_daily.py`, currently 08:30) to run after the download,
     not just after RRC's refresh — the local pipeline needs the *download* to have already
     picked up the fresh file that morning, not just to postdate RRC's own refresh.
  3. Move `TX-RRC-GitHub-Trigger` (`trigger_github_workflow.py` → dispatches
     `.github/workflows/daily-permit-intel.yml`, currently 09:00) correspondingly later, so
     the GitHub Actions run also sees a same-day-fresh inbox.
  All three should be checked against the actual refresh time once it's confirmed (see
  "Observed vs. inferred" above) rather than against the single 9:45:44 AM reading alone —
  the reading is only one data point.
  - Separately, whoever does this should also either fix or retire
    `setup_task_scheduler.ps1` so it reflects reality (correct script name, correct time) —
    right now it would silently fail to change anything if someone ran it expecting it to
    fix the live schedule.
- Independent of the schedule fix: because the 34 extra permits are already sitting on
  RRC's server as of this morning, the *next* successful `TX-RRC-Auto-Download` run (today,
  07-29, 07:50, before this note's revision was even finished) may already have captured
  them — that would resolve this specific episode without waiting on the admin action
  above. The schedule-vs-refresh gap will keep recurring on other mornings, though, until
  the tasks are re-registered.

## What the new alarm will do

`core.invariants.check_records_advancing` (`core/invariants.py:38-80`) treats a flat record
count as frozen once it has held for `alarm_after_days` (4) days. Per the module's own
docstring, this threshold was recalibrated from an original value of 3 after a full replay
of July 2026 showed a legitimate 3-day plateau (111 permits held 07-05 through 07-07 over
the Independence Day week) that a threshold of 3 would have false-alarmed on; 4 was chosen
specifically so that plateau passes and a real freeze still catches. Docstring: *"The real
freeze (last movement 07-26) still alarms on 07-30."*

Verified independently by calling the function directly with the known header counts
(567/602/637/669/706/706/706 for 07-22 through 07-28):

```
2026-07-28 -> ok= True | record count last moved 2026-07-26 (now 706) (2d ago, alarms at 4d)
2026-07-29 -> ok= True | record count last moved 2026-07-26 (now 706) (3d ago, alarms at 4d)
2026-07-30 -> ok= False | record count last moved 2026-07-26 (now 706) (4d ago, alarms at 4d)
2026-07-31 -> ok= False | record count last moved 2026-07-26 (now 706) (5d ago, alarms at 4d)
```

**It will fire starting 2026-07-30**, if the count is still 706 by then.

Given the evidence above, that is the *correct* backstop behavior, but it may never
actually fire for this specific episode: the 740-record file already sitting on RRC's
server means the next successful automated run should move the ledger's last-moved date to
on/after 07-29, resetting the flat-day counter before it reaches 4. If a run is missed, or
the schedule-vs-refresh gap causes another stale capture, and the count is still 706 on
07-30, the alarm firing is the right outcome — a genuine (if resolvable) gap between what
RRC has published and what this pipeline has captured, exactly the class of silent failure
this check exists to catch.

## Scope note

The task brief's header states "Bug 2 is upstream of this repo and cannot be fixed by
changing the pipeline." This investigation does not bear that out cleanly: the mechanism is
a schedule-vs-refresh gap across three separate morning triggers, compounded by a weekend
non-publish, and the remedy is an operational change (re-registering Windows Scheduled
Tasks) rather than an RRC portal action or a code fix to the parsing/diff pipeline. It *is*
an out-of-band action the repo owner must perform on the machine — just not the kind of
"contact RRC / reissue a share link" action the brief's framing suggested.
