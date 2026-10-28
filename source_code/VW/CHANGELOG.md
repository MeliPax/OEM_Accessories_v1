# VW Changelog

What shipped, newest first: one entry per build or completion, with the plan numbers and the commit. Status and next actions are in [planning/README.md](planning/README.md#index).

## 2026-10-28 — Work process, tracking and indexing (plan 010)

- Every idea and plan opens with a fixed five-field header (`Status`, `Updated`, `Next`, `Links`, `Summary`), using fixed status words.
- The planning index gains `Next` and `Updated` columns, and the README gains a run *Baseline* table.
- New `planning/open_items.md` (OI-01 to OI-14) and this changelog.
- New `tests/test_planning_docs.py` keeps the index, the headers and the open items in step.
- `CLAUDE.md` gains the resume procedure for interrupted build work.

## 2026-10-28 — Labour hours, comment cleaning, work process rules (plans 006, 007) · `97c0229`

- Labour time converted from minutes to hours using unit definitions in config, with `labor_time_source` kept and suspect values flagged (`ACCESS_CLEAN_UNIT_SUSPECT`). The export header is `Labour Time (hours)`.
- Comments are cleaned into sentences (tags, pipes, links, spaces) by the new `clean_text` step, which runs before dedupe. `comments_source` is kept, and links no rule covers are flagged (`ACCESS_CLEAN_UNREVIEWED_LINK`).
- As-built plans 006–008. New ideas 005 (run report), 009 (verified facts) and 010 (process), and plans 009 and 010.
- `source_code/VW/CLAUDE.md`: the idea → plan → build → completed process, loaded automatically for VW work.

## 2026-10-27 — Accessory pipeline, flag messages, part numbers (plans 003, 008) · `f0e0ffa`

- The accessory pipeline produces the per-model dict and the Excel export, matching by a unique (model, submodel, year) lookup.
- Coverage and data-quality flags go to `accessory_review.csv`.
- Flag codes `CONFG_` / `VEH_` / `ACCESS_` come from `config/messages.yaml` (idea 004).
- Part numbers are proven against `make&model`: leading zeros restored only when proven, never padded, and exported as Excel text.

## 2026-10-26 — Vehicle ingest and logging (plans 001, 002) · `b068917`

- Vehicle ingest from the VW model export into `db/final/vehicles.csv` (269 vehicles), driven by YAML config: keywords, models and option sets per vehicle.
- Logging on every step: run log, `steps.csv`, change log (before → after), flag log, run summary.

## 2026-10-23 — Planning workspace and datasets · `7b42c88`, `ea1c31f`

- `planning/` with ideas and the ingest MVP plan.
- Datasets moved into `source_code/VW/datasets`.
- Keyword taxonomy guides added.
