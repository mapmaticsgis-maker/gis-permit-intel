# RRC source freeze: diagnosis

**Investigated:** 2026-07-29, ~07:25 CDT, from worktree `phase1-sensor-fix`.

## Finding

RRC has continued to publish new permit data — the source is **not** frozen upstream and
`auto_download_rrc.py` is **not** writing stale content; the automated download simply runs
(Task Scheduler, daily at 8:00 AM) *before* RRC's own daily refresh lands (observed at
7/28 9:45:44 AM on the portal), so it has been capturing a same-day, pre-refresh snapshot on
each of the last several runs. As of this check, RRC's server already holds 34 more permit
headers (issue dates through 2026-07-27) than the committed `daf420.dat.07-28-2026`, sitting
uncaptured.

This does not cleanly match any of the three anticipated outcomes as originally framed — it
is closest to "RRC has not published new permits **as of when the automated run executed**,"
but is importantly *not* a multi-day upstream outage: new data exists on the server right now.

## Evidence

### 1. Plain GET on the configured `fetch_url` returns the portal page, not data (expected)

```
$ python -c "import hashlib,requests,yaml; u=yaml.safe_load(open('config.yaml'))['texas']['fetch_url']; r=requests.get(u,timeout=120); print(r.status_code, len(r.content), hashlib.sha256(r.content).hexdigest()[:16], r.headers.get('last-modified'), r.headers.get('content-type'))"
200 298699 f250668fa35fb408 None text/html;charset=UTF-8
```

This is the GoDrive file-listing HTML page (~298 KB), consistent with the previous day's
check and with the comment at the top of `auto_download_rrc.py` ("A plain HTTP GET on the
link URL just returns the HTML file browser page, not the data"). This is normal behavior
for this endpoint, not evidence of an expired/auth-gated link — the link only "fails" a
plain GET because it was never meant to be fetched that way.

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
files' actual byte counts (1,900,001 B = 1.81 MiB) — there is no sign of a caching or
stale-write bug in `auto_download_rrc.py`; it wrote exactly what the server returned to it
at that moment.

### 5. The scheduled run time races RRC's daily refresh

`setup_task_scheduler.ps1:66` registers the download task as:

```
$trigger2 = New-ScheduledTaskTrigger -Daily -At "08:00 AM"
```

Actual observed runs land close to that (07:50 and 09:15 above). The portal's own
"Last Modified" column for the live `daf420.dat`, read fresh in this investigation on
2026-07-29 at ~07:25 CDT, reads **7/28/26 9:45:44 AM** — i.e. RRC's most recent refresh
landed *after* the 07:50 AM download run on 07-28 (and, going by the 07-27 run at 09:15 AM
which also came back with the same 706-count content, apparently after that run too). The
8:00 AM trigger is on the wrong side of RRC's own publish window.

(Note: the prior day's investigation, reported in the task brief as run "~00:40" on
2026-07-28, already recorded this same "7/28/26 9:45:44 AM" reading — a timestamp that
postdates a 00:40 check on the same calendar day. That inconsistency is in the prior
report, not something this investigation can resolve; it is flagged here rather than
papered over.)

## Remedy

- **No RRC portal/share-link action needed.** The link is valid and functioning; ruling out
  bucket 1's remedy (reissuing the MFT share link).
- **No downloader code fix needed.** `auto_download_rrc.py` is not caching or writing stale
  content; ruling out bucket 2's remedy.
- **This needs a scheduling change, which is in-repo/ops, not external.** Move the Windows
  Task Scheduler trigger in `setup_task_scheduler.ps1` later than RRC's observed ~9:45 AM
  refresh (e.g. 10:30 AM), or add a second daily run later in the morning, so the download
  reliably lands after the day's publish instead of racing it. This is *not* something that
  requires the repo owner to act outside this codebase (no RRC contact, no new share link)
  — it is a config change to a file already in this repository. I have **not** made that
  change; Task 9 is investigation-only.
- Separately: because the 34 extra permits are already sitting on RRC's server as of this
  morning, the *next* successful scheduled run (today, 07-29, whenever it executes) will
  very likely capture them on its own, independent of any schedule fix — this specific
  freeze may resolve itself before any action is taken. The schedule mismatch will keep
  recurring on other days, though, until the trigger time is moved.

## What the new alarm will do

`core.invariants.check_records_advancing` (see `core/invariants.py:38-80`) treats a flat
record count as frozen once it has held for `alarm_after_days` (default 4) days. The
module's own docstring states: *"The real freeze (last movement 07-26) still alarms on
07-30."* Verified independently by calling the function directly with the known header
counts (567/602/637/669/706/706/706 for 07-22 through 07-28):

```
2026-07-28 -> ok= True | record count last moved 2026-07-26 (now 706) (2d ago, alarms at 4d)
2026-07-29 -> ok= True | record count last moved 2026-07-26 (now 706) (3d ago, alarms at 4d)
2026-07-30 -> ok= False | record count last moved 2026-07-26 (now 706) (4d ago, alarms at 4d)
2026-07-31 -> ok= False | record count last moved 2026-07-26 (now 706) (5d ago, alarms at 4d)
```

**It will fire starting 2026-07-30**, if the count is still 706 by then.

Given the evidence above, that is the *correct* backstop behavior, but it may never actually
fire for this specific episode: the 740-record file already sitting on RRC's server means
the next successful automated run should move the ledger's last-moved date to on/after
07-29, resetting the flat-day counter before it reaches 4. If a run is missed or fails and
the count is still 706 on 07-30, the alarm firing is the right outcome — it is a genuine
(if resolvable) gap between what RRC has published and what this pipeline has captured.

## Scope note

The task brief's header states "Bug 2 is upstream of this repo and cannot be fixed by
changing the pipeline." This investigation does not fully bear that out: the evidence
points to a schedule mismatch between an in-repo Task Scheduler trigger and RRC's publish
time, which *is* fixable by changing something in this repo (the trigger time), not by
contacting RRC or reissuing the share link. Flagging this discrepancy rather than forcing
the finding to fit the original framing.
