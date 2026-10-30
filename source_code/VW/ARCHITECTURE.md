# VW Data Pipeline: Architecture Overview

How the VW vehicle and accessory pipelines work, end to end, with real examples from the 2026-10-20 accessory file and the VW model export. For how to run them, see [README.md](README.md). For every table and flag code, see [db/README.md](db/README.md). For the history, see [CHANGELOG.md](CHANGELOG.md).

---

## 1. Purpose

VW provides two files that don't share a key:

- a **vehicle export** that describes each vehicle in free text, with its model number;
- an **accessory catalogue** that lists parts by model name and year range, with no model numbers.

The system turns the vehicle text into structured fields, then attaches the right VW model numbers to every accessory. The result is an Excel file with one sheet per model, plus review files for everything a person should check.

**Example:** accessory `000019819C` (Seat Underlay, Golf GTI, years 2006–2026) is exported as 9 rows. That is one row per GTI model number for 2024, 2025 and 2026, such as `CD1PU2` with variant `Performance`.

## 2. System context

```
 datasets/vw_models_data.csv                       datasets/<date> VW Canada Accessories Data EN.xlsx
 (VW model export, 323 rows)                       (accessory catalogue, 24,396 rows)
          │                                                   │
          ▼                                                   ▼
 ┌──────────────────────┐                      ┌───────────────────────────┐
 │ 1. Vehicle ingest    │                      │ 2. Accessory pipeline     │
 │    run_ingest.py     │── vehicles file ───► │    run_accessories.py     │
 └──────────────────────┘   (newest run)       │    or the notebook        │
          │                                     └───────────────────────────┘
          ▼                                                   │
 db/final/vehicles_<run_id>.csv                               ▼
 db/review/review_queue_<run_id>.csv           output/vw_accessories_<run_id>.xlsx
                                               db/review/accessory_review_<run_id>.csv
                     ▲                                        ▲
                     └──────── config/ (YAML): vocabulary, availability, rules, messages ───────┘
```

- The two pipelines run in order. The vehicle ingest builds the vehicle database, and the accessory pipeline reads the newest vehicles file.
- Both read the same `config/`. Behaviour changes are made in config, not in code.
- Both write logs, flags and review files for every run, named with the run id.

## 3. Design principles

| Principle | What it means in practice | Example |
|---|---|---|
| Config drives behaviour | No model, word, year, rule or column name is hard-coded | Adding a trim word is one line in `keywords.yaml` |
| Lookup, not merge | Vehicles are searched once per unique key; nothing merged is saved | 1,028 accessory rows need only 29 lookups |
| Every change is traceable | Each changed value is logged before → after, with the rule and row count | `labor_time: "10" -> "0.17" (minutes -> hours; 89 rows)` |
| Every problem is a coded flag | Each flag says what was checked, what was found, the causes and the fix | `ACCESS_LOOKUP_YEAR_AFTER_LAST_KNOWN` (section 7) |
| Never guess | Part numbers are proven from the source, never padded; ambiguous words are resolved only with evidence | `71200` is restored to `000071200` only because `make&model` says `000071200Atlas` |
| Nothing is overwritten | Every output file carries its run id | `accessory_review_vw_accessories_20261029_085242.csv` |
| A broken config stops the run | Config is validated before any data is read, and each problem gets a `CONFG_` code | `restore: pad` → "part_number.restore must be one of leading_zeros_only, never" |

## 4. Components

```
source_code/VW/
├── run_ingest.py           entry point: vehicle ingest
├── run_accessories.py      entry point: accessory pipeline (the notebook calls build_accessory_model_dict())
├── new_vehicle.py          sets up config/vehicles/<model>.yaml from the template
├── config/                 every rule (section 5)
├── pipeline/               plain helper modules, one job each
│   ├── config_helpers.py      load and validate config; year windows; definition tables
│   ├── ingest_helpers.py      read the source, stage it untouched, apply the year window
│   ├── clean_helpers.py       aliases, spaces, repeated words (vehicle descriptions)
│   ├── parse_helpers.py       description → taxonomy fields
│   ├── resolve_helpers.py     re-read ambiguous values using the option sets
│   ├── validate_helpers.py    vehicle checks and the vehicle review queue
│   ├── accessory_helpers.py   accessory steps, the result dict and the Excel export
│   ├── text_helpers.py        comment cleaning (HTML, pipes, links, spacing)
│   ├── lookup_helpers.py      vehicle index, lookup per key, coverage
│   ├── verify_helpers.py      human-verified facts
│   ├── message_helpers.py     flag wording from messages.yaml
│   ├── logging_helpers.py     run context, step wrapper, change / flag / step logs
│   └── storage_helpers.py     the only module that knows the db/ layout
├── db/                     outputs (section 9)
├── output/                 the Excel exports
└── tests/                  285 tests (section 11)
```

Every step goes through one wrapper, `run_step(ctx, name, func, df, conditions)`. It logs the step's start with its conditions, and its end with rows in, out, changed, excluded and flagged, plus the duration. A step can't skip logging.

## 5. Configuration model

| File | Kind | Holds | Example |
|---|---|---|---|
| `pipeline.yaml` | Settings | Source files, one year window per pipeline, logging | `accessories: min_model_year: current_year - 2` |
| `categories.yaml` | Taxonomy | The fields a vehicle is described by, in order, and whether each is used for matching | `inventory_status: use_for_matching: false` |
| `models.yaml` | Vocabulary | Models, submodels, series and spelling aliases | `GTI: Golf GTI`, `Atlas Sport Cross: Atlas Cross Sport` |
| `keywords.yaml` | Vocabulary | What each word or phrase means, optionally only for some models; resolution rules | `4MOTION` → drivetrain `AWD`; `S` is a trim on ID.4 only |
| `vehicles/<model>.yaml` | Availability | What each model can have per year range, its review status, and facts a person verified | ID.4 2023: trim `PRO`, drivetrain `AWD`/`RWD`, battery `LG Energy Solution`/`SK On` |
| `accessories.yaml` | Accessory spec | File layout, part-number proof, units, comment cleaning, data-quality rules, variant label, export columns | `header_row: 2`, `export.columns` (section 8.3) |
| `messages.yaml` | Messages | Severity, message, causes and fix for every flag code | `ACCESS_CLEAN_UNIT_SUSPECT: severity warning` |

- **Validation at start:** the config step loads every file and checks it. Examples of what it checks:
  - a value in `vehicles/*.yaml` that no keyword produces;
  - overlapping year ranges for the same model;
  - an export column that doesn't exist;
  - a header used twice.
- **Config version:** a hash of the vocabulary and availability files (e.g. `fa8f28d77a`) is written on every vehicle row. If the config changes after the vehicles were built, the accessory run warns `ACCESS_DB_STALE` and asks for the ingest to be rerun.
- **Template:** `config/vehicles/_template.yaml` shows every category and value. `python new_vehicle.py "Beetle"` copies it to `beetle.yaml`. Files starting with `_` are never read.

## 6. Pipeline 1: Vehicle ingest

```
config ─► ingest ─► staging ─► year_window ─► clean ─► parse ─► resolve ─► validate ─► verify ─► write
```

| Step | What it does | Example |
|---|---|---|
| config | Loads and validates all config; exports the definitions as tables | 42 option sets across 10 vehicle files |
| ingest | Reads the VW export as text | 323 rows |
| staging | Keeps the source row untouched next to a row id, for lineage | `stg_vw_models_<run_id>.csv` |
| year_window | Keeps model years in the vehicle window (2020+) and logs what it drops | 54 rows from 2019 excluded |
| clean | Applies aliases, normalizes spaces, removes repeated words and moves inventory notes out | `Golf GTI GTI Autobahn` → `Golf GTI Autobahn`; `*Ltd Avail*` → `inventory_status` |
| parse | Finds the model and submodel at the start, then keyword phrases before words, longest first, respecting model scope | `ID.4 PRO S AWD` → trim `PRO S`, drivetrain `AWD` |
| resolve | Re-reads a value when the vehicle's option set gives the evidence | A lone `Black` on a 2024 Tiguan → special edition `Black Edition` |
| validate | Checks every vehicle against its option set and model-number consistency; unknown words and undeclared years are flagged | `VEH_PARSE_UNKNOWN_WORD`, `VEH_VALID_NOT_IN_CONFIG` |
| verify | Applies human-verified facts; data that contradicts a fact becomes an error | A Golf R 2021 in a future export → `VEH_VERIFY_CONTRADICTED` |
| write | Writes the vehicles file and the review queue, sorted with fixed columns | 269 vehicles |

**Worked example: one vehicle**

```
source       Tiguan Comfortline R-Line Black Edition 4MOTION        model number BJ26VJ, 2022
clean        (unchanged)
parse        model Tiguan │ trim Comfortline │ special_edition Black Edition (phrase, before "Black")
             appearance_package R-Line │ drivetrain AWD (4MOTION)
validate     every value is offered by tiguan.yaml for 2022 → parse_status complete
vehicles     VW-2022-BJ26VJ, Volkswagen, BJ26VJ, 2022, Tiguan, ..., Comfortline, Black Edition, R-Line, ..., AWD
```

## 7. Pipeline 2: Accessories

```
config ─► ingest ─► staging ─► year_window ─► part_numbers ─► clean_text ─► dedupe ─► part_number_review
       ─► clean ─► resolve_names ─► lookup ─► build_dict ─► coverage ─► validate ─► verify ─► export
```

| Step | What it does | Real run, 2026-10-30 |
|---|---|---|
| config | Loads `pipeline`, `accessories`, `models`, `messages` and the vehicle files | 11 columns, 9 export columns, 4 verified facts |
| ingest | Reads the sheet with its real layout (headers on row 2), every column as text | 24,396 rows; 725 part numbers stored as numbers |
| staging | Renames and types the columns; keeps Active parts only | 3,997 inactive rows left out → 20,399 |
| year_window | Keeps rows whose year range overlaps the accessory window, and clips the range to it | 10,724 rows left out → 9,675; 9,499 clipped |
| part_numbers | Proves each part number from `make&model`; restores leading zeros only when proven; stops the run if more than 1% can't be proven | 9,524 the same, 151 restored |
| clean_text | Cleans comments: HTML, pipes, links, spacing, sentence ends. The raw text is kept | 34 of 40 texts changed; 1 link replaced |
| dedupe | Removes exact copies, logging each one against the row it copies | 8,647 removed → 1,028 unique |
| part_number_review | Flags every restored or unproven part number in scope | `000071200` restored (10 rows) |
| clean | Applies name aliases, converts units, types the numbers | `GTI` → `Golf GTI`; labour minutes → hours |
| resolve_names | Checks every accessory model name is a known model or submodel | 10 of 10 resolved |
| lookup | Builds a vehicle index for the window, then looks up each unique key once | 29 keys, 27 found |
| build_dict | Expands each year range to single years and attaches the model numbers and variant | 9,481 rows in 10 models; 93 part-years with no vehicle |
| coverage | Checks the other way: vehicles in the window with no parts | 14 vehicles (all 2027) |
| validate | Data-quality rules (MSRP above cost, non-null, non-negative) and fitment hints | 15 descriptions hint at narrower fitment (info) |
| verify | Applies verified facts, then writes the review and verified-flags files | ID.4 and ID. Buzz 2026 verified; 16 review rows |
| export | Writes one sheet per model with the final columns | 9,388 rows in 10 sheets |

### 7.1 Worked example: one accessory

```
source        000019819C │ GTI │ make&model 000019819CGTI │ 2006-2026 │ Active │ MSRP 82 │ laborTime 10
              21 identical rows in the file
staging       kept (Active)
year_window   2006-2026 overlaps 2024+ → clipped to 2024-2026
part_numbers  000019819C + "GTI" = make&model → proven, same
dedupe        21 rows → 1
clean         model GTI → Golf GTI (alias) │ labour 10 min → 0.17 h
lookup        keys golf gti 2024, 2025, 2026 → 5, 2 and 2 model numbers
build_dict    9 rows: one per year and model number, with a variant label
export (GTI sheet)
  Part        ModelName  Description                        Price  Hours  Year  Variant      Model
  000019819C  Golf GTI   Seat Underlay with Backrest Cover  82     0.17   2024  Base         CD19UZ
  000019819C  Golf GTI   Seat Underlay with Backrest Cover  82     0.17   2024  Autobahn     CD1AU2
  000019819C  Golf GTI   Seat Underlay with Backrest Cover  82     0.17   2024  Performance  CD1PU2
  ...         (9 rows in all)
```

### 7.2 How the lookup works

1. The newest vehicles file is filtered to the accessory window (111 of 269 vehicles) and grouped into an index keyed by `(make, model, submodel, year)`. That gives 32 vehicle keys.
2. Each accessory row gets a match key, e.g. `volkswagen|golf|gti|2024`. Only the unique keys are looked up: 29 for 1,028 rows.
3. Each key goes through these checks:
   - **C1:** the model name is known (done in `resolve_names`);
   - **C2:** the vehicle DB has the key;
   - **C3:** the vehicle file declares the year;
   - **C4:** if not, which years the DB and config do know (before, after or a gap);
   - **C5:** whether that vehicle file is drafted or reviewed.
4. A found key attaches its model numbers. *Example:* `volkswagen|id.4|(base)|2024` → 6 model numbers, which serve all 95 ID.4 parts for 2024.
5. A missed key is flagged once, not per part, with every check written out:

```
FLAG ACCESS_LOOKUP_YEAR_AFTER_LAST_KNOWN | volkswagen|id. buzz|(base)|2026 - 1 parts
  what:    Accessory file lists ID. Buzz for 2026, but neither the vehicle DB nor the config has it after 2025
  checked: 1) vehicles_vw_ingest_20261028_152148.csv model=ID. Buzz year=2026 -> 0 rows (known years 2025)
           2) config/vehicles/id_buzz.yaml declared 2025 -> 2026 not declared
  causes:  a) discontinued after 2025  b) not in the VW export yet  c) the config's end year is wrong
  fix:     1) confirm with the data source  2) discontinued -> no action  3) not exported -> rerun run_ingest.py
```

### 7.3 Variant label

Configured in `accessories.yaml` → `variant`. The label joins the vehicle's standardized fields in a set order: trim > edition > packages > engine > transmission > drivetrain > body style. A vehicle with none of them is labelled `Base`.

- *Example:* 2024 Golf GTI `CD1PU2` → `Performance`. 2024 Golf GTI `CD19UZ` → `Base`.
- Because the label comes from standardized fields, it reads the same every year, even when VW's text changes (Atlas `CA37PR` "Peak Edition" in 2024–2025 vs "Peak" in 2026).

## 8. Cross-cutting mechanisms

### 8.1 Year windows

- One window per pipeline in `pipeline.yaml`, worked out at run start.
  - Vehicles: `min_model_year: 2020`.
  - Accessories: `current_year - 2`. That is 2024 in 2026, and 2025 in 2027 with no edit.
  - An empty max means no upper limit.
- `within: vw_models` keeps the accessory window inside the vehicle window.
- Every step that selects data uses its window. The accessory run never sees 2020–2023 vehicles, so a 2020 vehicle can't cause a false "missing model number".

### 8.2 Flags, severities and run status

| Severity | Meaning | Run status | Example |
|---|---|---|---|
| fatal | The run stops | `failed` | `ACCESS_EXPORT_FILE_LOCKED` (the Excel file is open) |
| error | A row or key can't be used; goes to review | `ok_with_errors` | `ACCESS_LOOKUP_YEAR_AFTER_LAST_KNOWN` |
| warning | Used, but a person should look; goes to review | `ok_with_warnings` | `ACCESS_CLEAN_UNIT_SUSPECT` (0.4 minutes) |
| info | Noted in the log only | `ok` | `ACCESS_YEAR_CLIPPED` |

- Codes follow `<PIPELINE>_<STAGE>_<WHAT>`. The wording lives in `messages.yaml`, and the code passes only the facts.
- Exit codes: `0` = ok or ok with warnings, `1` = errors or a failed run, `2` = `pipeline.yaml` unreadable.

### 8.3 Human-verified facts

People record what they confirmed in `vehicles/<model>.yaml`, with a reason, who and when. The verify step runs last in both pipelines.

| Fact | Effect | Example |
|---|---|---|
| `never_offered: {years: [...]}` | Lookup flags for exactly that vehicle and year drop to info and leave the review file | ID.4 2026 and ID. Buzz 2026: review rows went from 109 to 16 |
| `never_offered: {<category>: [...]}` with `years` | Guards the data: a vehicle in the export with that option becomes an error | Golf R 2024–2025 never Manual (template example) |
| `no_parts_expected: {years, until}` | No-parts flags drop to info until the date, then return as `ACCESS_VERIFY_EXPIRED` | 2026 parts not published yet, until 2027-03-31 |

Nothing is deleted. A verified flag keeps its original severity in the flag log and is listed in `verified_flags_<run_id>.csv`.

### 8.4 Export

`accessories.yaml` → `export.columns` holds the **final column names**, in order. It maps each pipeline column to its header in the file:

`part_number: Part` · `model_name_clean: ModelName` · `product_description: Description` · `msrp: Price` · `labor_time: Hours` · `comments: Comments` · `variant: Variant` · `applicable_year: Year` · `model_number: Model`

- A column left out is not in the file; Cost, for now.
- The headers apply to the Excel file only. The dict returned to the notebook keeps the pipeline names.
- Only matched rows are exported (`include_unmatched: false`). Unmatched part-years stay in the review file.
- `Part` cells are written as Excel text, so Excel can't drop leading zeros again.

## 9. Storage and traceability

```
db/
├── definitions/  dim_<name>_<run_id>.csv        config flattened to tables (models, keywords, option sets, facts)
├── staging/      stg_vw_models_<run_id>.csv     source rows as read
├── final/        vehicles_<run_id>.csv          the vehicle database
├── review/       review_queue_<run_id>.csv      vehicles to check
│                 accessory_review_<run_id>.csv  part-years with no vehicle, restored part numbers, suspect values,
│                                                vehicles with no parts; each with code, checks, causes and fix
├── dq/           accessory_lookup_<run_id>.csv  one row per key: what was checked, what was found
│                 part_number_check_<run_id>.csv how each part number was proven
│                 verified_flags_<run_id>.csv    flags a verified fact explained
│                 ingest_runs.csv, accessory_runs.csv   one summary row per run (status, counts, files used)
└── logs/         runs/<run_id>.log              the readable story of a run
                  changes/<run_id>.csv           every value changed: before, after, rule
                  flags/<run_id>.csv             every flag with its full message
                  steps.csv                      one row per step, all runs
```

- **Run id:** `<pipeline>_<YYYYMMDD_HHMMSS>`, e.g. `vw_accessories_20261029_085242`. A reader always takes the newest file.
- **Lineage:** every value can be traced back to its source.
  - *Example:* a `Part` in the export → `part_number_check` (how it was proven) → `changes` (`71200` → `000071200`) → the source row number.
- **Where to look after a run:**
  1. `accessory_runs.csv`: the last row's status and files.
  2. The run log: what happened and why.
  3. The review file: what to fix.

## 10. Data challenges and where they are handled

| Challenge | Source | Scale | Handled by | Example |
|---|---|---|---|---|
| Only free text describes the vehicle | Vehicles | All 269 | parse (`keywords.yaml`) | `4MOTION` → AWD |
| Repeated words, misspelt submodel | Vehicles | 13 texts; 2020–2023 | clean, aliases | `ID.4 ID.4 PRO` → `ID.4 PRO` |
| A word with two meanings | Vehicles | Tiguan, Taos | resolve (option-set evidence) | Lone `Black` → `Black Edition` |
| Same vehicle written differently by year | Vehicles | e.g. `CA37PR` | keywords map both to one value | "Peak" and "Peak Edition" → `Peak Edition` |
| Many vehicles have no trim | Vehicles | 56 of 269 | variant label | GTI `CD19UZ` → `Base` |
| Headers on row 2 | Accessories | Whole file | `header_row: 2` | — |
| 90% exact copies | Accessories | 8,647 rows today | dedupe | 21 copies of `000019819C` GTI → 1 |
| Leading zeros lost | Accessories | 151 rows in scope | part_numbers (proof from `make&model`) | `71200` → `000071200` |
| Different model names | Accessories | 90 GTI rows | shared alias | `GTI` → `Golf GTI` |
| Year ranges past the vehicle's life | Accessories | 93 part-years | lookup flags + verified facts | ID.4 2026: never offered |
| Unit not stated | Accessories | All labour values | units config | `25` min → `0.42` h; `0.4` flagged |
| HTML, pipes, private links in comments | Accessories | 34 texts | clean_text | `<p>...</p><p>...` → two sentences; Salsify link → `Thule.com` |
| No parts for the newest year | Accessories | 14 vehicles (2027) | coverage | Flag for the data source |

Every challenge is listed with its full detail and status in [planning/data_issues.md](planning/data_issues.md) (DI-NN, DV-NN).

## 11. Quality gates

- **Config validation:** a broken setting stops the run before any data is read, with a `CONFG_` code that names the file and value.
- **Run-time stops:** the run stops if part-number proof fails above 1%, if a source file is missing, or if an output file is locked.
- **285 automated tests:**
  - unit tests per helper (`ID.4 PRO S AWD` → trim `PRO S`);
  - every broken config case gives its message;
  - end-to-end runs on the real files check the counts in section 7 (1,028 unique rows, 27 of 29 keys, every `Part` as text);
  - a planning test keeps the plan statuses and the index in step.
- **Baseline:** each real run's numbers are recorded in [planning/README.md](planning/README.md#baseline), so a change in the numbers is visible.

## 12. Extending the system

| Need | Change | Example |
|---|---|---|
| A new word in vehicle descriptions | Add it to `keywords.yaml` under its category | `- match: Dune` under `special_edition` |
| A new model | Add it to `models.yaml`, then run `python new_vehicle.py "<Model>"` and fill its option sets | `Beetle` → `config/vehicles/beetle.yaml` |
| A new model year | Extend or add an option set in `vehicles/<model>.yaml`, then rerun the ingest | Add `years: [2027, 2027]` |
| A fact a person confirmed | Add a `verified:` entry with reason, who and when | `never_offered: {years: [2026]}` |
| A different accessory window | Change `datasets.accessories.min_model_year` | `current_year - 3` |
| An export column or header | Edit `export.columns` | Add `cost: Cost` back |
| A new flag's wording | Edit its entry in `messages.yaml` | — |

## 13. Known limitations and open items

- **Data source:**
  - no parts for model year 2027 (DI-06);
  - base Atlas 2020 missing from the vehicle export (DV-08);
  - whether `0.4` labour on `3QF601025KAX1` is minutes or hours (OI-06);
  - export part numbers as text (OI-07).
- **Matching precision:** 14 vehicle rows share all their parsed fields with another row but have a different model number. Something that tells them apart isn't in the description, so their parts list both model numbers.
- **Fitment hints:** 15 descriptions say things like "not for R-Line". They are flagged as info but not used to narrow the match (DI-13).
- **Open decisions:** the run report (idea 005) and the documentation standard (idea 011). See [planning/open_items.md](planning/open_items.md).
