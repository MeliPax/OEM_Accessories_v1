# VW Data Issues Log

**Purpose:** a running log of the data issues found in the VW source files, how the pipeline handles each one, and what still needs action. It closes with the data boundaries and definitions the pipeline uses, so everyone reads the numbers the same way.
**Last updated:** 2026-10-28
**Sources reviewed:**

| Source | File | Received |
|---|---|---|
| VW accessory file | `datasets/2026_10_20_VW Canada Accessories Data EN.xlsx` (24,396 rows) | 2026-10-20 |
| VW model export | `datasets/vw_models_data.csv` (323 rows) | — |

**Status values:**

| Status | Meaning |
|---|---|
| **Handled** | The pipeline corrects or works around it today; no action needed |
| **Planned** | A fix is designed and approved, not built yet (idea number given) |
| **Open** | Needs a decision or confirmation from the data source |
| **Accepted** | Known and fine as it is |

---

## Summary

| ID | Source | Issue | Scale (in scope*) | Status |
|---|---|---|---|---|
| [DI-01](#di-01) | Accessories | Column names are on row 2; row 1 is empty | whole file | Handled |
| [DI-02](#di-02) | Accessories | 90% of rows are exact copies | 11,694 of 13,051 rows | Handled |
| [DI-03](#di-03) | Accessories | Part numbers lose their leading zeros | 1 part, 12 rows (704 rows file-wide) | Handled (008); ask the source |
| [DI-04](#di-04) | Accessories | Golf GTI is named only "GTI" | 109 parts | Handled |
| [DI-05](#di-05) | Accessories | Year ranges reach years with no VW vehicle | 7 model-years, 451 part-years | **Open** |
| [DI-06](#di-06) | Accessories | No parts listed for model year 2027 | 14 vehicles | **Open** |
| [DI-07](#di-07) | Accessories | Labour time unit not stated (minutes); one value looks like hours | 1,357 rows; 1 part suspect | Handled (006) + **Open** (one value) |
| [DI-08](#di-08) | Accessories | Comments hold HTML markup; sentences run together | 38 texts, 256 rows | Handled (007) |
| [DI-09](#di-09) | Accessories | Comments use `\|` / `\|\|` as line breaks | 8 texts, 64 rows | Handled (007) |
| [DI-10](#di-10) | Accessories | Comment links to a catalogue page that isn't public | 1 part, 13 rows | Handled (007) |
| [DI-11](#di-11) | Accessories | Comment spacing (non-breaking space, space before full stop) | 2 texts, 36 rows | Handled (007) |
| [DI-12](#di-12) | Accessories | Comments link to the VW dealer portal | 3 texts, 4 parts | Accepted |
| [DI-13](#di-13) | Accessories | Product descriptions hint at narrower fitment | 16 descriptions | Accepted |
| [DI-14](#di-14) | Accessories | Redundant `make&model` column | whole file | Handled |
| [DI-15](#di-15) | Accessories | Inactive parts and parts for older vehicles | 3,997 + 7,348 rows | Handled |
| [DI-16](#di-16) | Accessories | Two sentences glued together in a comment ("ReferAlways install") | 1 text, 2 rows | Accepted |
| [DV-01](#dv-01) | VW models | Only `Description` is filled; 7 columns are empty | whole file | Handled |
| [DV-02](#dv-02) | VW models | Repeated words in descriptions | 13 distinct descriptions | Handled |
| [DV-03](#dv-03) | VW models | "Atlas Sport Cross" spelling for Atlas Cross Sport | 2020–2023 | Handled |
| [DV-04](#dv-04) | VW models | A lone "Black" that means Black Edition | Tiguan 2024–26, Taos 2025–27 | Handled |
| [DV-05](#dv-05) | VW models | The same vehicle described differently in different years | e.g. Atlas CA37PR | Handled |
| [DV-06](#dv-06) | VW models | Model numbers reused across years with a trim change | CMC4NR, CMC4UR | Accepted |
| [DV-07](#dv-07) | VW models | Many vehicles have no trim in the description | 56 of 269 | Handled |
| [DV-08](#dv-08) | VW models | Base Atlas missing for 2020 | 2020 | **Open** |
| [DV-09](#dv-09) | VW models | ID.4 and ID. Buzz end at 2025 | 2026 | **Open** |
| [DV-10](#dv-10) | VW models | Inventory note `*Ltd Avail*` inside the description | 11 rows | Handled |
| [DV-11](#dv-11) | VW models | Model year 2019 rows | 54 rows | Handled |

\* "In scope" = Active parts whose year range reaches 2020 or later, after exact copies are removed (1,357 part / model rows). Vehicles are model years 2020 and later (269).

---

## Accessory file

### DI-01

**Column names are on row 2; row 1 is empty**

- **Found:** the sheet starts with an empty row, and the column names (`stockCode`, `model`, ...) are on row 2.
- **Impact:** read naively, every column comes in as `Unnamed: 0`, `Unnamed: 1`, ...
- **Handling:** `header_row: 2` in `config/accessories.yaml`. If the layout moves, the run stops with `ACCESS_SRC_HEADER_NOT_FOUND` and shows what the row holds.
- **Status:** Handled.

### DI-02

**90% of rows are exact copies**

- **Found:** of the 13,051 Active rows in the year window, 11,694 are exact copies of another row (same part, model, year range, description, comments, prices and labour). 1,357 unique rows remain.
- **Impact:** inflated counts and repeated parts if not removed.
- **Handling:** the `dedupe` step removes exact copies and logs each one with the row it copies. If two rows for the same part and model differ, they are flagged `ACCESS_STGNG_DUPLICATE_CONFLICT` and both are kept (none today).
- **Question for the data source:** why is each row repeated? (Possibly one row per trim or option that isn't in the file.)
- **Status:** Handled.

### DI-03

**Part numbers lose their leading zeros**

- **Found:** some `stockCode` cells are stored as numbers in Excel, so their leading zeros are gone. The `make&model` column (part number + model name) still has the full number.

  | `stockCode` in file | `make&model` | Real part number |
  |---|---|---|
  | `71200` | `000071200Atlas` | `000071200` (Cargo Box Carrier – Matte Black 340L) |
  | `61122` | `000061122Alltrack` | `000061122` (Inactive) |

- **Scale:** 704 rows, 3 parts file-wide (`000061122`, `000071200`, `000072709`; 415 rows Active). In scope: 1 part (`000071200`), 12 rows. The cells use Excel's `General` format, so the zeros are gone from the value itself, not just hidden. In the 23,671 text rows, `make&model` agrees with `stockCode` every time.
- **Impact:** the export shows `71200` instead of `000071200`, which won't match VW's catalogue.
- **Fix:** [idea 008](ideas/008_part_number_integrity_design.md):
  - compare `stockCode` with the part number inside `make&model`;
  - when only leading zeros differ, restore the full number and log the change;
  - when they differ in another way, flag it for review;
  - write Part Number as text in the export.

  Never padded: the complete number must be proven by `make&model`.
- **Handling (built 2026-10-27):** every row is checked; the result is in `db/dq/part_number_check.csv`. On the 2026-10-20 file, 704 rows are restored and 0 can't be proven. The in-scope part appears in `accessory_review.csv` as `ACCESS_STGNG_PART_NUMBER_RESTORED`, and the export shows `000071200`.
- **Ask the data source:** export `stockCode` as text.
- **Status:** Handled (idea 008). Still ask the data source to export `stockCode` as text.

### DI-04

**Golf GTI is named only "GTI"**

- **Found:** the accessory file names the Golf GTI `GTI`, without the family name. The VW model export says `Golf GTI`.
- **Handling:** a shared alias in `config/models.yaml` (`GTI: Golf GTI`). It only rewrites the word GTI; `Golf` alone stays the base Golf. Checked: no VW description changes.
- **Status:** Handled.

### DI-05

**Year ranges reach years with no VW vehicle**

- **Found:** 7 accessory model-years have no vehicle in the VW model export or the vehicle config:

  | Model / year | Parts | Code | Likely reason |
  |---|---|---|---|
  | Arteon 2022, 2023 | 58, 60 | `ACCESS_LOOKUP_YEAR_AFTER_LAST_KNOWN` | Arteon was discontinued after 2021 |
  | ID.4 2026 | 92 | `ACCESS_LOOKUP_YEAR_AFTER_LAST_KNOWN` | 2026 not in the VW export yet (see DV-09) |
  | ID. Buzz 2026 | 1 | `ACCESS_LOOKUP_YEAR_AFTER_LAST_KNOWN` | 2026 not in the VW export yet (see DV-09) |
  | Atlas (base) 2020 | 132 | `ACCESS_LOOKUP_YEAR_BEFORE_FIRST_KNOWN` | export has only Atlas Cross Sport for 2020 (see DV-08) |
  | Golf R 2020, 2021 | 54, 54 | `ACCESS_LOOKUP_YEAR_BEFORE_FIRST_KNOWN` | Golf R was not sold in those model years |

- **Impact:** 451 part-years get no model number. They stay in the data, are left out of the export, and are listed in `db/review/accessory_review.csv` with what was checked and the fix.
- **Ask the data source:** confirm Atlas 2020, ID.4 2026 and ID. Buzz 2026. Arteon and Golf R look like the accessory ranges running past the vehicle's life.
- **Status:** **Open**.

### DI-06

**No parts listed for model year 2027**

- **Found:** 14 vehicles in the VW export get no accessory parts. All of them are model year 2027:

  | Vehicle | Count |
  |---|---|
  | Atlas | 3 |
  | Jetta | 1 |
  | Jetta GLI | 1 |
  | Taos | 5 |
  | Tiguan | 4 |

  Their accessories stop at 2026.
- **Impact:** no parts are exported for 2027 vehicles.
- **Handling:** flagged `ACCESS_COVER_VEHICLE_NO_PARTS` (once per model-year) and listed in the review file.
- **Ask the data source:** an accessory file updated for 2027.
- **Status:** **Open**.

### DI-07

**Labour time unit not stated (minutes); one value looks like hours**

- **Found:** `laborTime` holds minutes, but the file doesn't say so. The values are 0 (793 rows) and whole minutes from 10 to 250. Part `3QF601025KAX1` (20" Mejorada wheel, Atlas and Atlas Cross Sport) has **0.4**, which is not a whole minute and is most likely already in hours (24 minutes).
- **Impact:** the export shows minutes under a "Labour Time" header; the 0.4 value is inconsistent with every other row.
- **Fix:** [idea 006](ideas/006_labor_time_units_design.md):
  - convert minutes to hours using unit definitions in config (2 decimals);
  - keep the raw minutes for lineage;
  - export the header as `Labour Time (hours)`;
  - flag values that look like the wrong unit (`ACCESS_CLEAN_UNIT_SUSPECT`).
- **Handling (built 2026-10-28):** the export shows hours. `3QF601025KAX1` is flagged `ACCESS_CLEAN_UNIT_SUSPECT` and listed in `accessory_review.csv`; it is still converted (0.4 min → 0.01 h) until the source confirms the value.
- **Ask the data source:** confirm the unit, and the labour time for `3QF601025KAX1`.
- **Status:** Handled (idea 006) + **Open** (the 0.4 value).

### DI-08

**Comments hold HTML markup; sentences run together**

- **Found:** 38 distinct comment texts (256 rows, 106 parts) contain HTML tags: `<p>`, `</p>`, `<br>`, `<br/>`, `<b>`. In 23 of them a closing `</p>` is followed straight by the next sentence, e.g. `...9TJ, 9TL</p>Always install...`.
- **Fix:** [idea 007](ideas/007_comment_text_cleaning_design.md):
  - paragraph and line-break tags become sentence breaks;
  - other tags are removed;
  - every change is logged before → after.
- **Handling (built 2026-10-28):** 54 of the 62 distinct comments change (2,969 rows in the year window); no tags or pipes are left in the export. The raw text is kept as `comments_source`.
- **Status:** Handled.

### DI-09

**Comments use `|` / `||` as line breaks**

- **Found:** 8 distinct texts (64 rows, 9 parts) start with `|` and separate lines with `||`. Example: `|Installs in top left of trunk under hat shelf. ||Weight limit 10 lbs. (5kg)||Not for vehicles with Fender Amplifier||...`
- **Fix:** idea 007 splits on the pipes, trims each piece, adds a full stop where one is missing, and joins the pieces into sentences.
- **Status:** Handled (2026-10-28).

### DI-10

**Comment links to a catalogue page that isn't public**

- **Found:** part `000071120APDC` (13 rows, one per model) says: "Visit https://app.salsify.com/catalogs/fde773be-fbbd-410b-99ab-5178d20956b6 for additional product information, information on spare parts, and THULE's warranty claim process." The Salsify page isn't publicly accessible.
- **Fix:** idea 007 link rule: replace the URL with `Thule.com`. That matches the wording VW already uses on other Thule parts. Any future link not covered by a rule or an allowed site is flagged `ACCESS_CLEAN_UNREVIEWED_LINK`.
- **Status:** Handled (2026-10-28).

### DI-11

**Comment spacing**

- **Found:** a non-breaking space in 1 text (2 rows), and a space before the full stop in 1 text (34 rows: "...warranty claim process .").
- **Fix:** idea 007 normalizes spaces and removes a space before punctuation, but only when the mark ends the word. So `5G0.071.644.B .GRU` (a part reference) is left as it is.
- **Status:** Handled (2026-10-28).

### DI-12

**Comments link to the VW dealer portal**

- **Found:** 3 texts (parts `17A071641GRU`, `3CN092730`, `5NA092730`, `5NL017221A`) link to `www.vwhub.com/...` (technician references).
- **Decision (2026-10-27):** keep them; `www.vwhub.com` is an allowed link host.
- **Status:** Accepted.

### DI-13

**Product descriptions hint at narrower fitment**

- **Found:** 16 descriptions name a trim or configuration, e.g. "Front Mud Flaps, not for R-Line", "(Without front passenger mat clips)", "(Bench Seating)", "Captain Chairs".
- **Decision:** an accessory fits **every** vehicle in its model and year range; descriptions never narrow it. These are noted in the run log only (`ACCESS_DQ_FITMENT_HINT`).
- **Question for the business:** should fitment ever be narrowed by trim? If so, it needs a proper source, not description text.
- **Status:** Accepted.

### DI-14

**Redundant `make&model` column**

- **Found:** `make&model` is the part number followed by the model name (e.g. `000019819CArteon`).
- **Handling:** not used, except as the source of the full part number for DI-03.
- **Status:** Handled.

### DI-15

**Inactive parts and parts for older vehicles**

- **Found:**
  - 3,997 rows are `Inactive`.
  - 7,348 Active rows are only for vehicles before 2020.
  - 10,197 rows start before 2020; only their years from 2020 on are used.
- **Handling:** left out by the status filter and the year window; each row is logged with its reason.
- **Status:** Handled.

### DI-16

**Two sentences glued together in a comment**

- **Found:** one comment reads `ReferAlways install the product according to the manufacturer's instructions...` (2 rows). It looks like a "Refer to ..." sentence was cut off and joined to the standard installation sentence.
- **Impact:** the export shows "ReferAlways".
- **Decision (2026-10-28):** leave the text as it is. Cleaning has no rule for it: there is no separator to split on, and the pipeline never guesses missing text.
- **Status:** Accepted.

---

## VW model export

### DV-01

**Only `Description` is filled; 7 columns are empty**

- **Found:** `Drivetrain`, `ModelName`, `Package`, `PassDoors`, `Style_ID`, `TrimName` and `engine_type` are empty in every row. Model, trim, packages, engine and so on exist only inside the free-text `Description`.
- **Handling:** the vehicle ingest parses each description into taxonomy fields, using `config/models.yaml` and `config/keywords.yaml`.
- **Status:** Handled.

### DV-02

**Repeated words in descriptions**

- **Found:** e.g. `Jetta GLI GLI`, `ID.4 ID.4 PRO`, `Golf GTI GTI Autobahn`, `Golf R Golf R Black`, `ID. Buzz ID. Buzz 1st Edition`.
- **Handling:** repeated words are removed while cleaning (`Jetta GLI`, `ID.4 PRO`, ...); logged before → after.
- **Status:** Handled.

### DV-03

**"Atlas Sport Cross" spelling for Atlas Cross Sport**

- **Found:** model years 2020–2023 say `Atlas Sport Cross`; later years say `Atlas Cross Sport`.
- **Handling:** alias in `config/models.yaml`.
- **Status:** Handled.

### DV-04

**A lone "Black" that means Black Edition**

- **Found:** some Tiguan (2024–2026) and Taos (2025–2027) descriptions say `Black` where the vehicle is the Black Edition.
- **Handling:** a resolution rule. A lone `Black` becomes `Black Edition` when that vehicle's option set offers it. Model-number evidence alone only raises `VEH_RESOLVE_SUGGESTED` for review.
- **Status:** Handled.

### DV-05

**The same vehicle described differently in different years**

- **Found:** Atlas `CA37PR` is "Atlas Peak Edition" in 2024–2025 but "Atlas Peak" in 2026.
- **Handling:** keywords map both to `Peak Edition`. The export's Variant is built from these standardized fields, not the raw text, so it reads the same every year.
- **Status:** Handled.

### DV-06

**Model numbers reused across years with a trim change**

- **Found:** `CMC4NR` and `CMC4UR` (Atlas Cross Sport) are Comfortline in 2020 and Highline in 2021–2022.
- **Decision:** the vehicle key is (model number, model year), so a reused code is fine. Only a change of model or submodel is flagged (`VEH_VALID_MODEL_NUMBER_REUSED`); trim changes are noted in the run log.
- **Status:** Accepted.

### DV-07

**Many vehicles have no trim in the description**

- **Found:** 56 of 269 vehicles have no trim (mostly Golf GTI, Golf R, Jetta GLI). 16 have nothing beyond model and submodel, e.g. 2024 Golf GTI `CD19UZ`.
- **Handling:** the export's **Variant** column combines the vehicle's standardized fields, e.g. `Performance Manual`, `40th Anniversary Automatic`. Vehicles with none of them are labelled `Base`. Both the label and the rule are config.
- **Status:** Handled.

### DV-08

**Base Atlas missing for 2020**

- **Found:** the 2020 rows have only Atlas Cross Sport; there is no base Atlas. The accessory file lists 132 parts for base Atlas 2020 (see DI-05).
- **Ask the data source:** is base Atlas 2020 missing from the export?
- **Status:** **Open**.

### DV-09

**ID.4 and ID. Buzz end at 2025**

- **Found:** the export has ID.4 for 2021–2025 and ID. Buzz for 2025 only. Other models reach 2026–2027.
- **Ask the data source:** are the 2026 ID models missing from the export? (See DI-05.)
- **Status:** **Open**.

### DV-10

**Inventory note `*Ltd Avail*` inside the description**

- **Found:** 11 rows carry `*Ltd Avail*` (limited availability) in the vehicle description.
- **Handling:** stored as `inventory_status = Limited Availability`. This is metadata and is never used for matching.
- **Status:** Handled.

### DV-11

**Model year 2019 rows**

- **Found:** 54 rows are model year 2019.
- **Handling:** outside the year window (2020+); left out and logged (`VEH_YEAR_OUT_OF_WINDOW`).
- **Status:** Handled.

---

## Data boundaries and definitions

### Scope

| Boundary | Definition | Where it's set |
|---|---|---|
| Make | Volkswagen only; rows of another make are flagged and left out | `config/models.yaml` |
| Model year window | 2020 and later. `max_model_year` is empty, so there is no upper limit; when set, it caps the window | `config/pipeline.yaml` |
| Vehicle years | A vehicle is in scope when its model year is inside the window | `datasets.vw_models: single_year` |
| Accessory years | A part is in scope when its year range overlaps the window. Only the years inside the window are used: 2018–2022 becomes 2020, 2021, 2022 | `datasets.accessories: range_overlap` |
| Accessory status | `Active` only; `Inactive` is left out; any other status is flagged and left out | `config/accessories.yaml` |

### Keys

| Key | Definition |
|---|---|
| Vehicle | (model number, model year). The same model number can be reused across years |
| `vehicle_id` | `VW-{model_year}-{model_number}`, unique and stable across runs |
| Accessory row | (part number, model name). The same part is listed once per model it fits |
| Match key | `make\|model\|submodel\|year`, e.g. `volkswagen\|golf\|gti\|2023`; `(base)` when there is no submodel |

### Vehicles and models

| Term | Definition |
|---|---|
| Model / submodel | From `config/models.yaml`, e.g. Golf with submodels GTI, R, Alltrack, SportWagen; Atlas with Cross Sport; Jetta with GLI |
| Base model | A model with no submodel. Accessory `Golf` means the **base Golf only** (not GTI or R); `Atlas` means base Atlas (not Cross Sport) |
| Aliases | Alternative spellings mapped to one standard name, **shared by both sources** so they produce the same names (`Atlas Sport Cross` → `Atlas Cross Sport`, `GTI` → `Golf GTI`) |
| Option set | What a model / submodel can have in a range of years (trims, packages, ...). It also says which years the model legitimately exists. A category not listed means "not offered" |
| Drafted / reviewed | A vehicle config file is `drafted` when built from the data and `reviewed` once a person has checked it. Today all 10 are `drafted` |
| Taxonomy fields | trim, special edition, appearance / technology / performance package, engine, transmission, drivetrain, body style, battery supplier, inventory status. Multi-value fields (appearance, technology, body style) can hold several values |
| Inventory status | Metadata (e.g. Limited Availability); never used for matching |
| Edition | "Edition" is never stored alone; it is part of an edition name (Black Edition, Peak Edition, 40th Anniversary) |
| Variant | The label that best describes a vehicle: its standardized fields joined in a fixed order (trim → special edition → appearance → performance → technology → engine → transmission → drivetrain → body style). `Base` when none has a value |

### Fitment and matching

| Rule | Definition |
|---|---|
| Fitment | An accessory fits **every** vehicle of its model / submodel in each year of its range. Every model number in that set applies |
| Descriptions | Product descriptions never narrow fitment (see DI-13) |
| Lookup | The vehicle database is searched once per unique (model, submodel, year), not once per row; nothing merged is saved |
| Unmatched | A part-year with no vehicle keeps an empty model number, goes to the review file, and is left out of the export |
| Duplicates | Rows identical on every column (except the row number) are copies and are removed; rows for the same part and model that differ are flagged and kept |

### Units and text (ideas 006 and 007)

| Item | Definition |
|---|---|
| Labour time | Source unit: minutes. Export unit: hours, 2 decimals (25 min → 0.42 h). The raw minutes are kept for lineage. Units are defined in config (`minutes: 60` per hour) |
| Comments | HTML removed; `\|` / `\|\|` and paragraph breaks become sentences; spaces tidied; dead links replaced by rules in config; `www.vwhub.com` links kept; raw text kept for lineage |

### Flags

| Severity | Meaning |
|---|---|
| `fatal` | The run stops (broken config, missing file, output file open) |
| `error` | A row or key can't be used (left out, or no model number); goes to review |
| `warning` | Used, but a person should look; goes to review |
| `info` | Noted in the run log only |

Codes are `<PIPELINE>_<STAGE>_<WHAT>`: `CONFG_` config, `VEH_` vehicle ingest, `ACCESS_` accessories. Each code's message, causes and fix are in `config/messages.yaml`.

---

## Adding an issue

Add a row to the summary and a section below it, with:
- the next ID (`DI-` for the accessory file, `DV-` for the VW model export);
- what was found, with an example;
- the scale (rows / parts in scope);
- the impact;
- the handling or proposed fix;
- what to ask the data source;
- the status.

When an issue is fixed or decided, update its status and note the date.
