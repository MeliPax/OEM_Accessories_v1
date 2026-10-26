# 003 — Accessory Ingest + Model Number Matching: Plan

**Status:** Plan — waiting for approval (2026-10-26)
**Idea / design:** [ideas/003_accessory_model_matching_design.md](../ideas/003_accessory_model_matching_design.md) (decisions A1–A9)
**Depends on:** [plan 001](001_vw_model_ingest_mvp.md) (`db/final/vehicles.csv`, `config/`) and [plan 002](002_pipeline_logging.md) (`run_step` and the logging helpers)

## Outcome

One call gives the notebook's per-model dict of accessory DataFrames, with a `model_number` column fetched from the vehicle DB:

```python
from pipeline.accessory_helpers import build_accessory_model_dict
model_year_dict = build_accessory_model_dict()
model_year_dict["GTI"]
# part_number | model_name | product_description | comments | msrp | cost | labor_time
# | min_year | max_year | applicable_year | match_key | model_number | match_status
```

- One row per part, applicable year and model number (A5). Unmatched part-years stay in with `model_number` empty and `match_status` set to the flag (A8).
- The vehicle DB is searched once per unique (model name, year) key, never per row, and nothing merged is saved (A1).
- `python run_accessories.py` runs the same thing from the terminal.

**Written to disk:** only the usual logs plus three small files:

| File | Content |
|---|---|
| `db/logs/...` | Run log, steps, changes and flags, as for the vehicle ingest |
| `db/dq/accessory_lookup.csv` | One row per key (71 today): what was checked, what was found, or why it missed |
| `db/review/accessory_review.csv` | One row per unmatched part-year and unknown model name, with both check results and the fix |
| `db/dq/accessory_runs.csv` | One summary row per run |

**Success criteria (today's data)**

- [ ] 13,051 rows in the year window → 1,357 (part, model) rows after exact-duplicate removal, logged.
- [ ] 14 model names resolved once each, 0 `unknown_accessory_model`.
- [ ] 71 keys looked up: 64 found, 7 flagged `model_not_offered` (Arteon 2022–23, Atlas 2020, Golf R 2020–21, ID. Buzz 2026, ID.4 2026), each flag naming both checks and their results.
- [ ] Every row in the dict with a `model_number` traces to one `LOOKUP` line in the run log via its `match_key`.
- [ ] The unmatched part-years in the dict equal the rows in `accessory_review.csv` (about 451 today).
- [ ] Rerunning the vehicle ingest with the shared `GTI` alias leaves `vehicles.csv` unchanged (0 added / removed / changed).
- [ ] A rerun with no data or config change gives identical lookup and review files.

---

## Phase 1 — Config

- [ ] `models.yaml`: add `GTI: Golf GTI` to the shared aliases (A3). It only rewrites the word `GTI` (the accessory file's name for the Golf GTI); `Golf` alone is never changed and stays the base Golf (2020–2021).
- [ ] Rerun `run_ingest.py`; confirm the `write` step reports 0 rows added / removed / changed.
- [ ] New `config/accessories.yaml` (A6): source file, sheet, header row in data, column renames and types, `keep_rows: {status: [Active]}`, output columns, DQ rules (the notebook's `data_rules`).
- [ ] `pipeline.yaml`: add `sources.accessories`; the year rule (`range_overlap`) is already there.
- [ ] `config_helpers.load_accessory_config()`: validates the file (required keys, renamed columns exist in the DQ rules and output columns, rule names known); errors raise `ConfigError`.
- [ ] `config_helpers.declared_years(option_sets)`: `{(model, submodel): set(years)}` from `vehicles/*.yaml`, used as the fallback check (A9).

**Done when:** a bad `accessories.yaml` (unknown column in a rule, missing source) stops with a clear `ConfigError`, and the vehicle ingest rerun is clean.

## Phase 2 — Ingest, staging, year window

New `pipeline/accessory_helpers.py`:

- [ ] `read_accessories(path, spec, ctx)`: read the sheet as text, promote the header row, keep the configured columns; log file, rows and columns.
- [ ] `stage_accessories(df, spec, ctx)`: rename, keep `status = Active`, add lineage (`source_file`); log rows filtered by status.
- [ ] `split_year_range(df, ctx)`: `year_range` → `min_year` / `max_year` (no "-" means one year); unparseable ranges flagged `bad_year_range` and excluded.
- [ ] Year window: reuse `ingest_helpers.filter_by_year_window(df, settings, 'accessories', ctx)`; each excluded row logged with its reason.
- [ ] Exact-duplicate removal: drop rows identical on every kept column; log the count; flag `conflicting_duplicate` for (part_number, model_name) pairs whose copies differ (idea risk 9).

**Done when:** today's file stages 20,399 Active rows, keeps 13,051 in the window, and dedupes to 1,357, all reconciled in `steps.csv`.

## Phase 3 — Clean and resolve model names

- [ ] `clean`: trim text, empty → null; type `msrp`, `cost`, `labor_time` as numbers (unparseable values flagged `not_numeric`, never guessed); `model_name_clean` via `clean_helpers.clean_value` with the shared aliases. Before → after logged per changed value.
- [ ] `resolve_names`: run `parse_helpers.match_model()` on each **unique** `model_name_clean` (14 today) → model and submodel. One `RESOLVED` log line per name; a name that doesn't match is flagged `unknown_accessory_model` and its rows go to review.

**Done when:** `GTI` → Golf / GTI, `Golf` → Golf / (base), `Atlas Cross Sport` → Atlas / Cross Sport, and an invented name in a test file is flagged, not guessed.

## Phase 4 — Lookup (the fetch)

New `pipeline/lookup_helpers.py`:

- [ ] `load_vehicle_index(db_dir, ctx)`: read only `model`, `submodel`, `model_year`, `model_number`, `taxonomy_version` from `vehicles.csv`; group once into `{(model, submodel, year): [model numbers]}`. Missing `vehicles.csv` → `PipelineFatal` ("run run_ingest.py first"). If its `taxonomy_version` differs from the current config, warn `stale_vehicle_db` (idea risk 6).
- [ ] `unique_keys(df)`: (model, submodel, year) for every applicable year, clipped to the window (D15); 71 today.
- [ ] `fetch(keys, index, declared, ctx)`: one lookup per key.
  - **Found:** log `LOOKUP | match_key=volkswagen|golf|gti|2023 | found=6 | model_numbers=...`.
  - **Not found:** run the fallback check against `declared_years`, then flag once per key, with the affected part count:
    - `model_number_not_found` when the config covers the year;
    - `model_not_offered` when it doesn't.
  - Each flag states `check_1` (vehicles.csv, what was searched, 0 rows), `check_2` (which YAML, which years it covers, the result) and `fix`, as in the idea's example.
- [ ] Write `db/dq/accessory_lookup.csv`: match_key, model, submodel, year, parts, check_1_result, check_2_result, flag, model_count, model_numbers.

**Done when:** today's data gives 64 found and 7 `model_not_offered`. A test with a year that's covered in the YAML but has no vehicle gives `model_number_not_found`.

## Phase 5 — Build the dict and the review file

- [ ] `build_model_year_dict(df, lookup)`: explode each row to its applicable years (clipped to the window), `map` the lookup result onto (model, submodel, year), explode the model numbers (A5), group by `model_name`. This is the notebook's function with the attach step added; output columns come from `accessories.yaml`.
- [ ] `match_status`: `matched`, `model_number_not_found`, `model_not_offered` or `unknown_accessory_model`.
- [ ] Write `db/review/accessory_review.csv`: one row per unmatched part-year (part_number, model_name, year, match_key, flag, check_1_result, check_2_result, fix), sorted by model and year.
- [ ] Log rows per model, matched part-years and unmatched part-years; check that unmatched part-years = review rows.

**Done when:** the dict has one DataFrame per accessory model name, and every unmatched row in it appears in the review file.

## Phase 6 — Validate, entry points, docs

- [ ] `validate`: the DQ rules from `accessories.yaml` (msrp > cost, max_year ≥ min_year, not null, non-zero, non-negative) as warnings that never stop the run. `fitment_hint` (qualifier words such as "not for R-Line" in descriptions) logged at INFO only (A4).
- [ ] `build_accessory_model_dict(config_dir, db_dir, source, ctx=...)` in `accessory_helpers.py`: runs the steps through `run_step` (config → ingest → staging → year_window → clean → resolve_names → lookup → build_dict → validate), writes `accessory_runs.csv`, returns the dict (A7).
- [ ] `run_accessories.py`: thin terminal wrapper, same exit codes as `run_ingest.py` (0 ok / ok with warnings, 1 errors or failed, 2 `pipeline.yaml` unreadable); prints rows per model and the flag summary.
- [ ] README: how to run the accessories step and where its outputs are; `db/README.md`: the three new files.
- [ ] Notebook: a cell that calls `build_accessory_model_dict()` (added when you close the notebook; I won't edit it while it's open).

**Done when:** the success criteria above pass on today's data, and a run from the terminal and from the notebook gives the same dict.

---

## Tests

Added to `tests/`, all on small fixture files, plus one end-to-end run on today's data:

| File | Covers |
|---|---|
| `test_accessory_helpers.py` | Header promotion, rename, Active filter, year-range split (single year, bad value), dedupe and `conflicting_duplicate`, `clean` typing and `not_numeric`, DQ rules |
| `test_lookup_helpers.py` | Index build, unique keys with year clipping, found key, `model_number_not_found` vs `model_not_offered` with both check results in the message, `unknown_accessory_model`, missing and stale `vehicles.csv` |
| `test_accessories_end_to_end.py` | Today's counts (1,357 / 71 / 64 / 7), dict ↔ review reconciliation, every `model_number` traceable to a `LOOKUP` line, stable rerun |
| `test_config_helpers.py` (extend) | `load_accessory_config` errors, `declared_years`, shared alias leaves VW descriptions unchanged |

The existing 84 tests must still pass.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-10-26 | Lookup by unique (model, submodel, year) key; attach while building the dict; no merged table saved (A1) | User: "a fetch will be enough"; 71 searches instead of 6,474 |
| 2026-10-26 | An accessory fits every vehicle in its specified set; descriptions never narrow it (A1, A4) | User requirement |
| 2026-10-26 | Accessory `Golf` = base Golf only; legit years come from `vehicles/<model>.yaml` (A2) | User; base Golf already declared 2020–2021 with AU22M2 / AU22MS / AU23M2 / AU23MS |
| 2026-10-26 | One alias list for all datasets (A3) | User: same standards on both sides; checked, no VW description changes |
| 2026-10-26 | One row per model number (A5) | User |
| 2026-10-26 | `accessories.yaml`; notebook function + terminal runner (A6, A7) | User |
| 2026-10-26 | Unmatched part-years kept in the dict, flagged in the logs and listed in a review file (A8) | User: "add them in the logs and report to review" |
| 2026-10-26 | Miss flags `model_number_not_found` / `model_not_offered`, using the YAML as fallback; each flag states what was checked and what failed (A9) | User: clearer names for faster debugging |

## Risks

| Risk | Mitigation |
|---|---|
| The shared `GTI` alias changes a future VW description | Phase 1 rerun shows any change in the `write` step; repeated-word removal covers today's "Golf GTI ..." |
| Accessories run against an old `vehicles.csv` | `stale_vehicle_db` warning when its `taxonomy_version` differs from the current config |
| The accessory file layout changes (new header row, renamed column) | Layout lives in `accessories.yaml`; a missing configured column is a `ConfigError` naming it |
| Exploding to one row per model number grows the dict | About 25k rows today; fine in memory. Revisit only if files get much bigger |
