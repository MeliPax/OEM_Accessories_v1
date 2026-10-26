# 001 — VW Model Ingest: Design Ideas

**Status:** Idea — all decisions made (see [Decisions](#decisions))
**Related plan:** [plans/001_vw_model_ingest_mvp.md](../plans/001_vw_model_ingest_mvp.md)
**Taxonomy source:** [assets/vw_vehicle_keyword_taxonomy_and_normalization_guide.md](../../assets/vw_vehicle_keyword_taxonomy_and_normalization_guide.md)

## Goal

Ingest the VW model file (`datasets/vw_models_data.csv`), break each `Description` down into structured vehicle attributes using the taxonomy, and store the result in a small CSV database. The structured output is what we will later match against the accessories data (`model_name`, `year_range`) to attach model numbers to accessories.

## What the data looks like today

Findings from profiling `vw_models_data.csv` (323 rows):

| Finding                                                                                                                                                                     | Impact on design                                                                                         |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| Only `Description`, `Manufacturer`, `ModelNumber`, `ModelYear` are populated. `ModelName`, `TrimName`, `Drivetrain`, etc. are empty for VW.                   | Everything must be derived from `Description`.                                                         |
| `ModelNumber` + `ModelYear` is unique (0 duplicates). `ModelNumber` alone is not (164 repeats across years).                                                          | Natural key = `(model_number, model_year)`.                                                            |
| 141 unique descriptions after cleaning.                                                                                                                                     | Small enough to review parse results by hand.                                                            |
| Descriptions repeat the model name (`Golf R Golf R`, `ID.4 ID.4 PRO`).                                                                                                  | Already handled by `clean_text_column` (repeated-word removal).                                        |
| 2020–2023 Atlas Cross Sport is spelled `Atlas Sport Cross`.                                                                                                              | Already handled by `VW_DESCRIPTION_ALIASES`.                                                           |
| Taxonomy covers every token **except** `Convertible`, `Coupe`, `Dune` (Beetle, 2019 only) and `Performance` (GTI) — now classified, see D4 / D5.          | Taxonomy needs 4 additions before the ingest can parse 100%.                                             |
| Model names contain spaces/dots (`ID. Buzz`, `ID.4`, `e-Golf`) and submodels are multi-word (`Cross Sport`).                                                        | Model/submodel must be matched as **phrases, longest first**, before splitting into single tokens. |
| Some tokens are only meaningful in context: `S` / `PRO` (ID.4 trims), `R` (Golf submodel), `On` (only in `w/SK On`), `Black` (appearance vs `Black Edition`). | Keywords need an optional **model scope**, and composites must run before single-token lookup.     |

## Idea 1 — Config format: YAML vs CSV tables

|                                                                                 | YAML config                                     | CSV definition tables                             |
| ------------------------------------------------------------------------------- | ----------------------------------------------- | ------------------------------------------------- |
| Hand editing                                                                    | Easy, supports comments ("why is `On` here?") | Spreadsheet-friendly but no comments              |
| Nested rules (model → submodels, composite token sequences, model scope lists) | Natural                                         | Needs extra join tables or delimiter-packed cells |
| Git diffs / review                                                              | Clean, line-based                               | Noisy when columns shift                          |
| Joining in pandas / reporting                                                   | Needs a loader                                  | Direct `read_csv`                               |
| Validation                                                                      | Load + validate once in a helper                | Same                                              |

**Recommendation: YAML as the source of truth, plus a generated CSV export.**

- Author the taxonomy in YAML (`config/`), because the rules are hierarchical and need comments.
- On every ingest run, the loader validates the YAML and **writes flattened definition tables** into `db/definitions/` (`dim_category.csv`, `dim_keyword.csv`, `dim_model.csv`). That gives us the "definition table that defines what each config keyword is" for joins, review and the future matching step, without hand-maintaining two copies.
- PyYAML 6.0.3 is already installed in the kernel environment.

Proposed config split (small, single-purpose files):

```
config/
├── pipeline.yaml     # run settings: min/max model year window, per-dataset year columns/rule (Idea 5)
├── categories.yaml   # the taxonomy levels: name, description, single/multi value, used for matching?, output column
├── models.yaml       # VOCABULARY: make → model → submodel (+ series), with aliases
├── keywords.yaml     # VOCABULARY: what each word/phrase in a description means, grouped by category (Idea 6)
├── vehicles/         # AVAILABILITY: one file per model, which options exist for which years (Idea 7)
│   ├── golf.yaml
│   └── tiguan.yaml ...
```

Two kinds of config, each with one job:

| Kind         | Files                              | Answers                                                           | Changes when                                     |
| ------------ | ---------------------------------- | ----------------------------------------------------------------- | ------------------------------------------------ |
| Vocabulary   | `models.yaml`, `keywords.yaml` | "What does this word mean?"                                       | A new word appears in a VW export                |
| Availability | `vehicles/*.yaml`                | "What can exist on this model, in this year?"                     | VW launches a model, trim, package or model year |

Sketch:

```yaml
# categories.yaml
categories:
  trim:
    description: Feature/content level (Trendline, Comfortline, ...)
    column: trim
    multi_value: false        # a vehicle has at most one trim
    use_for_matching: true
  inventory_status:
    description: Inventory metadata, never a vehicle characteristic
    column: inventory_status
    multi_value: false
    use_for_matching: false   # taxonomy rule: never use for matching
```

```yaml
# models.yaml
make: Volkswagen
models:
  Golf:
    submodels:
      GTI:        { series: Performance }
      R:          { series: Performance }
      Alltrack:   { series: Adventure }
      SportWagen: { series: null }   # series is optional and future-facing (D14)
  Atlas:
    submodels:
      Cross Sport: { series: null }
  ID.4: {}
  ID. Buzz: {}
aliases:                       # applied during cleaning, before parsing
  Atlas Sport Cross: Atlas Cross Sport
```

`keywords.yaml` is sketched in full in Idea 6.

## Idea 2 — Database design (CSV tables in `db/`)

Layered like a real warehouse, so the MVP maps 1:1 onto a future SQL DB:

```
db/
├── definitions/          generated from config/ every run (read-only)
│   ├── dim_category.csv      category, column, description, multi_value, use_for_matching
│   ├── dim_keyword.csv       keyword, category, normalized_value, model_scope, rule_type (keyword|composite)
│   └── dim_model.csv         make, model, submodel, series
├── staging/
│   └── stg_vw_models.csv     source rows as ingested + ingest metadata (untouched values)
├── final/
│   └── vehicles.csv          one row per (model_number, model_year) with taxonomy columns
├── review/
│   ├── review_queue.csv      vehicles a person should check (Idea 8), rebuilt every run
│   └── drafts/               generated option-set drafts to review (Idea 7); never read by the pipeline
└── dq/
    ├── ingest_issues.csv     row-level problems (unknown token, conflict, missing model)
    └── ingest_runs.csv       one row per run: timestamp, source file, row counts, parse coverage
```

`vehicles.csv` (wide, one row per vehicle):

| Column                                                                                                                                                                                                                                                | Example                                                                               |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| `vehicle_id`                                                                                                                                                                                                                                        | `VW-2024-CA33PR` (make + year + model number; deterministic, so re-runs are stable) |
| `make`, `model_number`, `model_year`                                                                                                                                                                                                            | `Volkswagen`, `CA33PR`, `2024`                                                  |
| `description_raw`, `description_clean`                                                                                                                                                                                                            | as ingested / after cleaning                                                          |
| `model`, `series`, `submodel`, `trim`, `special_edition`, `appearance_package`, `technology_package`, `performance_package`, `engine`, `transmission`, `drivetrain`, `body_style`, `battery_supplier`, `inventory_status` | taxonomy schema from the guide                                                        |
| `unparsed_tokens`                                                                                                                                                                                                                                   | words no rule claimed (should be empty)                                               |
| `parse_status`                                                                                                                                                                                                                                      | `complete` / `partial` / `failed`                                               |
| `source_file`, `ingested_at`, `taxonomy_version`                                                                                                                                                                                                | lineage                                                                               |

**Multi-value categories in the wide table.** Without a long keywords table, a category that can hold several values on one vehicle (`multi_value: true` in `categories.yaml`, e.g. `technology_package`) is stored as one cell: values sorted and joined with `|` (`IQ.DRIVE|Panoramic Sunroof`). One helper, `split_multi_value()`, is the only code that reads that format, so the search side never parses it by hand. Single-value categories (`trim`, `drivetrain`, ...) are plain values, and `validate_helpers.check_single_value_conflicts()` makes sure they stay single.

*A long `vehicle_keywords.csv` (one row per vehicle × attribute) was considered and dropped for the MVP (D8). It can be generated from `vehicles.csv` later if matching needs it, without changing the parse.*

## Idea 3 — Final vehicle table: extend the model file, or keep a separate final table?

| Option                                              | How it works                                                                                              | Pros                                                                                                                                                          | Cons                                                                                                       |
| --------------------------------------------------- | --------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| **A. Extend the model file**                  | Add taxonomy columns to `vw_models_data.csv` itself                                                     | One file, simple                                                                                                                                              | Overwrites the source; re-ingesting a new export loses our columns; no lineage; mixes raw and derived data |
| **B. Separate staging + final (recommended)** | Source stays untouched → `staging/stg_vw_models.csv` (as ingested) → `final/vehicles.csv` (derived) | Re-runnable end to end; source is never edited; easy to diff runs; mirrors how a real DB would work; final table can be rebuilt any time the taxonomy changes | One more file to keep track of                                                                             |
| **C. Final table only, no staging**           | Read source, write `vehicles.csv` directly                                                              | Fewer files                                                                                                                                                   | No record of exactly what was ingested; harder to debug a bad parse                                        |

**Recommendation: B.** The taxonomy will keep changing (we already found 4 missing words), so the final table must be cheap to rebuild from an untouched source. Staging is what makes that safe.

## Idea 4 — Pipeline shape (simple helpers, no classes)

Plain functions in small modules, each step takes and returns a DataFrame, and a thin runner wires them together. The notebook keeps doing exploration; the runner is what produces the DB.

```
pipeline/
├── config_helpers.py    load_taxonomy(), validate_taxonomy(), export_definitions()
├── ingest_helpers.py    read_source(), to_staging()           # add lineage, no value changes
├── clean_helpers.py     apply_aliases(), remove_repeated_words(), clean_description()   # moved from the notebook
├── parse_helpers.py     match_model(), apply_composites(), classify_tokens(), parse_description()
├── validate_helpers.py  check_required(), check_single_value_conflicts(), check_unknown_tokens()
└── storage_helpers.py   write_table(), read_table()           # one place that knows the db/ layout
run_ingest.py            ingest → clean → parse → validate → write, prints a run summary
```

Parse order per description (deterministic, longest match first):

1. Clean (aliases → trim → repeated-word removal).
2. Match **model** phrase at the start (`ID. Buzz` before `ID.4`, `Atlas` + submodel `Cross Sport`).
3. Match **submodel** phrase scoped to that model (`GTI`, `R`, `Alltrack`, ...), set `series` from `models.yaml` when one is defined (most stay `null`, D14).
4. Apply **composite rules** on the remaining tokens (`w/SK On Battery`, `IQ Drive`, `40th Anniversary`, `Ltd Avail`).
5. Look up remaining **single tokens**, honouring model scope (`S` only on ID.4).
6. Leftovers → `unparsed_tokens` + a DQ issue; set `parse_status`.

The notebook functions we already built (`clean_text_column`, `apply_aliases`, `VW_DESCRIPTION_ALIASES`) move into `clean_helpers.py`, and the alias map moves into `models.yaml`, so there is one source of truth.

## Idea 5 — Model year window (pipeline setting)

Two settings decide which model years the pipeline processes. They go in their own settings file, kept apart from the taxonomy, because they're run settings rather than vocabulary:

```yaml
# config/pipeline.yaml
min_model_year: 2020          # earliest model year processed (required)
max_model_year:               # latest model year processed; empty = no upper limit (every year from min onward)

datasets:
  vw_models:
    year_rule: single_year     # one year per row
    year_column: ModelYear
  accessories:
    year_rule: range_overlap   # a year range per row
    start_column: min_year
    end_column: max_year
```

**The window:** `min_model_year` to `max_model_year`. When `max_model_year` is empty, the window is open-ended: every available year from `min_model_year` onward, including years that show up in future exports.

| Setting                             | VW models kept                | Accessories kept                                        |
| ----------------------------------- | ----------------------------- | ------------------------------------------------------- |
| `min: 2020`, `max:` *(empty)* | `ModelYear >= 2020`         | `max_year >= 2020`                                    |
| `min: 2020`, `max: 2024`        | `2020 <= ModelYear <= 2024` | `max_year >= 2020` **and** `min_year <= 2024` |

- **One window for every dataset.** Both the VW models ingest and the accessories ingest read the same two settings, so the two sides of the match can't drift apart.
- **Range rule for accessories.** An accessory is kept if any year of its range falls inside the window (overlap). An accessory for 2018–2022 still fits 2020–2022 vehicles; with `max: 2021`, an accessory for 2022–2025 is dropped. With `max` empty, this is exactly the notebook's `filtered_recent_df` filter, which has 2020 hard-coded.
- **Applicable years are clipped to the window.** When an accessory range is expanded into one row per year (the notebook's `build_model_year_dict`), years outside the window are dropped. A 2018–2022 accessory with `min: 2020` gives applicable years 2020, 2021 and 2022, so matching never looks for 2018 vehicles that aren't in the final table. *(Decided, D15.)*
- **Where the filter runs.** Staging keeps every source row as ingested. The filter runs between staging and final, and each run records the window and the excluded count in `dq/ingest_runs.csv`. Changing the window only needs a rerun, not a re-ingest.
- **Validation.** The loader fails if `min_model_year` is missing or isn't a 4-digit integer, if `max_model_year` is set but isn't a 4-digit integer, or if `max_model_year < min_model_year`. If the window removes every row of a dataset, the run warns.
- **Effect on today's data (`min: 2020`, `max` empty):** VW models drop from 323 rows to 269 (the file spans 2019–2027), and the clean descriptions drop from 141 to 112. `Convertible`, `Coupe` and `Dune` only appear in 2019 Beetle rows, so `Performance` is the only taxonomy gap left.

## Idea 6 — Keyword config: grouped by category, phrases before words

The keyword file reads top to bottom as the taxonomy itself: one section per category, and inside it, **phrases** (several words) and **words** (one word). Each entry says what to look for (`match`) and what to store (`value`, defaults to `match`).

```yaml
# config/keywords.yaml
#
# HOW MATCHING WORKS
#   1. Phrases are matched before single words, longest phrase first, across ALL categories.
#   2. A matched phrase consumes its words, so they can't match again as single words.
#   3. Matching is whole-word and case-insensitive.
#   4. `models:` limits an entry to those models; without it, the entry applies to every model.

special_edition:
  phrases:
    - match: Black Edition          # "Black" followed by "Edition" -> special edition
    - match: Wolfsburg Edition
    - match: Peak Edition
    - match: 1st Edition
    - match: 35th Edition
      value: 35th Anniversary
    - match: 40th Anniversary
  words:
    - match: Rabbit
    - match: Dune                   # Beetle Dune (2019)

appearance_package:
  words:
    - match: R-Line
    - match: Black                  # "Black" on its own -> appearance. "Black Edition" never
                                    # reaches here: the phrase above has already consumed it.

performance_package:
  words:
    - match: Performance

transmission:
  words:
    - match: Auto
      value: Automatic
    - match: DSG
    - match: Manual

body_style:
  words:
    - match: Coupe                  # Beetle (2019)
    - match: Convertible            # Beetle (2019)

trim:
  words:
    - match: Highline
    - match: S
      models: [ID.4]                # "S" is only a trim on ID.4
```

Why this layout is clear:

- **The rule for `Black` lives in one place and is visible.** You don't need special code for "Black followed by Edition": phrases always win over words, and the comment says so at both entries.
- **Every word belongs to exactly one category.** The loader fails if the same `match` (with the same model scope) appears in two places, so a word can't silently mean two things.
- **Adding a word is one line** in the right category section.
- **The generated `db/definitions/dim_keyword.csv`** flattens this to one row per entry (`category, match, value, kind (phrase|word), models`), so you can review the whole vocabulary in a spreadsheet.
- **Mistakes in incoming data** (for example `Black` where VW meant `Black Edition`) aren't solved in this file. That's what the manual review in Idea 8 is for. The vocabulary stays a clean description of what words mean.

## Idea 7 — Vehicle option sets: the config boundary

The vocabulary says what words *mean*. The option sets say what is *available*: for each model (and submodel) and year range, the allowed values per category. This is the config boundary. A parsed vehicle must fit inside an option set, and a new vehicle or model year is onboarded by writing its option set.

```yaml
# config/vehicles/tiguan.yaml
make: Volkswagen
model: Tiguan

option_sets:
  - years: [2022, 2024]
    trim: [Comfortline, Highline]
    appearance_package: [R-Line, Black]
    special_edition: [Black Edition]
    drivetrain: [FWD, AWD]

  - years: [2025, null]               # null = no end year yet, still on sale
    trim: [Comfortline, Highline]
    appearance_package: [R-Line, Black]
    special_edition: [Black Edition]
    drivetrain: [AWD]
```

```yaml
# config/vehicles/golf.yaml
make: Volkswagen
model: Golf

option_sets:
  - submodel: GTI
    years: [2020, 2024]
    trim: [Autobahn]
    special_edition: [Rabbit, 40th Anniversary]
    performance_package: [Performance]
    transmission: [Automatic, Manual, DSG]

  - submodel: R
    years: [2020, null]
    special_edition: [20th Anniversary]
    appearance_package: [Black]
    transmission: [DSG, Manual]
```

*(Values above are illustrative; the real ones get drafted from the data, see below.)*

**Rules:**

- **Strict boundary.** A category that isn't listed in an option set means "not offered". If the parse finds a value outside the set, the vehicle is flagged `not_offered`. *(Decided, D16.)*
- **Values must exist in the vocabulary.** The loader fails if an option set lists a value that `keywords.yaml` can't produce for that category (catches typos like `Comfortine`).
- **Models and submodels must exist** in `models.yaml`.
- **No overlapping year ranges** for the same model + submodel, so every vehicle maps to at most one option set.
- **No option set for a vehicle** (a new model, or a new model year past the last set's end) → flagged `no_option_set`. That's the signal to onboard it: add or extend an option set.

**Onboarding a new vehicle or model year:**

1. Run the ingest. New vehicles show up in the review queue as `no_option_set`, and any new words as `unknown_token`.
2. Add new words to `keywords.yaml` (vocabulary).
3. Add or extend an option set in `config/vehicles/<model>.yaml` (availability).
4. Re-run. The vehicles should now pass with no flags.

**Bootstrapping today's data:** `draft_option_sets()` builds draft option sets from the parsed 2020+ vehicles (grouped by model + submodel, with consecutive years that have the same options merged into one range) and writes them to `db/review/drafts/`. You review and edit them, then copy them into `config/vehicles/`. The pipeline never writes to `config/` itself, so config only ever contains what a person approved.

**In the MVP, option sets validate; they don't steer the parse.** Parsing uses the vocabulary only. Using option sets to resolve ambiguous words automatically is possible later, but keeping them separate first makes errors visible instead of hiding them.

## Idea 8 — How the pieces work together, and the manual check

**Ingesting VW data (every run):**

1. The pipeline reads the VW model export, keeps rows inside the year window, and cleans each description.
2. It breaks each description into taxonomy values using the **vocabulary** (`keywords.yaml`, `models.yaml`).
3. It writes the result to `db/final/vehicles.csv`.
4. It checks every vehicle against the **option sets** (`config/vehicles/*.yaml`) and writes anything suspicious to the review queue.

**When new vehicles come out:**

1. Add any new words to `keywords.yaml` (and new models or submodels to `models.yaml`).
2. Add or extend the model's option set in `config/vehicles/<model>.yaml`: the trims, packages, drivetrains and so on it can have, for which years.
3. Run the ingest. The option sets act as the check that the update to `vehicles.csv` contains no errors: a value outside the option set, or a vehicle with no option set, is flagged.

**The manual check is the review queue:** `db/review/review_queue.csv`, rebuilt every run, one row per vehicle and issue:

| Issue | Meaning |
|---|---|
| `unknown_token` | A word no keyword matched |
| `not_offered` | A parsed value falls outside the vehicle's option set |
| `no_option_set` | No option set covers this model / submodel / year |
| `single_value_conflict` | Two values in a single-value category (e.g. two trims) |
| `inconsistent_model_number` | The same model number is described differently across years. Real example: `RM1VPJ` is "Tiguan Comfortline R-Line Black" in 2025–2026 but "… R-Line Black Edition" in 2027 |

Columns: `vehicle_id, model_number, model_year, description_clean, issue, category, current_value, detail`.

**Resolving a flag** means fixing the config, then re-running:

- A missing word → add it to `keywords.yaml`.
- A real option that isn't listed → add it to the option set.
- A mistake in the VW data itself (like `RM1VPJ`) → it stays flagged in the review queue. `vehicles.csv` always reflects what the parser derived from the description; the pipeline doesn't hand-edit values.

*A per-vehicle corrections file (manually overriding parsed values) was considered and removed for now (2026-10-26). It can be added later if data mistakes need fixing in `vehicles.csv` itself.*

## Decisions

IDs (`D1`, `D2`, ...) are stable labels referenced from the rest of this doc and the plan.

### Decided

| ID | Decision | Date |
|---|---|---|
| D1 | **Config format:** YAML as source of truth + generated CSV definition tables. | 2026-10-26 |
| D2 | **Final table:** staging + a separate final `vehicles.csv` (Idea 3, option B). | 2026-10-26 |
| D3 | **Code location:** `source_code/VW/` for now; can be promoted to `accy_v2/oems/vw/` later. | 2026-10-26 |
| D4 | **`Performance` is a package:** new category `performance_package` (single value, used for matching), after `technology_package`. | 2026-10-26 |
| D5 | **2019 words added:** `Coupe`, `Convertible` → `body_style`; `Dune` → `special_edition`. | 2026-10-26 |
| D6 | **`Black`:** `Black Edition` → `special_edition`; `Black` alone → `appearance_package`. | 2026-10-26 |
| D7 | **Make:** VW only for the MVP; `make` stays a column in every table. | 2026-10-26 |
| D8 | **`vehicles.csv` only:** no `vehicle_keywords.csv` for the MVP. | 2026-10-26 |
| D9 | **Model year window:** `min_model_year: 2020` + optional `max_model_year` (empty = every year from `min` onward), shared by both datasets. | 2026-10-26 |
| D10 | **Config layout:** vocabulary (`keywords.yaml` grouped by category, phrases before words; `models.yaml`) + availability (`config/vehicles/<model>.yaml` option sets). | 2026-10-26 |
| D11 | **Option sets for every 2020+ model**, not only new vehicles. | 2026-10-26 |
| D12 | **Manual check = review queue.** No corrections file for now: `vehicles.csv` always reflects the parse, and flags are resolved by fixing config. | 2026-10-26 |
| D13 | **`Edition` is never stored alone.** It's the second word of an edition phrase, always after the edition name (`Peak Edition`, `Wolfsburg Edition`, `Black Edition`, `1st Edition`). A bare `Edition` is an `unknown_token`. | 2026-10-26 |
| D14 | **`series` is an optional, future-facing field.** Filled today for Golf GTI / R (Performance) and Alltrack (Adventure); `null` for everything else until a consistent series strategy exists. The taxonomy must allow it later for Atlas Cross Sport, Jetta GLI, Atlas Peak Edition and future performance or lifestyle families. | 2026-10-26 |
| D15 | **Accessory years are clipped to the window.** When a range is expanded per year, only years inside the window are ingested (2018–2022 at `min: 2020` → 2020–2022). | 2026-10-26 |
| D16 | **Option sets are strict.** A category not listed in a model's option set means "not offered"; a parsed value there is flagged in the logs and review queue. | 2026-10-26 |
| D17 | **Option-set flags never stop the run.** `not_offered` / `no_option_set` are warnings; the vehicle still lands in `vehicles.csv`. Only broken config or a duplicate key stops a run. | 2026-10-26 |
| D18 | **Resolutions:** a lone `Black` becomes `special_edition = Black Edition` (and leaves `appearance_package`) when the vehicle's option set offers Black Edition. Same model number as Black Edition in another year, but not offered → `resolution_suggested` flag only. Rule lives in `keywords.yaml` (`resolutions:`); applied in a new `resolve` step between parse and validate. Tiguan 2024–2026 and Taos 2025–2027 option sets now offer Black Edition, not a Black appearance package. | 2026-10-26 |
| D19 | **Reused model numbers:** the key is `(model_number, model_year)`, so a model number may carry over to a new year with a different trim, package or edition (Atlas Cross Sport `CMC4NR` / `CMC4UR`: 2020 Comfortline features became the 2021 Highline baseline under the same code). Only a change of `model` or `submodel` is flagged (`validation.model_number_consistency.compare` in `pipeline.yaml`); other changes are noted in the run log. | 2026-10-26 |

Notes:

- **D4:** `Golf GTI Autobahn Performance DSG` → model `Golf`, submodel `GTI`, trim `Autobahn`, performance_package `Performance`, transmission `DSG`. Future values: Competition, Clubsport, Track Package. Related classifications: `Autobahn` → trim, `Rabbit` → special_edition, `40th Anniversary` → special_edition (phrase), `Auto` / `Manual` → transmission. The **word** `Performance` fills `performance_package`; the **series** `Performance` (Golf GTI / R) comes from the submodel lookup in `models.yaml`, so the two don't collide.
- **D5:** checked against the data. The 2019 Beetle rows are exactly `Beetle Coupe|Convertible` + `Dune Auto` or `Wolfsburg Edition`, which matches the 2019 Canadian Beetle (two body styles; Dune and Wolfsburg Edition as the two editions). The four descriptions become Phase 1 test cases.
- **D4, D5, D6 change the taxonomy guide** in `assets/` (new category; `Taos Black Edition` moves from appearance packages to special editions; 2019 words). Phase 1 updates the guide so it and the config match.

### Still open

None. All questions answered on 2026-10-26.

## Out of scope for the MVP

- Matching accessories to vehicles (next plan; this MVP produces the inputs for it).
- Mapping accessory `model_name` values like `GTI`, `Golf R`, `Atlas Cross Sport` to taxonomy `(model, submodel)` pairs — noted here because it's the first thing the matching plan needs.
- A real database engine; CSV only.
