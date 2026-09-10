# Apex Abstract Dashboard — 2026-09-09 Iteration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use `- [ ]`.

**Goal:** Update the Apex Abstract & Title Status dashboard (Jolie Adams') for: (1) "% complete" measuring the **abstract** stage rather than TO-received (client request); (2) the final whole-branch review's C1 + I2 findings (map/status contradiction, rollup denominators); (3) the new **09/04/2026** report (11 sections — 2 new LA units, cycle-2 data, new edge cases); (4) staging 2 Nacogdoches TX EOG units (Barton, Kendrick — plats in hand, abstract data pending).

**Architecture:** Same disk-only repo `C:\GIS\CLIENT\RROG\DASHBOARD\` (own git, on `master`, HEAD `f504a3c`). Additive/in-place edits to the abstract modules only. The RROG leasing dashboard (`build_rrog_dashboard.py`, `template.html`) and its tests must stay untouched and green.

**Tech Stack:** ArcGIS Pro Python (`C:\Program Files\ArcGIS\Pro\bin\Python\envs\arcgispro-py3\python.exe` = `PYEXE`). No new installs.

## Global Constraints

- **Interpreter:** always `PYEXE`. System Python has no GDAL.
- **Do not break the RROG leasing dashboard:** after every task `"$PYEXE" -m pytest -q` stays green (198 baseline + new) AND `"$PYEXE" build_rrog_dashboard.py` still produces `RROG_Dashboard.html` byte-identical (2,729,247 B). Only the abstract modules (`rrog/abstract_report.py`, `rrog/abstract_render.py`, `rrog/abstract_diff.py`, `abstract_template.html`, `build_abstract_dashboard.py`) + appends to `rrog/__init__.py` may change. `template.html`, `build_rrog_dashboard.py`, `rrog/render.py`, `rrog/geometry.py` are frozen.
- **Deliverable:** `C:\GIS\CLIENT\RROG\DASHBOARD\Apex_Abstract_Status.html` — one offline file, no external requests but basemap tiles, never `cartocdn`.
- **"% complete" semantics (client directive, 2026-09-09):** the headline / overview-column percentage counts tracts whose **abstract is complete** — rung is `abstract_submitted`, `in_review`, or `to_received` — over the non-3rd-party denominator. NOT the `to_received`-only count. Keep the TO-received fraction available as a secondary figure.
- **Rung ladder (unchanged):** `not_started → working → abstract_submitted → in_review → to_received`. `_PROGRESS_RANK` in `rrog/abstract_diff.py` is the ordering source.
- **Colours (unchanged):** `to_received` `#1B7A1B`, `in_review` `#0EA5A5`, `abstract_submitted` `#99FF99`, `working` `#FFA500`, `not_started` `#BFBFBF`.
- **Section-status authority (spec §6):** `ALL SECTIONS` `STATUS` is Jolie's word. `TITLE COMPLETE` / `HOLD PER TL` override the section badge AND the overview-map polygon fill, never the per-tract table or the rollup.
- **New report file:** `data/Apex_Abstract Status Report_9.4.2026.xlsx` (already copied). Prior: `data/Apex_Abstract Status Report_5.29.2026.xlsx`.
- **Commits:** conventional messages + `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>` trailer, in the DASHBOARD repo on `master`. The `permit_intel` `apex-abstract-iteration` branch holds only this plan + the spec append + memory.
- **Spec:** `docs/superpowers/specs/2026-09-01-apex-abstract-status-dashboard-design.md` (+ a `## 2026-09-09 iteration` append is part of Task 3).

---

## Investigation already done (controller, 2026-09-09)

- **9.4.2026 workbook: 11 section sheets** — `29-17N-12W, 32-17N-12W, 36-16N-14W, 3-16N-13W, 4-16N-13W, 1-15N-14W, 12-15N-14W, 5-12N-12W, 4-11N-11W, 34-11N-12W, 19&30-10N-10W`. `ALL SECTIONS` key `10N-10W-19&30` → `canon_section` already yields `19&30-10N-10W` (verified). Two new: `5-12N-12W` (Unit 164, DeSoto), `19&30-10N-10W` (Unit 149, Natchitoches). Both blank FRAC DATE.
- **Current parser against 9.4.2026:** parses 10/11 sheets fine. **`19&30-10N-10W` → 0 tracts** because that sheet's tract-# column (O) is blank on every row — tract identity is only the **tract name** in column P (`MOFFETT, ET AL`, `HOLLOWAY FARMS`, …). Parser stops at the first blank tract cell (`abstract_report.py:331`).
- **`WORKING ON CURATIVE`** appears in the TO-Received column (e.g. `34-11N-12W` tracts 4-6) — parser currently classifies these `abstract_submitted` (correct: curative is post-abstract, pre-final-TO), but the state is meaningful to Jolie.
- **Geometry:**
  - `19&30-10N-10W` → `C:\GIS\CLIENT\RROG\19-3010N10W.shp` exists. `TR_NO` is all `0`; the **`NAME`** field holds owner/tract names (`MOFFETT, ET AL`, `HOLLOWAY FARMS`) that match the workbook's `tract_name`. **Join on NAME, not number.**
  - `5-12N-12W` → no bare shapefile found; `C:\PDF\LA-DES_512N12W_ABS.pdf` exists. Try `.gdb TRACTS` filter (SEC=5 TWP=12N RNG=12W), else PDF-image fallback.
  - **Barton / Kendrick (Nacogdoches TX)** → no shapefiles. TX abstract/survey system (no PLSS sections). Plats: `C:\Users\mapma\Downloads\Barton Unit - Exhibit C.pdf` (Barton Gas Unit, EOG, 850.51 ac, 18 tracts) and `C:\Users\mapma\Downloads\Kendrick Plat.pdf` (Kendrick Gas Unit, EOG, 881.96 ac, 14 tracts). **PDF-image fallback from the plats.** NOT in the 9.4.2026 workbook — Jolie will add the section sheets later. Task 3 stages them so a later rebuild picks them up.
- **Final-review C1:** `abstract_template.html:450` `titleFill` keys only on `HOLD PER TL`; `TITLE COMPLETE` sections colour by `pct` (→ `4-11N-11W` @44% renders amber though its status is TITLE COMPLETE; `12-15N-14W` @100% renders green though its status is WORKING).
- **Final-review I2:** `abstract_report.py:372-378` rollup `pct` divides by `total` (all tracts) while the headline `pct` (`:379-384`) divides by non-3rd-party `counted` — same panel, contradictory numbers.

---

## Task 1: Parser — abstract-complete %, rollup denominators, blank-tract sheets, curative

**Files:**
- Modify: `rrog/abstract_report.py`, `rrog/__init__.py`
- Test: `tests/test_abstract_report.py`

**Interfaces:**
- `SectionAbstract` gains `abstract_complete_pct: float` (append after `title_complete_pct`; keep `title_complete_pct` as-is = the TO-received fraction, still non-3rd-party denominator). Both are `float` in `[0,1]`.
- `TractRung` gains `join_name: str | None` — the tract-name used as the geometry join key when `key` is a synthesized placeholder (`None` otherwise).
- `rung_of` unchanged. `canon_section` unchanged (already handles `19&30-10N-10W`).

- [ ] **Step 1: VC setup.** DASHBOARD repo on `master`, HEAD `f504a3c`. In `permit_intel`: `git checkout -b apex-abstract-iteration`.

- [ ] **Step 2: Failing tests** in `tests/test_abstract_report.py` (characterization against `data/Apex_Abstract Status Report_9.4.2026.xlsx` — confirm the exact numbers by opening the file first, then lock):

```python
import pathlib
from rrog.abstract_report import parse_abstract_report

WB94 = pathlib.Path(__file__).resolve().parent.parent / "data" / "Apex_Abstract Status Report_9.4.2026.xlsx"

def test_94_has_11_sections():
    r = parse_abstract_report(WB94)
    assert len(r.sections) == 11
    assert "5-12N-12W" in r.sections and "19&30-10N-10W" in r.sections

def test_1930_blank_tract_numbers_still_parse():
    s = parse_abstract_report(WB94).sections["19&30-10N-10W"]
    assert len(s.tracts) >= 2                       # was 0
    t0 = s.tracts[0]
    assert t0.tract_name and "MOFFETT" in t0.tract_name.upper()
    assert t0.join_name == t0.tract_name            # name is the join key
    assert t0.key                                   # a non-empty synthesized key

def test_abstract_complete_pct_counts_abstract_stage():
    s = parse_abstract_report(WB94).sections["34-11N-12W"]
    # tracts at abstract_submitted / in_review / to_received all count toward abstract_complete_pct
    counted = [t for t in s.tracts if "3rd_party" not in t.tags]
    done = [t for t in counted if t.rung in ("abstract_submitted", "in_review", "to_received")]
    assert abs(s.abstract_complete_pct - len(done)/len(counted)) < 1e-9
    assert s.abstract_complete_pct >= s.title_complete_pct    # abstract-done is a superset of TO-received

def test_rollup_pct_matches_headline_denominator():
    s = parse_abstract_report(WB94).sections["12-15N-14W"]
    counted = sum(1 for t in s.tracts if "3rd_party" not in t.tags)
    # every rollup pct is over the non-3rd-party count, so they sum to ~1.0 (minus any 3rd_party-only rungs)
    assert abs(sum(v["pct"] for v in s.rollup.values()) - 1.0) < 0.05

def test_working_on_curative_tag():
    s = parse_abstract_report(WB94).sections["34-11N-12W"]
    cur = [t for t in s.tracts if "curative" in t.tags]
    assert cur and all(t.rung == "abstract_submitted" for t in cur)

def test_529_still_parses():        # prior report must still parse identically for the diff
    r = parse_abstract_report(pathlib.Path(__file__).resolve().parent.parent/"data"/"Apex_Abstract Status Report_5.29.2026.xlsx")
    assert len(r.sections) == 9
```

- [ ] **Step 3: Run RED.** `"$PYEXE" -m pytest tests/test_abstract_report.py -q` — new tests fail.

- [ ] **Step 4: Implement.**
  - `rrog/__init__.py`: add `abstract_complete_pct: float` to `SectionAbstract` (after `title_complete_pct`), `join_name: str | None = None` to `TractRung`. Pure append/field-add — verify every existing `SectionAbstract(...)` / `TractRung(...)` construction still works (they are keyword-constructed).
  - `abstract_report.py` table-end check (`~:331`): break only when **both** the tract-# cell AND the tract-name cell (`c_name`) are blank. When tract-# is blank but name is present: `key = f"t{n}"` (1-based sequential within the section), `tract_ids = []`, `join_name = name`. When tract-# present: unchanged, `join_name = None`.
  - Rollup (`~:372`): `denom = len(counted)` (non-3rd-party); `rollup[r]["pct"] = count_r_in_counted / denom`. `rollup[r]["tracts"]` stays the full count (or switch to the counted count — pick one and note it; the template shows the count next to the bar). Keep `tracts` = all-tracts count for continuity, `pct` = counted-denominator.
  - `abstract_complete_pct = len([t for t in counted if _rank(t.rung) >= _rank("abstract_submitted")]) / len(counted)` (0.0 if no counted tracts). Import the rank from `rrog.abstract_diff` (`_PROGRESS_RANK`) or define a local `_ABSTRACT_DONE = {"abstract_submitted","in_review","to_received"}` set — set membership is simpler and rank-independent; use the set.
  - `curative` tag: in `_tract_tags` (or inline), add `"curative"` when the TO cell matches `WORKING ON CURATIVE` (case-insensitive). Rung stays whatever `rung_of` returned.

- [ ] **Step 5: Run GREEN** + full suite (`"$PYEXE" -m pytest -q` — 198 + new, all green) + `"$PYEXE" build_rrog_dashboard.py` unaffected.

- [ ] **Step 6: Commit** — `feat(abstract): abstract-complete %, rollup denominators, blank-tract & curative handling`.

---

## Task 2: Payload + template — relabel, C1 map/status fix, name-join

**Files:**
- Modify: `rrog/abstract_render.py`, `abstract_template.html`
- Test: `tests/test_abstract_render.py`

**Interfaces (payload additions — the template DEV_STUB must mirror them):**
- `overview[i]` and `sections[k]` gain `abstract_complete_pct` and `to_received_pct` (= the old `title_complete_pct`). Keep emitting `title_complete_pct` too (alias of `to_received_pct`) for one release so nothing breaks mid-change; the template reads the new names.
- Each `all_sections_boundaries` feature property set: `{section, status, abstract_complete_pct, to_received_pct}`.
- `sections[k].map` features: when the section's geometry is name-keyed (Task 1 `join_name`), `join_section` matches `feature NAME` (case-insensitive, trimmed) to `TractRung.join_name`. Add a `join_field` arg or detect: if >50% of the section's `TractRung`s have `join_name`, join on name.

- [ ] **Step 1: Failing tests** in `tests/test_abstract_render.py`:

```python
def test_payload_carries_both_pcts():
    from rrog.abstract_report import parse_abstract_report
    from rrog.abstract_render import abstract_payload, build_section_geoms
    import pathlib
    wb = pathlib.Path(__file__).resolve().parent.parent/"data"/"Apex_Abstract Status Report_9.4.2026.xlsx"
    rep = parse_abstract_report(wb)
    p = abstract_payload(rep, build_section_geoms(rep, pathlib.Path(__file__).resolve().parent.parent/"data"), {"type":"FeatureCollection","features":[]})
    row = next(r for r in p["overview"] if r["section"] == "34-11N-12W")
    assert "abstract_complete_pct" in row and "to_received_pct" in row
    assert row["abstract_complete_pct"] >= row["to_received_pct"]
    b = next(f for f in p["all_sections_boundaries"]["features"] if f["properties"]["section"] == "4-11N-11W")
    assert b["properties"]["status"] == "TITLE COMPLETE"

def test_1930_name_join_covers_tracts():
    from rrog.abstract_report import parse_abstract_report
    from rrog.abstract_render import build_section_geoms
    import pathlib
    d = pathlib.Path(__file__).resolve().parent.parent/"data"
    rep = parse_abstract_report(d/"Apex_Abstract Status Report_9.4.2026.xlsx")
    g = build_section_geoms(rep, d).get("19&30-10N-10W")
    assert g is not None and g.mode == "live" and (g.coverage or 0) > 0
```

- [ ] **Step 2: RED.**
- [ ] **Step 3: Implement.**
  - `abstract_render.py`: emit `abstract_complete_pct` / `to_received_pct` (from `SectionAbstract`) into `overview`, `sections`, and `all_sections_boundaries` feature props. Keep `title_complete_pct` alias.
  - `join_section` / `build_section_geoms`: add name-join. Copy `19-3010N10W.shp` sidecars into `data/` in Task 3 (CONFIGS), but the join logic lands here: if the `SectionAbstract`'s tracts are majority `join_name`-bearing, match on the geometry layer's name-ish field (`NAME`, else `OSR_NAME`, else `TN`) normalized (upper/trim/collapse spaces).
  - `abstract_template.html`:
    - `columns` (`~:489`): the `title_complete_pct` column → `{k:"abstract_complete_pct", t:"Abst %", num:true}`; `miniBar` reads `r.abstract_complete_pct`.
    - Level-2 headline (`~:586`): render `"Abstract complete " + pct(det.abstract_complete_pct)` as the big number, with a smaller line `"TO received " + pct(det.to_received_pct)` beneath.
    - `titleFill` (`~:450`) — **C1 fix**:
      ```js
      function titleFill(p, status){
        var u = (status||"").toUpperCase();
        if (u.indexOf("HOLD PER TL") >= 0)    return {c:"#BFBFBF", hold:true};
        if (u.indexOf("TITLE COMPLETE") >= 0) return {c:"#1B7A1B"};
        if (p == null) return {c:"#BFBFBF", nodata:true};
        if (p >= 0.75) return {c:"#99FF99"};
        if (p >= 0.25) return {c:"#FFA500"};
        return {c:"#BFBFBF"};
      }
      ```
      and its call site (`~:826`) passes `f.properties.abstract_complete_pct` (not `title_complete_pct`). Legend (`~` the legend block): top entry `"Title complete (status)"`, then `"≥ 75% abstracted"`, `"≥ 25% abstracted"`, `"< 25% / none"`, `"Hold per TL (hatched)"`. Give `nodata` a no-fill dashed style distinct from `< 25%`.
    - Rung-rollup bars (`~:571`): the `e.pct` values now already sum to ~1 over the non-3rd-party denominator (Task 1); label the block header `"Rung rollup — <N> Apex tracts"` where N = the non-3rd-party count, so the denominator is explicit. Show 3rd-party tracts as a separate greyed count line, not a ladder bar.
    - Level-2 header status chip and the headline must not contradict: if status is `TITLE COMPLETE`, the chip stays green and a small note `"attorney-signed complete"` sits by the headline even when `abstract_complete_pct < 1`.
  - Update the DEV_STUB in `abstract_template.html` to carry `abstract_complete_pct` + `to_received_pct` (+ keep it placeholder-only).

- [ ] **Step 4: GREEN + full suite. Browser-check** `Apex_Abstract_Status.html` after Task 3 builds it — deferred to Task 3 Step 5 (needs the real build). For now assert `render_abstract` still strips cleanly via the existing render test.
- [ ] **Step 5: Commit** — `feat(abstract): relabel to Abstract %, fix map/status agreement, name-based tract join`.

---

## Task 3: Orchestrator — geometry, prior/Change view, TX unit staging, rebuild, verify, memory

**Files:**
- Modify: `build_abstract_dashboard.py`, `docs/abstract_known_issues.md`
- Modify: `docs/superpowers/specs/2026-09-01-apex-abstract-status-dashboard-design.md` (append `## 2026-09-09 iteration`)
- Create: memory file update; `MEMORY.md` pointer already exists — update its line
- Copy into `data/`: `19-3010N10W.*` sidecars; `Barton Unit - Exhibit C.pdf`, `Kendrick Plat.pdf`

- [ ] **Step 1: Geometry + CONFIGS.**
  - Copy `C:\GIS\CLIENT\RROG\19-3010N10W.{shp,shx,dbf,prj,cpg,shp.xml}` → `data/`.
  - `5-12N-12W`: try `discover_tract_layer(data_dir, "5-12N-12W")` and a `.gdb TRACTS` filter (`SEC='5' AND TWP='12N' AND RNG='12W'`); if neither yields per-tract polygons, set `fallback_pdfs["5-12N-12W"] = r"C:\PDF\LA-DES_512N12W_ABS.pdf"` and let it go image-mode.
  - `19&30-10N-10W`: pin `data/19-3010N10W.shp`, name-join (Task 2). `fallback_pdfs["19&30-10N-10W"] = r"C:\PDF\LA-NCT_193010N10W_ABS.pdf"`.
  - `CONFIGS["prior"] = "data/Apex_Abstract Status Report_5.29.2026.xlsx"` — **the Change view activates.** `main()` already has the `diff_abstract` path; verify it fires and the payload `change` is non-null with real content (the 9.4 report has several `CHANGES FROM LAST REPORT = YES`).
  - `CONFIGS["workbook"]` → point at `9.4.2026` (or leave `None` = newest-by-mtime, which is now 9.4.2026 — confirm).
- [ ] **Step 2: Stage the 2 Nacogdoches TX units.**
  - Copy `Barton Unit - Exhibit C.pdf` and `Kendrick Plat.pdf` → `data/`.
  - Add a `CONFIGS["staged_units"]` (or commented block) mapping the section keys Jolie is expected to use (`BARTON` / `KENDRICK`, or `Barton Gas Unit` / `Kendrick Gas Unit` — note the guess) → `{fallback_pdf: "data/Barton Unit - Exhibit C.pdf", parish: "Nacogdoches", state: "TX", statefp: "48"}`.
  - `main()`: when a workbook section sheet's `canon_section` / parish resolves to a TX unit (parish text contains `Nacogdoches` or the sheet is in `staged_units`), (a) skip the LA `.gdb`/shapefile hunt, (b) use the staged plat PDF as the image-mode map, (c) call `load_context_geojson` with `statefp="48"` + `("Nacogdoches",)`. These paths must be inert this cycle (no such sheet in 9.4.2026) — guarded so the build is unchanged, just ready.
  - Note in the build report + known-issues: "Barton / Kendrick staged (plats in `data/`); will render image-mode once their section sheets appear in the report."
- [ ] **Step 3: Failing test** `tests/test_abstract_build.py` — extend:

```python
def test_build_94_report_and_change_view():
    # (subprocess build already asserted rc0 + tokens stripped by the existing test)
    import json, pathlib
    D = pathlib.Path(__file__).resolve().parent.parent
    h = (D/"Apex_Abstract_Status.html").read_text(encoding="utf-8")
    assert "report 09/04/2026" in h or "09/04/2026" in h
    assert "Abst %" in h                      # relabelled column
    m = __import__("re").search(r'<script id="apx-payload"[^>]*>(.*?)</script>', h, __import__("re").S)
    p = json.loads(m.group(1))
    assert len(p["overview"]) == 11
    assert p["change"] is not None            # prior wired
    assert any(r["section"] == "5-12N-12W" for r in p["overview"])
```

- [ ] **Step 4: RED → implement → GREEN + full suite.** `"$PYEXE" build_abstract_dashboard.py` clean; `"$PYEXE" build_rrog_dashboard.py` still byte-identical; `git status` clean (both HTMLs + both build reports git-ignored).
- [ ] **Step 5: Browser-verify** `Apex_Abstract_Status.html` (serve `"$PYEXE" -m http.server 8801`): 11 sections in the queue; overview column reads **Abst %**; `4-11N-11W` (TITLE COMPLETE) polygon is **green** on the all-sections map and its Level-2 chip agrees with the headline; `12-15N-14W` (WORKING, 100% TO) polygon is **not** green (status WORKING → coloured by abstract %); `19&30-10N-10W` renders with tracts (name-join) or a clean image fallback; a **"Changes since last report"** strip shows on sections flagged YES; rung bars sum sensibly; click a section → detail; back; theme toggle; no console errors. Screenshot notes in the report.
- [ ] **Step 6: Spec append + known-issues + memory.**
  - Spec `## 2026-09-09 iteration`: the % semantics change; the 09/04 report (11 sections); blank-tract-# name-join; `WORKING ON CURATIVE` tag; Change view now live; Barton/Kendrick staged.
  - `docs/abstract_known_issues.md`: strike the now-fixed C1/I2 lines; strike the stale entries flagged by the final review (`build_abstract_dashboard.py:339` unwrapped return; `rrog.render._DEFERRED_STATUS` bad attribution → it's `abstract_render._DEFERRED_STATUS`); add the residual final-review minors still open (M2 dead `_round`, M5 test overwrites the artifact, M6 no dual-template render test, `12-15N-14W` 100%-TO-but-WORKING stays in active queue, `5-12N-12W` geometry mode, Barton/Kendrick staged-not-wired).
  - Memory `project_apex_abstract_dashboard.md`: update to note the 09/04 cycle, the abstract-vs-TO % semantics, the Change view being live, the 2 pending TX units.
- [ ] **Step 7: Commit** — `feat(abstract): 09/04 report, Change view live, 2 new LA sections, TX unit staging`.
- [ ] **Step 8:** invoke `superpowers:finishing-a-development-branch` (base = `master`).

---

## Self-Review

**Coverage:** client % directive → Task 1 (`abstract_complete_pct`) + Task 2 (relabel, headline). C1 → Task 2 (`titleFill`). I2 → Task 1 (rollup denom) + Task 2 (bar labels). 09/04 report → Task 1 (parse, `19&30` fix, curative) + Task 3 (geometry, rebuild). Change view → Task 3 (`prior`). 2 TX units → Task 3 (staging). RROG-safety → Global Constraint + every task's Step 5/4.

**Placeholder scan:** the `5-12N-12W` geometry outcome and the exact Barton/Kendrick section-key strings are genuine build-time unknowns with documented fallbacks (image mode; staged block with a noted guess). No TBD.

**Type consistency:** `SectionAbstract` / `TractRung` field additions defined once (Task 1), consumed in Task 2 payload + Task 3. `abstract_complete_pct` / `to_received_pct` names identical across `abstract_report.py` → `abstract_render.py` → `abstract_template.html`. `join_name` set in Task 1, read by `join_section` in Task 2.
