# 005 — Pipeline Report Card + Data-Quality Sheet: Design (seed)

**Status:** Seed — to discuss after plan 003 (2026-10-27). Lists what to track; layout and format not decided.
**Asked for:** "a pipeline report card that covers all the statistics of the pipeline, from start to finish, to provide management overview ... know which vehicles got data updates, those that didn't have data, those missing model numbers, and all the necessary information for governance."

## Goal

One file per run that a manager can read in five minutes and act on:

- Did the run work, and on which data?
- What changed since last time?
- Which vehicles and parts have gaps, and who needs to do what?

Every number is computed from the logs the pipelines already write (`steps.csv`, flags, changes, lookup and review files). The report card never recounts the data, so it can't disagree with the logs.

## What to track

### 1. Run identity (traceability)

- Run id, start / end time, duration, status for each pipeline (vehicle ingest, accessories).
- Source files: name, last-modified date, row count, file hash. This shows whether a new file was actually used.
- Config version (taxonomy hash, accessory config hash), and which `vehicles/*.yaml` are `reviewed` vs `drafted` (idea 004 E5).
- The vehicle DB the accessories run used: its ingest run id and age, plus whether `ACCESS_DB_STALE` fired.

### 2. Funnel: where rows went (start to finish)

| Vehicle ingest | Accessories |
|---|---|
| rows in the export | rows in the file |
| staged | Active / Inactive / unexpected status |
| excluded by year (by year) | excluded by year window; years clipped |
| parsed complete % | duplicates removed |
| final vehicles | part-years after explode |
| | matched / unmatched part-years; rows exported per sheet |

Each step's in → out has to reconcile; a row that disappears without a logged reason is itself an alert.

### 3. Vehicle DB overview (per model, submodel, year)

- Vehicles and model numbers.
- **Data updates since the last run:** vehicles added, removed (`VEH_WRITE_VEHICLE_REMOVED`) and changed (which fields).
- Completeness: vehicles missing trim, missing other taxonomy fields, `parse_status` not complete. Today 56 of 269 have no trim.
- Config agreement: vehicles not declared in config (`VEH_VALID_NOT_IN_CONFIG`), options not offered.
- Model numbers reused across years with a change (`VEH_VALID_MODEL_NUMBER_REUSED`).

### 4. Accessory coverage (the governance core)

One row per (model, submodel, year) across **both** sides:

| Column | Meaning |
|---|---|
| vehicles in DB | count of model numbers |
| parts listed | accessory parts for that key |
| status | `covered` / `vehicle has no parts` (`ACCESS_COVER_VEHICLE_NO_PARTS`) / `parts have no vehicle` (the `ACCESS_LOOKUP_*` code) |
| action owner | data source / config / vehicle ingest, from the code |

From this table:

- **Vehicles with no parts** (today: the 14 model-year 2027 vehicles).
- **Parts with no vehicle**, by reason (today: 7 keys).
- Coverage % per model.

### 5. Accessory content

- Unique parts, parts per model, parts that fit several models.
- **Changes since the last run:** new parts, removed parts, price changes (MSRP, cost), labour time changes, status changes.
- Pricing sanity: msrp ≤ cost count, zero prices, margin range per model (optional).

### 6. Flags and review

- Counts by severity and by code, both pipelines; top codes.
- Open review items, and whether each is new or carried over from the last run.
- Trend over the last N runs (from `ingest_runs.csv` / `accessory_runs.csv`).

### 7. Outputs

- Export file path, sheets, rows per sheet, matched rows only (idea 003).

## Data-quality issues sheet (to plan separately)

A sheet, in the export or the report card, with one row per data issue found: code, severity, the row or key, what was checked, what was found, the fix (idea 004 fields). It's the review file in a readable form. Open: one sheet for both pipelines or one each; issues from this run only or all open ones.

## Open questions (for later)

- Format: an Excel workbook (overview sheet + detail sheets), a Markdown or HTML page, or both?
- Separate file per run, or one sheet added to the export?
- Thresholds that turn a number red (e.g. coverage below 95%, any `fatal`, a DB older than N days)?
- Who reads it, and which three numbers do they need first?
