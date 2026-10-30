# VW Data Pipeline: How It Was Built

A step-by-step account of how the VW vehicle and accessory pipelines were built, how they work, and the data problems they handle. For how to run them, see [README.md](README.md); for the history, see [CHANGELOG.md](CHANGELOG.md).

**What it does:** turns two VW source files into one result. Every accessory is matched to the VW model numbers it fits, and the result is exported to Excel with one sheet per model.

| Input | Output |
|---|---|
| `datasets/vw_models_data.csv`: VW model export, one free-text description per vehicle | `db/final/vehicles_<run_id>.csv`: one row per vehicle with taxonomy fields |
| `datasets/...Accessories Data EN.xlsx`: accessory catalogue with year ranges | `output/vw_accessories_<run_id>.xlsx`, plus review and data-quality files |

---

## Phase 0: Ground rules and workspace

- Set up `source_code/VW/` with its own config, pipeline code, tests and planning.
- Fixed the work process: **idea → plan → build → sign-off**, with the user approving at each gate (`planning/README.md`, `CLAUDE.md`).
- Decided on the non-negotiables:
  - config drives behaviour; code never hard-codes a model, word or year;
  - every change to a value is logged before → after;
  - every problem is a coded flag with causes and a fix;
  - part numbers are never padded or guessed.

## Phase 1: Understand the data (data analysis)

- Profiled both files in the notebook and recorded every finding as an issue (`planning/data_issues.md`, DI-NN / DV-NN).
- **Vehicle export findings:**
  - only `Description` is filled; trim, engine and the rest must be read from free text (DV-01);
  - repeated words (`Golf GTI GTI`), a misspelt submodel (`Atlas Sport Cross`), a lone `Black` that means Black Edition (DV-02 to DV-04);
  - inventory notes (`*Ltd Avail*`) inside the description, and model-year 2019 rows (DV-10, DV-11).
- **Accessory file findings:**
  - headers are on row 2; 90% of rows are exact copies (DI-01, DI-02);
  - part numbers lose leading zeros when exported as numbers (DI-03);
  - model names differ from VW's (`GTI` for Golf GTI) (DI-04);
  - year ranges reach years with no VW vehicle (DI-05);
  - labour time in minutes with no unit stated, and HTML markup and `|` separators in comments (DI-07 to DI-11).

## Phase 2: Vehicle ingest (plans 001, 002)

- **Vocabulary in config:**
  - `models.yaml`: models, submodels and aliases;
  - `keywords.yaml`: what each word means, e.g. `4MOTION` → drivetrain AWD;
  - `categories.yaml`: the taxonomy levels.
- **Availability in config:** `vehicles/<model>.yaml` sets which options each model can have per year range. Anything outside it is flagged.
- **Steps:** config → ingest → staging → year window → clean → parse → resolve → validate → write.
  - **Clean:** removes repeated words and inventory notes.
  - **Parse:** splits each description into taxonomy fields; unknown words are flagged.
  - **Resolve:** re-reads ambiguous words using the option sets (`Black` → `Black Edition` where offered).
  - **Validate:** checks each vehicle against its option set and model-number consistency.
- **Logging (plan 002):**
  - a readable run log;
  - a flag file, a change file and a step file;
  - one summary row per run.

## Phase 3: Accessory matching (plans 003, 004)

- Read the file with its real layout (header row 2), typed columns, and only Active parts in scope.
- Removed exact copies, then standardized model names through the aliases (`GTI` → `Golf GTI`).
- **Lookup design:**
  - the vehicle database is searched **once per unique (model, submodel, year)** key, not once per row;
  - each accessory fits every vehicle in its model and year range;
  - nothing merged is saved.
- Built the result: one DataFrame per accessory model name, with a `variant` label built from the vehicle's fields.
- **Coverage:** vehicles with no parts are flagged.
- **Misses:** each one explains what was checked and why it missed.
- **Messages (idea 004):** every flag code has its severity, message, causes and fix in `messages.yaml`.

## Phase 4: Data quality fixes (plans 006, 007, 008)

- **Labour time (006):** minutes → hours using unit definitions in config. The raw value is kept; suspect values are flagged and still converted.
- **Comment cleaning (007):** HTML tags and `|` separators become clean sentences, spacing is fixed, and links follow allow-listed rules. The raw text is kept.
- **Part numbers (008):**
  - the full number is proven from the `make&model` column, and lost leading zeros are restored only when proven;
  - more unproven numbers than a set share stops the run;
  - the export writes part numbers as Excel text.

## Phase 5: Human knowledge and process (plans 009, 010)

- **Verified facts (009):** a person records in `vehicles/<model>.yaml` what they confirmed:
  - **never offered**, e.g. Golf R 2020–21, Arteon 2022–23, ID.4 and ID. Buzz 2026;
  - **no parts expected**, until a date.
  - Matching flags drop to info and leave the review file; data that contradicts a fact becomes an error.
- **Tracking (010):** planning index, open items (OI-NN), changelog and a baseline of run numbers; a test keeps them in step.

## Phase 6: Scope, traceability and output

- **Year windows:** one per pipeline in `pipeline.yaml`. Vehicles 2020+; accessories `current_year - 2` (2024+ in 2026), worked out at run start. Every step that selects data ignores anything outside its window.
- **Run-id file names:** every file a run writes is named `<name>_<pipeline>_<YYYYMMDD_HHMMSS>`; nothing is overwritten, and each run records the files it used.
- **Vehicle file template:** `config/vehicles/_template.yaml` plus `python new_vehicle.py "<Model>"` to set up a new model.
- **Final export columns (012):** `Part`, `ModelName`, `Description`, `Price`, `Hours`, `Comments`, `Variant`, `Year`, `Model`, set in `export.columns`; Cost left out.

## Phase 7: Testing and verification

- 285 automated tests:
  - unit tests per helper;
  - config validation (every broken setting gives a `CONFG_` error);
  - end-to-end runs on the real files with the expected counts.
- Real runs after every build, with the numbers recorded in the baseline (2026-10-29):
  - 269 vehicles, 9,388 exported rows in 10 sheets, 27 of 29 lookup keys found;
  - the other 2 are verified as never offered;
  - 16 review rows.

---

## Still open

- **Data source:**
  - no parts listed for model year 2027 (DI-06, OI-05);
  - base Atlas 2020 missing from the vehicle export (DV-08);
  - one labour value that looks like hours (OI-06);
  - export part numbers as text (OI-07).
- **User:**
  - sign off testing (OI-01);
  - review the drafted vehicle files (OI-03);
  - decide the run report (idea 005) and the documentation standard (idea 011).
