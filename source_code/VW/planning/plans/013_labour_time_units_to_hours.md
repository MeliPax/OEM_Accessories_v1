# 013 — Labour Time Units to Hours: Plan

**Status:** Built — in user testing (2026-11-02)
**Updated:** 2026-11-02
**Next:** user signs off testing (013-T)
**Links:** idea [013](../ideas/013_labour_time_units_to_hours_design.md) · corrects plan [006](006_labor_time_units.md) · changes the export of plans [003](003_accessory_model_matching.md) and [012](012_final_export_columns.md) · data issue [DI-07](../data_issues.md#di-07)
**Summary:** `laborTime` is read as `labor_time_source` (time units, 100 = 1 hour) and converted in `clean` to a new `labor_hours` column, which the DQ rules, dict and export use; `labor_time` is removed.

## Outcome

The accessory export's `Hours` column shows `laborTime ÷ 100` (300 → 3.00, 25 → 0.25). The ingest value stays in the dict as `labor_time_source` for tracing and is never exported. Nothing downstream reads a column named `labor_time`.

```
laborTime ─stage─► labor_time_source (time units) ─clean: ÷100, 2 dp─► labor_hours (hours) ─► DQ, dict, export "Hours"
```

**Success criteria (real run, accessory file 2026-10-20)**

- [x] Run log: `UNITS labor_time_source: time_units -> hours x 0.01, 2 decimals`.
- [x] Export `Hours` matches `labor_time_source / 100` on every row: 0 → 0, 10 → 0.10, 25 → 0.25, 30 → 0.30, 40 → 0.40, 50 → 0.50, 100 → 1.00, 250 → 2.50.
- [x] `3QF601025KAX1` (0.4): `ACCESS_CLEAN_UNIT_SUSPECT` once per part and value, `Hours` **empty** in the export, a `type = value` row in `accessory_review.csv`; no `not_null` flag for the same value (H5).
- [x] No column named `labor_time` in the dict, the review file or the code (`grep -rn "'labor_time'" pipeline tests` finds nothing).
- [x] Export headers unchanged (plan 012): `Part, ModelName, Description, Price, Hours, Comments, Variant, Year, Model`.
- [x] Full test suite passes; `run_ingest.py` and `run_accessories.py` complete.

## Phase H1 — Config and validation

- [x] `config/accessories.yaml`:
  - `columns: laborTime: { name: labor_time_source, type: number }`.
  - `units.definitions`: add `time_units: 100` (comment: the labour unit in the accessory file, 100 time units = 1 hour); keep `hours`, `minutes`.
  - `units.columns`: key `labor_time_source`, `source_unit: time_units`, `target_unit: hours`, new `target_column: labor_hours`, `decimals: 2`, `suspect_if: { not_whole: true, above: 1000 }` (H3, H4, H6).
  - `dq_rules`: `labor_time` → `labor_hours` in `not_null` and `numeric_non_negative`.
  - `export.columns`: `labor_hours: Hours`.
- [x] `pipeline/config_helpers.py` `_units_spec`:
  - `target_column` required, a valid name, not a column already read in `columns:` and not used by two units entries (`CONFG_VALUE_INVALID`);
  - the units column key must be a column read in `columns:` (`CONFG_UNKNOWN_REFERENCE`, as today);
  - the lineage set (line 613) adds the units column itself when it already ends in `_source`, instead of `<col>_source`.
- [x] `dq_rules` and `export.columns` may name a units `target_column` (it doesn't exist until `clean`); a name that is neither read nor produced (e.g. a stale `labor_time`) fails with `CONFG_UNKNOWN_REFERENCE`.

**Done when:** the real config loads; config tests for a missing / clashing `target_column` and a stale `labor_time` reference fail with their messages.

## Phase H2 — Conversion and routing

- [x] `pipeline/accessory_helpers.py` `convert_units`:
  - reads `col` (the source), writes `rule['target_column']`; no longer overwrites the source or adds `<col>_source` when `col` already ends in `_source`;
  - change log, suspect flags and review rows as today, with the target column named (`labor_time_source 25 -> labor_hours 0.25`);
  - suspect values: flag `ACCESS_CLEAN_UNIT_SUSPECT` and leave the target **empty** (H5).
- [x] `check_quality` (the `validate` step): `not_null` skips rows whose value was flagged `ACCESS_CLEAN_UNIT_SUSPECT` for that column, so a part gets one flag.
- [x] `DICT_COLUMNS`: `labor_time` → `labor_time_source`, `labor_hours`.
- [x] `config/messages.yaml` `ACCESS_CLEAN_UNIT_SUSPECT`: message and fix say the value is **left empty** (was "still converted").

**Done when:** the unit tests below pass.

## Phase H3 — Tests, real run and docs

- [x] Tests updated (table below); full suite passes.
- [x] Real runs: `python run_ingest.py`, `python run_accessories.py`; success criteria ticked with the numbers; Baseline table in `planning/README.md` updated.
- [x] Docs:
  - idea / plan 006: a note at the top, "source unit corrected by 013 (time units, ÷ 100, not minutes)";
  - `data_issues.md` DI-07 rewritten (the unit is 100 time units per hour; 0.4 is still suspect, now left empty);
  - `open_items.md` OI-06 reworded (0.4: a fraction of a time unit);
  - `ARCHITECTURE.md` examples (`labour 10 min → 0.17 h` → `labour 10 → 0.10 h`, `25 min → 0.42 h` → `25 → 0.25 h`);
  - `README.md`, `db/README.md` (`ACCESS_CLEAN_UNIT_SUSPECT` row), `CHANGELOG.md` entry with the commit.
- [x] Commit (approved and tested; not pushed).

**Done when:** the suite and real runs pass and the docs match the code → `Built — in user testing`.

## Tests

| File | Test |
|---|---|
| `tests/test_text_helpers.py` | units section: factor `== 1/100`; `0, 10, 25, 250, None → 0.0, 0.1, 0.25, 2.5, NaN` in `labor_hours`; `labor_time_source` unchanged; `0.4` and `1200` flagged, `labor_hours` empty for both; flag message names time units |
| `tests/test_config_helpers.py` | `target_column` missing / clashes with a read column / used twice; stale `labor_time` in `dq_rules` or `export.columns` → `CONFG_UNKNOWN_REFERENCE` |
| `tests/test_accessory_helpers.py` | `part(labor=...)` cases read `labor_hours`; `not_null` doesn't double-flag a suspect value |
| `tests/test_accessories_end_to_end.py` | `test_labour_time_is_exported_in_hours`: pairs `(labor_time_source, labor_hours)` are exactly `value / 100` (suspect excluded); export `Hours` equals `labor_hours`; no `labor_time` column in the dict |
| `tests/test_messages.py` (existing catalogue check) | still passes with the reworded message |

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-11-02 | H1–H7 approved as proposed; the unit is named `time_units` (not `hundredths_of_hour`) | User: clearer and more accurate |
| 2026-11-02 | Plan approved; build started | User |
| 2026-11-02 | **Build.** H1 and H2 committed together: the config from H1 can't run until `convert_units` (H2) writes `labor_hours` | Claude |
| 2026-11-02 | **Build.** `not_null` on `labor_hours` skips a row whose `labor_time_source` is filled: the only way the target is empty with a filled source is a suspect value, so no extra state is needed | Claude |
| 2026-11-02 | **Build.** The "used by two entries" check is `CONFG_DUPLICATE_ENTRY` (the plan said `CONFG_VALUE_INVALID`); suspect values are not logged as `unit_convert` changes (nothing was converted) | Claude |
| 2026-11-02 | **Real run** `vw_accessories_20261102_105718`: log `time_units -> hours x 0.01, 2 decimals`; 13 distinct values converted (10 → 0.1 … 250 → 2.5); `3QF601025KAX1` flagged once, `Hours` empty on its 22 export rows, 0 missing-labour flags; headers unchanged; 9,388 export rows, 16 review rows | Claude |
| 2026-11-02 | **Build.** Test fixture `part()` default labour changed 0.5 → 50: 0.5 is now a fraction of a time unit and would be flagged | Claude |

## Risks

| Risk | Mitigation |
|---|---|
| Something downstream still reads `labor_time` and silently gets nothing | Config validation rejects stale names; the end-to-end test asserts no `labor_time` column; grep check in the success criteria |
| The unit is wrong again (e.g. some rows are minutes) | Suspect rules (`not_whole`, `above: 1000`) flag outliers; the change log lists every distinct value and its result for review |
| Every non-zero labour value changes (≈ 560 rows) versus earlier exports | Expected; the CHANGELOG entry and DI-07 state the correction so nobody reads it as a regression |
