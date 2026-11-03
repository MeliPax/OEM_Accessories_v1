# VW Open Items

**Purpose:** every follow-up and open question across the VW work, in one list, each with an owner. An item's ID starts with the doc it belongs to, so the ID alone says where to look (idea / plan [015](plans/015_doc_numbered_item_ids.md)).
**Last updated:** 2026-11-03

**IDs:** `NNN-Kn` for a doc (`013-D2` → `ideas/013_*` or `plans/013_*`), `DInn-Sn` for a data issue (`DI07-S1` → [data_issues.md#di-07](data_issues.md#di-07)), `000-Kn` for the planning process itself. A decision set is one row with a range (`005-D4 – 005-D12`); the doc's Decisions table holds each one.
**Kinds:** `D` decision · `T` testing sign-off (one per plan) · `P` plan approval (one per plan) · `U` task for the user · `A` task for Claude · `S` question for the data source
**Owners:** `user` (decide or sign off) · `data source` (VW data) · `Claude` (work to do)
**Status:** `Open` · `Waiting` (asked; waiting for an answer) · `Closed YYYY-MM-DD` (the row is kept)
**Was:** the old `OI-NN` (and decision letters), so references in commits and dated history still resolve.

| ID | Where | What | Owner | Status | Was |
|---|---|---|---|---|---|
| 001-T | [plan 001](plans/001_vw_model_ingest_mvp.md) | Sign off testing, so the plan can move to `completed/` | user | Open | OI-01 |
| 001-U1 | [plan 001](plans/001_vw_model_ingest_mvp.md) | Review `config/vehicles/*.yaml`: all 10 `reviewed` by P.M (ID. Buzz 2026-10-29, the other 9 2026-11-03) | user | Closed 2026-11-03 | OI-03 |
| 002-T | [plan 002](plans/002_pipeline_logging.md) | Sign off testing, so the plan can move to `completed/` | user | Open | OI-01 |
| 003-A1 | [plan 003](plans/003_accessory_model_matching.md) | Notebook cells for plans 001, 002, 003; added only while the notebook is closed | Claude | Open | OI-02 |
| 003-D18 | [plan 003](plans/003_accessory_model_matching.md) | Should accessory lookup misses be warnings instead of errors? **No: they stay errors** (missing data that needs action; a warning may need none). They don't stop the run; unresolved ones go to the review file | user | Closed 2026-11-03 | OI-09 |
| 003-T | [plan 003](plans/003_accessory_model_matching.md) | Sign off testing, so the plan can move to `completed/` | user | Open | OI-01 |
| 005-D4 – 005-D12 | [idea 005](ideas/005_pipeline_report_card_design.md) | Decisions for the run report (parked 2026-11-03: kept for later) | user | Open | OI-11 (R4–R12) |
| 005-U1 | [idea 005](ideas/005_pipeline_report_card_design.md) | `db/review/accessory_review.csv` was overwritten outside the pipeline on 2026-10-28 at 09:04 (13 bare match keys instead of 467 rows). Rebuilt by the plan 009 real run (241 rows); the overwritten version was copied to the session scratchpad first (`accessory_review_overwritten_0904.csv`) | user | Closed 2026-10-28 | OI-14 |
| 006-T | [plan 006](plans/006_labor_time_units.md) | Sign off testing, so the plan can move to `completed/` | user | Open | OI-01 |
| 007-T | [plan 007](plans/007_comment_text_cleaning.md) | Sign off testing, so the plan can move to `completed/` | user | Open | OI-01 |
| 008-T | [plan 008](plans/008_part_number_integrity.md) | Sign off testing, so the plan can move to `completed/` | user | Open | OI-01 |
| 009-D1 – 009-D8 | [idea 009](ideas/009_human_verified_vehicle_facts_design.md) | Decisions for human-verified vehicle facts | user | Closed 2026-10-28 | OI-10 (V1–V8) |
| 009-T | [plan 009](plans/009_human_verified_vehicle_facts.md) | Sign off testing, so the plan can move to `completed/` | user | Open | OI-01 |
| 009-U1 | [plan 009](plans/009_human_verified_vehicle_facts.md) | Name to record as `verified_by` for the Golf R 2020–2021 and Arteon 2022–2023 entries: **P.M** | user | Closed 2026-10-28 | OI-12 |
| 010-T | [plan 010](plans/010_work_process_and_tracking.md) | Sign off testing, so the plan can move to `completed/` | user | Open | OI-01 |
| 011-D1 – 011-D10 | [idea 011](ideas/011_requirements_and_documentation_design.md) | Decisions for the requirements register and documentation standard | user | Open | OI-13 (DOC-1 – DOC-10) |
| 012-D4 – 012-D6 | [plan 012](plans/012_final_export_columns.md) | Final export column names: `hours` lowercase, keep `columns:`, Excel file only | user | Closed 2026-10-29 | OI-15 (E4–E6) |
| 012-T | [plan 012](plans/012_final_export_columns.md) | Sign off testing, so the plan can move to `completed/` | user | Open | OI-01 |
| 013-D1 – 013-D7 | [idea 013](ideas/013_labour_time_units_to_hours_design.md) | Decisions for labour time units to hours (new `labor_hours` column) | user | Closed 2026-11-02 | OI-16 (H1–H7) |
| 013-P | [plan 013](plans/013_labour_time_units_to_hours.md) | Approve plan 013 (labour time ÷ 100 into `labor_hours`) | user | Closed 2026-11-02 | OI-17 |
| 013-T | [plan 013](plans/013_labour_time_units_to_hours.md) | Sign off testing, so the plan can move to `completed/` | user | Open | OI-01 |
| 014-D1 – 014-D7 | [idea 014](ideas/014_labour_below_one_correction_design.md) | Decisions for correcting labour values below 1 (× 100) | user | Closed 2026-11-03 | OI-18 (B1–B7) |
| 014-P | [plan 014](plans/014_labour_below_one_correction.md) | Approve plan 014 (labour values below 1 corrected × 100) | user | Closed 2026-11-03 | OI-19 |
| 014-T | [plan 014](plans/014_labour_below_one_correction.md) | Sign off testing, so the plan can move to `completed/` | user | Open | OI-01 |
| 015-D1 – 015-D8 | [idea 015](ideas/015_doc_numbered_item_ids_design.md) | Decisions for numbering pending items by their doc | user | Closed 2026-11-03 | OI-20 (N1–N8) |
| 015-P | [plan 015](plans/015_doc_numbered_item_ids.md) | Approve plan 015 (items renamed by doc; kind `P` added) | user | Closed 2026-11-03 | OI-21 |
| 015-T | [plan 015](plans/015_doc_numbered_item_ids.md) | Sign off testing, so the plan can move to `completed/` | user | Open | — |
| DI03-S1 | [DI-03](data_issues.md#di-03), [plan 008](plans/008_part_number_integrity.md) | Export `stockCode` as text, so leading zeros aren't lost. Not asked: the pipeline restores the full number from `make&model` every run (idea 008) | data source | Closed 2026-11-03 | OI-07 |
| DI05-S1 | [DI-05](data_issues.md#di-05) | Part-years with no vehicle. Not asked as a standing question: each run applies the configured checks (window, `verified:` never offered); whatever is still unresolved goes to the review file for the user to check with the source or the vehicle config | data source | Closed 2026-11-03 | OI-04 |
| DI06-S1 | [DI-06](data_issues.md#di-06) | No accessory parts for model year 2027. Not asked as a standing question: each run lists the vehicles with no parts (`ACCESS_COVER_VEHICLE_NO_PARTS`) in the review file, and the user checks with the source from there | data source | Closed 2026-11-03 | OI-05 |
| DI07-S1 | [DI-07](data_issues.md#di-07) | Labour time 0.4 on `3QF601025KAX1`: what is the right value? | data source | Closed 2026-11-03 (corrected by rule, idea 014: read as hours → 40; the source is asked to fix the file) | OI-06 |
| DI16-S1 | [DI-16](data_issues.md#di-16) | "ReferAlways install": what the "Refer..." sentence should say (optional; text left as it is) | data source | Open | OI-08 |

## Adding or closing an item

- **Add:** the ID is the doc's number (or `DInn`), the kind letter and the next free number for that doc and kind (`003-A2`). Testing sign-off and plan approval have no number: one per plan (`013-T`, `013-P`). Fill every column, and name the ID in the doc's `Next:` line (or its Decisions table). Never create an `OI-NN`.
- **Close:** set the status to `Closed YYYY-MM-DD` and keep the row. If the answer changes a doc, update the doc in the same change.
- Never renumber, and never reuse an ID. Rows stay sorted by ID.
