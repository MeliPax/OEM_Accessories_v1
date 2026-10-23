# 001 — VW Model Ingest MVP: Plan

**Status:** Draft — starts once the decisions in the idea doc are confirmed
**Idea / design:** [ideas/001_vw_model_ingest_design.md](../ideas/001_vw_model_ingest_design.md)
**Branch:** `feature/vw-data-analysis` (or a new `feature/vw-model-ingest` from `dev`, per `accy_v2/planning/VERSIONING.md`)

## Outcome

Running one command rebuilds a CSV database from `datasets/vw_models_data.csv`:

- every VW model row is in staging, untouched;
- every row is in `db/final/vehicles.csv` with its description broken into taxonomy columns;
- every derived attribute is also in `db/final/vehicle_keywords.csv` (long format, for matching);
- anything the rules couldn't classify is reported in `db/dq/ingest_issues.csv`, never silently dropped.

**MVP success criteria**

- [ ] 323 / 323 source rows land in staging and final (row counts reconcile).
- [ ] 141 / 141 unique clean descriptions parse with `parse_status = complete` (0 unparsed tokens).
- [ ] Re-running produces identical output (deterministic `vehicle_id`, sorted writes).
- [ ] Changing one keyword in YAML and re-running changes only the affected rows.
- [ ] The golden examples from the taxonomy guide parse exactly as documented.

## Target layout

```
source_code/VW/
├── config/                 categories.yaml, models.yaml, keywords.yaml
├── pipeline/               *_helpers.py (plain functions)
├── db/
│   ├── definitions/        generated from config/
│   ├── staging/
│   ├── final/
│   └── dq/
├── tests/                  pytest for the helpers
└── run_ingest.py
```

---

## Phase 1 — Taxonomy config (YAML) + loader

Turn the markdown guide into machine-readable config, and make sure bad config fails loudly.

- [ ] Write `config/categories.yaml`: the 13 taxonomy categories from the guide's catalog schema, each with `description`, `column`, `multi_value`, `use_for_matching`.
- [ ] Write `config/models.yaml`: make, models, submodels (+ `series`), and the alias map (move `VW_DESCRIPTION_ALIASES` here).
- [ ] Write `config/keywords.yaml`: single keywords (category, normalized value, optional model scope) and composite rules from the guide, plus the 4 gap words once classified (idea doc, decision 4).
- [ ] `config_helpers.load_taxonomy()` — read the three files into plain dicts.
- [ ] `config_helpers.validate_taxonomy()` — fail with a clear message if: a keyword points to an unknown category, a model scope names an unknown model, a keyword is defined twice, a composite token is undefined, a single-value category could be set twice by one composite.
- [ ] `config_helpers.export_definitions()` — write `db/definitions/dim_category.csv`, `dim_keyword.csv`, `dim_model.csv`.

**Done when:** the loader validates cleanly, a deliberately broken config fails with a readable error, and the three definition CSVs are generated.

## Phase 2 — Storage + ingest to staging

- [ ] `storage_helpers.py` — the only module that knows the `db/` paths: `write_table(df, layer, name)`, `read_table(layer, name)`. Writes are sorted by key and use a fixed column order, so diffs between runs are meaningful.
- [ ] `ingest_helpers.read_source()` — read the CSV with codes as text (`ModelNumber`, `Package`, `Style_ID`), drop all-empty columns.
- [ ] `ingest_helpers.to_staging()` — rename to snake_case, add `source_file`, `source_row`, `ingested_at`, keep values untouched.
- [ ] Validate on ingest: required columns present, `(model_number, model_year)` unique, `model_year` numeric. Failures go to `dq/ingest_issues.csv`; a duplicate key stops the run.

**Done when:** `stg_vw_models.csv` has 323 rows and the key check passes.

## Phase 3 — Clean + parse (transform)

- [ ] Move `apply_aliases` and the repeated-word cleanup from the notebook into `clean_helpers.py` (same behaviour; the notebook imports them afterwards instead of redefining them).
- [ ] `parse_helpers.match_model()` — longest model phrase at the start of the description, then submodel phrase scoped to that model; returns model, submodel, series and the remaining tokens.
- [ ] `parse_helpers.apply_composites()` — longest token sequence first; consumes the matched tokens.
- [ ] `parse_helpers.classify_tokens()` — single-token lookup with model scope; returns (category, raw token, normalized value) triples and the leftovers.
- [ ] `parse_helpers.parse_description()` — runs the three steps for one description and returns a dict: taxonomy columns + `unparsed_tokens` + `parse_status`.
- [ ] Parse each **unique** clean description once and join the result back to the rows (141 parses instead of 323; also guarantees identical descriptions get identical attributes).
- [ ] Build `vehicles` (wide) and `vehicle_keywords` (long) DataFrames, with `vehicle_id = VW-{model_year}-{model_number}`.

**Done when:** the taxonomy guide's golden examples parse exactly as documented (they become pytest cases), and every unique description has a parse result.

## Phase 4 — Validation + DQ reporting

- [ ] `validate_helpers.check_required()` — `make`, `model`, `model_year`, `model_number` present.
- [ ] `validate_helpers.check_single_value_conflicts()` — e.g. two different trims on one vehicle.
- [ ] `validate_helpers.check_unknown_tokens()` — one issue per unparsed token, with the description it came from.
- [ ] Each issue row: `run_id, vehicle_id, rule, severity (error|warning), detail`.
- [ ] Append one row per run to `dq/ingest_runs.csv`: run id, timestamp, source file, rows in/staged/final, % parsed complete, issue counts by rule.

**Done when:** a description with a made-up word ends up as `partial` with exactly one `unknown_token` issue, and the run summary reports it.

## Phase 5 — Runner, tests, notebook hook-up

- [ ] `run_ingest.py` — `config → staging → clean → parse → validate → final` in order, prints a short summary (rows, coverage, issues), and exits non-zero on errors.
- [ ] `tests/` — pytest for: config validation, model/submodel matching (`ID. Buzz` vs `ID.4`, `Golf R` vs `R-Line`), composites, model scope (`S`), golden examples, end-to-end row-count reconciliation.
- [ ] Notebook: add a cell that loads `db/final/vehicles.csv` for analysis, and import the clean helpers instead of redefining them.
- [ ] Short `db/README.md` describing each table and column (generated from `dim_category.csv` where possible).

**Done when:** all MVP success criteria above are ticked, and `pytest source_code/VW/tests` passes.

## Phase 6 — Handover to matching (next plan, not MVP)

Captured so the MVP output is shaped correctly for it:

- Map accessory `model_name` values to taxonomy pairs: `GTI` → (Golf, GTI), `Golf R` → (Golf, R), `Atlas Cross Sport` → (Atlas, Cross Sport), `Jetta GLI` → (Jetta, GLI).
- Join accessories (`model`, `submodel`, `applicable_year`) to `vehicle_keywords` to attach `model_number`s.
- Use only categories with `use_for_matching = true` (so `inventory_status` is never used, per the taxonomy rule).

---

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-10-23 | Natural key = `(model_number, model_year)` | Profiled: unique across all 323 rows; `model_number` alone repeats 164 times |
| | *(pending)* Config format, final-table option, code location, gap-word classification | See idea doc, *Decisions needed* |

## Risks

| Risk | Mitigation |
|---|---|
| New VW exports bring words the taxonomy doesn't know | Unknown tokens are reported, never dropped; coverage % is tracked per run |
| Short tokens (`S`, `R`, `On`) match the wrong thing | Model scope on keywords; composites before single tokens; whole-token matching only |
| Taxonomy and notebook drift apart | Aliases and cleaning helpers move out of the notebook into `pipeline/` + `config/` |
