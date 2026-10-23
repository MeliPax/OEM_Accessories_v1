# 001 — VW Model Ingest: Design Ideas

**Status:** Idea — decisions pending (see [Decisions needed](#decisions-needed))
**Related plan:** [plans/001_vw_model_ingest_mvp.md](../plans/001_vw_model_ingest_mvp.md)
**Taxonomy source:** [assets/vw_vehicle_keyword_taxonomy_and_normalization_guide.md](../../assets/vw_vehicle_keyword_taxonomy_and_normalization_guide.md)

## Goal

Ingest the VW model file (`datasets/vw_models_data.csv`), break each `Description` down into structured vehicle attributes using the taxonomy, and store the result in a small CSV database. The structured output is what we will later match against the accessories data (`model_name`, `year_range`) to attach model numbers to accessories.

## What the data looks like today

Findings from profiling `vw_models_data.csv` (323 rows):

| Finding | Impact on design |
|---|---|
| Only `Description`, `Manufacturer`, `ModelNumber`, `ModelYear` are populated. `ModelName`, `TrimName`, `Drivetrain`, etc. are empty for VW. | Everything must be derived from `Description`. |
| `ModelNumber` + `ModelYear` is unique (0 duplicates). `ModelNumber` alone is not (164 repeats across years). | Natural key = `(model_number, model_year)`. |
| 141 unique descriptions after cleaning. | Small enough to review parse results by hand. |
| Descriptions repeat the model name (`Golf R Golf R`, `ID.4 ID.4 PRO`). | Already handled by `clean_text_column` (repeated-word removal). |
| 2020–2023 Atlas Cross Sport is spelled `Atlas Sport Cross`. | Already handled by `VW_DESCRIPTION_ALIASES`. |
| Taxonomy covers every token **except** `Convertible`, `Coupe`, `Dune` (Beetle) and `Performance` (GTI). | Taxonomy needs 4 additions before the ingest can parse 100%. |
| Model names contain spaces/dots (`ID. Buzz`, `ID.4`, `e-Golf`) and submodels are multi-word (`Cross Sport`). | Model/submodel must be matched as **phrases, longest first**, before splitting into single tokens. |
| Some tokens are only meaningful in context: `S` / `PRO` (ID.4 trims), `R` (Golf submodel), `On` (only in `w/SK On`), `Black` (appearance vs `Black Edition`). | Keywords need an optional **model scope**, and composites must run before single-token lookup. |

## Idea 1 — Config format: YAML vs CSV tables

| | YAML config | CSV definition tables |
|---|---|---|
| Hand editing | Easy, supports comments ("why is `On` here?") | Spreadsheet-friendly but no comments |
| Nested rules (model → submodels, composite token sequences, model scope lists) | Natural | Needs extra join tables or delimiter-packed cells |
| Git diffs / review | Clean, line-based | Noisy when columns shift |
| Joining in pandas / reporting | Needs a loader | Direct `read_csv` |
| Validation | Load + validate once in a helper | Same |

**Recommendation: YAML as the source of truth, plus a generated CSV export.**

- Author the taxonomy in YAML (`config/`), because the rules are hierarchical and need comments.
- On every ingest run, the loader validates the YAML and **writes flattened definition tables** into `db/definitions/` (`dim_category.csv`, `dim_keyword.csv`, `dim_model.csv`). That gives us the "definition table that defines what each config keyword is" for joins, review and the future matching step, without hand-maintaining two copies.
- PyYAML 6.0.3 is already installed in the kernel environment.

Proposed config split (small, single-purpose files):

```
config/
├── categories.yaml   # the taxonomy levels: name, description, single/multi value, used for matching?, output column
├── models.yaml       # make → model → submodel (+ series), with aliases
└── keywords.yaml     # keyword → category + normalized value (+ optional model scope), and composite rules
```

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
      SportWagen: { series: null }
  Atlas:
    submodels:
      Cross Sport: { series: null }
  ID.4: {}
  ID. Buzz: {}
aliases:                       # applied during cleaning, before parsing
  Atlas Sport Cross: Atlas Cross Sport
```

```yaml
# keywords.yaml
composites:                    # matched first, longest sequence first
  - tokens: [w/SK, On, Battery]
    category: battery_supplier
    value: SK On
  - tokens: [IQ, Drive]
    category: technology_package
    value: IQ.DRIVE
keywords:
  Highline: { category: trim }
  4MOTION:  { category: drivetrain, value: AWD }
  S:        { category: trim, models: [ID.4] }     # scoped: only a trim on ID.4
  Auto:     { category: transmission, value: Automatic }
```

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
│   ├── vehicles.csv          one row per (model_number, model_year) with taxonomy columns
│   └── vehicle_keywords.csv  one row per (vehicle, category, value) — long format for matching
└── dq/
    ├── ingest_issues.csv     row-level problems (unknown token, conflict, missing model)
    └── ingest_runs.csv       one row per run: timestamp, source file, row counts, parse coverage
```

`vehicles.csv` (wide, one row per vehicle):

| Column | Example |
|---|---|
| `vehicle_id` | `VW-2024-CA33PR` (make + year + model number; deterministic, so re-runs are stable) |
| `make`, `model_number`, `model_year` | `Volkswagen`, `CA33PR`, `2024` |
| `description_raw`, `description_clean` | as ingested / after cleaning |
| `model`, `series`, `submodel`, `trim`, `special_edition`, `appearance_package`, `technology_package`, `engine`, `transmission`, `drivetrain`, `body_style`, `battery_supplier`, `inventory_status` | taxonomy schema from the guide |
| `unparsed_tokens` | words no rule claimed (should be empty) |
| `parse_status` | `complete` / `partial` / `failed` |
| `source_file`, `ingested_at`, `taxonomy_version` | lineage |

`vehicle_keywords.csv` (long) exists because matching accessories is a keyword problem: "find vehicles where model = Golf and submodel = GTI and year in 2022–2024" is a simple filter on a long table, and multi-value categories (an engine can be `2.0` + `TSI`) don't need packed cells.

## Idea 3 — Final vehicle table: extend the model file, or keep a separate final table?

| Option | How it works | Pros | Cons |
|---|---|---|---|
| **A. Extend the model file** | Add taxonomy columns to `vw_models_data.csv` itself | One file, simple | Overwrites the source; re-ingesting a new export loses our columns; no lineage; mixes raw and derived data |
| **B. Separate staging + final (recommended)** | Source stays untouched → `staging/stg_vw_models.csv` (as ingested) → `final/vehicles.csv` (derived) | Re-runnable end to end; source is never edited; easy to diff runs; mirrors how a real DB would work; final table can be rebuilt any time the taxonomy changes | One more file to keep track of |
| **C. Final table only, no staging** | Read source, write `vehicles.csv` directly | Fewer files | No record of exactly what was ingested; harder to debug a bad parse |

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
3. Match **submodel** phrase scoped to that model (`GTI`, `R`, `Alltrack`, ...), set `series` from `models.yaml`.
4. Apply **composite rules** on the remaining tokens (`w/SK On Battery`, `IQ Drive`, `40th Anniversary`, `Ltd Avail`).
5. Look up remaining **single tokens**, honouring model scope (`S` only on ID.4).
6. Leftovers → `unparsed_tokens` + a DQ issue; set `parse_status`.

The notebook functions we already built (`clean_text_column`, `apply_aliases`, `VW_DESCRIPTION_ALIASES`) move into `clean_helpers.py`, and the alias map moves into `models.yaml`, so there is one source of truth.

## Decisions needed

1. **Config format** — OK with YAML as source of truth + generated CSV definition tables? *(recommended)*
2. **Final table** — OK with Option B (staging + separate final `vehicles.csv` + long `vehicle_keywords.csv`)? *(recommended)*
3. **Where the code lives** — `source_code/VW/` for the MVP *(recommended, matches where the data and notebook are)*, or straight into `accy_v2/oems/vw/` alongside the other OEM pipelines?
4. **Taxonomy gaps** — proposed classification for the 4 unknown words:
   - `Convertible`, `Coupe` → `body_style` (Beetle)
   - `Dune` → `special_edition` (Beetle Dune)
   - `Performance` → `trim`? It's sold as "GTI Performance Package". Could also be a package category. **Your call.**
5. **Ambiguous keywords** — confirm:
   - `Black` alone → `appearance_package`; `Black Edition` (Taos) → `appearance_package = Black Edition` (per the guide's example), not `special_edition`.
   - Standalone `Edition` (`Atlas Peak Edition`, `Passat Wolfsburg Edition`) is absorbed into the edition composite, never stored on its own.
   - `Series`: populate only where the guide defines it (Golf GTI/R = Performance, Alltrack = Adventure), null elsewhere.
6. **Make scope** — VW only for the MVP, but keep `make` in every table so Audi etc. can be added without a schema change? *(recommended)*

## Out of scope for the MVP

- Matching accessories to vehicles (next plan; this MVP produces the inputs for it).
- Mapping accessory `model_name` values like `GTI`, `Golf R`, `Atlas Cross Sport` to taxonomy `(model, submodel)` pairs — noted here because it's the first thing the matching plan needs.
- A real database engine; CSV only.
