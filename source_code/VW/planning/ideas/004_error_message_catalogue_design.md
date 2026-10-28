# 004 — Error and Flag Messages: Design

**Status:** Idea — approved (E1–E7, 2026-10-27)
**Updated:** 2026-10-27
**Next:** completed with plan 003 once testing is signed off (OI-01)
**Links:** built in plan [003](../plans/003_accessory_model_matching.md) · catalogue `config/messages.yaml`
**Summary:** Every flag and fatal gets a prefixed code with message, checked, found, causes and fix, worded in config/messages.yaml.
**Applies to:** the vehicle ingest (built, plans 001–002) and the accessory pipeline (plan 003)
**Asked for:** "go through all the possible scenarios ... from start to end, to come up with a concrete error message plan"; prefix every error so it's clear what is going on.

## Goal

Every flag tells the person troubleshooting, without opening the code:

1. **What** happened, in one plain sentence.
2. **What was checked**: which file, which values.
3. **What was found**: the actual result, with the known values for context (for example "known years 2021–2027").
4. **The likely causes**, in order.
5. **How to fix it**, as numbered steps that name the file or command.

## Message format

Every flag has the same fields, in the run log, the flags CSV and the review file:

| Field        | Example                                                                                                                                                                                                                                                                              |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `code`     | `ACCESS_LOOKUP_YEAR_BEFORE_FIRST_KNOWN`                                                                                                                                                                                                                                               |
| `severity` | `error`                                                                                                                                                                                                                                                                            |
| `step`     | `lookup`                                                                                                                                                                                                                                                                           |
| `subject`  | `volkswagen\|atlas\|(base)\|2020` · 37 parts |
| `message`  | Accessory file lists base Atlas for 2020, but neither the vehicle DB nor the config has base Atlas before 2021                                                                                                                                                                       |
| `checked`  | 1) `db/final/vehicles.csv`: model=Atlas, submodel=(base), year=2020 → 0 rows (known years 2021–2027) · 2) `config/vehicles/atlas.yaml`: base Atlas declared 2021–2027 → 2020 not declared (file status: drafted from data, not reviewed)                                    |
| `causes`   | a) base Atlas wasn't sold in 2020 · b) the VW model export is missing base Atlas 2020                                                                                                                                                                                               |
| `fix`      | 1) Confirm with the data source whether base Atlas 2020 exists. 2) If it wasn't sold: no action (the accessory range starts before the vehicle). 3) If it was sold: get an export that includes it, add 2020 to `atlas.yaml`, rerun `run_ingest.py`, then `run_accessories.py` |

In the run log this prints as one block:

```
[ERROR] [lookup] ACCESS_LOOKUP_YEAR_BEFORE_FIRST_KNOWN | volkswagen|atlas|(base)|2020 · 37 parts
  what:    Accessory file lists base Atlas for 2020, but neither the vehicle DB nor the config has base Atlas before 2021
  checked: 1) db/final/vehicles.csv model=Atlas submodel=(base) year=2020 -> 0 rows (known years 2021-2027)
           2) config/vehicles/atlas.yaml base Atlas declared 2021-2027 -> 2020 not declared (drafted from data, not reviewed)
  causes:  a) base Atlas wasn't sold in 2020  b) the VW model export is missing base Atlas 2020
  fix:     1) confirm with the data source  2) not sold -> no action  3) sold -> new export, add 2020 to atlas.yaml,
           rerun run_ingest.py then run_accessories.py
```

(37 parts is illustrative; the real count is filled in at run time.)

### Codes and prefixes

`<PIPELINE>_<STAGE>_<WHAT>`, upper case, so the code alone says where and what:

| Pipeline   |                                      | Stage                   |                                            |
| ---------- | ------------------------------------ | ----------------------- | ------------------------------------------ |
| `CONFG`  | Config files (shared)                | `SRC`                 | Reading a source file                      |
| `VEH`    | Vehicle ingest (`run_ingest.py`)   | `DB`                  | Using the vehicle DB from another pipeline |
| `ACCESS` | Accessories (`run_accessories.py`) | `STGNG`               | Staging checks                             |
|            |                                      | `YEAR`                | Year range and year window                 |
|            |                                      | `CLEAN`               | Cleaning and typing                        |
|            |                                      | `PARSE` / `RESOLVE` | Vehicle description parsing                |
|            |                                      | `VALID`               | Vehicle validation                         |
|            |                                      | `LOOKUP`              | Fetching model numbers for accessories     |
|            |                                      | `COVER`               | Vehicles that got no parts                 |
|            |                                      | `DQ`                  | Data-quality rules                         |
|            |                                      | `EXPORT` / `WRITE`  | Writing output files                       |

### Severities

| Severity    | Meaning                                                                          | Run                       |
| ----------- | -------------------------------------------------------------------------------- | ------------------------- |
| `fatal`   | Nothing useful can be produced (broken config, missing file, output file locked) | Stops                     |
| `error`   | A row or key can't be used: excluded, or left without a model number             | Continues; goes to review |
| `warning` | Used, but needs a person's eye                                                   | Continues; goes to review |
| `info`    | Noted for the record; no action expected                                         | Continues; log only       |

### Where the text lives: `config/messages.yaml` (single source of truth)

The wording is config, not code, so it can be improved without touching Python:

```yaml
ACCESS_LOOKUP_IN_CONFIG_NOT_IN_DB:
  severity: error
  message: "Config says {vehicle} is offered in {year}, but the vehicle DB has no model numbers for it"
  causes:
    - The VW model export used for the last ingest doesn't include this vehicle
    - The vehicle DB is older than the export (run_ingest.py not rerun)
  fix:
    - Rerun run_ingest.py with the latest VW model export
    - If it is still missing, ask the data source whether the vehicle exists
    - If it exists, add it to the source data (manual-add process to be defined), then rerun run_ingest.py and run_accessories.py
```

The code supplies only the facts (`vehicle`, `year`, `checked`, `found`, counts). A test checks that every code the code can raise exists in `messages.yaml` with a message, causes and fix, and that no entry is unused.

## The core case: an accessory (model, year) key

Each unique accessory key is checked in this order:

| #  | Check                                                                             | Source                                             |
| -- | --------------------------------------------------------------------------------- | -------------------------------------------------- |
| C1 | Is the accessory model name a known model or submodel (directly or by alias)?     | `models.yaml`                                    |
| C2 | Does the vehicle DB have this model, submodel and year?                           | `db/final/vehicles.csv`                          |
| C3 | Does the config declare this model / submodel for this year?                      | `vehicles/<model>.yaml`                          |
| C4 | If not, which years *are* known for it, in the DB and in the config?            | both                                               |
| C5 | Has the YAML been reviewed by a person, or is it still the draft built from data? | `vehicles/<model>.yaml` → new `status:` field |

Every combination, and what it means:

| C1 name | C2 in DB      | C3 in config                              | Year vs known years         | Code                                   | Severity | What the troubleshooter does                                                                                                                  |
| ------- | ------------- | ----------------------------------------- | --------------------------- | -------------------------------------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| unknown | –            | –                                        | –                          | `ACCESS_LOOKUP_UNKNOWN_MODEL_NAME`      | error    | Spelling → add an alias to `models.yaml`. New vehicle → add it to `models.yaml` and `vehicles/<model>.yaml`, rerun the vehicle ingest |
| known   | yes           | yes                                       | –                          | *(matched, `LOOKUP OK` at info)*   | –       | Nothing                                                                                                                                       |
| known   | yes           | **no**                              | –                          | `ACCESS_LOOKUP_IN_DB_NOT_IN_CONFIG`     | warning  | Model numbers **are** attached (the DB is the evidence). Add the year to `vehicles/<model>.yaml`                                      |
| known   | **no**  | yes                                       | –                          | `ACCESS_LOOKUP_IN_CONFIG_NOT_IN_DB`     | error    | Config says it's offered, DB has nothing. Rerun the vehicle ingest with a newer export; then ask the source; then add manually                |
| known   | no            | no                                        | after the last known year   | `ACCESS_LOOKUP_YEAR_AFTER_LAST_KNOWN`   | error    | Discontinued → no action. New model year not exported yet → rerun the ingest when it is. Config end year wrong → fix the YAML              |
| known   | no            | no                                        | before the first known year | `ACCESS_LOOKUP_YEAR_BEFORE_FIRST_KNOWN` | error    | Launched later → no action. Export missing early years → ask the source                                                                     |
| known   | no            | no                                        | between known years         | `ACCESS_LOOKUP_YEAR_IN_GAP`             | error    | Model skipped a year → no action. Export missing a year → ask the source                                                                    |
| known   | no (any year) | –                                        | –                          | `ACCESS_LOOKUP_MODEL_NOT_IN_DB`         | error    | Model is in `models.yaml` but has no vehicles at all (e.g. Beetle). Check the export includes it; if not sold in the window, no action      |
| known   | –            | no YAML or no option set for the submodel | –                          | `ACCESS_LOOKUP_NO_CONFIG_FOR_MODEL`     | error    | Add `vehicles/<model>.yaml` (or the submodel's option set)                                                                                  |

**C5, reviewed or drafted:** every check-2 line says the YAML's status, e.g. `(drafted from data, not reviewed)`. A drafted file was built from the same export as the DB, so it can't tell "not sold" from "missing from the export". The troubleshooter knows to confirm with the source before trusting "no action". A new optional field in each `vehicles/<model>.yaml`:

```yaml
status: drafted          # drafted | reviewed
reviewed_by:             # filled when reviewed
reviewed_on:
```

**Today's 7 misses under this scheme:**

| Key                      | Code                                   | Known years (DB / config)                                           |
| ------------------------ | -------------------------------------- | ------------------------------------------------------------------- |
| Arteon 2022, 2023        | `ACCESS_LOOKUP_YEAR_AFTER_LAST_KNOWN`   | 2020–2021 / 2020–2021                                             |
| Atlas (base) 2020        | `ACCESS_LOOKUP_YEAR_BEFORE_FIRST_KNOWN` | 2021–2027 / 2021–2027; the 2020 export has only Atlas Cross Sport |
| Golf R 2020, 2021        | `ACCESS_LOOKUP_YEAR_BEFORE_FIRST_KNOWN` | 2022–2026 / 2022–2026                                             |
| ID.4 2026, ID. Buzz 2026 | `ACCESS_LOOKUP_YEAR_AFTER_LAST_KNOWN`   | to 2025 / to 2025                                                   |

These replace the two names agreed in idea 003 A9 (`model_number_not_found` → `ACCESS_LOOKUP_IN_CONFIG_NOT_IN_DB`; `model_not_offered` → split into the after / before / gap codes, so the code already says which way the year is off).

## Every other scenario, start to end

### Config (shared, `CONFG_`, all fatal)

| Code                      | When                                                                                                                                                                                       | Fix shown                             |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------- |
| `CONFG_FILE_NOT_FOUND`    | A config file is missing                                                                                                                                                                   | The expected path                     |
| `CONFG_YAML_INVALID`      | A file isn't valid YAML                                                                                                                                                                    | File, line and column from the parser |
| `CONFG_VALUE_INVALID`     | A setting has a wrong type or value (e.g. `min_model_year: 20`)                                                                                                                          | Setting, value, what's allowed        |
| `CONFG_UNKNOWN_REFERENCE` | A name points at something that doesn't exist (a keyword value not in categories, a DQ rule or export column not in the accessory layout, a model in `vehicles/` not in `models.yaml`) | Where it's used, the valid names      |
| `CONFG_DUPLICATE_ENTRY`   | The same keyword, alias or option set is defined twice                                                                                                                                     | Both places                           |
| `CONFG_NO_VEHICLE_FILES`  | `config/vehicles/` is empty                                                                                                                                                              | Expected folder                       |

All config problems are collected and shown together, as today, each with its code.

### Vehicle ingest (`VEH_`): today's flags renamed, plus two new ones

| Today                                                           | New code                          | Severity |
| --------------------------------------------------------------- | --------------------------------- | -------- |
| source file not found                                           | `VEH_SRC_FILE_NOT_FOUND`        | fatal    |
| missing required column                                         | `VEH_SRC_COLUMN_MISSING`        | fatal    |
| duplicate (model_number, model_year)                            | `VEH_STGNG_DUPLICATE_KEY`         | fatal    |
| `invalid_model_year`                                          | `VEH_STGNG_INVALID_MODEL_YEAR`    | error    |
| `missing_model_number`                                        | `VEH_STGNG_MISSING_MODEL_NUMBER`  | error    |
| `unexpected_manufacturer`                                     | `VEH_STGNG_UNEXPECTED_MAKE`       | warning  |
| (excluded by year)                                              | `VEH_YEAR_OUT_OF_WINDOW`        | info     |
| `empty_year_window`                                           | `VEH_YEAR_WINDOW_EMPTY`         | warning  |
| `no_model_match`                                              | `VEH_PARSE_NO_MODEL_MATCH`      | error    |
| `unknown_token`                                               | `VEH_PARSE_UNKNOWN_WORD`        | warning  |
| `single_value_conflict`                                       | `VEH_PARSE_CONFLICTING_VALUES`  | warning  |
| `resolution_suggested`                                        | `VEH_RESOLVE_SUGGESTED`         | warning  |
| `resolution_conflict`                                         | `VEH_RESOLVE_CONFLICT`          | warning  |
| `missing_required`                                            | `VEH_VALID_MISSING_REQUIRED`    | error    |
| `no_option_set`                                               | `VEH_VALID_NOT_IN_CONFIG`       | warning  |
| `not_offered`                                                 | `VEH_VALID_OPTION_NOT_OFFERED`  | warning  |
| `inconsistent_model_number`                                   | `VEH_VALID_MODEL_NUMBER_REUSED` | warning  |
| *(new)* a vehicle in the previous DB is gone                  | `VEH_WRITE_VEHICLE_REMOVED`     | warning  |
| *(new)* output file locked (open in Excel or another program) | `VEH_WRITE_FILE_LOCKED`         | fatal    |

Each one gets the same checked / found / causes / fix text in `messages.yaml`.

### Accessories (`ACCESS_`), outside the lookup

| Stage      | Code                                                                         | Severity | When / what the message shows                                                                                                                                                                        |
| ---------- | ---------------------------------------------------------------------------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Vehicle DB | `ACCESS_DB_NOT_FOUND`                                                         | fatal    | `vehicles.csv` missing → "run run_ingest.py first"                                                                                                                                                |
|            | `ACCESS_DB_COLUMN_MISSING`                                                    | fatal    | A column the lookup needs isn't in `vehicles.csv`                                                                                                                                                  |
|            | `ACCESS_DB_STALE`                                                             | warning  | The DB was built with a different config version than now → rerun `run_ingest.py`                                                                                                                 |
|            | `ACCESS_DB_LAST_INGEST_NOT_OK`                                                | warning  | The last vehicle ingest ended `failed` or `ok_with_errors` (from `ingest_runs.csv`)                                                                                                            |
| Source     | `ACCESS_SRC_FILE_NOT_FOUND`                                                   | fatal    | Path from `accessories.yaml`                                                                                                                                                                       |
|            | `ACCESS_SRC_SHEET_NOT_FOUND`                                                  | fatal    | Sheet asked for, sheets that exist                                                                                                                                                                   |
|            | `ACCESS_SRC_HEADER_NOT_FOUND`                                                 | fatal    | The configured header row doesn't hold the expected column names; shows what it does hold                                                                                                            |
|            | `ACCESS_SRC_COLUMN_MISSING`                                                   | fatal    | Configured columns that aren't in the file                                                                                                                                                           |
|            | `ACCESS_SRC_EMPTY`                                                            | fatal    | No data rows                                                                                                                                                                                         |
| Staging    | `ACCESS_STGNG_MISSING_PART_NUMBER` / `ACCESS_STGNG_MISSING_MODEL_NAME`             | error    | Row excluded                                                                                                                                                                                         |
|            | `ACCESS_STGNG_MAKE_MISMATCH`                                                    | error    | Make isn't `Volkswagen` (from `models.yaml`); row excluded                                                                                                                                       |
|            | `ACCESS_STGNG_STATUS_UNEXPECTED`                                                | warning  | Status is neither Active nor Inactive; row excluded, value shown                                                                                                                                     |
|            | `ACCESS_STGNG_DUPLICATE_CONFLICT`                                               | warning  | Same (part, model) appears with different values; which copy was kept and which columns differ                                                                                                       |
| Year       | `ACCESS_YEAR_RANGE_INVALID`                                                   | error    | `year_range` can't be read; row excluded, value shown                                                                                                                                              |
|            | `ACCESS_YEAR_RANGE_REVERSED`                                                  | error    | End year before start year; row excluded                                                                                                                                                             |
|            | `ACCESS_YEAR_OUT_OF_WINDOW`                                                   | info     | Whole range before `min_model_year` (or after max); row excluded                                                                                                                                   |
|            | `ACCESS_YEAR_CLIPPED`                                                         | info     | Range starts before the window; years before it dropped (count per run, not per row)                                                                                                                 |
|            | `ACCESS_YEAR_WINDOW_EMPTY`                                                    | warning  | No rows left after the window                                                                                                                                                                        |
| Clean      | `ACCESS_CLEAN_NOT_NUMERIC`                                                    | error    | MSRP, cost or labour time can't be read as a number; value shown, left empty                                                                                                                         |
|            | `ACCESS_CLEAN_BAD_CHARACTERS`                                                 | info     | Text holds replacement characters (`�`) from an encoding problem; count per column                                                                                                                |
| DQ         | `ACCESS_DQ_MSRP_NOT_ABOVE_COST`                                               | warning  | Both values shown                                                                                                                                                                                    |
|            | `ACCESS_DQ_VALUE_MISSING` / `ACCESS_DQ_VALUE_ZERO` / `ACCESS_DQ_VALUE_NEGATIVE` | warning  | Column and value                                                                                                                                                                                     |
|            | `ACCESS_DQ_FITMENT_HINT`                                                      | info     | Description has a qualifier ("not for R-Line"); fitment unchanged (idea 003 A4)                                                                                                                      |
| Coverage   | `ACCESS_COVER_VEHICLE_NO_PARTS`                                               | warning  | A DB vehicle (model, submodel, year) gets no parts; shows the years its accessories do cover (e.g. "Taos accessories cover 2022–2026") → likely the accessory file isn't updated for that year yet |
|            | `ACCESS_COVER_MODEL_NO_PARTS`                                                 | warning  | A DB model gets no parts in any year                                                                                                                                                                 |
| Export     | `ACCESS_EXPORT_FILE_LOCKED`                                                   | fatal    | The Excel file is open → "close it and rerun"                                                                                                                                                       |
|            | `ACCESS_EXPORT_SHEET_RENAMED`                                                 | info     | A model name had to be shortened or cleaned to be a valid sheet name (31 characters, no `/ \ ? * [ ] :`)                                                                                           |
|            | `ACCESS_EXPORT_SHEET_EMPTY`                                                   | warning  | A model has no matched rows, so its sheet is empty                                                                                                                                                   |

## How flags are counted

- **Once per key, not once per row**, where the cause is the key: lookup and coverage flags are one per (model, submodel, year), with the affected part or vehicle count. The review file lists the rows behind each.
- **Once per row** where the row itself is the problem (bad year range, missing part number, DQ rules).
- **Once per run** for counts that aren't problems (`ACCESS_YEAR_CLIPPED`, `ACCESS_CLEAN_BAD_CHARACTERS`).

## Decisions

| #  | Question                                                                                                                          | Proposed                                        |
| -- | --------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------- |
| E1 | Code format `<PIPELINE>_<STAGE>_<WHAT>` for every flag and fatal? | ✅ 2026-10-27: yes, with prefixes `CONFG` / `VEH` / `ACCESS` and stage `STGNG` (user edit) |
| E2 | Message text (message, causes, fix) in `config/messages.yaml`; code passes only facts; a test keeps code and catalogue in sync? | ✅ 2026-10-27: Yes |
| E3 | Rename the vehicle ingest's existing flags to the new codes (the table above)?                                                    | ✅ 2026-10-27: Yes, as the first phase, with the tests updated |
| E4 | Replace A9's two names with the lookup codes above (after / before / gap split)?                                                  | ✅ 2026-10-27: Yes |
| E5 | Add `status: drafted / reviewed` to `vehicles/*.yaml`; every drafted file starts as `drafted`?                              | ✅ 2026-10-27: Yes |
| E6 | `ACCESS_LOOKUP_IN_DB_NOT_IN_CONFIG` still attaches the model numbers (warning, not error)?                                         | ✅ 2026-10-27: Yes: the DB is the evidence |
| E7 | Four severities: fatal / error / warning / info, with info in the log only?                                                       | ✅ 2026-10-27: Yes |
