import pandas as pd
from common import family_of, corridor_of

def _fmt_depth(vals):
    vals = sorted(set(v for v in vals if pd.notna(v)))
    if not vals: return ""
    if len(vals) == 1: return f", {vals[0]:.0f}' TD"
    return f", {min(vals):.0f}-{max(vals):.0f}' TD"

def _group_line(g, area_field, fams=None):
    r0 = g.iloc[0]
    n = len(g)
    wells = sorted({str(x) for x in g.get("well_num", pd.Series(dtype=object)).dropna()})
    depth = _fmt_depth(g["depth"]) if "depth" in g.columns else ""
    area = str(r0.get(area_field, "")).title()
    fam = None
    if fams is not None and "_fam" in g.columns:
        fam_vals = g["_fam"].dropna().unique()
        fam = fam_vals[0] if len(fam_vals) else None
    fam_str = f"  _[{fam}]_" if pd.notna(fam) else ""
    name = r0.get("well") or r0.get("lease", "")
    if n == 1:
        return f"- **{r0['operator']}** — {name} ({area}{depth}){fam_str}"
    well_list = f" ({', '.join(wells)})" if wells else ""
    return f"- **{r0['operator']}** — {name}: {n} wells{well_list} ({area}{depth}){fam_str}"

def build_digest(state_label, new, amended, cfg, state_key, area_field):
    fams = cfg["operator_families"]; cors = cfg["corridors"]
    L = [f"# {state_label} Permit Intel — {pd.Timestamp.now():%a %b %d %Y}", ""]
    L.append(f"**{len(new)} new** | **{len(amended)} amended** vs master.\n")
    if len(new):
        new = new.copy()
        new["_fam"] = new["operator"].map(lambda o: family_of(o, fams))
        new["_cor"] = new.apply(lambda r: corridor_of(r, cors, state_key, area_field), axis=1)
        hits = new[new["_cor"].notna()]
        if len(hits):
            L.append("## Corridor hits (client-relevant)")
            for cor, g in hits.groupby("_cor"):
                L.append(f"\n### {cor}")
                for _, grp in g.groupby(["operator", "well"], dropna=False):
                    L.append(_group_line(grp, area_field, fams))
        watch = new[new["_fam"].notna() & new["_cor"].isna()]
        if len(watch):
            L.append("\n## Watched-family activity outside corridors")
            for _, grp in watch.groupby(["operator", "well"], dropna=False):
                r0 = grp.iloc[0]
                n = len(grp)
                wells = sorted({str(x) for x in grp.get("well_num", pd.Series(dtype=object)).dropna()})
                well_list = f" ({', '.join(wells)})" if wells and n > 1 else ""
                count = f": {n} wells{well_list}" if n > 1 else ""
                L.append(f"- {r0['_fam']}: {r0['operator']} — {str(r0.get(area_field,'')).title()}{count}")
        L.append("\n## All new permits by " + area_field)
        for a, g in new.groupby(new[area_field].astype(str).str.upper()):
            L.append(f"\n### {a.title()} ({len(g)})")
            for _, r in g.iterrows():
                name = r.get("well") or r.get("lease", "") or ""
                well_num = r.get("well_num")
                well_num_str = f" ({well_num})" if pd.notna(well_num) and str(well_num).strip() else ""
                L.append(f"- {r['operator']} — {name}{well_num_str}")
    if len(amended):
        L.append("\n## Amendments")
        for _, r in amended.head(40).iterrows():
            L.append(f"- {r['operator']} — {r.get('well') or r.get('lease','')} ({str(r.get(area_field,'')).title()})")
    L.append("\n---\n_New-entrant check: any operator above with no prior record in master is flagged NEW OPERATOR in new_permits.csv (col: first_seen)._")
    return "\n".join(L)
