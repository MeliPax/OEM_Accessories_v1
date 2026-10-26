# 003 — Accessory Ingest + Model Number Matching: Design

**Status:** Idea — all decisions (A1–A9) made 2026-10-26; plan: [plans/003](../plans/003_accessory_model_matching.md)
**Builds on:** [001 VW model ingest](001_vw_model_ingest_design.md) (`db/final/vehicles.csv`), [002 logging](002_pipeline_logging_design.md)
**Source:** `datasets/2026_10_20_VW Canada Accessories Data EN.xlsx`, explored in `oem_access_data_analysis.ipynb`

## Goal

Process the accessories file the way the notebook does today, but **before** building the per-model dict, attach the VW model numbers each accessory fits. The match must use the **same config** as the vehicle ingest (`models.yaml`, `pipeline.yaml`), so there's one source of truth for what "Golf GTI 2024" means on both sides.

## Requirement: an accessory fits its whole specified set (2026-10-26)

> An accessory applies to **all** vehicles in the set it specifies: its year range plus the model / submodel it names. Every model number in that set matches and is applicable to the part.

So the fitment rule is set membership, not a best-match search:

```
fits(part, vehicle)  ⇔  vehicle.make     = part.make
                      ∧ vehicle.model    = part.model
                      ∧ vehicle.submodel = part.submodel        (empty = base model; see A2)
                      ∧ vehicle.year     ∈ part's year range, clipped to the window
```

- **No ranking, no scoring, no "best" model number.** Every vehicle in the set is attached.
- **Nothing narrows the set** beyond the fields the accessory specifies. Product descriptions are not used to include or exclude vehicles (A4 resolved).

## What the accessory data looks like

Profiled 2026-10-26 (sheet `Sheet1`, 24,396 rows, first data row holds the real headers):

| Finding | Impact on design |
|---|---|
| 20,399 Active rows; 13,051 inside the 2020+ window | Same `status = Active` filter and year window as the notebook |
| **13,051 rows collapse to 1,357 unique (part, model) rows.** The repeats are exact copies; no column differs | Deduplicate on (part_number, model_name), and log how many were removed |
| Each (part, model) has exactly one `year range` (e.g. `2018-2024`, `1990-2026`) | Expand to one row per applicable year, clipped to the window (D15) |
| 448 unique parts; 186 of them are listed for more than one model | Part number alone is not the key; (part_number, model_name) is |
| **14 model names**, all of which map to `models.yaml` with **one alias**: `GTI` → `Golf GTI` | The accessory side can use the same model / submodel parser as the vehicle side |
| Submodels are listed separately: `Golf`, `GTI`, `Golf R` / `Jetta`, `Jetta GLI` / `Atlas`, `Atlas Cross Sport` | Accessory `Golf` means the **base** Golf only, not GTI or R. Match on model **and** submodel |
| Accessory years run to 2026; vehicle years to 2027 | 2027 vehicles get no accessories until the accessory file covers 2027 (expected) |
| `productDescription` rarely says anything about fitment. Real qualifiers in ~10 descriptions: `for R-Line` / `not for R-Line` (mud flaps), `Trunk Liner 4Motion (AWD)`, `Peak Edition` (wheel, mud flaps) | Not used for matching: an accessory fits its whole specified set (A4). Noted in the run log only |
| Running the vehicle vocabulary over product descriptions gives **false positives**: `Black` (colour, 65 descriptions), `Dune` (mat colour), `PRO` (Thule T2 Pro) | Do **not** parse product descriptions with `keywords.yaml` |
| `specialNote`, `applicationNotes`, `dealerNotes` are marketing / install text, not fitment | Not used for matching |

## The idea: resolve each unique (model name, year) once, then attach

The match is a **lookup, not a merge.** The accessory file has thousands of part-years but only a handful of distinct keys, so the vehicle DB is searched once per key, and the answers are attached while building the per-model dict.

```
accessories.xlsx (1,357 part/model rows)              db/final/vehicles.csv (269 vehicles)
        |                                                       |
        | 1. resolve the 14 unique model names once             | 3. build the lookup once:
        |    "GTI" -> alias "Golf GTI" -> Golf / GTI            |    group by (model, submodel, model_year)
        |    (same clean + match_model() as the vehicle side)   |    -> sorted model numbers
        v                                                       v
 2. unique (model_name, year) keys: 71              {(Golf, GTI, 2023): [model numbers], ...}  69 groups
        +------------- 4. fetch: 71 dict lookups --------------+
                                  |      hit  -> model numbers (logged: key -> count + numbers)
                                  |      miss -> flag once per key; reason from vehicles/<model>.yaml (A9):
                                  |              year declared, no vehicle in DB -> model_number_not_found
                                  |              year not declared               -> model_not_offered
                                  v
 5. build_model_year_dict(): explode each part to its applicable years (as today),
    then attach the fetched model numbers with one vectorized map on (model_name, year)
                                  |
                                  v
          {"GTI": DataFrame[part_number, ..., applicable_year, model_number], "Jetta": ..., ...}
```

**The search key is `(make, model, submodel, model_year)`:**

- **Canonical values, not free text.** The accessory model name goes through the same `clean_helpers` and `parse_helpers.match_model()` as the vehicle descriptions, driven by `models.yaml`. So `GTI` and `Golf GTI Autobahn Manual` both end up as `Golf` / `GTI`. The lookup is an exact dictionary hit, with no fuzzy matching.
- **Submodel is part of the key.** An empty submodel means the base model (A2).
- **A readable `match_key`** such as `volkswagen|golf|gti|2023` is logged for every lookup, so every attached model number can be traced to one log line.

**Why this is efficient:**

| | Record by record | Lookup by key |
|---|---|---|
| Model-name parses | 1,357 (one per row) | **14** (one per unique name) |
| Vehicle DB searches | 6,474 (one per part-year) | **71** (one per unique model name + year) |
| Building the vehicle index | per search | **once**, one `groupby` over 269 rows |
| Attaching | a join per row | **one vectorized `map`**, then `explode` |

Nothing joined is saved. The vehicle DB is read with only the columns needed (model, submodel, model_year, model_number, vehicle_id), the lookup lives in memory, and the result is the dict.

**What it gives on today's data (estimate):**

| | Count |
|---|---|
| Accessory (part, model) rows after dedupe | 1,357 |
| Unique (model_name, year) keys | 71 |
| Keys found in the vehicle DB | 64 |
| Keys with **no vehicle** (flagged once each) | 7: Arteon 2022, 2023; Atlas 2020; Golf R 2020, 2021; ID. Buzz 2026; ID.4 2026 |
| Part-years affected by those 7 misses | 451 of 6,474 |
| Model numbers per found key | 1 to 13 (median 4) |

## Where the config lives (single source of truth)

| Need | Where | New or existing |
|---|---|---|
| What a model / submodel is | `models.yaml` | existing |
| Spelling differences | `models.yaml` aliases, **one list shared by every dataset** (A3) | add `GTI: Golf GTI` |
| Year window and rule (`range_overlap` on `min_year` / `max_year`) | `pipeline.yaml` → `datasets.accessories` | existing |
| Which years a model / submodel legitimately exists (A2, A9) | `vehicles/<model>.yaml` option sets | existing |
| Accessory file layout: source path, sheet, header row, column renames, `status` filter, DQ rules (MSRP > cost, ...) | **new** `config/accessories.yaml` | new |

**One alias list for every dataset (A3).** The same aliases clean the VW descriptions and the accessory model names, so both sides produce the same standard names. `models.yaml` gets one new entry:

```yaml
aliases:
  Atlas Sport Cross: Atlas Cross Sport   # VW model export
  GTI: Golf GTI                          # accessory file
```

Checked 2026-10-26: with `GTI: Golf GTI` added, all 142 VW descriptions clean to exactly the same text as today ("Golf GTI Autobahn" -> "Golf Golf GTI Autobahn" -> repeated word removed -> "Golf GTI Autobahn"). The plan reruns the vehicle ingest to prove `vehicles.csv` is unchanged.

**Base models and their years (A2, A9).** An accessory `Golf` means the **base Golf only** (empty submodel). Which years a model or submodel legitimately exists is already declared in `vehicles/<model>.yaml`: the base Golf is the option set with no submodel, years 2020–2021. Every accessory `Golf` range ends by 2021, so all base Golf part-years are found today. A future model or year is made legit the same way: add its option set to `vehicles/<model>.yaml` (and its name to `models.yaml` if it's new).

**`config/accessories.yaml` (sketch)** moves the notebook's hard-coded choices into config:

```yaml
source: datasets/2026_10_20_VW Canada Accessories Data EN.xlsx
sheet: 0
header_row_in_data: true          # the first data row holds the real column names
columns:                          # source column -> pipeline column (the notebook's column_mapping)
  stockCode: part_number
  model: model_name
  year range: year_range
  status: status
  productDescription: product_description
  dealerNotes: comments
  MSRP: msrp
  cost: cost
  laborTime: labor_time
keep_rows:
  status: [Active]
dq_rules:                         # the notebook's data_rules, as flags (never stop the run)
  greater_than: [[msrp, cost]]
  greater_or_equal: [[max_year, min_year]]
  not_null: [part_number, model_name, product_description, msrp, cost, labor_time]
  numeric_non_zero: [msrp, cost, min_year, max_year]
  numeric_non_negative: [labor_time]
```

## Output structure

**Result: the per-model dict, with model numbers attached. Nothing merged is written to the DB.**

```python
model_year_dict = build_accessory_model_dict()      # from pipeline/, called by the notebook
model_year_dict["GTI"]
# part_number | model_name | product_description | ... | applicable_year | model_number
```

How the model numbers sit in each DataFrame (A5):

| Option | Shape | Notes |
|---|---|---|
| **(a) One row per model number** *(recommended)* | A part that fits 6 GTIs in 2023 has 6 rows for 2023, one `model_number` each | Plain filters (`df[df.model_number == "..."]`); matches "a column with the model number"; ~25k rows in memory |
| (b) One row per part-year, list column | `model_numbers = [...]` + `model_number_count` | Fewer rows; the list has to be exploded before filtering |

- **Unmatched part-years stay in the dict** with `model_number` empty and `match_status` set to the miss reason, so the gap is visible where you work (A8).
- **Every miss is logged and sent to review (A8):**
  - the run log and flags CSV get one flag per missing key, with how many parts it affects;
  - `db/review/accessory_review.csv` gets one row per unmatched part-year (part_number, model_name, year, match_key, reason), about 451 rows today. Unknown model names go there too.
- **What else is written to disk:** the usual run log, steps, flags and changes, plus a small **lookup report** (`db/dq/accessory_lookup.csv`): 71 rows, one per key, with the model numbers found or the miss reason. It is the audit trail of every fetch, not the merged data.

## Miss flags: what was checked, what failed (A9)

A key that finds no vehicle is checked in two places, in order, and the flag names both checks and their results:

1. **Vehicle DB** (`db/final/vehicles.csv`): rows with this model, submodel and year.
2. **Fallback, config** (`vehicles/<model>.yaml`): does an option set for this model / submodel cover the year?

| Check 1: vehicle DB | Check 2: config | Flag | Meaning | Fix |
|---|---|---|---|---|
| found | (not checked) | none | Model numbers attached | |
| 0 rows | year covered | `model_number_not_found` | The config says this vehicle existed that year, but the DB has no model numbers for it | Get a fuller VW model export, rerun the vehicle ingest |
| 0 rows | year not covered | `model_not_offered` | The accessory file lists a year the config says this vehicle wasn't sold | Usually nothing (the accessory range runs past the vehicle's life); if the vehicle was sold, add the year to `vehicles/<model>.yaml` |
| (model name unknown) | (not checked) | `unknown_accessory_model` | The accessory model name isn't in `models.yaml` or its aliases | Add an alias or the model to `models.yaml` |

Example log line (one per key, not per part):

```
FLAG model_not_offered | match_key=volkswagen|arteon|(base)|2022 | parts=<count>
  | check_1=vehicles.csv model=Arteon submodel=(base) year=2022 -> 0 rows
  | check_2=config/vehicles/arteon.yaml base Arteon covers 2020-2021 -> 2022 not covered
  | fix=accessory range runs past the vehicle's last year; add 2022 to arteon.yaml only if it was sold
```

The review file carries the same columns per part-year: `match_key`, `flag`, `check_1_result`, `check_2_result`, `fix`.

**Today's 7 misses** are all `model_not_offered`, because the config was drafted from the same VW export as the DB. Arteon 2022–23 is a real example: it was discontinued after 2021, `arteon.yaml` stops at 2021, and the accessory file's ranges run to 2023.

## Pipeline shape

One function, `build_accessory_model_dict()`, in `pipeline/accessory_helpers.py`, called from the notebook. A thin `run_accessories.py` calls the same function from the terminal (A7). Every step goes through `run_step`, so it is logged like the vehicle ingest:

```
config -> ingest -> staging -> year_window -> clean -> resolve_names -> lookup -> build_dict -> validate
```

| Step | What happens | Logged / flagged |
|---|---|---|
| `config` | Load `accessories.yaml`, `models.yaml`, `pipeline.yaml`; check `vehicles.csv` exists and record its `taxonomy_version` | Config errors / missing vehicle DB -> FATAL |
| `ingest` | Read the Excel sheet, promote the header row | Source file, rows, columns |
| `staging` | Rename columns (`accessories.yaml`), keep `status = Active`, drop exact duplicates on (part_number, model_name) | Rows filtered, duplicates removed |
| `year_window` | Split `year_range` into `min_year` / `max_year`; `range_overlap` (existing helper) | Each excluded row + reason |
| `clean` | Trim text; apply the shared `models.yaml` aliases to `model_name` (`GTI` -> `Golf GTI`) | Before -> after per value |
| `resolve_names` | `match_model()` on each of the 14 **unique** names -> canonical model / submodel | One line per name; unknown name -> `unknown_accessory_model` flag |
| `lookup` | Build the vehicle index once; fetch the 71 unique keys; on a miss, check the declared years in `vehicles/<model>.yaml` | One line per key (`match_key` -> count + model numbers); a miss is flagged once per key with its reason (A9); lookup report written |
| `build_dict` | Explode to applicable years (clipped, D15), attach model numbers by `map`, group by model name | Rows per model; unmatched part-years written to the review file |
| `validate` | DQ rules from `accessories.yaml` (MSRP > cost, not null, ...); `fitment_hint` note for descriptions with qualifiers | Flags (never stop the run); hints at INFO only |

**Code:** a new `pipeline/accessory_helpers.py` (read, header promotion, staging, DQ rules, `build_accessory_model_dict`) and a small `pipeline/lookup_helpers.py` (vehicle index, key fetch, lookup report). Reused unchanged: `clean_helpers`, `parse_helpers.match_model`, `ingest_helpers.filter_by_year_window` / `clip_years`, `logging_helpers`, `storage_helpers`.

## Risks

| # | Risk | How likely / impact | Mitigation |
|---|---|---|---|
| 1 | **Accessory model names that don't map** (a new name, or a spelling like `GTI`) | Certain for new files / medium | Unknown names flagged `unknown_accessory_model` and sent to review, never guessed; fix with an alias in `models.yaml` (shared by all datasets) |
| 2 | **Trim-specific descriptions inside a set.** E.g. `Front Mud Flaps, not for R-Line` is attached to every vehicle in its Tiguan set, R-Line ones included | Low volume (~10 descriptions) / accepted | **By requirement:** an accessory fits its whole specified set. The descriptions are noted in the run log (INFO, `fitment_hint`) for visibility only; they don't change matches and aren't flagged |
| 3 | **Matching on the wrong vocabulary.** Running `keywords.yaml` over product descriptions misreads colours and brand names (`Black`, `Dune`, `PRO`) | High if attempted / high | Product descriptions are never parsed with the vehicle vocabulary; only explicit qualifier rules, if approved |
| 4 | **Base model vs submodel.** Accessory `Golf` might sometimes be meant for all Golfs | Low (the file lists GTI / R separately) / medium | ✅ A2: base model only, exact submodel match; base years declared in `vehicles/<model>.yaml` |
| 5 | **Gaps in the vehicle DB** (Arteon 2022–23, Atlas 2020, Golf R 2020–21, ID.4 / ID. Buzz 2026) | Certain today / low | Flagged once per key and listed in the review file; the reason says whether the year is declared (DB gap) or not (A9); resolved by a fuller VW model export or by declaring the years |
| 6 | **Stale vehicle DB.** The accessories run uses an old `vehicles.csv` | Medium / medium | The run records the vehicles file's `taxonomy_version` and last ingest `run_id`, and warns if the config changed since |
| 7 | **Per-record searching is slow and noisy** | Certain if done per row / low | Lookup by unique key: 71 fetches instead of 6,474; logs are per key, not per part-year |
| 8 | **Messy source values** (prices as text, odd encodings like `�`, header row inside the data) | Certain / low | Staging keeps text; typed in `clean` with flags; encoding doesn't affect matching fields |
| 9 | **Exact-duplicate rows** (13,051 → 1,357) hide real changes if deduped carelessly | Low / medium | Dedupe only rows identical on every column used; log the count; flag (part, model) pairs whose duplicates differ |

## Decisions

| ID | Question | Recommendation |
|---|---|---|
| A1 | Match = canonical (make, model, submodel, model_year) built from `models.yaml` on both sides? | ✅ 2026-10-26: yes. An accessory fits **every** vehicle in its specified set; fetched by unique key, not merged |
| A2 | Accessory `Golf` / `Jetta` / `Atlas` = base model only (submodel must match exactly)? | ✅ 2026-10-26: yes. A base model is legit for the years its no-submodel option set declares in `vehicles/<model>.yaml` (base Golf: 2020–2021) |
| A3 | Aliases per dataset or shared? | ✅ 2026-10-26: **one shared list** in `models.yaml`, so every dataset produces the same standard names; add `GTI: Golf GTI` (checked: no VW description changes) |
| A4 | Trim-level fitment from product descriptions? | ✅ 2026-10-26: **not used.** An accessory fits its whole specified set. Qualifier words in descriptions are only noted in the run log |
| A5 | In each model's DataFrame: (a) one row per model number, or (b) one row per part-year with a list of model numbers? | ✅ 2026-10-26: (a) one row per model number |
| A6 | New `config/accessories.yaml` for the file layout, filters and DQ rules (moved out of the notebook)? | ✅ 2026-10-26: yes |
| A7 | `build_accessory_model_dict()` in `pipeline/` called from the notebook, plus a thin `run_accessories.py` for the terminal; both need `vehicles.csv` to exist? | ✅ 2026-10-26: yes |
| A8 | Unmatched part-years? | ✅ 2026-10-26: kept in the dict (`model_number` empty, `match_status` = reason), flagged in the logs, and listed in `db/review/accessory_review.csv`; plus the 71-row lookup report; no merged table |
| A9 | What reason does a miss get? | ✅ 2026-10-26: check the vehicle DB first, then the config as a fallback. `model_number_not_found` (config covers the year, DB has no vehicle) or `model_not_offered` (config doesn't cover the year). Each flag states what was checked and what failed |

## Out of scope for this idea

- French accessories file / bilingual descriptions.
- Prices, labour and DQ beyond what the notebook already checks.
- Writing back to `accy_v2` or a real database.
