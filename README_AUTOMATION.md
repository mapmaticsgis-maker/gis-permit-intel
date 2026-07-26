# Permit Intel — Daily Automation (on top of your v8 pipeline)

This adds three files to what you already had (`common.py`, `digest.py`,
`tx_daf420.py`, `la_pull.py`, `county_lookup.py`, `config.yaml` are all
yours, mostly untouched) and one small addition to `tx_daf420.py`:

- **`run_daily_ci.py`** — new. GitHub Actions entry point: runs both
  pulls, self-checks the results, emails you the brief (or an alert),
  pings an optional heartbeat. Your existing `run_daily.py` (Windows
  Task Scheduler) is untouched — keep using it locally if useful, or
  retire it once the Action's been reliable for a couple weeks.
- **`self_check.py`** — new. The "is it actually working" layer.
- **`send_email.py`** — new. SMTP delivery, credentials from GitHub Secrets.
- **`tx_daf420.py`** — one addition: a `fetch_daily_file()` function and
  a `texas.fetch_url` branch in `main()`, so TX can run headless instead
  of needing the daily manual download. See below — this needs a quick
  verification pass from you before you trust it unattended.

LA was already fully hands-off (`la_pull.py` hits the SONRIS REST
endpoint directly) — no changes needed there beyond wiring it into the
new orchestrator.

## TX fetch_url — confirmed working

Your own README already flagged the plan ("paste the URL you hit
manually each day... your existing RRC MFT link pattern works here")
but `fetch_url` was only wired into the older `tx_pull.py`, not into
`tx_daf420.py` (the one you actually run). I added it there.

The link itself is confirmed two ways:
1. You uploaded the actual `daf420_dat.07-26-2026` pull from that URL —
   it parses clean through `parse_rrc()`: 706 real permit records,
   coordinates, counties, corridor/family tags all correct.
2. Zach's dashboard already fetches this same URL programmatically
   (`rrcdashboard.zachg.org`), confirming it's not gated behind a
   browser session.

`config.yaml`'s `texas.fetch_url` is already set to
`https://mft.rrc.texas.gov/link/5f07cc72-2e79-4df8-ade1-9aeb792e03fc`
(the trailing `#` some browsers show is just a URL fragment — never
sent to the server, so it's the same request either way). TX now runs
exactly as hands-off as LA already was.

## Setup

1. Push this folder (with the additions) to your GitHub repo.
2. Settings → Secrets and variables → Actions, add:
   - `SMTP_HOST` (e.g. `smtp.gmail.com`), `SMTP_PORT` (`587`)
   - `SMTP_USER`, `SMTP_PASSWORD` (Gmail **App Password**, not your login)
   - `ALERT_TO_EMAIL`
   - `HEALTHCHECK_URL` *(optional, see below)*
3. Commit whatever's currently in `data/tx/master.csv` and
   `data/la/master.csv` so day one is a real diff, not a "everything is
   new" flood.

## The self-check layer

- **In-run checks** (`self_check.py`): master row count never shrinks,
  no mojibake in the digest text, new-permit counts land in a sane
  range. Any failure → you still get the normal brief, but also a
  second, distinctly-subject-lined alert email, so a broken parser
  quietly returning 0 rows never just reads like a quiet day.
- **Hard-crash handling**: if both pulls fail outright, you get an
  immediate alert with the tail of stderr from each, and the Action
  shows red on the Actions tab.
- **Out-of-band heartbeat (optional)**: the two checks above only work
  if GitHub Actions is still running the workflow at all — if it gets
  disabled or billing lapses, nothing above ever fires. Free fix:
  [healthchecks.io](https://healthchecks.io) — create a check with a
  26-hour grace period, drop its ping URL in as `HEALTHCHECK_URL`. It
  emails you if the daily ping *doesn't* show up — detection from
  completely outside GitHub.
- **`data/run_log.csv`** — one row per run, so drift shows up over
  weeks, not just today.

## Testing before you trust it

`workflow_dispatch` is enabled, so use the "Run workflow" button on the
Actions tab to trigger it by hand as many times as you want — do this
a few times after confirming `fetch_url` before letting the 8:30 cron
run unsupervised.
