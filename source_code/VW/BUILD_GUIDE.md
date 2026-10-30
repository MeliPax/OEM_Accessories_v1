# VW Data Pipeline: How It Was Built

A step-by-step account of how the VW vehicle and accessory pipelines were built, how they work, and the data problems they handle. Each subtask says what was done, with one or two real examples. For how to run them, see [README.md](README.md); for the history, see [CHANGELOG.md](CHANGELOG.md).

**What it does:** turns two VW source files into one result. Every accessory is matched to the VW model numbers it fits, and the result is exported to Excel with one sheet per model.

| Input | Output |
|---|---|
| `datasets/vw_models_data.csv`: VW model export, one free-text description per vehicle | `db/final/vehicles_<run_id>.csv`: one row per vehicle with taxonomy fields |
| `datasets/...Accessories Data EN.xlsx`: accessory catalogue with year ranges | `output/vw_accessories_<run_id>.xlsx`, plus review and data-quality files |

---

## Phase 0: Ground rules and workspace

- **Own workspace.** `source_code/VW/` holds everything for VW: `config/` (YAML), `pipeline/` (helpers), `run_ingest.py` and `run_accessories.py`, `tests/` and `planning/`.
- **A fixed work process.** Every change that alters code, config behaviour or outputs goes idea → plan → build → sign-off, and the user approves at each gate.
  - *Example:* the final export columns were written as idea 012 and plan 012. The build started only after the user decided E4–E6 (`Hours` capitalized, keep `export.columns`, Excel file only).
- **Config drives behaviour.** No model, word, year or column name is hard-coded.
  - *Example:* adding a new trim word means one line in `keywords.yaml`, not a code change.
- **Everything is traceable.** Every value change is logged before → after with the rule that made it. Every problem is a coded flag that says what was checked, what was found, the likely causes and the fix.
- **Part numbers are never padded or guessed.** A full part number must be proven from the source (Phase 4).

## Phase 1: Understand the data

- **Profiled both files** in the notebook. Each finding was recorded as a numbered issue in `planning/data_issues.md` (DI-NN for accessories, DV-NN for vehicles), with its scale and how it is handled.
- **Vehicle export: everything is in one text field (DV-01).** Only `Description` is filled; trim, engine, drivetrain and the rest must be read from text.
  - *Example:* `Tiguan Comfortline R-Line Black Edition 4MOTION` has to become model Tiguan, trim Comfortline, appearance R-Line, edition Black Edition, drivetrain AWD.
- **Vehicle export: inconsistent text (DV-02 to DV-05).**
  - *Example:* repeated words: `Golf GTI GTI Autobahn`, `ID.4 ID.4 PRO`.
  - *Example:* the same vehicle written two ways: Atlas `CA37PR` is "Atlas Peak Edition" in 2024–2025 and "Atlas Peak" in 2026. Model years 2020–2023 spell `Atlas Sport Cross` instead of `Atlas Cross Sport`.
- **Accessory file: layout and duplicates (DI-01, DI-02).** The headers are on row 2, and of 13,051 Active rows in scope, 11,694 were exact copies of another row.
- **Accessory file: values that don't line up with VW's (DI-03 to DI-05).**
  - *Example:* part `000071200` arrives as `71200`, because the export stored it as a number and dropped the leading zeros.
  - *Example:* the Golf GTI is called just `GTI`. ID.4 and ID. Buzz parts are listed for 2026, but the VW export ends at 2025.
- **Accessory file: unclear units and messy text (DI-07 to DI-11).** Labour time is in minutes with no unit stated, and comments carry HTML and pipe separators.
  - *Example:* `|Installs in top left of trunk under hat shelf. ||Weight limit 10 lbs. (5kg)||...`

## Phase 2: Vehicle ingest (plans 001, 002)

- **Vocabulary in config.**
  - `models.yaml` lists models, submodels and spelling aliases (`Atlas Sport Cross: Atlas Cross Sport`, `GTI: Golf GTI`).
  - `keywords.yaml` says what each word means. Phrases match before single words and entries can be limited to certain models.
  - *Example:* `PRO S` is matched as one ID.4 trim before `PRO` or `S`. `S` alone counts as a trim only on ID.4.
- **Availability in config.** Each `vehicles/<model>.yaml` lists the options a model can have per year range. A vehicle with an option or year outside its file is flagged.
  - *Example:* ID.4 2023 offers trim `PRO`, drivetrain `AWD`/`RWD`, and battery `LG Energy Solution`/`SK On`.
- **The steps:** config → ingest → staging → year window → clean → parse → resolve → validate → write.
  - **Year window:** keeps 2020+, so the 54 rows from model year 2019 are excluded and logged.
  - **Clean:** removes repeated words and inventory notes. *Example:* `Jetta GLI GLI` → `Jetta GLI`; `*Ltd Avail*` moves to `inventory_status`.
  - **Parse:** fills the taxonomy fields. A word the vocabulary doesn't know is flagged `VEH_PARSE_UNKNOWN_WORD` so someone adds it to `keywords.yaml`.
  - **Resolve:** re-reads ambiguous words using the option sets. *Example:* a lone `Black` on a Tiguan 2024–2026 becomes `Black Edition`, but only where that vehicle's option set offers it.
  - **Validate:** checks each vehicle against its option set and checks model-number consistency. *Example:* a year missing from the config raises `VEH_VALID_NOT_IN_CONFIG`.
- **Logging (plan 002).** Every run writes a readable log, a flag file, a change file, a step row per step, and one summary row in `db/dq/ingest_runs.csv`.
  - *Example:* every cleaned description appears in the change file with its before, after and the rule that changed it.

## Phase 3: Accessory matching (plans 003, 004)

- **Reading the file correctly.** The file is read with its real layout (header row 2) and typed columns. Only Active parts are kept, which leaves out 3,997 inactive rows (DI-15).
- **Removing duplicates.** Exact copies are removed, and each one is logged against the row it copies. Today this takes 9,675 rows in the window down to 1,028 unique part/model rows.
- **Standardized names.** Accessory model names go through the shared aliases. *Example:* `GTI` → `Golf GTI`; `Golf` alone stays the base Golf.
- **One lookup per key.** The vehicle database is searched once per unique `(make, model, submodel, year)`, not once per accessory row. Nothing merged is saved.
  - *Example:* the key `volkswagen|id.4|(base)|2024` is looked up once. It finds 6 model numbers (`E812MJ`, `E812MS`, ...), which apply to all 95 ID.4 parts for that year.
- **Building the result.** Each accessory year range is expanded into single years and joined to the model numbers found. The result is one DataFrame per accessory model name, with a `Variant` label built from the vehicle's standardized fields.
  - *Example:* a 2024 Golf GTI `CD1PU2` is labelled `Performance`. A vehicle with no extra fields is labelled `Base`.
- **Coverage.** Vehicles with no parts at all are flagged. *Example:* 14 model-year 2027 vehicles, because the accessory file has no 2027 parts yet (DI-06).
- **Misses explain themselves.** A key with no vehicle is flagged once, with every check made.
  - *Example:* `ACCESS_LOOKUP_YEAR_AFTER_LAST_KNOWN` for ID. Buzz 2026. It says the DB and the config both stop at 2025, lists three possible causes (discontinued, not exported yet, wrong config), and gives the fix for each.
- **Message catalogue (idea 004).** Every flag code has its severity, message, causes and fix in `config/messages.yaml`, so the wording is changed in config, not in code.

## Phase 4: Data quality fixes (plans 006, 007, 008)

- **Labour time in hours (006).** The multiplier comes from unit definitions in config (hours 1, minutes 60 → ×1/60), and the run log states the rule. The raw minutes are kept as `labor_time_source`.
  - *Example:* `25` → `0.42` hours.
  - *Example:* `0.4` on part `3QF601025KAX1` is not a whole number of minutes. It is flagged `ACCESS_CLEAN_UNIT_SUSPECT` for review and still converted, to `0.01`.
- **Comment cleaning (007).** HTML tags and pipes become separated sentences, spacing is fixed, and links follow allow-listed rules. The raw text is kept as `comments_source`, and each change is logged.
  - *Example:* `...9TJ, 9TL</p>Always install...` becomes two sentences.
  - *Example:* a link to a non-public Salsify catalogue page is replaced with `Thule.com` by a link rule.
- **Part numbers proven from the source (008).** The `make&model` column holds the full part number followed by the model name. The pipeline proves each part number from it, and restores lost leading zeros only when they are proven.
  - *Example:* `71200` + `make&model` = `000071200Atlas` → restored to `000071200` and flagged for review as restored. It is never padded by guesswork.
  - If more than 1% of part numbers can't be proven, the run stops, because the file layout has probably changed. The export writes part numbers as Excel text, so Excel can't drop the zeros again.

## Phase 5: Human knowledge and process (plans 009, 010)

- **Verified facts (009).** A person records what they confirmed in `vehicles/<model>.yaml`, with a reason, who and when.
  - *Example (never offered):* Golf R 2020–2021, Arteon 2022–2023, and ID.4 / ID. Buzz 2026, all "not offered in Canada". Their lookup errors drop to info and leave the review file, which went from 109 rows to 16 on 2026-10-29.
  - *Example (no parts expected):* a fact with an `until:` date silences a no-parts flag only until that date. After it, the flag returns as `ACCESS_VERIFY_EXPIRED`.
  - If new data contradicts a fact, for example a Golf R 2021 appearing in a future export, that becomes an error.
- **Tracking (010).** The planning index, open items (OI-NN), changelog and a baseline of run numbers record where everything stands. A test (`test_planning_docs.py`) fails if a plan's status and the index disagree.

## Phase 6: Scope, traceability and output

- **One year window per pipeline.** Set in `pipeline.yaml` and worked out at run start. Every step that selects data ignores anything outside its window.
  - *Example:* vehicles use 2020+. Accessories use `current_year - 2`, which is 2024+ in 2026 and moves to 2025+ in 2027 with no edit. The accessory run reads only vehicles 2024+ (111 of 269).
- **Run-id file names.** Every file a run writes carries the run id, so nothing is overwritten and each file traces to its run.
  - *Example:* `db/review/accessory_review_vw_accessories_20261029_085242.csv`. `db/dq/accessory_runs.csv` records which vehicles file each run used.
- **Vehicle file template.** `config/vehicles/_template.yaml` shows every category, its allowed values, and example option sets and facts. The pipeline never reads files starting with `_`.
  - *Example:* `python new_vehicle.py "Beetle"` creates `config/vehicles/beetle.yaml` with make, model and submodels filled in. It refuses an unknown model and never overwrites a file.
- **Final export columns (012).** `Part`, `ModelName`, `Description`, `Price`, `Hours`, `Comments`, `Variant`, `Year`, `Model` are set in `export.columns`; Cost is left out of the file.
  - *Example:* `Model` now holds the model number (`E812MJ`) and `ModelName` holds the name (`Golf GTI`). Two columns given the same header stop the run with a config error.

## Phase 7: Testing and verification

- **Unit tests per helper.** *Example:* the parser test checks that `PRO S` on an ID.4 is one trim, not `PRO` plus `S`.
- **Config validation tests.** Each broken setting must fail with its own `CONFG_` message.
  - *Example:* `restore: pad` is rejected ("part_number.restore must be one of leading_zeros_only, never").
- **End-to-end tests on the real files.** Both pipelines run start to finish and the expected counts are checked.
  - *Example:* 1,028 unique rows, 27 of 29 lookup keys found, every exported `Part` is text.
- **Real runs after each build.** The numbers go into the baseline in `planning/README.md`. *2026-10-29:* 269 vehicles, 9,388 exported rows in 10 sheets, 16 review rows, 285 tests passing.

---

## Still open

- **Data source:**
  - no parts listed for model year 2027 (DI-06, OI-05);
  - base Atlas 2020 missing from the vehicle export (DV-08);
  - whether `0.4` labour on `3QF601025KAX1` is minutes or hours (OI-06);
  - export part numbers as text (OI-07).
- **User:**
  - sign off testing (OI-01);
  - review the drafted vehicle files (OI-03);
  - decide the run report (idea 005) and the documentation standard (idea 011).
