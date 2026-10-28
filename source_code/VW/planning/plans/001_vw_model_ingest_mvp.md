# 001 — VW Model Ingest MVP: Plan

**Status:** Built — in user testing (2026-10-26)
**Updated:** 2026-10-26
**Next:** user signs off testing (OI-01); review config/vehicles (OI-03); notebook cell (OI-02)
**Links:** idea [001](../ideas/001_vw_model_ingest_design.md) · logging from plan [002](002_pipeline_logging.md)
**Summary:** The VW vehicle ingest: config, staging, year window, cleaning, parsing, resolutions, validation and vehicles.csv.
**Branch:** `feature/vw-data-analysis` (or a new `feature/vw-model-ingest` from `dev`, per `accy_v2/planning/VERSIONING.md`)

## Outcome

Running one command rebuilds a CSV database from `datasets/vw_models_data.csv`:

- every VW model row is in staging, untouched;
- every row is in `db/final/vehicles.csv` with its description broken into taxonomy columns;
- every vehicle is checked against its option set in `config/vehicles/`;
- anything that needs a person's eye is in `db/review/review_queue.csv` (the manual check); it's resolved by fixing the config and re-running;
- anything the rules couldn't classify is reported in `db/dq/ingest_issues.csv`, never silently dropped.

**MVP success criteria**

- [x] All 323 source rows land in staging. At `min_model_year: 2020` with `max_model_year` empty, 269 reach final and 54 are counted as excluded by year (staged = final + excluded).
- [x] 112 / 112 unique clean descriptions (2020+) parse with `parse_status = complete` (0 unparsed tokens).
- [x] Changing `min_model_year` / `max_model_year` in `config/pipeline.yaml` and re-running changes the final row count with no code change. Emptying `max_model_year` includes every year from `min` onward.
- [x] Re-running produces identical output (deterministic `vehicle_id`, sorted writes).
- [x] Changing one keyword in YAML and re-running changes only the affected rows.
- [x] The golden examples from the taxonomy guide parse exactly as documented (with `Black Edition` as a special edition).
- [ ] Every 2020+ vehicle is covered by a reviewed option set, with 0 `not_offered` flags left unexplained.

## Target layout

```
source_code/VW/
├── config/                 pipeline.yaml, categories.yaml, models.yaml, keywords.yaml
│   └── vehicles/           one option-set file per model
├── pipeline/               *_helpers.py (plain functions)
├── db/
│   ├── definitions/        generated from config/
│   ├── staging/
│   ├── final/
│   ├── review/             review_queue.csv, drafts/
│   └── dq/
├── tests/                  pytest for the helpers
└── run_ingest.py
```

---

## Phase 1 — Taxonomy config (YAML) + loader

Turn the markdown guide into machine-readable config, and make sure bad config fails loudly.

- [x] Write `config/pipeline.yaml`: `min_model_year: 2020`, `max_model_year:` (empty), plus per-dataset year settings (`vw_models`: `single_year` on `ModelYear`; `accessories`: `range_overlap` on `min_year` / `max_year`).
- [x] `config_helpers.load_settings()`: read `pipeline.yaml`; fail if `min_model_year` is missing or not a 4-digit int, `max_model_year` is set but not a 4-digit int, `max_model_year < min_model_year`, or a dataset names an unknown `year_rule`. Empty `max_model_year` loads as `None`.
- [x] Write `config/categories.yaml`: the 15 taxonomy categories (the guide's 14 schema fields incl. make + `performance_package`), each with `description`, `column`, `multi_value`, `use_for_matching`.
- [x] Write `config/models.yaml`: make, models, submodels, an optional `series` (GTI / R = Performance, Alltrack = Adventure; null elsewhere, D14), and the alias map (move `VW_DESCRIPTION_ALIASES` here).
- [x] Write `config/keywords.yaml` in the grouped layout (idea doc, Idea 6): one section per category, `phrases` and `words`, each entry `match` / optional `value` / optional `models`. Includes the guide's keywords and composites, `Performance` → `performance_package`, `Black Edition` → `special_edition` phrase, `Black` → `appearance_package` word, and the 2019 words (`Coupe`, `Convertible` → `body_style`; `Dune` → `special_edition`).
- [x] Update the taxonomy guide in `assets/`: add `performance_package`, move `Black Edition` to special editions, add the 2019 words, so the guide and config match.
- [x] `config_helpers.load_taxonomy()` — read the three files into plain dicts.
- [x] `config_helpers.validate_taxonomy()` — fail with a clear message if: a section names an unknown category, a `models:` scope names an unknown model, the same `match` + scope appears twice (in any category), or a single-value category could be set twice by one phrase.
- [x] `config_helpers.export_definitions()` — write `db/definitions/dim_category.csv`, `dim_keyword.csv`, `dim_model.csv`.

**Done when:** the loader validates cleanly, a deliberately broken config fails with a readable error, and the three definition CSVs are generated. The four 2019 Beetle descriptions are test cases (`Beetle Coupe Dune Auto` → body_style `Coupe`, special_edition `Dune`, transmission `Automatic`).

## Phase 2 — Storage + ingest to staging

- [x] `storage_helpers.py` — the only module that knows the `db/` paths: `write_table(df, layer, name)`, `read_table(layer, name)`. Writes are sorted by key and use a fixed column order, so diffs between runs are meaningful.
- [x] `ingest_helpers.read_source()` — read the CSV with codes as text (`ModelNumber`, `Package`, `Style_ID`), drop all-empty columns.
- [x] `ingest_helpers.to_staging()` — rename to snake_case, add `source_file`, `source_row`, `ingested_at`, keep values untouched.
- [x] Validate on ingest: required columns present, `(model_number, model_year)` unique, `model_year` numeric. Failures go to `dq/ingest_issues.csv`; a duplicate key stops the run.

- [x] `ingest_helpers.filter_by_year_window(df, settings, dataset)`: one helper for both datasets. `single_year`: `min <= year <= max`. `range_overlap`: `end >= min` and `start <= max`. The `max` check is skipped when `max_model_year` is `None`. Returns `(kept_df, excluded_count)`. It runs after staging, so staging keeps every row.

**Done when:** `stg_vw_models.csv` has 323 rows, the key check passes, and the year filter keeps 269 at `min: 2020` / `max` empty, and 197 at `max: 2024`.

## Phase 3 — Clean + parse (transform)

- [x] Move `apply_aliases` and the repeated-word cleanup from the notebook into `clean_helpers.py` (same behaviour; the notebook imports them afterwards instead of redefining them).
- [x] `parse_helpers.match_model()` — longest model phrase at the start of the description, then submodel phrase scoped to that model; returns model, submodel, series and the remaining tokens.
- [x] ~~`parse_helpers.apply_composites()`~~ — folded into `classify_tokens()`: phrases and words are one list, matched longest first, so a phrase consumes its words.
- [x] `parse_helpers.classify_tokens()` — single-token lookup with model scope; returns (category, raw token, normalized value) triples and the leftovers.
- [x] `parse_helpers.parse_description()` — runs the three steps for one description and returns a dict: taxonomy columns + `unparsed_tokens` + `parse_status`.
- [x] Parse each **unique** clean description once and join the result back to the rows (112 parses instead of 269 at the 2020 window; also guarantees identical descriptions get identical attributes).
- [x] Build the `vehicles` DataFrame, with `vehicle_id = VW-{model_year}-{model_number}`. Multi-value categories are stored sorted and `|`-joined; `parse_helpers.split_multi_value()` is the only reader of that format.

**Done when:** the taxonomy guide's golden examples parse exactly as documented (they become pytest cases), and every unique description has a parse result.

## Phase 4 — Validation + DQ reporting

- [x] `validate_helpers.check_required()` — `make`, `model`, `model_year`, `model_number` present.
- [x] `validate_helpers.check_single_value_conflicts()` — e.g. two different trims on one vehicle.
- [x] `validate_helpers.check_unknown_tokens()` — one issue per unparsed token, with the description it came from.
- [x] Each issue row: `run_id, vehicle_id, rule, severity (error|warning), detail`.
- [x] Append one row per run to `dq/ingest_runs.csv`: run id, timestamp, source file, `min_model_year`, `max_model_year`, rows in/staged/excluded_by_year/final, % parsed complete, issue counts by rule.

**Done when:** a description with a made-up word ends up as `partial` with exactly one `unknown_token` issue, and the run summary reports it.

## Phase 5 — Option sets + manual review

- [x] `config_helpers.load_option_sets()`: read every `config/vehicles/*.yaml`. Fail if a model/submodel isn't in `models.yaml`, a value isn't in the vocabulary for that category, or two sets for the same model + submodel overlap in years.
- [x] ~~`config_helpers.draft_option_sets(vehicles)`~~: done as a one-off instead (2026-10-26). The 10 files in `config/vehicles/` were drafted from the 2020+ data, so no pipeline helper is needed; future vehicles are added by hand.
- [ ] Review the drafted `config/vehicles/*.yaml` (Arteon, Atlas, e-Golf, Golf, ID. Buzz, ID.4, Jetta, Passat, Taos, Tiguan) and adjust where the data under-describes a vehicle. From then on, option sets are written by hand when new vehicles come out.
- [x] `validate_helpers.check_option_sets()`: flag `no_option_set` and `not_offered` (strict: unlisted category = not offered).
- [x] `validate_helpers.check_model_number_consistency()`: flag a model number whose parsed values differ across years (e.g. `RM1VPJ`).
- [x] `storage_helpers` writes `db/review/review_queue.csv` every run (columns in the idea doc, Idea 8).

**Done when:** the reviewed option sets cover every 2020+ vehicle; a deliberately wrong value (e.g. trim `Execline` on a 2025 Tiguan) shows up as `not_offered` in the review queue; and `RM1VPJ` shows up as `inconsistent_model_number`.

## Phase 6 — Runner, tests, notebook hook-up

- [x] `run_ingest.py` — `config → staging → year window → clean → parse → validate → final + review queue` in order, prints a short summary (rows, coverage, issues), and exits non-zero on errors.
- [x] `tests/` — pytest for: config validation, model/submodel matching (`ID. Buzz` vs `ID.4`, `Golf R` vs `R-Line`), phrases before words (`Black Edition` vs `Black`), model scope (`S`), option-set validation, golden examples, end-to-end row-count reconciliation.
- [ ] Notebook: add a cell that loads `db/final/vehicles.csv` for analysis, and import the clean helpers instead of redefining them.
- [x] Short `db/README.md` describing each table and column (generated from `dim_category.csv` where possible).

**Done when:** all MVP success criteria above are ticked, and `pytest source_code/VW/tests` passes.

## Phase 7 — Handover to matching (next plan, not MVP)

Captured so the MVP output is shaped correctly for it:

- Map accessory `model_name` values to taxonomy pairs: `GTI` → (Golf, GTI), `Golf R` → (Golf, R), `Atlas Cross Sport` → (Atlas, Cross Sport), `Jetta GLI` → (Jetta, GLI).
- Filter `vehicles.csv` on the accessory's (`model`, `submodel`, ...) columns and year range to attach `model_number`s. If matching on many attribute combinations gets awkward, generate a long keywords table from `vehicles.csv` at that point.
- Filter the accessories with the same `filter_by_year_window` helper and `pipeline.yaml` window (range overlap). This replaces the hard-coded `2020` in the notebook's `filtered_recent_df`.
- When expanding accessory ranges into applicable years, clip them to the window (idea doc, D15).
- Use only categories with `use_for_matching = true` (so `inventory_status` is never used, per the taxonomy rule).

---

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-10-23 | Natural key = `(model_number, model_year)` | Profiled: unique across all 323 rows; `model_number` alone repeats 164 times |
| 2026-10-26 | `min_model_year: 2020` in `config/pipeline.yaml`, shared by VW models + accessories | One cutoff for both sides of the match. At 2020 the Beetle-only gap words (`Convertible`, `Coupe`, `Dune`) drop out of scope |
| 2026-10-26 | Structure accepted: YAML config + generated definitions, staging + final | User approved the proposed layout |
| 2026-10-26 | Code lives in `source_code/VW/` for now | Next to the data and notebook; promote to `accy_v2/oems/vw/` later |
| 2026-10-26 | `vehicles.csv` is the only final table; `vehicle_keywords.csv` dropped | Search can work off the wide table; a long table can be derived later if needed |
| 2026-10-26 | New category `performance_package`; `Performance` is a package, not a trim | Performance equipment sits on top of a trim (`GTI Autobahn Performance`) |
| 2026-10-26 | Accessories kept when their year range overlaps the window | An accessory for 2018–2022 still fits 2020–2022 vehicles |
| 2026-10-26 | Optional `max_model_year`; empty = every available year from `min` onward | Lets a run be capped without losing the open-ended default |
| 2026-10-26 | 2019 Beetle words added: `Coupe`, `Convertible` → body_style; `Dune` → special_edition | Checked against the 2019 rows; lets the window be lowered without parse failures |
| 2026-10-26 | `Black Edition` → special_edition; `Black` alone → appearance_package (guide updated) | Phrases match before words, so the rule needs no special code |
| 2026-10-26 | `make` stays a column in every table | Other makes can be added without a schema change |
| 2026-10-26 | Two kinds of config: vocabulary and availability (per-model option sets); review queue as the manual check | Clear config boundary for onboarding new vehicles |
| 2026-10-26 | Corrections file removed for now | `vehicles.csv` always reflects the parse; flags are resolved by fixing config |
| 2026-10-26 | Option sets for every 2020+ model, not only new ones | Every vehicle in `vehicles.csv` is checked |
| 2026-10-26 | Option sets drafted for all 10 current models (`config/vehicles/`) | All 269 rows (2020+) classified with 0 unknown words and 0 single-value conflicts |
| 2026-10-26 | Option sets use explicit end years, not `null` | A new model year (e.g. 2028) must be onboarded on purpose; it shows up as `no_option_set` until it is |
| 2026-10-26 | Engine phrases are one value: `2.0 TSI` → `2.0L TSI`, `3.6 FSI` → `3.6L FSI`, `Turbo` | Keeps `engine` single-value; one value per vehicle is easier to match |
| 2026-10-26 | `PRO S` (ID.4) is one trim phrase, not `PRO` + `S` | Otherwise `ID.4 PRO S` gets two trims |
| 2026-10-26 | `appearance_package` and `body_style` are multi-value | Real data: `R-Line Black` (Tiguan, Atlas Cross Sport), `5dr HB` (e-Golf) |
| 2026-10-26 | Q1–Q5 answered: `Edition` never alone; `series` optional and mostly null; accessory years clipped to the window; strict option sets; option-set flags warn, never stop | Idea doc D13–D17 |
| 2026-10-26 | Logging layer on every pipeline step | See [plans/002_pipeline_logging.md](002_pipeline_logging.md); built first, used by every phase |
| 2026-10-26 | **Built.** 15 categories (make, model, series, submodel come from config / `models.yaml`) | The guide's schema has 14 fields including make; + `performance_package` |
| 2026-10-26 | Extra definition table `dim_option_set.csv` | Option sets reviewable in a spreadsheet, like the vocabulary |
| 2026-10-26 | `ingested_at` kept in staging only, not in `vehicles.csv` | Re-runs produce a byte-identical `vehicles.csv`; run time is in the logs and `ingest_runs.csv` |
| 2026-10-26 | `inconsistent_model_number` compares only categories filled in both years | Later years have shorter descriptions; comparing empty cells would flag almost every model number |
| 2026-10-26 | First real run: 12 `inconsistent_model_number` flags, 0 others | `RM1VPJ`, `BJ2VVJ` (Tiguan Black vs Black Edition), and new: `CMC4NR`, `CMC4UR` (Atlas Cross Sport Comfortline 2020 vs Highline 2021+) |
| 2026-10-26 | Resolution rule: lone `Black` → `Black Edition` where the option set offers it (idea doc D18); new `resolve` step; Tiguan 2024–2026 + Taos 2025–2027 option sets updated | 6 vehicles resolved (BJ2VVJ 2024, RM1VPJ 2025–26, CL26SR 2025–27); flags 12 → 7 (only the Atlas Cross Sport Comfortline/Highline issue left); 81 tests |
| 2026-10-26 | Reused model numbers may change trim / packages across years; only model / submodel changes are flagged (idea doc D19), configurable in `pipeline.yaml` | User validated the Atlas Cross Sport case; flags 7 → 0, run status `ok`; 84 tests |

## Risks

| Risk | Mitigation |
|---|---|
| New VW exports bring words the taxonomy doesn't know | Unknown tokens are reported, never dropped; coverage % is tracked per run |
| Short tokens (`S`, `R`, `On`) match the wrong thing | Model scope on keywords; composites before single tokens; whole-token matching only |
| Taxonomy and notebook drift apart | Aliases and cleaning helpers move out of the notebook into `pipeline/` + `config/` |
| VW labels the same vehicle differently across years (`RM1VPJ`: Black vs Black Edition) | `inconsistent_model_number` flag in the review queue |
| Option sets go stale as VW changes line-ups | `no_option_set` / `not_offered` flags on every run point at exactly what to update |
