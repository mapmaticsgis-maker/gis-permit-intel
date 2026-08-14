"""
Market-wide permit brief — reads the master(s) tx_daf420.py / la_pull.py
already maintain and produces daily/weekly/monthly analysis.

This is deliberately NOT a second ingestion pipeline. It does not fetch, parse,
or diff anything; tx_daf420.py and the (unseen, presumed analogous) la_pull.py
already do that better than a rewrite would, complete with the ingestion
ledger, skip markers, and union-write semantics that make "was there really
nothing new" an answered question instead of a guess.

What this adds: the analytical layer the daily digest doesn't cover — rolling
7-day momentum, basin mix, spud-conversion by cohort, aging inventory,
step-outs, permit-banking candidates, amendment clusters. digest.py answers
"what happened today." This answers "what does the pattern look like."

Run after tx_daf420.py / la_pull.py have updated their masters for the day:

    python market_brief.py --out market_brief.md
    python market_brief.py --asof 2026-08-14 --out market_brief.md
"""

import argparse
from datetime import datetime, timedelta

import pandas as pd

from common import load_cfg, load_master, family_of, corridor_of
from county_lookup import COUNTY_LOOKUP

BASELINE_MONTHLY = 750
BASELINE_DAILY = 35
SPUD_LAG_DAYS = 21
AGING_THRESHOLD_DAYS = 45

PERMIAN = {
    "ANDREWS", "BORDEN", "CRANE", "CROCKETT", "CULBERSON", "DAWSON", "ECTOR",
    "GAINES", "GLASSCOCK", "HOWARD", "HOCKLEY", "IRION", "LOVING", "MARTIN",
    "MIDLAND", "MITCHELL", "PECOS", "REAGAN", "REEVES", "SCURRY", "STERLING",
    "TERRY", "UPTON", "WARD", "WINKLER", "YOAKUM",
}
EAGLE_FORD = {
    "ATASCOSA", "BASTROP", "BEE", "BRAZOS", "BURLESON", "CALDWELL", "COLORADO",
    "DEWITT", "DIMMIT", "FAYETTE", "FRIO", "GONZALES", "GRIMES", "KARNES",
    "LA SALLE", "LAVACA", "LEE", "LEON", "LIVE OAK", "MADISON", "MAVERICK",
    "MCMULLEN", "MILAM", "ROBERTSON", "WASHINGTON", "WEBB", "WILSON", "ZAVALA",
}
EAST_TX_GAS = {
    "ANDERSON", "ANGELINA", "CASS", "CHEROKEE", "FREESTONE", "GREGG", "HARRISON",
    "HENDERSON", "LIMESTONE", "MARION", "MORRIS", "NACOGDOCHES", "PANOLA",
    "RUSK", "SAN AUGUSTINE", "SHELBY", "SMITH", "UPSHUR",
}


def basin_of(county):
    if pd.isna(county):
        return "Other"
    name = str(county).upper()
    if name in PERMIAN:
        return "Permian"
    if name in EAGLE_FORD:
        return "Eagle Ford"
    if name in EAST_TX_GAS:
        return "East Texas gas"
    return "Other"


def lease_stem(name):
    if pd.isna(name):
        return ""
    parts = str(name).strip().split()
    if len(parts) > 1 and len(parts[-1]) <= 6:
        return " ".join(parts[:-1])
    return str(name).strip()


def prep_tx(master):
    """
    Coerce the string-dtype master into working types and attach the derived
    columns (basin, county-label check, reentry flag) this brief needs.

    load_master reads with dtype=str throughout, so every numeric/date column
    needs an explicit cast here — nothing upstream has done it yet.
    """
    df = master.copy()
    for col in ("Received_Date", "Issue_Date", "Spud_Date"):
        df[col] = pd.to_datetime(df[col], errors="coerce")
    df["Total_Depth"] = pd.to_numeric(df["Total_Depth"], errors="coerce")
    df["Operator_Name"] = df["Operator_Name"].astype(str).str.upper().str.strip()

    # Self-check against the (hopefully corrected) lookup. This catches two
    # different failure modes: county_lookup.py not yet fixed, or master.csv
    # rows written before the fix and never migrated (see
    # migrate_county_labels.py — dropping in the lookup does not retroactively
    # correct rows already on disk).
    code = df["CountyCode"].astype(str).str.zfill(3)
    df["County_Expected"] = code.map(COUNTY_LOOKUP)
    df["County_Label_Error"] = (
        df["County_Expected"].notna() & (df["County"] != df["County_Expected"])
    )

    df["basin"] = df["County"].map(basin_of)
    df["cycle_days"] = (df["Spud_Date"] - df["Issue_Date"]).dt.days
    df["is_reentry"] = df["cycle_days"] < 0
    return df


def window(df, start, end, column="Issue_Date"):
    return df[(df[column] >= start) & (df[column] <= end)]


def detect_batches(df, minimum=3):
    if df.empty:
        return []
    work = df.copy()
    work["stem"] = work["Lease_Name"].map(lease_stem)
    grouped = work.groupby(["Operator_Name", "Received_Date", "stem"]).size()
    return [
        {"operator": op, "received": rd.date() if pd.notna(rd) else "unknown",
         "stem": stem, "count": int(n)}
        for (op, rd, stem), n in grouped.items() if n >= minimum
    ]


def section_today(df, asof, cfg, lines):
    today = window(df, asof, asof)
    trailing30 = window(df, asof - timedelta(days=30), asof)
    business_days = max(1, len(pd.bdate_range(asof - timedelta(days=30), asof)))
    daily_avg = len(trailing30) / business_days

    lines.append("## Today\n")
    lines.append(f"- Permits issued: **{len(today)}** "
                 f"(30-day average {daily_avg:.0f}/business day, baseline ~{BASELINE_DAILY})")

    spuds = df[(df["Spud_Date"] == asof) & (~df["is_reentry"])]
    lines.append(f"- New spud postings dated today: **{len(spuds)}**")

    if len(today):
        ops = (today.groupby("Operator_Name")
               .agg(n=("Permit_Number", "count"),
                    counties=("County", lambda s: ", ".join(sorted(set(s.dropna())))))
               .sort_values("n", ascending=False).head(5))
        lines.append("\n**Leading operators**\n")
        for name, row in ops.iterrows():
            lines.append(f"- {name} — {row['n']} ({row['counties']})")

        counties = today["County"].value_counts().head(5)
        lines.append("\n**Leading counties**\n")
        for name, count in counties.items():
            lines.append(f"- {name} — {count}")

        batches = detect_batches(today)
        if batches:
            lines.append("\n**Batch filings** (one decision, not a ramp — "
                         "same operator, same lease stem, same Received_Date)\n")
            for batch in batches:
                lines.append(f"- {batch['operator']} — {batch['stem']}, "
                             f"{batch['count']} permits received {batch['received']}")
    else:
        lines.append("\nNo permits carry today's issue date. If the prior pull "
                     "was identical, check tx_daf420.py's ingestion ledger — it "
                     "already distinguishes a genuine RRC posting gap from a "
                     "stale fetch; this brief does not re-derive that.")
    lines.append("")


def section_week(df, asof, lines):
    this_start = asof - timedelta(days=6)
    prior_start = asof - timedelta(days=13)
    prior_end = asof - timedelta(days=7)

    this_week = window(df, this_start, asof)
    prior_week = window(df, prior_start, prior_end)

    change = ""
    if len(prior_week):
        pct = (len(this_week) - len(prior_week)) / len(prior_week) * 100
        change = f", {pct:+.0f}% vs prior week"

    lines.append("## Rolling week\n")
    lines.append(f"- 7-day issuance: **{len(this_week)}** "
                 f"(prior 7-day: {len(prior_week)}{change})")

    this_ops = this_week["Operator_Name"].value_counts()
    prior_ops = prior_week["Operator_Name"].value_counts()
    momentum = (this_ops.subtract(prior_ops, fill_value=0)
                .sort_values(ascending=False))
    gainers = momentum[momentum > 0].head(5)
    decliners = momentum[momentum < 0].tail(5)

    if len(gainers):
        lines.append("\n**Accelerating**\n")
        for name, delta in gainers.items():
            lines.append(f"- {name} — {int(this_ops.get(name, 0))} this week "
                         f"({int(delta):+d})")
    if len(decliners):
        lines.append("\n**Decelerating**\n")
        for name, delta in decliners.items():
            lines.append(f"- {name} — {int(this_ops.get(name, 0))} this week "
                         f"({int(delta):+d})")

    prior30 = window(df, asof - timedelta(days=37), asof - timedelta(days=7))
    established = set(prior30["Operator_Name"].dropna())
    entrants = sorted(set(this_week["Operator_Name"].dropna()) - established)
    if entrants:
        lines.append("\n**New entrants this week** (no permits in prior 30 days — "
                     "check operator_families first; a rebrand or merged alias "
                     "should not read as new)\n")
        for name in entrants[:10]:
            counties = ", ".join(sorted(set(
                this_week[this_week["Operator_Name"] == name]["County"].dropna())))
            lines.append(f"- {name} ({counties})")

    spudded = df[(df["Spud_Date"] >= this_start) & (df["Spud_Date"] <= asof)
                & (~df["is_reentry"])]
    if len(spudded):
        lines.append(f"\n- Wells spudded this week: **{len(spudded)}**, "
                     f"median permit-to-spud **{spudded['cycle_days'].median():.0f} days**")
    lines.append("")


def section_month(df, asof, cfg, lines):
    month_start = asof.replace(day=1)
    mtd = window(df, month_start, asof)
    elapsed = max(1, len(pd.bdate_range(month_start, asof)))
    total_bdays = len(pd.bdate_range(month_start, month_start + pd.offsets.MonthEnd(1)))
    projected = len(mtd) / elapsed * total_bdays

    lines.append("## Month to date\n")
    lines.append(f"- MTD issuance: **{len(mtd)}** over {elapsed} business days, "
                 f"tracking to ~**{projected:.0f}** (baseline ~{BASELINE_MONTHLY})")

    if len(mtd):
        mix = mtd["basin"].value_counts(normalize=True) * 100
        parts = [f"{basin} {pct:.0f}%" for basin, pct in mix.items()]
        lines.append(f"- Basin mix: {', '.join(parts)}")

        fams = mtd["Operator_Name"].map(lambda o: family_of(o, cfg["operator_families"]))
        fam_counts = fams.value_counts()
        if len(fam_counts):
            lines.append("\n**Watched families, MTD**\n")
            for fam, n in fam_counts.items():
                lines.append(f"- {fam}: {n}")

    lines.append("\n**Spud conversion by issue cohort** *(floor, not a true "
                 "rate — see Data notes)*\n")
    cohorts = df[df["Issue_Date"].notna()].copy()
    cohorts["cohort"] = cohorts["Issue_Date"].dt.to_period("M")
    recent = sorted(cohorts["cohort"].unique())[-5:]
    for cohort in recent:
        group = cohorts[cohorts["cohort"] == cohort]
        if len(group) < 5:
            continue
        spudded = group["Spud_Date"].notna() & (~group["is_reentry"])
        age = (asof - group["Issue_Date"].max()).days
        note = "  *(inside spud-reporting lag)*" if age < SPUD_LAG_DAYS else ""
        lines.append(f"- {cohort}: {spudded.sum()}/{len(group)} "
                     f"({spudded.mean() * 100:.0f}%){note}")

    aging = df[(df["Issue_Date"] <= asof - timedelta(days=AGING_THRESHOLD_DAYS))
              & (df["Spud_Date"].isna())]
    lines.append(f"\n- Aging inventory: **{len(aging)}** permits issued "
                 f"{AGING_THRESHOLD_DAYS}+ days ago, still unspudded")

    deep = mtd[mtd["Total_Depth"] >= 16000]
    lines.append(f"- Ultra-deep (16,000'+) permits MTD: **{len(deep)}**")
    lines.append("")


def section_patterns(df, asof, cfg, lines):
    lines.append("## Pattern candidates\n")
    lines.append("*Machine-surfaced. Review before including — not all are meaningful.*\n")

    trailing90 = window(df, asof - timedelta(days=90), asof)
    this_week = window(df, asof - timedelta(days=6), asof)

    step_outs = []
    for (operator, county), group in this_week.groupby(["Operator_Name", "County"]):
        history = df[(df["Operator_Name"] == operator) & (df["County"] == county)
                     & (df["Issue_Date"] < asof - timedelta(days=6))]
        elsewhere = df[(df["Operator_Name"] == operator) & (df["County"] != county)]
        if history.empty and not elsewhere.empty:
            step_outs.append((operator, county, len(group)))
    if step_outs:
        step_outs.sort(key=lambda item: -item[2])
        lines.append("**Step-outs** — first permit in this county in 90+ days\n")
        for operator, county, count in step_outs[:10]:
            lines.append(f"- {operator} → {county} ({count} permit(s))")
        lines.append("")

    # Permit banking candidates. This is a FLOOR, not a rate — see the Data
    # notes section for why, and never report a ratio from here without a
    # direct well-status check first.
    bankers = []
    for operator, group in trailing90.groupby("Operator_Name"):
        if len(group) < 8:
            continue
        spudded = int((group["Spud_Date"].notna() & (~group["is_reentry"])).sum())
        if spudded == 0 or len(group) / max(spudded, 1) >= 5:
            bankers.append((operator, len(group), spudded))
    if bankers:
        bankers.sort(key=lambda item: -item[1])
        lines.append("**Permit banking candidates** — 90-day permits vs spuds "
                     "*visible to this master*\n")
        lines.append("> Floor, not a rate. Confirm against a direct well-status "
                     "query before reporting a ratio to anyone.\n")
        for operator, permits, spudded in bankers[:8]:
            lines.append(f"- {operator} — {permits} permits, {spudded} spuds seen")
        lines.append("")

    amended = df[(df["Received_Date"] >= asof - timedelta(days=7))
                & (df["Issue_Date"] <= asof - timedelta(days=30))]
    if len(amended):
        clusters = (amended.assign(stem=amended["Lease_Name"].map(lease_stem))
                    .groupby(["Operator_Name", "stem"]).size())
        clusters = clusters[clusters >= 2].sort_values(ascending=False)
        if len(clusters):
            lines.append("**Amendment clusters** — block-wide refiling often "
                         "precedes drilling\n")
            for (operator, stem), count in clusters.head(8).items():
                lines.append(f"- {operator} — {stem} ({count} permits refiled)")
            lines.append("")

    # Corridors come straight from config.yaml via common.corridor_of — every
    # corridor defined there, not a hardcoded subset. The Lee/Fayette/Lavaca
    # corridor is "DLS / EOG — Giddings & Eastern Eagle Ford" and covers nine
    # counties, not three; report the corridor as configured, not as remembered.
    trailing90 = trailing90.copy()
    trailing90["corridor"] = trailing90.apply(
        lambda r: corridor_of(r, cfg["corridors"], "tx", "County"), axis=1)
    this_week = this_week.copy()
    this_week["corridor"] = this_week.apply(
        lambda r: corridor_of(r, cfg["corridors"], "tx", "County"), axis=1)
    for cor_name in cfg["corridors"]:
        cor_data = trailing90[trailing90["corridor"] == cor_name]
        lines.append(f"**Corridor — {cor_name}, trailing 90 days**\n")
        if len(cor_data):
            for operator, count in cor_data["Operator_Name"].value_counts().items():
                op_counties = ", ".join(sorted(set(
                    cor_data[cor_data["Operator_Name"] == operator]["County"])))
                lines.append(f"- {operator} — {count} ({op_counties})")
            cor_week = this_week[this_week["corridor"] == cor_name]
            lines.append(f"\nNew in this corridor this week: {len(cor_week)}")
        else:
            lines.append("- No permits in the trailing 90 days")
        lines.append("")


def section_data_notes(df, asof, lines):
    lines.append("## Data notes\n")

    errors = int(df["County_Label_Error"].sum())
    if errors:
        lines.append(f"- **{errors} rows still carry a stale Mc-block county "
                     f"label.** county_lookup.py may need the fix, or "
                     f"migrate_county_labels.py needs to run against this "
                     f"master — the lookup fix alone does not correct rows "
                     f"already on disk.")
    else:
        lines.append("- County labels check out against county_lookup.py "
                     "(Mc-block self-check passed)")

    reentries = int(df["is_reentry"].sum())
    if reentries:
        lines.append(f"- {reentries} records excluded from cycle statistics "
                     f"(spud predates issue — wellbore re-entries)")

    newest = df["Issue_Date"].max()
    if pd.notna(newest):
        stale = (asof - newest).days
        lines.append(f"- Newest issue date in master: {newest.date()} "
                     f"({stale} day(s) behind as-of date)")

    lines.append("- Permits age out of the rolling daily source pull after "
                 "~30 days; a permit's disappearance from new activity is "
                 "coverage boundary, not inactivity")
    lines.append("- **Spud conversion and permit-banking figures are floors.** "
                 "A permit that ages past the rolling window before spudding "
                 "never posts its spud date back to the source, so every "
                 "conversion figure here understates reality. Confirm against "
                 "a direct well-status query before either reaches a client.")
    lines.append(f"- Spud reporting lags ~{SPUD_LAG_DAYS} days; silence inside "
                 f"that window is not a signal")
    lines.append("")


def build_brief(cfg, asof):
    master = load_master(cfg, "tx")
    if master is None:
        raise SystemExit("No TX master found at the path in config.yaml — "
                         "run tx_daf420.py at least once first.")
    df = prep_tx(master)

    lines = [f"# Permit Market Brief — {asof.date()}\n"]
    lines.append("## Headline\n")
    lines.append("*[Write this last. Two to three sentences on what today's "
                 "activity means in context. If the day was unremarkable, "
                 "say so plainly.]*\n")

    section_today(df, asof, cfg, lines)
    section_week(df, asof, lines)
    section_month(df, asof, cfg, lines)
    section_patterns(df, asof, cfg, lines)
    section_data_notes(df, asof, lines)

    la_master = load_master(cfg, "la")
    if la_master is not None and len(la_master):
        lines.append("## Louisiana\n")
        lines.append(f"- {len(la_master)} records in the LA master. "
                     "Reported separately from TX by design — parish activity "
                     "and Texas county activity are not directly comparable, "
                     "and Haynesville spans the state line.")
        lines.append("- *(Parish-level rolling/cohort analysis not yet built "
                     "here — the LA REST layer per config.yaml has no BHL/line "
                     "geometry, only surface points, so some of the TX-side "
                     "metrics may not translate cleanly. Extend prep_tx's "
                     "twin for LA's field names before relying on this.)*\n")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--asof", help="YYYY-MM-DD (default: today)")
    parser.add_argument("--out", default="market_brief.md")
    args = parser.parse_args()

    cfg = load_cfg(args.config)
    asof = pd.Timestamp(args.asof) if args.asof else pd.Timestamp(datetime.now().date())

    text = build_brief(cfg, asof)

    with open(args.out, "w", encoding="utf-8") as handle:
        handle.write(text)

    print(text)
    print(f"\n---\nWritten to {args.out}")


if __name__ == "__main__":
    main()
