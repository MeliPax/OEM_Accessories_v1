# 008 — Part Numbers Kept Exactly as the Source: Plan

**Status:** Built 2026-10-27 — in user testing. Open: ask the data source to export `stockCode` as text
**Idea / design:** [ideas/008_part_number_integrity_design.md](../ideas/008_part_number_integrity_design.md) (decisions P1–P13, split cases S1–S11)
**Depends on:** [plan 003](003_accessory_model_matching.md) (accessory ingest, staging, dedupe, export)
**Note:** written after the build, on 2026-10-28, from the idea's decisions and build notes. The plan step was skipped at build time, and this file records the work in the standard format.

## Outcome

Part numbers reach the dict and the export exactly as the source means them, leading zeros included:
- a part number is only restored when `make&model` proves the complete number, and is **never padded** (P6);
- every row gets a split result;
- anything that can't be proven keeps `stockCode` as read and is flagged;
- the export writes Part Number as Excel text, so the zeros survive opening and editing.

**Success criteria (2026-10-20 file)**

- [x] All 24,396 rows split (`make&model` minus the row's own `model`): 23,692 `same`, 704 `restored` (3 parts), 0 not proven.
- [x] `db/dq/part_number_check.csv` is written every run, one row per distinct (`stockCode`, `make&model`, `model`).
- [x] In scope, there is 1 flag: `ACCESS_STGNG_PART_NUMBER_RESTORED`, `71200` → `000071200` on 12 rows, listed in `accessory_review.csv` (`type = part_number`). The other 2 restored parts are counted in the log only (P13).
- [x] The export has 248 `000071200` cells across 12 sheets, all in Excel text format (`@`).
- [x] The dict keeps `part_number_source` and `part_number_check` (P4). Dedupe ignores them and still ends at 1,357 rows.
- [x] Each of S1–S11 has a hand-made test case. No code path pads a number.
- [x] More than 1% of rows not proven stops the run (`ACCESS_STGNG_PART_NUMBER_SPLIT_RATE`, P12). A missing `make&model` column stops the run (P11).
- [x] `accessory_runs.csv` gains `part_numbers_restored` (704) and `part_numbers_unproven` (0).

---

## Phase N1 — Config and reading

- [x] `config/accessories.yaml`: add a `part_number:` block with these settings:
  - `column`, `check_column: make&model`, `suffix_column: model_name`;
  - `restore: leading_zeros_only`, `allowed_characters: A-Z0-9`;
  - `max_unproven_share: 0.01`, `export_as_text: true`.
- [x] `pipeline/config_helpers.py` `_part_number_spec`: validate it, and read `make&model` as the pipeline column `make_model`. `part_number` must stay `type: text`.
- [x] `read_accessories`: read with `dtype=object` and record how Excel stored each part number (`part_number_stored_as`).

**Done when:** the real config loads, and each broken case fails with its `CONFG_` message.

## Phase N2 — Prove and restore (`part_numbers` step, all rows)

- [x] `split_check_value`, `prove_part_number`, `suffix_hint` return a split result per row (`same`, `restored`, `mismatch`, `no_make_model`, `model_not_at_end`, `no_part_left`, `unexpected_characters`). The hint is shown, never used (S5).
- [x] `check_part_numbers` writes the check report and logs each restore (`71200 -> 000071200`, rule `restore_leading_zeros`).
- [x] `check_unproven_share`: the run stops above `max_unproven_share` (S11).
- [x] `config/messages.yaml` gets six new codes:
  - `ACCESS_STGNG_PART_NUMBER_RESTORED` (warning);
  - `_MISMATCH` (error), `_UNVERIFIED_NUMBER` (error), `_UNVERIFIED` (info);
  - `_INCONSISTENT` (warning), `_SPLIT_RATE` (fatal).

**Done when:** every case S1–S11 passes in `tests/test_part_number_helpers.py`.

## Phase N3 — Review, export, run summary (`part_number_review` step, rows in scope)

- [x] `flag_part_numbers` runs after dedupe and flags only rows still in scope (P13).
- [x] Export: Part Number cells use number format `@` (P5).
- [x] `storage_helpers.append_row` rewrites a table when a row brings new columns. The run summary gained two.
- [x] Docs: `README.md`, `db/README.md` (the check report and review rows), [DI-03](../data_issues.md#di-03) set to Handled.

**Done when:** the end-to-end test passes on the real file, and the real run gives the success-criteria numbers.

---

## Tests

| File | Covers |
|---|---|
| `tests/test_part_number_helpers.py` | The split removes the row's own model name; each split result; **never padded**; restore only when proven; hints explained but not used; severity from how the cell was stored; two spellings flagged; out-of-scope rows counted, not flagged; the run stops above the unproven share; read keeps how Excel stored the value; a missing `make&model` column stops the run; an empty `stockCode` shows the number but never fills it; restored and text copies become one row after dedupe; text cells in the export; `append_row` with new columns (15 tests) |
| `tests/test_config_helpers.py` | Bad `restore`, `max_unproven_share`, `suffix_column`, `allowed_characters`, `check_column` read twice |
| `tests/test_accessories_end_to_end.py` | `test_part_numbers_are_proven_by_make_and_model` on the real file |

193 tests passed at the build. All 221 pass after plans 006 and 007 (2026-10-28).

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-10-27 | **Never pad.** The complete part number must be proven from `make&model` (P6) | User: "never do padding" |
| 2026-10-27 | Split `make&model` by removing the row's own `model` from the end (P7), confirmed on all 24,396 rows before building | User: "confirm that logic first" |
| 2026-10-27 | P1–P5 and P8–P13 approved as proposed | User: "let's go ahead and implement" |
| 2026-10-27 | **Build.** P9 is two codes (`_UNVERIFIED_NUMBER` error, `_UNVERIFIED` info) | Severity belongs to the code in `messages.yaml` |
| 2026-10-27 | **Build.** S8 (unexpected characters) uses `_MISMATCH`, with the reason in `found` | Same handling and review as any other mismatch |
| 2026-10-27 | **Build.** Two steps: `part_numbers` (all rows, before dedupe) and `part_number_review` (in scope, after dedupe) | Restore before dedupe so `71200` and `000071200` are one part; flag only what reaches the export |
| 2026-10-27 | **Build.** The first count said 6 parts lost their zeros; the real count is 3 | Corrected in the idea and data issues |
| 2026-10-28 | **Build.** The plan was written after the build | The plan step was skipped; recorded so the process is followed from now on (see `CLAUDE.md`) |

## Risks

| Risk | Mitigation |
|---|---|
| The file layout changes and rows stop splitting | Above 1% not proven, the run stops before export (S11) |
| A model name ends with another model name (`City Golf`) | The split uses the row's own `model`, never a name list |
| Excel strips zeros when someone edits the export | Part Number cells are Excel text (`@`) |
| The source keeps storing `stockCode` as numbers | Restores are flagged and in review, with the fix: export `stockCode` as text |

## Follow-ups

- Ask the data source to export `stockCode` as text. The `RESTORED` flag then stops on its own.
