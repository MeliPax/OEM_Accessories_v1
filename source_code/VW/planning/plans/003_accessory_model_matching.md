# 003 — Accessory Ingest + Model Number Matching: Plan

**Status:** Built — in user testing (2026-10-27)
**Updated:** 2026-10-27
**Next:** user signs off testing (OI-01); notebook cell (OI-02); lookup misses as warnings? (OI-09)
**Links:** ideas [003](../ideas/003_accessory_model_matching_design.md), [004](../ideas/004_error_message_catalogue_design.md) · depends on plans [001](001_vw_model_ingest_mvp.md), [002](002_pipeline_logging.md) · later: idea [005](../ideas/005_pipeline_report_card_design.md)
**Summary:** The accessory pipeline: ingest, dedupe, model-number lookup, per-model dict, coverage, data quality and the Excel export; flag codes from messages.yaml.

## Outcome

1. **Clearer flags in both pipelines:**
   - every flag and fatal has a prefixed code (`CONFG_` / `VEH_` / `ACCESS_`);
   - every flag says what was checked, what was found, the likely causes and the fix;
   - the wording lives in `config/messages.yaml`.
2. **Run ids end with the run's date and time,** e.g. `vw_ingest_20261027_143005` and `vw_accessories_20261027_143005`.
3. **One call gives the per-model dict** of accessory DataFrames, keyed by accessory model name (14 today). Each row is one part, one applicable year and one vehicle, with `model_number` and `trim` fetched from the vehicle DB:

   ```python
   from pipeline.accessory_helpers import build_accessory_model_dict
   model_year_dict = build_accessory_model_dict()
   model_year_dict["GTI"]
   # part_number | model_name | model | submodel | product_description | comments | msrp | cost | labor_time
   # | applicable_year | match_key | model_number | vehicle_id | trim | match_status
   ```

4. **An Excel export** `output/vw_accessories_<YYYYMMDD_HHMMSS>.xlsx`:
   - one sheet per accessory model name, matched rows only;
   - columns and headers from `accessories.yaml`: Part Number, Model, Description, MSRP, Cost, Labour Time, Comments, Trim, Year, Model Number.
5. **Every gap is logged and listed for review:**
   - parts with no vehicle (`ACCESS_LOOKUP_*`);
   - vehicles with no parts (`ACCESS_COVER_*`);
   - data-quality issues.

**Written to disk:**

| File | Content |
|---|---|
| `db/logs/...` | Run log, steps, changes, flags (flags now carry code, message, checked, found, causes, fix) |
| `db/dq/accessory_lookup.csv` | One row per (model, submodel, year) key: checks C1–C5 and their results, model numbers found |
| `db/review/accessory_review.csv` | One row per unmatched part-year and per vehicle with no parts, with the flag fields |
| `db/dq/accessory_runs.csv` | One summary row per run (input for the report card later) |
| `output/<run_id>.xlsx` | The export (git-ignored) |

**Success criteria (today's data)**

- [x] The vehicle ingest still produces the same 269 vehicles, under the new run id and flag codes.
- [x] 13,051 accessory rows in the year window → 1,357 (part, model) rows after exact-duplicate removal, logged.
- [x] 14 model names resolved once each, 0 `ACCESS_LOOKUP_UNKNOWN_MODEL_NAME`.
- [x] 71 keys looked up: 64 found and 7 flagged:
  - `ACCESS_LOOKUP_YEAR_AFTER_LAST_KNOWN`: Arteon 2022, 2023; ID.4 2026; ID. Buzz 2026;
  - `ACCESS_LOOKUP_YEAR_BEFORE_FIRST_KNOWN`: Atlas (base) 2020; Golf R 2020, 2021.
  - Each flag names both checks, the known years and the YAML's `drafted` status.
- [x] 14 vehicles with no parts flagged `ACCESS_COVER_VEHICLE_NO_PARTS`, one flag per key:
  - Atlas 2027, Jetta 2027, Jetta GLI 2027, Taos 2027, Tiguan 2027.
- [x] The unmatched part-years in the dict equal those rows in `accessory_review.csv` (about 451 today).
- [x] The export has 14 sheets with the configured columns in order, no unmatched rows, and the `Year` column.
- [x] Every exported `Model Number` traces to one `LOOKUP OK` line in the run log via its `match_key`.
- [x] Every code the code can raise exists in `messages.yaml`, and every entry there is used (test).
- [x] A rerun with no data or config change gives identical lookup, review and export content.

---

## Phase 0 — Shared groundwork: run ids, flag codes, messages (vehicle ingest first)

Changes the built vehicle ingest before anything new is added, so both pipelines share one flag system.

- [x] **Run id (A17):** `start_run(..., pipeline='vw_ingest')` builds `<pipeline>_<YYYYMMDD_HHMMSS>`, with a same-second `_2` suffix as today. Log, changes and flags file names follow it. `steps.csv` and `ingest_runs.csv` keep working with old and new ids.
- [x] **`config/messages.yaml` (E2):**
  - one entry per code: severity, message template, causes, fix steps;
  - `config_helpers.load_messages()` validates it, so every entry has all fields and a known severity.
- [x] **`log_flag(ctx, step, subject, code, **facts)`:**
  - looks up the code;
  - fills the message from `facts`, then adds `checked` and `found`;
  - writes the flag fields (code, severity, step, subject, message, checked, found, causes, fix) to the flags CSV and the run-log block;
  - an unknown code fails loudly (programming error).
- [x] **Rename the vehicle ingest's flags and fatals (E3):** use the idea-004 table, e.g. `unknown_token` → `VEH_PARSE_UNKNOWN_WORD` and `no_option_set` → `VEH_VALID_NOT_IN_CONFIG`.
- [x] **New vehicle codes:**
  - `VEH_WRITE_VEHICLE_REMOVED`: from the existing DB compare;
  - `VEH_WRITE_FILE_LOCKED`: a `PermissionError` on write.
- [x] **Config errors:** each problem in a `ConfigError` gets its `CONFG_` code (`CONFG_FILE_NOT_FOUND`, `CONFG_YAML_INVALID`, `CONFG_VALUE_INVALID`, `CONFG_UNKNOWN_REFERENCE`, `CONFG_DUPLICATE_ENTRY`, `CONFG_NO_VEHICLE_FILES`).
- [x] **`vehicles/*.yaml` (E5):**
  - add `status: drafted` (plus empty `reviewed_by` / `reviewed_on`) to all 10 files;
  - the loader accepts `drafted | reviewed` and rejects anything else.
- [x] **Review queue:** carries the new fields.
- [x] **Tests:** update the 84 existing tests for the new codes and run id, and add a catalogue-sync test (codes used in `pipeline/` ↔ entries in `messages.yaml`).

**Done when:** all tests pass, a vehicle ingest rerun reports 0 rows added / removed / changed, and its flags CSV shows the new fields.

## Phase 1 — Accessory config

- [x] **`models.yaml`:**
  - add `GTI: Golf GTI` to the shared aliases (A3). It only rewrites the word `GTI` (the accessory file's name for the Golf GTI); `Golf` alone is never changed and stays the base Golf (2020–2021).
  - Rerun the vehicle ingest and confirm 0 changes.
- [x] **New `config/accessories.yaml` (A6):**
  - source file, sheet and header row;
  - column renames and types;
  - `keep_rows: {status: [Active]}`;
  - DQ rules (the notebook's `data_rules`);
  - the `export:` block: output dir, `file_name: "{run_id}.xlsx"`, `include_unmatched: false`, `sort_by`, and ordered `columns:` with their headers (A13–A15).
- [x] **`pipeline.yaml`:** add `sources.accessories`.
- [x] **`config_helpers.load_accessory_config()`:**
  - validates required keys, rule names, and that every DQ-rule and export column exists in the pipeline columns;
  - errors are `CONFG_UNKNOWN_REFERENCE` / `CONFG_VALUE_INVALID`.
- [x] **`config_helpers.vehicle_years(option_sets)`:** returns `{(model, submodel): {'years': set, 'file': path, 'status': drafted|reviewed}}`, for checks C3–C5.

**Done when:**
- a bad `accessories.yaml` (an unknown export column, a missing source) stops with the right `CONFG_` code and names the setting;
- the vehicle ingest rerun is clean.

## Phase 2 — Ingest, staging, year window

New `pipeline/accessory_helpers.py`:

- [x] **`read_accessories(path, spec, ctx)`:** read the sheet as text, promote the header row, keep the configured columns. Fatals: `ACCESS_SRC_FILE_NOT_FOUND`, `_SHEET_NOT_FOUND`, `_HEADER_NOT_FOUND`, `_COLUMN_MISSING`, `_EMPTY`.
- [x] **`stage_accessories(df, spec, ctx)`:** rename, add lineage, keep `status = Active`.
  - Flags: `ACCESS_STGNG_STATUS_UNEXPECTED`, `ACCESS_STGNG_MAKE_MISMATCH` (make vs `models.yaml`), `ACCESS_STGNG_MISSING_PART_NUMBER` / `_MISSING_MODEL_NAME`.
  - Excluded rows are logged with a reason.
- [x] **`split_year_range(df, ctx)`:** `year_range` → `min_year` / `max_year`; a single year counts as both. Flags: `ACCESS_YEAR_RANGE_INVALID`, `ACCESS_YEAR_RANGE_REVERSED` (row excluded).
- [x] **Year window:**
  - reuse `ingest_helpers.filter_by_year_window(df, settings, 'accessories', ctx)`;
  - out-of-window rows: `ACCESS_YEAR_OUT_OF_WINDOW` (info);
  - an empty result: `ACCESS_YEAR_WINDOW_EMPTY`.
- [x] **Exact-duplicate removal:**
  - drop rows identical on every kept column and log the count;
  - a (part, model) pair whose copies differ: `ACCESS_STGNG_DUPLICATE_CONFLICT`.

**Done when:** today's file stages 20,399 Active rows, keeps 13,051 in the window and dedupes to 1,357, all reconciled in `steps.csv`.

## Phase 3 — Clean and resolve model names

- [x] **`clean`:**
  - trim text and turn empty into null;
  - type `msrp`, `cost` and `labor_time`: a failure gives `ACCESS_CLEAN_NOT_NUMERIC`, with the value shown and left empty;
  - count replacement characters (`ACCESS_CLEAN_BAD_CHARACTERS`, once per column per run);
  - `model_name_clean` via `clean_helpers.clean_value` with the shared aliases; before → after logged.
- [x] **`resolve_names`:**
  - `parse_helpers.match_model()` on each **unique** name (14) → model and submodel, with one `RESOLVED` line per name;
  - a name that doesn't match: `ACCESS_LOOKUP_UNKNOWN_MODEL_NAME`, rows to review.

**Done when:**
- `GTI` → Golf / GTI, `Golf` → Golf / (base), `Atlas Cross Sport` → Atlas / Cross Sport;
- an invented name in a test file is flagged, not guessed.

## Phase 4 — Lookup (the fetch)

New `pipeline/lookup_helpers.py`:

- [x] **`load_vehicle_index(db_dir, ctx)`:**
  - read only `vehicle_id`, `model`, `submodel`, `model_year`, `model_number`, `trim` and `taxonomy_version`;
  - group once into `{(model, submodel, year): [vehicles]}`, plus the known DB years per (model, submodel).
  - Fatals: `ACCESS_DB_NOT_FOUND` ("run run_ingest.py first"), `ACCESS_DB_COLUMN_MISSING`.
  - Warnings: `ACCESS_DB_STALE` (taxonomy version differs from the current config); `ACCESS_DB_LAST_INGEST_NOT_OK` (from `ingest_runs.csv`).
- [x] **`unique_keys(df)`:** (model, submodel, year) for every applicable year, clipped to the window (D15, `ACCESS_YEAR_CLIPPED` once per run); 71 today.
- [x] **`fetch(keys, index, vehicle_years, ctx)`:** checks C1–C5 per key, in order (idea 004):
  - **found in the DB and declared in config:** `LOOKUP OK` at info, with the count and model numbers;
  - **found in the DB, not declared:** `ACCESS_LOOKUP_IN_DB_NOT_IN_CONFIG` (warning; model numbers still attached, E6);
  - **declared, not in the DB:** `ACCESS_LOOKUP_IN_CONFIG_NOT_IN_DB`;
  - **neither:** `..._YEAR_AFTER_LAST_KNOWN` / `..._YEAR_BEFORE_FIRST_KNOWN` / `..._YEAR_IN_GAP`, from the known years;
  - **model has no vehicles at all:** `ACCESS_LOOKUP_MODEL_NOT_IN_DB`;
  - **no YAML or option set for it:** `ACCESS_LOOKUP_NO_CONFIG_FOR_MODEL`;
  - **every flag:** once per key, with the part count, the known DB / config years and the YAML's status.
- [x] **Write `db/dq/accessory_lookup.csv`:** match_key, model, submodel, year, parts, c2_in_db, c3_in_config, known_db_years, known_config_years, config_status, code, model_count, model_numbers.

**Done when:**
- today's data gives 64 found plus the 7 codes in the success criteria;
- tests cover every row of the idea-004 lookup table, including `IN_CONFIG_NOT_IN_DB`, `YEAR_IN_GAP` and `IN_DB_NOT_IN_CONFIG`.

## Phase 5 — Build the dict, coverage, review file

- [x] **`build_model_year_dict(df, lookup)`:**
  - explode each row to its applicable years (clipped to the window);
  - drop `year_range`, `min_year` and `max_year` (A11);
  - `map` the lookup result onto (model, submodel, year) and explode to one row per vehicle, bringing `model_number`, `vehicle_id` and `trim` (A5, A12);
  - group by accessory `model_name` (A10).
- [x] **`match_status`:** `matched` or the `ACCESS_LOOKUP_*` code.
- [x] **`coverage`:**
  - DB vehicles whose (model, submodel, year) no accessory covers: `ACCESS_COVER_VEHICLE_NO_PARTS`, once per key, with the vehicle count and the years that model's accessories do cover;
  - a model with no parts in any year: `ACCESS_COVER_MODEL_NO_PARTS`.
- [x] **Write `db/review/accessory_review.csv`:**
  - one row per unmatched part-year and per vehicle with no parts;
  - columns: type (`part` / `vehicle`), part_number or model_number, model_name, model, submodel, year, match_key, code, severity, message, checked, found, causes, fix.
- [x] **Reconcile:** log rows per model, matched and unmatched part-years, and vehicles with no parts; check that unmatched part-years equal the part rows in the review file.

**Done when:** the dict has 14 DataFrames, every unmatched row in it appears in the review file, and the 5 coverage keys are flagged.

## Phase 6 — Validate (data quality)

- [x] **DQ rules from `accessories.yaml`:** `ACCESS_DQ_MSRP_NOT_ABOVE_COST`, `ACCESS_DQ_VALUE_MISSING`, `_VALUE_ZERO` and `_VALUE_NEGATIVE`, as warnings (never stop the run), once per row.
- [x] **`ACCESS_DQ_FITMENT_HINT`:** for descriptions with a qualifier ("not for R-Line"), at info only; fitment unchanged (A4).

**Done when:** the rules produce the same failures as the notebook's `data_quality_check` on today's data, now as coded flags.

## Phase 7 — Export, entry points, docs

- [x] **`export_accessories(model_year_dict, spec, run_id, ctx)`:**
  - writes `output/<run_id>.xlsx`, one sheet per model name, matched rows only (A13);
  - columns and headers in config order; sorted by `sort_by`.
  - Sheet names are cleaned to Excel's rules: `ACCESS_EXPORT_SHEET_RENAMED` (info).
  - A model with no matched rows: `ACCESS_EXPORT_SHEET_EMPTY`.
  - A file open in Excel: `ACCESS_EXPORT_FILE_LOCKED` (fatal, "close it and rerun").
- [x] **`build_accessory_model_dict(config_dir, db_dir, source, export=True)`:**
  - runs config → ingest → staging → year_window → clean → resolve_names → lookup → build_dict → coverage → validate → export, all through `run_step`;
  - writes `accessory_runs.csv` and returns the dict (A7).
- [x] **`run_accessories.py`:**
  - a thin terminal wrapper with the same exit codes as `run_ingest.py`;
  - prints rows per model, the export path and the flag summary by code.
- [x] **`.gitignore`:** add `output/` (A15).
- [x] **Docs:** README (run the accessories step; outputs; the message catalogue), `db/README.md` (new files), `config/README` notes for `accessories.yaml` and `messages.yaml`.
- [ ] **Notebook:** a cell that calls `build_accessory_model_dict()`. I'll add it once you've closed the notebook, and won't edit it while it's open.

**Done when:** the success criteria above pass, and a terminal run and a notebook run give the same dict and export content.

---

## Tests

| File | Covers |
|---|---|
| existing 84 tests | Updated for the new codes and run id (Phase 0) |
| `test_messages.py` | `messages.yaml` loads; every code used in `pipeline/` has an entry and every entry is used; messages fill without missing fields |
| `test_accessory_helpers.py` | Header promotion and source fatals, rename, Active filter, year-range split, dedupe and conflict, typing, DQ rules |
| `test_lookup_helpers.py` | Index build, unique keys with clipping, every row of the idea-004 lookup table, DB fatals and the stale warning |
| `test_export.py` | Sheet per model, column order and headers from config, matched rows only, sheet-name cleaning, locked file |
| `test_accessories_end_to_end.py` | Today's counts (1,357 / 71 / 64 / 7 / 14 vehicles with no parts), dict ↔ review reconciliation, `LOOKUP OK` traceability, stable rerun |

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-10-26 | Lookup by unique (model, submodel, year) key; attach while building the dict; no merged table saved (A1) | User: "a fetch will be enough"; 71 searches instead of 6,474 |
| 2026-10-26 | An accessory fits every vehicle in its specified set; descriptions never narrow it (A1, A4) | User requirement |
| 2026-10-26 | Accessory `Golf` = base Golf only; legit years from `vehicles/<model>.yaml` (A2) | User; base Golf declared 2020–2021 with AU22M2 / AU22MS / AU23M2 / AU23MS |
| 2026-10-26 | One alias list for all datasets (A3) | User: same standards on both sides; checked, no VW description changes |
| 2026-10-26 | One row per model number; `accessories.yaml`; notebook function + terminal runner (A5–A7) | User |
| 2026-10-26 | Unmatched part-years kept in the dict, flagged and listed for review (A8) | User |
| 2026-10-27 | Prefixed codes with message / checked / found / causes / fix from `messages.yaml`; vehicle ingest flags renamed; YAML `status: drafted / reviewed` (idea 004, E1–E7) | User: "concrete error message plan" for faster troubleshooting; prefixes `CONFG` / `VEH` / `ACCESS` / `STGNG` per user edit |
| 2026-10-27 | Sheet / dict entry per accessory model name, not per family (A10) | User |
| 2026-10-27 | Range columns dropped after explode; trim and vehicle_id fetched (A11, A12) | User |
| 2026-10-27 | Export matched rows only, with a Year column, to git-ignored `output/` (A13–A15) | User |
| 2026-10-27 | Vehicles with no parts flagged and listed for review (A16) | User: governance overview; report card later (idea 005) |
| 2026-10-27 | Run id = pipeline name + run date-time at the end (A17) | User: tell runs apart by time |
| 2026-10-27 | **Build notes.** `dedupe` is its own step, between `year_window` and `clean` | Its 11,694 removed rows get their own count in `steps.csv` |
| 2026-10-27 | **Build notes.** The MSRP-vs-cost rule is `ACCESS_DQ_VALUE_NOT_ABOVE` (any configured left > right pair), not `..._MSRP_NOT_ABOVE_COST` | The rule pairs are config, so the code shouldn't name one pair |
| 2026-10-27 | **Build notes.** The export's Model column is the standard name (`model_name_clean`, e.g. "Golf GTI"); the sheet name keeps the file's name ("GTI") | Same standard names on both sides (A3); sheets per accessory model name (A10) |
| 2026-10-27 | **Build notes.** Change and flag logs gained a `record` column: the vehicle_id, or `ACC-<source row>-<part>` for accessory rows | Accessory rows have no vehicle_id; every logged row must still be traceable |
| 2026-10-27 | **Build notes.** Fitment hint words are config (`fitment_hints` in `accessories.yaml`); 16 descriptions noted today | No hard-coded words |
| 2026-10-27 | **Variant replaces Trim** in the dict and the export: the vehicle's standardized fields joined in config order (trim > special edition > appearance > performance > technology > engine > transmission > drivetrain > body style), empty fields skipped; `Base` when none has a value (`base_label` / `base_when: all_fields_empty` in `accessories.yaml`). Today: 64 distinct variants, 16 vehicles `Base`, 0 blank cells | User: 56 of 269 vehicles had no trim; build from parsed fields (not raw text) so a vehicle reads the same every year; the Base keyword and its rule are config, not code |

## Risks

| Risk | Mitigation |
|---|---|
| Renaming flags breaks the built vehicle ingest | Phase 0 runs first, on its own, with all tests updated and a "0 changes" rerun before any accessory work |
| A message template refers to a fact the code doesn't pass | `test_messages.py` fills every template; `log_flag` fails loudly on a missing fact |
| The shared `GTI` alias changes a future VW description | Phase 1 rerun shows any change in the `write` step; repeated-word removal covers today's "Golf GTI ..." |
| Accessories run against an old `vehicles.csv` | `ACCESS_DB_STALE` and `ACCESS_DB_LAST_INGEST_NOT_OK` warnings |
| The accessory file layout changes | Layout in `accessories.yaml`; a missing column is a fatal naming it |
| Export file open in Excel on Windows | `ACCESS_EXPORT_FILE_LOCKED` with "close it and rerun"; each run writes a new file name anyway |
| Exploding to one row per vehicle grows the dict | About 25k rows today; fine in memory |
