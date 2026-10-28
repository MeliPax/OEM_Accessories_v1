# 002 — Pipeline Logging: Design

**Status:** Idea — approved (L1–L6, 2026-10-26)
**Updated:** 2026-10-26
**Next:** completed with plan 002 once testing is signed off (OI-01)
**Links:** plan [002](../plans/002_pipeline_logging.md) · used by plan [001](../plans/001_vw_model_ingest_mvp.md)
**Summary:** Every pipeline step logs what ran, rows in and out, each value changed (before → after) and every flag.

## Goal

Every activity in the pipeline leaves a record that answers four questions:

1. **What ran?** Which step, in which run, with which settings and conditions.
2. **What went in and what came out?** Row counts in, out, changed and excluded.
3. **What changed, exactly?** For each affected row, the value before, the value after, and the rule that changed it.
4. **What looks wrong?** Every flag, its severity, and the row it applies to.

Logs must be readable by a person scrolling a file, and filterable in pandas or Excel.

## What exists today in `accy_v2`

| Piece | What it does | Reuse? |
|---|---|---|
| `core/helpers/pipeline_logger.py` (`PipelineLogger`) | stdlib `logging`, file + console, `EVENT \| key=value` messages | **Reuse the message style**, not the class |
| `core/helpers/dq_logger.py` (`DQLogger`) | Collects data-quality warnings, writes a JSON report | **Reuse the idea** (flags as structured records); write CSV instead of JSON so it opens in Excel |
| `model_lookup/logging_config.py` | Console at INFO, file at DEBUG, `[time] [LEVEL] [component]` format | **Reuse the levels and format** |

VW stays consistent with the rest of the repo, while keeping the plain-functions approach agreed for this MVP (no classes).

## Design: one run, four outputs

Every run gets a `run_id` (local timestamp, e.g. `20261026_142530`). Everything it writes carries that ID.

```
db/logs/
├── runs/
│   └── 20261026_142530.log          1. Run log: the readable story of the run
├── steps.csv                        2. Step log: one row per step, appended every run
├── changes/
│   └── 20261026_142530.csv          3. Change log: one row per value changed (before → after)
└── flags/
    └── 20261026_142530.csv          4. Flag log: one row per warning or error on a row
```

`db/dq/ingest_runs.csv` (plan 001, Phase 4) stays as the one-row-per-run summary. The run log, step log and flag log are where its numbers come from.

### 1. Run log (`runs/<run_id>.log`): the readable story

Plain text, same format as `accy_v2`: `[time] [LEVEL] [step] EVENT | key=value | ...`. The console shows INFO and above; the file keeps DEBUG too.

```
[2026-10-26 14:25:30] [INFO   ] [run]        RUN START | run_id=20261026_142530 | source=datasets/vw_models_data.csv | min_model_year=2020 | max_model_year=None
[2026-10-26 14:25:30] [INFO   ] [config]     STEP START | files=pipeline.yaml, categories.yaml, models.yaml, keywords.yaml, vehicles/*.yaml (10)
[2026-10-26 14:25:30] [INFO   ] [config]     STEP END | status=ok | categories=14 | models=10 | keywords=41 | option_sets=42 | 0.08s
[2026-10-26 14:25:30] [INFO   ] [ingest]     STEP START | file=datasets/vw_models_data.csv
[2026-10-26 14:25:30] [INFO   ] [ingest]     STEP END | status=ok | rows_in=323 | rows_out=323 | dropped_empty_columns=21 | 0.05s
[2026-10-26 14:25:30] [INFO   ] [year_window] STEP START | rule=single_year | column=model_year | window=2020..(no max)
[2026-10-26 14:25:30] [INFO   ] [year_window] STEP END | status=ok | rows_in=323 | rows_out=269 | excluded=54 | excluded_years=2019 | 0.01s
[2026-10-26 14:25:30] [INFO   ] [clean]      STEP START | rules=aliases(1), trim_spaces, remove_repeated_words
[2026-10-26 14:25:30] [INFO   ] [clean]      CHANGED | rule=alias | count=25 | e.g. "Atlas Sport Cross Trendline 2.0 TSI 4MOTION" -> "Atlas Cross Sport Trendline 2.0 TSI 4MOTION"
[2026-10-26 14:25:30] [INFO   ] [clean]      CHANGED | rule=remove_repeated_words | count=… | e.g. "Golf R Golf R Black" -> "Golf R Black"
[2026-10-26 14:25:30] [INFO   ] [clean]      STEP END | status=ok | rows_in=269 | rows_out=269 | rows_changed=… | 0.02s
[2026-10-26 14:25:30] [DEBUG  ] [parse]      MATCH | vehicle=VW-2027-RM1VPJ | phrase "Black Edition" -> special_edition=Black Edition
[2026-10-26 14:25:30] [WARNING] [validate]   FLAG | rule=inconsistent_model_number | vehicle=VW-2025-RM1VPJ | detail=2025-2026 "R-Line Black", 2027 "R-Line Black Edition"
[2026-10-26 14:25:31] [INFO   ] [run]        RUN END | status=ok_with_warnings | rows_final=269 | parsed_complete=100.0% | flags: warning=… error=0 | 0.6s
```

*(Illustrative: counts such as `keywords=41` and `…` are filled in by the real run.)*

**Levels**

| Level | Used for | Example |
|---|---|---|
| `DEBUG` | Per-row detail: each keyword match, each value change | `MATCH \| phrase "Black Edition" -> special_edition` |
| `INFO` | Step start / end, counts, settings, a few before → after examples | `STEP END \| rows_in=323 \| rows_out=269` |
| `WARNING` | Data flags; the run continues (D17) | `FLAG \| rule=not_offered` |
| `ERROR` | A problem that stops the run (broken config, duplicate key) | `FATAL \| step=config \| reason=keyword "Black" defined twice` |

### 2. Step log (`steps.csv`): one row per step, every run

Appended, never overwritten, so runs can be compared over time.

| Column | Example |
|---|---|
| `run_id` | `20261026_142530` |
| `step_order` | `4` |
| `step` | `year_window` |
| `started_at`, `duration_s` | `2026-10-26 14:25:30`, `0.01` |
| `rows_in`, `rows_out` | `323`, `269` |
| `rows_changed`, `rows_excluded` | `0`, `54` |
| `conditions` | `rule=single_year; column=model_year; min=2020; max=None` |
| `status` | `ok` / `ok_with_warnings` / `failed` |
| `message` | `excluded_years=2019` |

`conditions` records **the settings and rules the step ran with**, so any output can be traced back to the config that produced it.

### 3. Change log (`changes/<run_id>.csv`): before and after

One row per value that a step changed, added or removed:

| run_id | step | vehicle_id | model_number | model_year | field | before | after | rule | detail |
|---|---|---|---|---|---|---|---|---|---|
| 20261026_142530 | clean | VW-2020-CMC2NR | CMC2NR | 2020 | description | Atlas Sport Cross Trendline 2.0 TSI 4MOTION | Atlas Cross Sport Trendline 2.0 TSI 4MOTION | alias | Atlas Sport Cross → Atlas Cross Sport |
| 20261026_142530 | clean | VW-2025-DA1BPT | DA1BPT | 2025 | description | Golf R Golf R Black | Golf R Black | remove_repeated_words | removed: Golf, R |
| 20261026_142530 | parse | VW-2025-DA1BPT | DA1BPT | 2025 | submodel | | R | model_phrase | "Golf R" |
| 20261026_142530 | parse | VW-2025-DA1BPT | DA1BPT | 2025 | appearance_package | | Black | keyword_word | "Black" |
| 20261026_142530 | parse | VW-2023-E813MN | E813MN | 2023 | battery_supplier | | SK On | keyword_phrase | "w/SK On Battery" |
| 20261026_142530 | year_window | VW-2019-5C2CP6 | 5C2CP6 | 2019 | *(row)* | kept | excluded | year_window | 2019 < min_model_year 2020 |

- **Why `before` is often empty in parse:** parsing fills new columns, so the change is "nothing → value". The `rule` and `detail` columns say which keyword or phrase produced the value. That's the "what really happened" part.
- **Excluded rows** are logged as a row-level change (`kept → excluded`) with the reason, so nothing disappears silently.
- **Size:** about 269 vehicles × ~5 values ≈ 1,500 rows per run. Small enough to keep every run in full.

### 4. Flag log (`flags/<run_id>.csv`): what looks wrong

One row per flag. Same columns as the plan-001 issue list: `run_id, step, vehicle_id, model_number, model_year, rule, severity, category, value, detail`.

The review queue (`db/review/review_queue.csv`) is built **from** this file (warnings only, latest run), so there's one source for flags.

## How steps log: plain helpers in `pipeline/logging_helpers.py`

The run context is a plain dict (run id, paths, logger, in-memory change and flag rows), passed from step to step. No classes.

| Function | What it does |
|---|---|
| `start_run(settings, source_file)` | Creates the `run_id` and folders, sets up stdlib logging (file DEBUG, console INFO), logs `RUN START` with the settings. Returns the context dict. |
| `run_step(ctx, step, func, df, conditions, key_cols, watch_cols)` | **The standard wrapper.** Logs `STEP START` with conditions, runs `func(df)`, compares before and after on `watch_cols`, records every changed value in the change log, logs `STEP END` with counts and duration, appends to `steps.csv`. If `func` raises, logs `FATAL` and re-raises. |
| `log_change(ctx, step, row_key, field, before, after, rule, detail)` | For a step to record *why* a value changed (e.g. which keyword matched), where a plain before/after diff can't tell. |
| `log_excluded(ctx, step, df_excluded, reason)` | Records rows a step dropped, with the reason. |
| `log_flag(ctx, step, row_key, rule, severity, category, value, detail)` | Records a flag; logs it at WARNING or ERROR. |
| `diff_frames(before, after, key_cols, watch_cols)` | Returns the changed cells as rows (used by `run_step`, testable on its own). |
| `end_run(ctx, status)` | Writes the change and flag CSVs, logs `RUN END` with totals, applies retention. |

**What a step looks like with this:**

```python
ctx = start_run(settings, source_file)
staged = run_step(ctx, "ingest", read_and_stage, None, conditions={"file": source_file}, ...)
kept = run_step(ctx, "year_window", lambda df: filter_by_year_window(df, settings, "vw_models", ctx),
                staged, conditions=settings["window"], key_cols=KEY, watch_cols=[])
cleaned = run_step(ctx, "clean", clean_descriptions, kept,
                   conditions={"aliases": 1}, key_cols=KEY, watch_cols=["description"])
...
end_run(ctx, status="ok_with_warnings")
```

Helpers stay usable from the notebook: when `ctx` is `None`, logging calls do nothing beyond a console message, so exploring doesn't create log files.

## What each step logs

| Step | Conditions logged | Before → after captured | Flags |
|---|---|---|---|
| `config` | file list, counts per file, taxonomy version | — | config errors (`ERROR`, stops) |
| `ingest` | source path, file size, modified time | columns dropped as all-empty | missing required column (`ERROR`) |
| `staging` | column renames | — | duplicate `(model_number, model_year)` (`ERROR`, stops) |
| `year_window` | rule, column, min, max | each excluded row + reason | window removes every row (`WARNING`) |
| `clean` | aliases used, cleaning rules | description before → after, per rule | — |
| `parse` | keyword count, phrase count | each filled field + the keyword or phrase that filled it | `unknown_token`, `single_value_conflict` |
| `validate` | option sets loaded, rules run | — | `not_offered`, `no_option_set`, `inconsistent_model_number` (all `WARNING`, D16 / D17) |
| `write` | output paths, row counts | rows added / removed / changed vs. the previous `vehicles.csv` | — |

The **`write` step compares against the previous run's `vehicles.csv`**, so each run's change log also answers "what changed in the vehicle DB since last time?". That's the check you'll rely on when new vehicles are added.

## Settings (`config/pipeline.yaml`)

```yaml
logging:
  console_level: INFO
  file_level: DEBUG
  examples_per_rule: 3       # before -> after examples printed per rule at INFO
  keep_runs: 30              # per-run files kept in runs/, changes/, flags/; steps.csv is never pruned
```

## Decisions

| ID | Question | Recommendation |
|---|---|---|
| L1 | Four outputs (run log, step log, change log, flag log) as above? | Yes |
| L2 | Plain helper functions plus a context dict, reusing the `accy_v2` message format, rather than reusing the `PipelineLogger` / `DQLogger` classes? | Yes, matches the no-classes MVP rule |
| L3 | CSV for structured logs (not JSON like `DQLogger`)? | Yes, opens in Excel, loads with `pd.read_csv` |
| L4 | Keep the last 30 runs of per-run files; `steps.csv` kept forever? | Yes |
| L5 | `db/logs/` is git-ignored (logs are run output, not source)? | Yes |
| L6 | Change log captures **every** changed value (not just samples)? | Yes, about 1,500 rows per run is small |
