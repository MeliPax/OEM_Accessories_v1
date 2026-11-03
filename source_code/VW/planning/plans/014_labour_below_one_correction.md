# 014 — Labour Values Below One Corrected (× 100): Plan

**Status:** Built — in user testing (2026-11-03)
**Updated:** 2026-11-03
**Next:** user signs off testing (014-T)
**Links:** idea [014](../ideas/014_labour_below_one_correction_design.md) · builds on plan [013](013_labour_time_units_to_hours.md) · data issue [DI-07](../data_issues.md#di-07) · data-source question DI07-S1
**Summary:** In the `clean` step, a labour value above 0 and below 1 is read as hours typed into a time-units column, multiplied by 100 into `labor_time_corrected`, flagged `ACCESS_CLEAN_UNIT_CORRECTED`, and then converted to `labor_hours` like any other value.

## Outcome

`3QF601025KAX1` (0.4) exports `Hours` **0.40** instead of empty, with a warning and a review row asking the source to fix the file. Every other labour value is unchanged. The correction runs on the 1,028 deduplicated rows, before the dict expands them.

```
dedupe (1,028) ─► clean: correct (0 < v < 1: × 100 → labor_time_corrected) ─► suspect check ─► ÷ 100 → labor_hours ─► … ─► build_dict (~9,400)
```

**Success criteria (real run, accessory file 2026-10-20)**

- [x] Run log: `UNITS ... correct between 0 and 1 entered as hours x 100` before the conversion line.
- [x] Change log: `0.4 -> 40` (rule `unit_correct`, 2 rows), then `40 -> 0.4` (rule `unit_convert`).
- [x] `3QF601025KAX1`: `labor_time_source` 0.4, `labor_time_corrected` 40, `labor_hours` 0.4 in the dict; `Hours` 0.4 on its 22 export rows.
- [x] Flags: `ACCESS_CLEAN_UNIT_CORRECTED` once for `3QF601025KAX1`; **no** `ACCESS_CLEAN_UNIT_SUSPECT` (0 suspects today); one `type = value` review row with the new code.
- [x] Values of 0 untouched (no `unit_correct` change for 0); all other `Hours` values as in plan 013's run.
- [x] Full test suite passes (apart from the known `id_buzz.yaml` test, unless fixed separately); `run_ingest.py` and `run_accessories.py` complete.

## Phase C1 — Config, message and validation

- [x] `config/accessories.yaml`, `units.columns.labor_time_source`: add
  `correct_if: { between: [0, 1], entered_as: hours }` with comments (B1, B3).
- [x] `config/messages.yaml`: new `ACCESS_CLEAN_UNIT_CORRECTED` (warning). Message: `Part {part_number}: {column} {value} is below {high}, read as {entered_as} and corrected to {corrected} {source_unit} ({rows})`; causes (the value was typed in hours; a typo); fix (ask the source to correct the file; if values below 1 are real, remove `correct_if`; rerun).
- [x] `pipeline/config_helpers.py` `_units_spec`: `correct_if` is optional; `between` is two numbers with low < high; `entered_as` is in `units.definitions`; unknown keys rejected (`CONFG_VALUE_INVALID` / `CONFG_UNKNOWN_REFERENCE`). Returns `correct: {low, high, entered_as, factor}` with `factor = definitions[source_unit] / definitions[entered_as]` (100 / 1 = 100), or `None`.

**Done when:** the real config loads with `factor == 100`; config tests for a bad `between`, an unknown `entered_as` and an unknown key fail with their messages.

## Phase C2 — Correction step

- [x] `pipeline/accessory_helpers.py` `convert_units`, first for each units column with `correct`:
  - a new column `<column without _source>_corrected` (`labor_time_corrected`): rows with `low < value < high` get `value × factor`, every other row the value as read;
  - change log: one `unit_correct` row per distinct corrected value (`0.4 -> 40`, `between 0 and 1: entered as hours x 100; 2 rows`);
  - flag `ACCESS_CLEAN_UNIT_CORRECTED` once per part and value, with a `type = value` review row (B5);
  - the suspect check and the ÷ 100 conversion then read the corrected column, so a corrected whole value is not suspect; a value still not whole (0.405 → 40.5) stays suspect and is left empty (B6).
- [x] `DICT_COLUMNS`: add `labor_time_corrected` after `labor_time_source` (B4).
- [x] Run summary: `unit_corrected` counted apart from `unit_suspects` (both go to the review file).

**Done when:** the unit tests below pass.

## Phase C3 — Tests, real run and docs

- [x] Tests (table below); full suite.
- [x] Real runs; success criteria ticked with the numbers; Baseline in `planning/README.md`.
- [x] Docs: DI-07 (0.4 handled by the rule, still ask the source) and OI-06 closed (B7); `db/README.md` (new code, `labor_time_corrected`); `README.md` units line; `ARCHITECTURE.md` (clean step, 0.4 example); `CHANGELOG.md`.
- [x] Commit (approved and tested; not pushed).

**Done when:** suite and real runs pass, docs match → `Built — in user testing`.

## Tests

| File | Test |
|---|---|
| `tests/test_text_helpers.py` | `0, 0.4, 0.5, 40, -0.5` → corrected `0, 40, 50, 40, -0.5` (0 and negatives untouched), `labor_hours` `0, 0.4, 0.5, 0.4, -0.01`; `labor_time_source` unchanged; `unit_correct` changes only for 0.4 and 0.5; `ACCESS_CLEAN_UNIT_CORRECTED` per part and value with its message; `0.405` → 40.5 still `ACCESS_CLEAN_UNIT_SUSPECT`, `labor_hours` empty; without `correct_if` nothing is corrected |
| `tests/test_config_helpers.py` | `factor == 100`; `between: [1, 0]`, `entered_as: days`, `correct_if: { below: 1 }` rejected |
| `tests/test_accessory_helpers.py` | the suspect / no-double-flag test uses a value still suspect after correcting (`0.405`); a 0.4 row gives `ACCESS_CLEAN_UNIT_CORRECTED` and no `ACCESS_DQ_VALUE_MISSING` |
| `tests/test_accessories_end_to_end.py` | `3QF601025KAX1`: source 0.4, corrected 40, `labor_hours` 0.4, export `Hours` 0.4; review value row code `ACCESS_CLEAN_UNIT_CORRECTED`; `unit_suspects == 0`, `unit_corrected == 1`; every other row `labor_hours == labor_time_source / 100` |
| `tests/test_messages.py` (existing) | the new code is in the catalogue and used in code |

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-11-03 | B1–B7 approved as proposed | User |
| 2026-11-03 | Plan approved; build started | User |
| 2026-11-03 | **Build.** C1 and C2 committed together: the message catalogue test fails until code raises the new code (C2) | Claude |
| 2026-11-03 | **Build.** Corrected values rounded to 9 decimals (0.29 x 100 = 28.999999999999996 would read as not whole and be flagged suspect) | Claude |
| 2026-11-03 | **Build.** A value corrected and still suspect (0.405 -> 40.5) gets both flags; the suspect flag shows the value as read and adds "checked after correcting: 40.5" | Claude |
| 2026-11-03 | **Real run** `vw_accessories_20261103_083930`: `UNITS CORRECT ... rows=2`; `0.4 -> 40` (unit_correct), `40 -> 0.4` (unit_convert); 1 `ACCESS_CLEAN_UNIT_CORRECTED`, 0 suspects, 0 missing-labour flags; `3QF601025KAX1` `Hours` 0.4 on 22 export rows; 0 empty `Hours`; vs the plan 013 run only those 22 rows changed; 9,388 export rows, 16 review rows | Claude |
| 2026-11-03 | **Build.** Tests that used 0.4 as a suspect example now use 1.5 (0.4 is corrected) | Claude |

## Risks

| Risk | Mitigation |
|---|---|
| A real labour value below 1 time unit (e.g. 0.5 = 18 seconds) gets multiplied | Every correction is a warning with a review row; removing `correct_if` turns it off |
| 0 is corrected or flagged by mistake (14,774 source rows) | The range is strictly above 0; a test pins 0 → 0 with no change row or flag |
| The correction runs after the suspect check and 0.4 is still left empty | Order fixed in `convert_units` and pinned by the end-to-end test (`Hours` 0.4) |
