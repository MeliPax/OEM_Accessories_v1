# VW Planning

Planning workspace for the VW data work: ideas, plans, completion records, data issues and open items. The rules agents follow are in [../CLAUDE.md](../CLAUDE.md), which loads automatically for VW work.

**To see what has been worked on and what comes next, read the [Index](#index) below and [open_items.md](open_items.md).** You don't need to open the docs themselves.

```
planning/
├── ideas/          Design: what was asked, what the data shows, options, decisions. Approved before planning.
├── plans/          Approved work: outcome, success criteria, phases and tasks, tests, decision log, risks.
├── completed/      Plans the user signed off, with Completion notes. The idea stays in ideas/ (status Completed).
├── open_items.md   Every follow-up and open question (OI-NN), with an owner.
└── data_issues.md  Data issues in the VW source files (DI-NN, DV-NN), and the data definitions.
```

## Lifecycle: four stages, three approval gates

```
Idea ──(user approves the decisions)──► Plan ──(user approves the plan)──► Build ──(user signs off testing)──► Completed
```

| Stage | Status words (fixed) | Lives in | Leaves the stage when |
|---|---|---|---|
| Idea | `Seed` · `Idea — waiting for decisions` · `Idea — approved` | `ideas/NNN_*_design.md` | the user approves every decision |
| Plan | `Plan — waiting for approval` · `Plan — approved` | `plans/NNN_*.md` | the user approves the plan |
| Build | `Building` · `Built — in user testing` | `plans/NNN_*.md` | tests and real runs pass, and the user signs off |
| Completed | `Completed` (the idea and the plan) | the plan moves to `completed/` | — |
| — | `Dropped` (with the reason) | where it is | — |

A date or detail may follow in brackets, e.g. `Idea — approved (V1–V8, 2026-10-28)`. At completion the plan gets a `## Completion notes` section: what shipped, where it lives, tests and real-run numbers, follow-ups.

**Resuming interrupted work:** a `Building` plan carries a `**Checkpoint:**` line (where it stopped, what's done, what's in progress, which files). The next session reads it, checks `git status` and the tests, and continues from the first unticked task.

## The header every idea and plan starts with

```markdown
# NNN — Title: Design | Plan

**Status:** one of the fixed status words
**Checkpoint:** (Building plans only) where the work stopped
**Updated:** YYYY-MM-DD
**Next:** the next action and who owns it (OI-NN)
**Links:** the idea, plan, dependencies, data issues
**Summary:** one sentence: what this is
```

`grep -m1 "^\*\*Status:" planning/*/*.md` gives the status of every doc. `tests/test_planning_docs.py` checks the headers, this index and the open items stay in step.

## Naming

- `NNN_` is a 3-digit number shared by an idea, its plan and its completion record (`009_human_verified_vehicle_facts_design.md` → `009_human_verified_vehicle_facts.md`). Take the next free number from the index.
- Lowercase `snake_case` after the number.

## Where each fact is tracked

| What | Where |
|---|---|
| Stage, next action, last update of every idea and plan | The doc's header, mirrored in the [Index](#index) |
| Decisions before the build | The idea's *Decisions* table |
| Tasks, progress, deviations | The plan's checkboxes and *Decision log* |
| Follow-ups and open questions | [open_items.md](open_items.md) |
| Data issues | [data_issues.md](data_issues.md) |
| What shipped, and when | [../CHANGELOG.md](../CHANGELOG.md) |
| Today's run numbers | [Baseline](#baseline) below |
| Flag codes and their wording | `config/messages.yaml` |

Write a fact in its home and link to it from elsewhere; copies go stale.

## Baseline

Real runs on 2026-10-28 (accessory file 2026-10-20, vehicle export `vw_models_data.csv`). Update after each build's real run.

| Measure | Value |
|---|---|
| Vehicles in `vehicles.csv` | 269 (54 rows excluded by the year window) |
| Year windows | Vehicles 2020+ (`datasets.vw_models`); accessories `current_year - 2` = 2024+ (`datasets.accessories`), and the accessory run reads only vehicles 2024+ (111 of 269; 158 ignored) |
| Accessory rows: read / in window / unique (part, model) | 24,396 / 9,675 / 1,028 (13,051 / 1,357 at 2020+) |
| Lookup keys: total / found / missed / verified | 29 / 27 / 2 / 0 (2 errors: ID.4, ID. Buzz 2026); 71 / 64 / 7 / 4 at 2020+ |
| Dict rows / exported rows / export sheets | 9,481 / 9,388 / 10 (25,796 / 25,345 / 14 at 2020+) |
| Vehicles with no parts | 14 (model year 2027) |
| Accessory review rows | 109 (241 at 2020+) |
| Part numbers restored / unproven | 151 / 0 (rows inside the window only; 704 across the whole file before) |
| Tests | 284 passing |

## Index

| # | Doc | Stage | Next | Updated |
|---|---|---|---|---|
| 001 | [VW Model Ingest: Design Ideas](ideas/001_vw_model_ingest_design.md) | Idea — approved | completed with plan 001 once testing is signed off (OI-01) | 2026-10-26 |
| 001 | [VW Model Ingest MVP: Plan](plans/001_vw_model_ingest_mvp.md) | Built — in user testing | user signs off testing (OI-01); review config/vehicles (OI-03); notebook cell (OI-02) | 2026-10-26 |
| 002 | [Pipeline Logging: Design](ideas/002_pipeline_logging_design.md) | Idea — approved | completed with plan 002 once testing is signed off (OI-01) | 2026-10-26 |
| 002 | [Pipeline Logging: Plan](plans/002_pipeline_logging.md) | Built — in user testing | user signs off testing (OI-01); notebook cell (OI-02) | 2026-10-26 |
| 003 | [Accessory Ingest + Model Number Matching: Design](ideas/003_accessory_model_matching_design.md) | Idea — approved | completed with plan 003 once testing is signed off (OI-01) | 2026-10-27 |
| 003 | [Accessory Ingest + Model Number Matching: Plan](plans/003_accessory_model_matching.md) | Built — in user testing | user signs off testing (OI-01); notebook cell (OI-02); lookup misses as warnings? (OI-09) | 2026-10-27 |
| 004 | [Error and Flag Messages: Design](ideas/004_error_message_catalogue_design.md) | Idea — approved | completed with plan 003 once testing is signed off (OI-01) | 2026-10-27 |
| 005 | [Pipeline Run Report: Design](ideas/005_pipeline_report_card_design.md) | Idea — waiting for decisions | user decides R4–R12 (OI-11) | 2026-10-28 |
| 006 | [Labour Time Units (minutes → hours): Design](ideas/006_labor_time_units_design.md) | Idea — approved | completed with plan 006 once testing is signed off (OI-01) | 2026-10-28 |
| 006 | [Labour Time Units (minutes → hours): Plan](plans/006_labor_time_units.md) | Built — in user testing | user signs off testing (OI-01); confirm the 0.4 value with the source (OI-06) | 2026-10-28 |
| 007 | [Comment Text Cleaning: Design](ideas/007_comment_text_cleaning_design.md) | Idea — approved | completed with plan 007 once testing is signed off (OI-01) | 2026-10-28 |
| 007 | [Comment Text Cleaning: Plan](plans/007_comment_text_cleaning.md) | Built — in user testing | user signs off testing (OI-01) | 2026-10-28 |
| 008 | [Part Numbers Kept Exactly as the Source: Design](ideas/008_part_number_integrity_design.md) | Idea — approved | completed with plan 008 once testing is signed off (OI-01) | 2026-10-27 |
| 008 | [Part Numbers Kept Exactly as the Source: Plan](plans/008_part_number_integrity.md) | Built — in user testing | user signs off testing (OI-01); ask the source to export stockCode as text (OI-07) | 2026-10-28 |
| 009 | [Human-Verified Vehicle Facts: Design](ideas/009_human_verified_vehicle_facts_design.md) | Idea — approved | build plan 009 | 2026-10-28 |
| 009 | [Human-Verified Vehicle Facts: Plan](plans/009_human_verified_vehicle_facts.md) | Built — in user testing | user signs off testing (OI-01) | 2026-10-28 |
| 010 | [Work Process, Tracking and Indexing: Design](ideas/010_work_process_and_tracking_design.md) | Idea — approved | build plan 010 | 2026-10-28 |
| 010 | [Work Process, Tracking and Indexing: Plan](plans/010_work_process_and_tracking.md) | Built — in user testing | user signs off testing (OI-01); idea 011 extends the checks once approved (OI-13) | 2026-10-28 |
| 011 | [Requirements Register and Documentation Standard: Design](ideas/011_requirements_and_documentation_design.md) | Idea — waiting for decisions | user decides DOC-1 to DOC-10 (OI-13) | 2026-10-28 |
