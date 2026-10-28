# VW Changelog

What shipped, newest first: one entry per build or completion, with the plan numbers and the commit. Status and next actions are in [planning/README.md](planning/README.md#index).

## 2026-10-28 — Accessories from model year 2024 (plan 003 config)

- `pipeline.yaml`: a dataset can narrow the shared year window. `datasets.accessories.min_model_year: 2024`; the vehicle ingest keeps 2020+. A dataset window outside the shared one is a `CONFG_VALUE_INVALID` error.
- Coverage checks only vehicle years inside the accessory window, so 2020–2023 vehicles aren't flagged as having no parts.
- Verified facts entirely outside the window are logged as `OUTSIDE WINDOW`, not flagged unused.
- Today's data: unique accessory rows 1,357 -> 1,028, keys 71 -> 29, lookup errors 3 -> 2, review rows 241 -> 109, export 14 -> 10 sheets.

## 2026-10-28 — Human-verified vehicle facts (plan 009) · `05acbae`

- New `verified:` section in `config/vehicles/<model>.yaml`: `never_offered` years or options, and `no_parts_expected` until a date. Each entry needs a reason, `verified_by` and `verified_on`, and is validated at load.
- New final `verify` step in both pipelines:
  - a flag a fact covers exactly drops to info, keeping its original severity, and leaves the review file;
  - contradictions become errors (`ACCESS_VERIFY_CONTRADICTED`, `VEH_VERIFY_CONTRADICTED`);
  - unused facts are reported, and expired facts bring their flags back.
- New `db/dq/verified_flags.csv` and `db/definitions/dim_verified.csv`. Flags gain `model`, `submodel`, `original_severity` and `verified_entry`.
- First facts (P.M, 2026-10-28): Golf R never offered 2020–2021, Arteon never offered 2022–2023. Accessory lookup errors go from 7 to 3, and review rows from 467 to 241.

## 2026-10-28 — Work process, tracking and indexing (plan 010) · `18a80bf`

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
