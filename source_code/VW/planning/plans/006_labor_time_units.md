# 006 — Labour Time Units (minutes → hours): Plan

**Status:** Built — in user testing (2026-10-28)
**Updated:** 2026-10-28
**Next:** user signs off testing (OI-01); confirm the 0.4 value with the source (OI-06)
**Links:** idea [006](../ideas/006_labor_time_units_design.md) · depends on plan [003](003_accessory_model_matching.md)
**Summary:** Labour minutes converted to hours in the clean step, with lineage, suspect-value flags and the unit in the export header.
**Note:** written after the build, on 2026-10-28, from the idea's decisions and build notes. The plan step was skipped at build time, and this file records the work in the standard format.

## Outcome

Labour time arrives in minutes. The dict and the export show hours:
- the multiplier comes from unit definitions in config, never typed by hand;
- every run logs the rule it used;
- the raw minutes are kept for lineage;
- values that look like the wrong unit are flagged for review but still converted.

**Success criteria (2026-10-20 file)**

- [x] The multiplier is worked out from `units.definitions` (hours 1, minutes 60 → 1/60), and the run log states it: `minutes -> hours x 0.0166667, 2 decimals`.
- [x] 15 distinct non-zero values are converted, one change-log row each (`25 -> 0.42`, rule `unit_convert`). 0 stays 0 and isn't logged.
- [x] The dict keeps `labor_time_source` (minutes) next to `labor_time` (hours). The export shows hours only, under the header `Labour Time (hours)`.
- [x] `3QF601025KAX1` (0.4 min, 2 rows) is flagged `ACCESS_CLEAN_UNIT_SUSPECT` (warning), still converted to 0.01 h, and listed in `accessory_review.csv` as `type = value`.
- [x] A bad units block (unknown unit, a definition of 0 or less, negative decimals) stops the run with a `CONFG_` error naming the setting.
- [x] `accessory_runs.csv` gains `unit_suspects` (1 today).

---

## Phase U1 — Config and validation

- [x] `config/accessories.yaml`: add a `units:` block with `definitions` (hours 1, minutes 60), and a `labor_time` entry with `source_unit`, `target_unit`, `decimals: 2` and `suspect_if` (`not_whole: true`, `above: 600`) (L1, L2).
- [x] `pipeline/config_helpers.py` `_units_spec`: validate units, columns, decimals and suspect rules, and return a factor per column.

**Done when:** the real config loads, and each broken case in `test_config_helpers.py` fails with its message.

## Phase U2 — Conversion in the `clean` step

- [x] `pipeline/accessory_helpers.py` `convert_units`: keep `<column>_source`, multiply and round, and log one change per distinct value (L4).
- [x] Suspect values: one `ACCESS_CLEAN_UNIT_SUSPECT` flag per part and value, giving the reason (`not a whole number of minutes`, `above 600 minutes`). The value is still converted (L3).
- [x] Review: a `type = value` row per flag, through `_value_review` / `_keep_review`.
- [x] `config/messages.yaml`: the `ACCESS_CLEAN_UNIT_SUSPECT` entry (message, causes, fix: "confirm the unit with the data source").

**Done when:** the unit tests in `tests/test_text_helpers.py` (units section) pass.

## Phase U3 — Export, run summary, docs

- [x] Export header `Labour Time (hours)` (L5).
- [x] `unit_suspects` in the run summary.
- [x] Docs: `README.md` (units config), `db/README.md` (the `type = value` review rows and the flag), [DI-07](../data_issues.md#di-07) set to Handled, with the 0.4 value still Open.

**Done when:** the end-to-end test passes on the real file, and the real run gives the numbers in the success criteria.

---

## Tests

| File | Covers |
|---|---|
| `tests/test_text_helpers.py` | Multiplier from definitions; minutes → hours with rounding; 0 not logged; empty values left empty; suspect values flagged and still converted, with the message text |
| `tests/test_config_helpers.py` | Unknown target unit, definition of 0, negative decimals |
| `tests/test_accessories_end_to_end.py` | `test_labour_time_is_exported_in_hours` on the real file |

All 221 tests pass (2026-10-28).

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-10-27 | L1–L5 approved as proposed: definitions table, 2 decimals, flag-and-convert suspect values, keep `labor_time_source`, header with the unit | User |
| 2026-10-28 | Built together with plan 007, in one change | Both touch the accessory cleaning steps and `accessories.yaml` |
| 2026-10-28 | **Build.** 0 → 0 isn't logged as a change | It isn't a change; logging it would add 793 rows of noise |
| 2026-10-28 | **Build.** A suspect value is flagged once per part and value, not once per row | One review line per thing to fix; the row count is in the message (`(1 row)`) |
| 2026-10-28 | **Build.** The plan was written after the build | The plan step was skipped; recorded so the process is followed from now on (see `CLAUDE.md`) |

## Risks

| Risk | Mitigation |
|---|---|
| 0.4 is really hours, so 0.01 h is wrong | Flagged and in review; DI-07 stays Open until the source confirms |
| The source switches the column to hours | Fractions get flagged `not_whole` at once, so the review file shows the change in the first run |
| A second column needs a unit | Add it under `units.columns`; the definitions table already serves it |

## Follow-ups

- Confirm the unit and the value for `3QF601025KAX1` with the data source (DI-07).
