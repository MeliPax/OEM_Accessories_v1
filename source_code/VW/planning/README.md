# VW Planning

Planning workspace for the VW data work (model ingest, taxonomy, accessory matching).

```
planning/
├── ideas/       Design options, trade-offs, open questions. Nothing here is committed to yet.
├── plans/       Approved work, broken into phases with tasks and acceptance criteria.
└── completed/   Plans (or phases) that are done, moved here with a short completion note.
```

## Lifecycle

The rules agents follow are in [../CLAUDE.md](../CLAUDE.md), which loads automatically for VW work. Each stage needs the user's approval before the next one starts.

1. **Idea** — write it in `ideas/NNN_short_name.md`. Capture the problem, options, a recommendation and open questions.
2. **Plan** — once the idea's decisions are made, create `plans/NNN_short_name.md` with phases. Link back to the idea.
3. **Execute** — tick off tasks in the plan as they land. Note deviations in the plan's *Decision log*.
4. **Complete** — when a plan (or a self-contained phase) is done, move it to `completed/`, and add a *Completion notes* section: what shipped, where it lives, test/verification results, follow-ups.

## Naming

- `NNN_` is a 3-digit sequence shared across all three folders, so an idea, its plan and its completion record keep the same number (e.g. `001_vw_model_ingest_design.md` → `001_vw_model_ingest_mvp.md`).
- Use lowercase `snake_case` after the number.

## Data issues log

[data_issues.md](data_issues.md): data issues found in the VW source files, how each is handled, what is still open, and the data boundaries and definitions. Shared with the team; add new issues there.

## Index

| # | Title | Stage |
|---|---|---|
| 001 | [VW model ingest — design ideas](ideas/001_vw_model_ingest_design.md) | Idea (all decisions made) |
| 001 | [VW model ingest — MVP plan](plans/001_vw_model_ingest_mvp.md) | Plan (built 2026-10-26; in user testing) |
| 002 | [Pipeline logging — design](ideas/002_pipeline_logging_design.md) | Idea (all decisions made) |
| 002 | [Pipeline logging — plan](plans/002_pipeline_logging.md) | Plan (built 2026-10-26; in user testing) |
| 003 | [Accessory ingest + model number matching — design](ideas/003_accessory_model_matching_design.md) | Idea (all decisions made) |
| 003 | [Accessory ingest + model number matching — plan](plans/003_accessory_model_matching.md) | Plan (built 2026-10-27; in user testing) |
| 004 | [Error and flag messages — design](ideas/004_error_message_catalogue_design.md) | Idea (all decisions made) |
| 005 | [Pipeline run report (platform manager view) — design](ideas/005_pipeline_report_card_design.md) | Idea (R1–R3 decided; waiting for R4–R12) |
| 006 | [Labour time units (minutes to hours) — design](ideas/006_labor_time_units_design.md) | Idea (all decisions made) |
| 006 | [Labour time units — plan (as built)](plans/006_labor_time_units.md) | Plan (built 2026-10-28; in user testing) |
| 007 | [Comment text cleaning — design](ideas/007_comment_text_cleaning_design.md) | Idea (all decisions made) |
| 007 | [Comment text cleaning — plan (as built)](plans/007_comment_text_cleaning.md) | Plan (built 2026-10-28; in user testing) |
| 008 | [Part numbers kept exactly as the source — design](ideas/008_part_number_integrity_design.md) | Idea (all decisions made) |
| 008 | [Part numbers kept exactly as the source — plan (as built)](plans/008_part_number_integrity.md) | Plan (built 2026-10-27; in user testing) |
| 009 | [Human-verified vehicle facts — design](ideas/009_human_verified_vehicle_facts_design.md) | Idea (approved 2026-10-28) |
| 009 | [Human-verified vehicle facts — plan](plans/009_human_verified_vehicle_facts.md) | Plan (approved 2026-10-28) |
| 010 | [Work process, tracking and indexing — design](ideas/010_work_process_and_tracking_design.md) | Idea (approved 2026-10-28) |
| 010 | [Work process, tracking and indexing — plan](plans/010_work_process_and_tracking.md) | Plan (approved 2026-10-28) |
