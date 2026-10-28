# 002 — Pipeline Logging: Plan

**Status:** Built — in user testing (2026-10-26)
**Updated:** 2026-10-26
**Next:** user signs off testing (OI-01); notebook cell (OI-02)
**Links:** idea [002](../ideas/002_pipeline_logging_design.md) · built before plan [001](001_vw_model_ingest_mvp.md) Phase 1
**Summary:** Logging helpers wired into every step: run log, steps.csv, change log, flag log, run summary and retention.
**Order:** built **before** [plan 001](001_vw_model_ingest_mvp.md) Phase 1, so every ingest phase logs from day one.

## Outcome

Every step of the VW pipeline records what ran (with which settings), the counts in and out, each value it changed (before → after, with the rule), and every flag, in four places:

- `db/logs/runs/<run_id>.log`: readable run story
- `db/logs/steps.csv`: one row per step, every run
- `db/logs/changes/<run_id>.csv`: before → after per value
- `db/logs/flags/<run_id>.csv`: warnings and errors per row

**Success criteria**

- [x] Every step in `run_ingest.py` goes through `run_step`, so none can run without logging.
- [x] For any value in `vehicles.csv`, the change log shows which step and which rule produced it.
- [x] Every row excluded or flagged appears in the change or flag log with a reason; staged = final + excluded reconciles in `steps.csv`.
- [x] A failing step leaves a `FATAL` line with the step and reason, and a `failed` row in `steps.csv`.
- [x] Running twice with no data or config change gives a `write` step with 0 rows added / removed / changed.

---

## Phase L1 — Logging helpers

- [x] `pipeline/logging_helpers.py`: `start_run`, `end_run`, `run_step`, `log_change`, `log_excluded`, `log_flag`, `diff_frames` (signatures in the idea doc).
- [x] stdlib `logging` setup: file at DEBUG, console at INFO, format `[time] [LEVEL] [step] EVENT | key=value`, same as `accy_v2`.
- [x] `ctx=None` mode: helpers work from the notebook without creating log files.
- [x] Add the `logging:` block to `config/pipeline.yaml` (levels, `examples_per_rule`, `keep_runs`), validated by `load_settings()`.
- [x] Add `db/logs/` to `.gitignore`.

**Done when:** a dummy two-step run produces all four outputs, and `diff_frames` has unit tests (changed value, added value, removed value, excluded row, no change).

## Phase L2 — Wire into the ingest (alongside plan 001)

Each plan-001 phase calls its steps through `run_step` and adds the explicit logging below:

- [x] **Config (001 Phase 1):** log counts per config file; config errors → `FATAL` + stop.
- [x] **Ingest + staging (001 Phase 2):** log source file details and dropped columns; duplicate key → `FATAL`.
- [x] **Year window (001 Phase 2):** `log_excluded` for each row outside the window, with the reason (e.g. `2019 < min_model_year 2020`).
- [x] **Clean (001 Phase 3):** one change row per description changed, with the rule (`alias`, `remove_repeated_words`) and what was removed or replaced.
- [x] **Parse (001 Phase 3):** `log_change` for every filled field, naming the keyword or phrase that filled it; `log_flag` for `unknown_token` and `single_value_conflict`.
- [x] **Validate (001 Phases 4–5):** `log_flag` for `not_offered`, `no_option_set`, `inconsistent_model_number` (WARNING, never stops, D17).
- [x] **Write (001 Phase 6):** compare against the previous `vehicles.csv` and log rows added / removed / changed.

**Done when:** a full run on today's data has 269 vehicles with every value traceable in the change log, 54 excluded rows logged with reasons, and `RM1VPJ` flagged.

## Phase L3 — Run summary + retention

- [x] `end_run` writes the `db/dq/ingest_runs.csv` row from the step and flag logs (one source of truth for counts).
- [x] Build `db/review/review_queue.csv` from the latest flag log (warnings only).
- [x] Retention: keep the last `keep_runs` per-run files; never prune `steps.csv` or `ingest_runs.csv`.
- [ ] Notebook cell: load the latest change and flag logs for a quick look.

**Done when:** after 31 runs only 30 per-run files remain, and `steps.csv` still has every run.

---

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-10-26 | Logging on every pipeline step, with before → after and conditions | User request |
| 2026-10-26 | Built before plan 001 Phase 1 | Every phase logs from the start, instead of bolting logging on later |
| 2026-10-26 | L1–L6 accepted as recommended | User: "looks good, let's build it" |
| 2026-10-26 | Per-row flag lines go to the run log file only; the console shows one summary line per rule | Keeps the terminal readable when a run has many flags |
| 2026-10-26 | Run ids get a `_2` suffix when two runs start in the same second | Otherwise the second run would overwrite the first one's logs |
| 2026-10-26 | Review queue includes errors as well as warnings | Errors need a person's eye too |

## Risks

| Risk | Mitigation |
|---|---|
| A step is added without logging | `run_ingest.py` only calls steps through `run_step`; a test checks every step name appears in `steps.csv` |
| Logs grow without limit | Per-run files pruned to `keep_runs`; `steps.csv` is one small row per step |
| Diffs are slow on big inputs | Diff only `watch_cols`; today's data is 323 rows. Revisit if a source gets much bigger |
