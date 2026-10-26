# VW Vehicle Data Pipeline

Builds a clean, structured Volkswagen vehicle database from the VW model export, as the first step towards attaching VW model numbers to accessories.

The VW export only has a free-text `Description` per vehicle (e.g. `Tiguan Comfortline R-Line Black Edition 4MOTION`). The pipeline breaks each description into taxonomy fields (model, submodel, trim, special edition, packages, engine, transmission, drivetrain, ...), checks the result against what each model is allowed to have, and logs every step with before → after detail.

```
datasets/vw_models_data.csv
        │
        ▼
config ─► ingest ─► staging ─► year window ─► clean ─► parse ─► resolve ─► validate ─► write
                                                                              │
                     db/final/vehicles.csv  ◄─────────────────────────────────┤
                     db/review/review_queue.csv  ◄────────────────────────────┤
                     db/logs/  (every step, every change, every flag)  ◄──────┘
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
python run_ingest.py
```

The terminal shows each step with counts and examples, then a summary:

```
[run        ] RUN END | status=ok_with_warnings | rows_staged=323 | rows_excluded_by_year=54 | rows_final=269 | parsed_complete_pct=100.0
```

| Exit code | Meaning |
|---|---|
| `0` | Finished; may have warnings (check the review queue) |
| `1` | Errors were flagged, or the run failed (see the `FATAL` line in the run log) |
| `2` | `config/pipeline.yaml` is invalid |

Options:

```bash
python run_ingest.py --source path/to/other_export.csv   # a different VW export
python run_ingest.py --db-dir path/to/db                 # write the database somewhere else
```

## Test

```bash
python -m pytest tests -q
```

The tests cover each helper module plus full runs on the real data (row counts, traceability of every value, re-run stability, broken config, the year window).

## Where to look after a run

| File | What it shows |
|---|---|
| `db/final/vehicles.csv` | One row per vehicle with its taxonomy fields |
| `db/review/review_queue.csv` | Vehicles a person should check, with the reason |
| `db/logs/runs/<run_id>.log` | The readable story of the run |
| `db/logs/changes/<run_id>.csv` | Every value set or changed: before, after, and the rule or keyword that did it |
| `db/logs/flags/<run_id>.csv` | Every warning and error |
| `db/logs/steps.csv` | One row per step, across all runs |
| `db/dq/ingest_runs.csv` | One summary row per run |

[db/README.md](db/README.md) explains every table, column and review rule.

## Configuration

Everything the pipeline knows lives in `config/` (YAML). The code doesn't change when VW adds vehicles; the config does.

| File | Purpose |
|---|---|
| `pipeline.yaml` | Model year window (`min_model_year: 2020`, `max_model_year:` empty = no upper limit), source file, which fields a reused model number must keep across years, logging |
| `categories.yaml` | The taxonomy fields and whether each is single- or multi-value |
| `models.yaml` | Models, submodels, series, and spelling aliases |
| `keywords.yaml` | What each word or phrase in a description means, grouped by category; plus `resolutions:` that re-read a value for specific vehicles (a lone `Black` becomes `Black Edition` where the option set offers it) |
| `vehicles/<model>.yaml` | What each model can have, per year range (the check on every vehicle) |

### When new vehicles come out

1. Run `python run_ingest.py` on the new export.
2. New words show up in the review queue as `unknown_token` → add them to `config/keywords.yaml`.
3. New models or years show up as `no_option_set` → add or extend the option set in `config/vehicles/<model>.yaml`.
4. Re-run. The `write` step logs exactly which vehicles were added or changed in `vehicles.csv`.

A broken config (unknown category, duplicate keyword, typo in an option set, overlapping years) stops the run with a message saying which file and entry to fix.

## Project layout

```
source_code/VW/
├── run_ingest.py                    entry point
├── requirements.txt
├── config/                          YAML config (see above)
├── pipeline/                        plain helper functions, one module per job
│   ├── logging_helpers.py           run / step / change / flag logs
│   ├── config_helpers.py            load + validate config, export definitions
│   ├── ingest_helpers.py            read source, staging, year window
│   ├── clean_helpers.py             aliases, repeated-word removal
│   ├── parse_helpers.py             description → taxonomy fields
│   ├── resolve_helpers.py           resolutions (e.g. lone "Black" → Black Edition)
│   ├── validate_helpers.py          option-set and consistency checks
│   └── storage_helpers.py           the only module that knows the db/ layout
├── tests/                           pytest
├── db/                              generated output (db/logs/ is git-ignored)
├── datasets/                        source files (VW model export, accessories)
├── assets/                          taxonomy guide
├── planning/                        ideas → plans → completed
└── oem_access_data_analysis.ipynb   exploration notebook
```

## More detail

- Taxonomy rules: [assets/vw_vehicle_keyword_taxonomy_and_normalization_guide.md](assets/vw_vehicle_keyword_taxonomy_and_normalization_guide.md)
- Design decisions: [planning/ideas/001_vw_model_ingest_design.md](planning/ideas/001_vw_model_ingest_design.md), [planning/ideas/002_pipeline_logging_design.md](planning/ideas/002_pipeline_logging_design.md)
- Build plans and status: [planning/plans/](planning/plans/)
