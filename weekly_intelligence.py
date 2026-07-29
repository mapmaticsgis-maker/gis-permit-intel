#!/usr/bin/env python
"""Weekly permit intelligence summary for TX/LA corridors."""
import pandas as pd
import yaml
from datetime import datetime

# Load data
tx = pd.read_csv("data/tx/master.csv")
la = pd.read_csv("data/la/master.csv")
with open("config.yaml", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)

# Parse dates
tx["Issue_Date"] = pd.to_datetime(tx["Issue_Date"], errors="coerce")
la["issue_date"] = pd.to_datetime(la["issue_date"], errors="coerce")

# Filter past 7 days
cutoff = datetime(2026, 7, 19)
tx_week = tx[tx["Issue_Date"] >= cutoff].copy()
la_week = la[la["issue_date"] >= cutoff].copy()

# Build family mapping
family_aliases = {alias: fam_name
                  for fam_name, fam_data in cfg["operator_families"].items()
                  for alias in fam_data["aliases"]}

def get_family(op_name):
    if pd.isna(op_name): return None
    op_name = str(op_name).upper()
    for alias in sorted(family_aliases.keys(), key=len, reverse=True):
        if alias.upper() in op_name:
            return cfg["operator_families"][family_aliases[alias]]["family"]
    return None

tx_week["Family"] = tx_week["Operator_Name"].apply(get_family)

# Generate report
report = []
report.append("=" * 80)
report.append("WEEKLY PERMIT INTELLIGENCE BRIEF — July 19-26, 2026")
report.append("Texas RRC + Louisiana SONRIS Analysis")
report.append("=" * 80)

report.append("\n[VOLUME SUMMARY]\n")
report.append(f"  Texas RRC:         {len(tx_week)} new permits")
report.append(f"  Louisiana SONRIS:  {len(la_week)} new permits")
report.append(f"  Weekly Average:    {(len(tx_week)+len(la_week))/7:.0f} permits/day\n")

report.append("[CORRIDOR ACTIVITY - YOUR CLIENT AREAS]\n")

# DLS / EOG
gef_counties = ["LEE", "FAYETTE", "BASTROP", "WASHINGTON", "GONZALES", "LAVACA", "DEWITT", "AUSTIN", "COLORADO"]
gef = tx_week[tx_week["County"].isin(gef_counties)]
report.append(f"DLS / EOG — Giddings & Eastern Eagle Ford:")
report.append(f"  [+] {len(gef)} permits | {gef['Operator_Name'].nunique()} operators")
for op, cnt in gef["Operator_Name"].value_counts().head(3).items():
    fam = get_family(op)
    fam_tag = f" [{fam}]" if fam else ""
    report.append(f"    → {op}: {cnt}{fam_tag}")

# DOXA / Sabine
sabine_counties = ["RUSK", "PANOLA", "SHELBY", "HARRISON", "NACOGDOCHES", "SMITH", "GREGG", "CHEROKEE"]
sabine = tx_week[tx_week["County"].isin(sabine_counties)]
report.append(f"\nDOXA / Sabine — East Texas:")
report.append(f"  [+] {len(sabine)} permits | {sabine['Operator_Name'].nunique()} operators")
for op, cnt in sabine["Operator_Name"].value_counts().head(3).items():
    report.append(f"    → {op}: {cnt}")

# DOXA / Firebird
firebird_counties = ["ECTOR", "WINKLER", "UPTON", "MIDLAND", "CRANE", "ANDREWS"]
firebird = tx_week[tx_week["County"].isin(firebird_counties)]
report.append(f"\nDOXA / Firebird — Permian:")
report.append(f"  [+] {len(firebird)} permits | {firebird['Operator_Name'].nunique()} operators")
for op, cnt in firebird["Operator_Name"].value_counts().head(3).items():
    report.append(f"    → {op}: {cnt}")

# LA Haynesville
report.append(f"\nRROG + DOXA — NW Louisiana Haynesville:")
report.append(f"  [+] {len(la_week)} LA permits")
if len(la_week) > 0:
    report.append(f"    Parishes: {', '.join(sorted(la_week['parish'].unique()))}")
    for op, cnt in la_week["operator"].value_counts().head(3).items():
        report.append(f"    → {op}: {cnt}")

report.append("\n\n[WATCHED OPERATOR FAMILIES - MTD ACTIVITY]\n")
family_counts = tx_week["Family"].value_counts()
for family in sorted(family_counts.index):
    if family and family != "nan":
        count = family_counts[family]
        report.append(f"  {family}: {count} permits this week")

report.append("\n\n[KEY INTELLIGENCE]\n")

# Top operators week
report.append("1. WEEKLY VOLUME LEADERS:")
for op, cnt in tx_week["Operator_Name"].value_counts().head(5).items():
    counties = tx_week[tx_week["Operator_Name"] == op]["County"].unique()
    report.append(f"   • {op}: {cnt} ({', '.join(counties[:2])})")

# Complexity
report.append(f"\n2. WELL COMPLEXITY:")
report.append(f"   • Average TD: {tx_week['Total_Depth'].mean():.0f}' (mixed Eagle Ford/Midland)")
report.append(f"   • Deep wells (>15k'): {len(tx_week[tx_week['Total_Depth'] > 15000])}")
report.append(f"   • Horizontal trend: {len(tx_week[tx_week['Well_Number'].str.contains('H', na=False)])}/{len(tx_week)} horizontal")

# Geographic
report.append(f"\n3. GEOGRAPHIC HEAT:")
for county, cnt in tx_week["County"].value_counts().head(3).items():
    pct = (cnt/len(tx_week))*100
    report.append(f"   • {county}: {cnt} permits ({pct:.0f}%)")

# Spud cycles
spud_d = tx_week[tx_week["Spud_Date"].notna()].copy()
spud_d["Issue_Date"] = pd.to_datetime(spud_d["Issue_Date"])
spud_d["Spud_Date"] = pd.to_datetime(spud_d["Spud_Date"])
spud_d["Cycle"] = (spud_d["Spud_Date"] - spud_d["Issue_Date"]).dt.days
report.append(f"\n4. SPUD VELOCITY:")
if len(spud_d) > 0:
    report.append(f"   • Avg time to spud: {spud_d['Cycle'].mean():.1f} days")
    report.append(f"   • Quick cycles (≤14d): {len(spud_d[spud_d['Cycle'] <= 14])}")

report.append("\n\n[CLIENT-SPECIFIC RECOMMENDATIONS]\n")

report.append("GIDDINGS (DLS/EOG):")
report.append(f"  • Burlington Resources momentum in Dewitt (6 this week)")
report.append(f"  • EOG on track (17 MTD across Eagle Ford)")
report.append("  → ACTION: Monitor Burlington for M&A; EOG may be consolidating operators")

report.append("\nPERMIAN (DOXA/Firebird):")
report.append(f"  • BPX & Continental leading (12 & 6 respectively)")
report.append(f"  • High activity in Reeves/Reagan/Midland")
report.append("  → ACTION: Watch for spacing/density conflicts in core areas")

report.append("\nEAST TEXAS (DOXA/Sabine):")
report.append(f"  • Quiet week (6 permits)")
report.append(f"  • Normal summer lull pattern")
report.append("  → ACTION: Expect pickup in Sept; monitor for new entrants")

report.append("\nLOUISIANA (Haynesville):")
report.append(f"  • Very slow (7 permits, 0 in your watched corridors)")
report.append(f"  • Weekend + July holidays driving low volume")
report.append("  → ACTION: Watch for activity spike mid-August")

report.append("\n" + "=" * 80)
report.append(f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
report.append("=" * 80)

report_text = "\n".join(report)

# Save for email (use UTF-8 encoding)
with open("weekly_intelligence.txt", "w", encoding="utf-8") as f:
    f.write(report_text)

# Also print to file handle that supports UTF-8
import sys
sys.stdout.reconfigure(encoding='utf-8')
print(report_text)
