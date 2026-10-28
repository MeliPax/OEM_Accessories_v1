# VW Open Items

**Purpose:** every follow-up and open question across the VW work, in one list, each with an owner. Ideas and plans refer to these by `OI-NN` instead of keeping their own lists.
**Last updated:** 2026-10-28

**Owners:** `user` (decide or sign off) · `data source` (VW data) · `agent` (work to do)
**Status:** `Open` · `Waiting` (asked; waiting for an answer) · `Closed YYYY-MM-DD` (the row is kept)

| OI | Item | Owner | Linked | Status |
|---|---|---|---|---|
| OI-01 | Sign off testing of plans 001, 002, 003, 006, 007, 008, 009, 010, so they can move to `completed/` | user | [plans](README.md#index) | Open |
| OI-02 | Notebook cells for plans 001, 002, 003; added only while the notebook is closed | agent | [plan 003](plans/003_accessory_model_matching.md) | Open |
| OI-03 | Review `config/vehicles/*.yaml`: all 10 are `drafted`; set `reviewed` with who and when | user | [plan 001](plans/001_vw_model_ingest_mvp.md) | Open |
| OI-04 | Atlas 2020, ID.4 2026, ID. Buzz 2026: parts listed, no vehicle in the export. Missing vehicles or wrong year ranges? (Golf R and Arteon: verified never offered, plan 009) | data source | [DI-05](data_issues.md#di-05) | Open |
| OI-05 | No accessory parts for model year 2027 (14 vehicles) | data source | [DI-06](data_issues.md#di-06) | Open |
| OI-06 | Labour time 0.4 on `3QF601025KAX1`: minutes or hours? | data source | [DI-07](data_issues.md#di-07) | Open |
| OI-07 | Export `stockCode` as text, so leading zeros aren't lost | data source | [DI-03](data_issues.md#di-03), [plan 008](plans/008_part_number_integrity.md) | Open |
| OI-08 | "ReferAlways install": what the "Refer..." sentence should say (optional; text left as it is) | data source | [DI-16](data_issues.md#di-16) | Open |
| OI-09 | Should accessory lookup misses be warnings instead of errors? | user | [plan 003](plans/003_accessory_model_matching.md) | Open |
| OI-10 | Decisions V1–V8 for human-verified vehicle facts | user | [idea 009](ideas/009_human_verified_vehicle_facts_design.md) | Closed 2026-10-28 |
| OI-11 | Decisions R4–R12 for the run report | user | [idea 005](ideas/005_pipeline_report_card_design.md) | Open |
| OI-12 | Name to record as `verified_by` for the Golf R 2020–2021 and Arteon 2022–2023 entries: **P.M** | user | [plan 009](plans/009_human_verified_vehicle_facts.md) | Closed 2026-10-28 |
| OI-13 | Decisions DOC-1 to DOC-10 for the requirements register and documentation standard | user | [idea 011](ideas/011_requirements_and_documentation_design.md) | Open |
| OI-14 | `db/review/accessory_review.csv` was overwritten outside the pipeline on 2026-10-28 at 09:04 (13 bare match keys instead of 467 rows). Rebuilt by the plan 009 real run (241 rows); the overwritten version was copied to the session scratchpad first (`accessory_review_overwritten_0904.csv`) | user | [idea 005](ideas/005_pipeline_report_card_design.md) | Closed 2026-10-28 |

## Adding or closing an item

- **Add:** take the next number and fill every column. Link the item from the idea or plan's `Next:` line.
- **Close:** set the status to `Closed YYYY-MM-DD` and keep the row. If the answer changes a doc, update the doc in the same change.
- Never renumber, and never reuse a number.
