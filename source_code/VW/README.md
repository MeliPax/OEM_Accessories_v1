# VW Vehicle + Accessory Pipeline

Two pipelines, run in order:

1. **Vehicle ingest** (`run_ingest.py`) builds a clean Volkswagen vehicle database from the VW model export. The export only has a free-text `Description` per vehicle (e.g. `Tiguan Comfortline R-Line Black Edition 4MOTION`). The pipeline breaks each description into taxonomy fields (model, submodel, trim, special edition, packages, engine, transmission, drivetrain, ...) and checks the result against what each model is allowed to have.
2. **Accessories** (`run_accessories.py`, or `build_accessory_model_dict()` from the notebook) attaches VW model numbers to the accessory file. An accessory fits every vehicle in its model / submodel and year range. The vehicle database is searched **once per unique (model, year)**, not once per row, and nothing merged is saved. The result is one DataFrame per accessory model name, exported to Excel with one sheet per model.

Both pipelines log every step with before → after detail. Every problem is a **coded flag** (e.g. `ACCESS_LOOKUP_YEAR_AFTER_LAST_KNOWN`) that says what was checked, what was found, the likely causes and how to fix it.

```
datasets/vw_models_data.csv
   │  run_ingest.py
   ▼
config ─► ingest ─► staging ─► year window ─► clean ─► parse ─► resolve ─► validate ─► write
                                                                                        │
                                                         db/final/vehicles.csv  ◄───────┘
                                                                │
datasets/...Accessories Data EN.xlsx                            │ (one lookup per unique key)
   │  run_accessories.py                                        ▼
   ▼
config ─► ingest ─► part numbers ─► staging ─► year window ─► clean text ─► dedupe ─► part number review ─► clean ─► resolve names ─► lookup
        ─► build dict ─► coverage ─► validate ─► verify ─► export ─► output/vw_accessories_<date_time>.xlsx
```

## Requirements

- Python 3.11 or newer (tested on 3.14)
- The packages in [requirements.txt](requirements.txt): pandas, PyYAML, pytest, openpyxl

## Install

From this folder (`source_code/VW`):

```bash
python -m pip install -r requirements.txt
```

Use `python -m pip`, not `pip`, so the packages go into the same Python that runs the pipeline. Optionally, create a virtual environment first:

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (macOS / Linux: source .venv/bin/activate)
python -m pip install -r requirements.txt
```

## Run

```bash
python run_ingest.py          # 1. vehicle database (rerun when the VW export or the config changes)
python run_accessories.py     # 2. accessories + model numbers + Excel export
```

`run_accessories.py` prints rows per model, then where everything went:

```
status: ok_with_errors | keys found 64 of 71 | unmatched part-years 451 | vehicles without parts 14
export: output/vw_accessories_20261027_100331.xlsx
review: db/review/accessory_review.csv | lookup: db/dq/accessory_lookup.csv
```

From the notebook:

```python
from pipeline.accessory_helpers import build_accessory_model_dict
model_year_dict = build_accessory_model_dict()          # export=False to skip the Excel file
model_year_dict["GTI"]   # one row per part, applicable year and vehicle, with model_number and variant
```

| Exit code | Meaning |
|---|---|
| `0` | Finished; may have warnings (check the review files) |
| `1` | Errors were flagged (e.g. accessory years with no vehicle), or the run failed (see the `FATAL` line) |
| `2` | `config/pipeline.yaml` is invalid |

Options:

```bash
python run_ingest.py --source path/to/other_export.csv          # a different VW export
python run_accessories.py --source path/to/other_accessories.xlsx
python run_accessories.py --no-export                           # dict + reports only
python run_ingest.py --db-dir path/to/db                        # database somewhere else (both scripts)
```

Run ids are the pipeline name followed by the run's date and time, e.g. `vw_ingest_20261027_143005` or `vw_accessories_20261027_143005`. Every log file and the export are named after them.

## Test

```bash
python -m pytest tests -q
```

The tests cover each helper module, the message catalogue, and full runs of both pipelines on the real data: row counts, traceability, rerun stability, broken config, the year window, every lookup case, and the export.

## Where to look after a run

| File | What it shows |
|---|---|
| `db/final/vehicles.csv` | One row per vehicle with its taxonomy fields |
| `db/review/review_queue.csv` | Vehicles a person should check (vehicle ingest) |
| `db/review/accessory_review.csv` | Accessory part-years with no vehicle, part numbers restored or not proven, suspect values (labour units, unreviewed links), and vehicles with no parts, each with code, checks, causes and fix |
| `db/dq/part_number_check.csv` | How every part number was proven by `make&model`: same, restored (leading zeros put back) or why not |
| `db/dq/accessory_lookup.csv` | One row per (model, submodel, year) key: what was checked, the model numbers found or why it missed |
| `db/dq/verified_flags.csv` | Flags a verified fact explained this run (now info, left out of review), with the entry, reason, who and when |
| `output/<run_id>.xlsx` | The accessory export: one sheet per accessory model name, matched rows only (git-ignored) |
| `db/logs/runs/<run_id>.log` | The readable story of a run; each flag is a block with what / checked / found / causes / fix |
| `db/logs/changes/<run_id>.csv` | Every value set or changed: before, after, and the rule or keyword that did it |
| `db/logs/flags/<run_id>.csv` | Every flag, with its code and full message |
| `db/logs/steps.csv` | One row per step, across all runs |
| `db/dq/ingest_runs.csv`, `db/dq/accessory_runs.csv` | One summary row per run |

[db/README.md](db/README.md) explains every table, column and flag code.

## Flags and messages

Every flag has a code `<PIPELINE>_<STAGE>_<WHAT>`: `CONFG_` for config, `VEH_` for the vehicle ingest, `ACCESS_` for accessories. Its severity and wording live in [config/messages.yaml](config/messages.yaml):

| Severity | Meaning |
|---|---|
| `fatal` | The run stops (broken config, missing file, output file open in Excel) |
| `error` | A row or key can't be used (left out, or no model number) and goes to review |
| `warning` | Used, but a person should look; goes to review |
| `info` | Noted in the log only |

To improve a message, edit `messages.yaml`. A test keeps the codes in the code and the catalogue in sync. The full list of scenarios is in [planning/ideas/004_error_message_catalogue_design.md](planning/ideas/004_error_message_catalogue_design.md).

## Configuration

Everything the pipelines know lives in `config/` (YAML). The code doesn't change when VW adds vehicles or the accessory file changes; the config does.

| File | Purpose |
|---|---|
| `pipeline.yaml` | One model year window per pipeline under `datasets:`. Vehicles `vw_models`: `min_model_year: 2020`. Accessories: `min_model_year: current_year - 2` (2024 in 2026, worked out at run start). `max_model_year:` empty = no upper limit. Every step that selects data uses its window and ignores anything outside it: the accessory run reads only vehicles inside the accessory window. `within: vw_models` keeps the accessory window inside the vehicle window (an empty accessory max takes the vehicle max). Also source files, which fields a reused model number must keep across years, logging |
| `categories.yaml` | The taxonomy fields and whether each is single- or multi-value |
| `models.yaml` | Models, submodels, series, and spelling aliases **shared by both pipelines** (e.g. accessory `GTI` → `Golf GTI`) |
| `keywords.yaml` | What each word or phrase in a description means, grouped by category; plus `resolutions:` that re-read a value for specific vehicles (a lone `Black` becomes `Black Edition` where the option set offers it) |
| `vehicles/<model>.yaml` | What each model can have, per year range. It also says which years a model legitimately exists. `status: drafted` (built from the data) or `reviewed` (checked by a person). A `verified:` section records facts a person confirmed, e.g. never offered in a year (see below) |
| `accessories.yaml` | Accessory file layout (sheet, header row, columns), the **part number** check (`make&model` proves the full part number; never padded), **units** (labour minutes → hours), **comment cleaning** (separators, tags, link rules, allowed link hosts), kept statuses, data-quality rules, fitment hint words, the **variant** label (which vehicle fields describe it, in what order, and the `Base` label when none has a value), and the export (folder, file name, columns and headers in order) |
| `messages.yaml` | Severity, message, causes and fix for every flag code |

### When new vehicles or a new accessory file come out

1. Run `python run_ingest.py` on the new VW export.
2. New words show up as `VEH_PARSE_UNKNOWN_WORD` → add them to `config/keywords.yaml`.
3. New models or years show up as `VEH_VALID_NOT_IN_CONFIG` → add or extend the option set in `config/vehicles/<model>.yaml`.
4. Run `python run_accessories.py`. Check `db/review/accessory_review.csv`:
   - an `ACCESS_LOOKUP_*` code means accessory years have no vehicle; the fix steps say whether to rerun the ingest, add a year to the config, or ask the data source;
   - `ACCESS_COVER_VEHICLE_NO_PARTS` means vehicles have no parts yet, usually because the accessory file isn't updated for that model year.
5. Once someone has checked a `vehicles/<model>.yaml`, set `status: reviewed` with `reviewed_by` / `reviewed_on`.

### Recording what a person confirmed (verified facts)

When a flag keeps coming back for something a person has confirmed, record the fact once in `config/vehicles/<model>.yaml`:

```yaml
verified:
  - submodel: R                      # leave out for the base model
    never_offered:
      years: [2020, 2021]            # each year listed; never a range
    reason: Golf R wasn't offered in Canada for model years 2020-2021; it returned for 2022
    verified_by: P.M
    verified_on: 2026-10-28
```

| Fact | Means | Effect |
|---|---|---|
| `never_offered: {years: [...]}` | The vehicle didn't exist in those years | Accessory lookup flags for exactly that model, submodel and year drop to info and leave the review file |
| `never_offered: {<category>: [...]}` + `years: [...]` | That option didn't exist on the vehicle in those years | Guards the data: a vehicle in the export with that option is an error |
| `no_parts_expected: {years: [...], until: YYYY-MM-DD}` | The vehicle exists, but no parts are expected yet | Its `ACCESS_COVER_VEHICLE_NO_PARTS` flags drop to info until the date, then come back (`ACCESS_VERIFY_EXPIRED`) |

The final `verify` step in both pipelines applies these:
- **Kept:** nothing is deleted. A verified flag keeps its original severity and the entry in the flag log, and is listed in `db/dq/verified_flags.csv`.
- **Contradictions:** data that contradicts a fact becomes an error (`ACCESS_VERIFY_CONTRADICTED`, `VEH_VERIFY_CONTRADICTED`), for example a Golf R 2021 in a future export.
- **Unused facts:** a fact that matched nothing is reported as info (`ACCESS_VERIFY_ENTRY_UNUSED`).
- **Which flags:** only the codes marked `verifiable: true` in `messages.yaml` can be verified.

A broken config stops the run with a `CONFG_` code, the file and entry to fix, and the fix steps. Examples: an unknown category, a duplicate keyword, a typo in an option set, an export column that doesn't exist.

## Project layout

```
source_code/VW/
├── run_ingest.py                    vehicle ingest entry point
├── run_accessories.py               accessories entry point
├── requirements.txt
├── config/                          YAML config (see above)
├── pipeline/                        plain helper functions, one module per job
│   ├── logging_helpers.py           run / step / change / flag logs, fatal()
│   ├── message_helpers.py           the flag message catalogue (messages.yaml)
│   ├── config_helpers.py            load + validate config, export definitions
│   ├── ingest_helpers.py            read source, staging, year window
│   ├── clean_helpers.py             aliases, repeated-word removal
│   ├── parse_helpers.py             description → taxonomy fields
│   ├── resolve_helpers.py           resolutions (e.g. lone "Black" → Black Edition)
│   ├── validate_helpers.py          option-set and consistency checks
│   ├── accessory_helpers.py         accessory ingest, part numbers, units, dict, data quality, export
│   ├── text_helpers.py              comment cleaning (tags, pipes, links, spaces)
│   ├── lookup_helpers.py            vehicle index, per-key fetch, coverage
│   └── storage_helpers.py           the only module that knows the db/ layout
├── tests/                           pytest
├── db/                              generated output (db/logs/ is git-ignored)
├── output/                          accessory exports (git-ignored)
├── datasets/                        source files (VW model export, accessories)
├── assets/                          taxonomy guide
├── planning/                        ideas → plans → completed
└── oem_access_data_analysis.ipynb   exploration notebook
```

## More detail

- Taxonomy rules: [assets/vw_vehicle_keyword_taxonomy_and_normalization_guide.md](assets/vw_vehicle_keyword_taxonomy_and_normalization_guide.md)
- Design decisions: [planning/ideas/](planning/ideas/) (001 vehicle ingest, 002 logging, 003 accessories, 004 flag messages, 005 report card, 006 labour units, 007 comment cleaning, 008 part numbers)
- Data issues found in the source files: [planning/data_issues.md](planning/data_issues.md)
- Build plans and status: [planning/plans/](planning/plans/)
