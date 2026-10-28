# 008 — Part Numbers Kept Exactly as the Source: Design

**Status:** Idea — approved (P1–P13, 2026-10-27)
**Updated:** 2026-10-27
**Next:** completed with plan 008 once testing is signed off (OI-01)
**Links:** plan [008](../plans/008_part_number_integrity.md) (as built) · data issue [DI-03](../data_issues.md#di-03)
**Summary:** Part numbers kept exactly as the source: leading zeros restored only when make&model proves them; never padded.
**Applies to:** the accessory pipeline (plan 003): `ingest`, `staging` and `export`
**Asked for:** keep part numbers exactly as the source has them, leading zeros included ([DI-03](../data_issues.md#di-03)).

## What the data shows (2026-10-27, whole file, 24,396 rows)

| How `stockCode` is stored | Rows | Distinct parts | Compared with the part number inside `make&model` |
|---|---|---|---|
| Text | 23,671 | all others | **identical in every row** |
| Number, leading zeros lost | 704 | 3 | `61122` vs `000061122`; also `71200`, `72709` (all 9 characters with the zeros) |
| Number, no leading zeros to lose | 21 | 4 | `330061104`, `571071213`, `571071303`, `760698137`: correct |

Notes:
- The 725 number cells use Excel's `General` format, so the zeros are not hidden behind a display format. They are gone from the cell value. Reading the file differently can't bring them back.
- The pipeline already reads every column as text (`dtype=str`), so nothing is lost after the file is read. The loss happens in the source file.
- `make&model` is the part number followed by the model name (`000071200` + `Atlas`). It agrees with `stockCode` in all 23,671 text rows, so it is a reliable second copy of the part number.
- No part appears both with and without its zeros, so there are no hidden duplicates today.
- In scope (Active, 2020 and later): 1 part, `000071200` (Cargo Box Carrier), on 12 rows. The current export shows `71200`.

## Splitting `make&model` (logic confirmed on the data, 2026-10-27)

`make&model` is the part number followed directly by the model name, with no separator: `000019819CAlltrack`. The split creates two new columns:

| New column | Rule |
|---|---|
| `make_model_part_number` | `make&model` with the row's own `model` value removed from the end |
| `make_model_model_name` | that `model` value (proves the suffix matched) |

Why the split uses the row's own `model` and not a list of model names:
- No separator exists, and part numbers end in letters too (`000019819C` + `Alltrack`). You can't tell where the part ends by its characters.
- Some model names end with another model name: `City Golf` / `e-Golf` end with `Golf`, and `City Jetta` ends with `Jetta`. Splitting on a list of names would cut `City Golf` rows as part `...City` + `Golf`, unless the longest name always wins.

The split only counts when `make&model` ends with exactly the row's `model` (same case and spaces) and something is left over. Otherwise the row gets `cannot split` and no part number is proven.

Checked on all 24,396 rows of the 2026-10-20 file:

| Check | Result |
|---|---|
| `make&model` ends with the row's `model`, with a part number left over | 24,396 of 24,396 |
| A second method (longest known model name, without the `model` column) gives the same split | 24,396 of 24,396 |
| Stray spaces or non-breaking spaces in `stockCode`, `make&model` or `model` | none |
| Split part = `stockCode` | 23,692 rows (all 23,671 text cells, plus 21 numbers without zeros) |
| Split part = `stockCode` with its leading zeros back | 704 rows: `61122` → `000061122` (289, Inactive), `71200` → `000071200` (299, Active), `72709` → `000072709` (116, Active) |
| Any other difference | 0 |
| Part numbers spelled two ways across rows | 0 (638 distinct part numbers) |
| Split part lengths | 9–14 characters |

Check workbook (all rows with the two new columns, plus a `changed` sheet): `make_model_split_check.xlsx`, in the session scratchpad. It is not part of the pipeline.

## When a row doesn't split (proposed)

Today every row splits. A future file may not, so every row gets a **split result**. Only `same` and `restored` count as proven. Every other result keeps `stockCode` exactly as read, never changes it, and gets a flag saying what was checked and what was found.

| # | What can go wrong | Example | Split result | Code (severity) | Handling |
|---|---|---|---|---|---|
| S1 | Clean split, equals `stockCode` | `000019819CAlltrack` / `Alltrack` | `same` | none | kept |
| S2 | Clean split, `stockCode` lost leading zeros | `71200` vs `000071200Atlas` | `restored` | `ACCESS_STGNG_PART_NUMBER_RESTORED` (warning) | full number used; before → after logged |
| S3 | Clean split, differs in another way | `71200` vs `000071201Atlas` | `mismatch` | `ACCESS_STGNG_PART_NUMBER_MISMATCH` (error) | `stockCode` kept; review decides which is right |
| S4 | `make&model` empty | `''` | `no_make_model` | `ACCESS_STGNG_PART_NUMBER_UNVERIFIED` (see P9) | `stockCode` kept |
| S5 | `make&model` doesn't end with the row's `model` | `000071200Atlas` / `Atlas Cross Sport` | `model_not_at_end` | `..._UNVERIFIED` | `stockCode` kept. The message adds a **hint** from looser checks (different case, spaces, or a different known model name at the end), e.g. "ends with 'atlas', not 'Atlas'". The hint is never used to restore |
| S6 | Nothing left after removing the model | `Atlas` / `Atlas` | `no_part_left` | `..._UNVERIFIED` | `stockCode` kept |
| S7 | `stockCode` empty, `make&model` has a part | `''` vs `000071200Atlas` | (existing check) | `ACCESS_STGNG_MISSING_PART_NUMBER` (error) | row left out as today. The message shows the part number found in `make&model`, but doesn't fill it in (P10) |
| S8 | Split part has unexpected characters (inner space, symbol, lowercase) | `000 071200Atlas` | `unexpected_characters` | `..._MISMATCH` (error) | `stockCode` kept. Allowed characters are set in config (`allowed_characters: A-Z0-9`) |
| S9 | The same part number written two ways across rows | `000071200` and `71200` both as split parts | (whole-file check) | `ACCESS_STGNG_PART_NUMBER_INCONSISTENT` (warning) | one flag per part, listing the spellings and rows |
| S10 | The `make&model` column is missing from the file | renamed header | (ingest) | `ACCESS_SRC_COLUMN_MISSING` (fatal) | run stops: the part numbers can't be verified (P11) |
| S11 | Many rows fail to split (file layout changed) | more than 1% of rows not `same` / `restored` | (whole-file check) | `ACCESS_STGNG_PART_NUMBER_SPLIT_RATE` (fatal) | run stops before anything is exported. Threshold `max_unproven_share: 0.01` in config (P12) |

How the results are reported:
- **Run log:** one summary line per run, e.g. `part numbers: 23,692 same | 704 restored | 0 mismatch | 0 unverified`.
- **Check report:** `db/dq/part_number_check.csv`, one row per distinct (`stockCode`, `make&model`, `model`). It has the split result, the two new columns, the row count and the source rows, in the same style as `accessory_lookup.csv`. It's written every run, even when every row is clean, so there's always proof the check ran.
- **Review:** `accessory_review.csv` gets one row per part for every flag except `same`. Rows the status filter or year window removes later are counted in the log but kept out of review (P13).
- **Tests:** one small hand-made row for each of S1–S11, so a change to the logic that breaks a case fails a test.

## The idea: restore only what can be proven, never guess

Three layers.

### 1. Keep text as text, end to end

- **Read:** keep reading as text (already the case). Also detect cells Excel stored as numbers, so the next step knows which values to check.
- **Never convert:** `part_number` stays `type: text` in config. A test fails if a number type is ever set for it.
- **Export:** write the Part Number column as an Excel text cell (format `@`), so Excel never strips the zeros when someone opens or edits the export.

### 2. Restore from `make&model`, with proof (staging step)

```
stockCode (as read)  ──┐
                       ├─► compare ─► same ─────────────────────────► keep
make&model − model ────┘         ├─► differ only by leading zeros ──► restore the full number, log before -> after,
                                 │                                   flag ACCESS_STGNG_PART_NUMBER_RESTORED (warning)
                                 ├─► differ in another way ─────────► keep stockCode, flag
                                 │                                   ACCESS_STGNG_PART_NUMBER_MISMATCH (error)
                                 └─► make&model missing, or does ──► keep stockCode, flag
                                     not end with the model name     ACCESS_STGNG_PART_NUMBER_UNVERIFIED (info)
```

- The step runs **before duplicate removal**. Otherwise `71200` and `000071200` would count as two different parts.
- Each restore goes in the change log: `71200 -> 000071200`, rule `restore_leading_zeros`, with the source rows.
- `part_number_source` (the value as read) is kept in the dict for lineage, the same way 006 and 007 keep source values. The export shows the restored number.

### 3. Report it back to the source

The restored parts appear in `db/review/accessory_review.csv`, one row per part with its row count. The fix line asks the data source to export `stockCode` as text. Once they do, the flag stops on its own.

### Config: a `part_number:` block in `accessories.yaml`

```yaml
part_number:
  column: part_number                  # the pipeline column to protect
  check_against:                       # a second copy of the part number in the file
    source_column: make&model          # read as text alongside the other columns
    strip_suffix_column: model_name    # make&model = part number + model name
  restore: leading_zeros_only          # leading_zeros_only | never
  export_as_text: true                 # Part Number cells written with Excel text format "@"
```

`load_accessory_config` validates it: an unknown column, or a bad `restore` value, stops the run with a `CONFG_` code.

## Rule: no padding, ever

The pipeline never pads a part number (adds zeros to reach a length). The complete part number must be proven by `make&model`. When it can't be proven, `stockCode` is kept as it is and flagged. Padding is a guess: part numbers run from 9 to 14 characters, and a padded value is never checked against anything. (User decision, 2026-10-27.)

## What it gives on today's data

| | Whole file | In scope |
|---|---|---|
| Part numbers restored | 704 rows, 3 parts | 12 rows, 1 part (`000071200`) |
| Mismatches (`..._MISMATCH`) | 0 | 0 |
| Unverified (`..._UNVERIFIED`) | 0 | 0 |
| Export | | `000071200` stored as text |

Restoring happens in staging, before the status filter and year window. So the 704 rows are all fixed, but only the 12 in-scope rows reach the export.

## Decisions

| # | Question | Proposed |
|---|---|---|
| P1 | Restore leading zeros from `make&model`, but only when the two copies differ by nothing else? | ✅ 2026-10-27: Yes: proven by the file itself, never guessed |
| P2 | Severity of `ACCESS_STGNG_PART_NUMBER_RESTORED`? | ✅ 2026-10-27: **warning**: the value is used, and it goes to review so the data source fixes the export |
| P3 | Any other mismatch: keep `stockCode` and flag an **error** for review (not leave the row out)? | ✅ 2026-10-27: Yes; 0 today |
| P4 | Keep `part_number_source` in the dict; export the restored number only? | ✅ 2026-10-27: Yes (same as 006 / 007) |
| P5 | Write Part Number as Excel text cells in the export? | ✅ 2026-10-27: Yes |
| P6 | Padding? | ✅ 2026-10-27: **Never.** The complete part number must be proven from `make&model` |
| P7 | Split `make&model` by removing the row's own `model` from the end, into `make_model_part_number` and `make_model_model_name`? | ✅ 2026-10-27: approved (confirmed on all 24,396 rows) |
| P8 | Every row gets a split result; only `same` and `restored` are proven, and nothing else ever changes `stockCode` (S1–S11)? | ✅ 2026-10-27: Yes |
| P9 | `..._UNVERIFIED` severity: **error** when `stockCode` was stored as a number (zeros may be lost and can't be checked); **info** when it was text? | ✅ 2026-10-27: Yes |
| P10 | `stockCode` empty but `make&model` has a part (S7): leave the row out as today, showing the part found in the message? | ✅ 2026-10-27: Yes: nothing to compare against, so it isn't proven |
| P11 | `make&model` missing from the file stops the run (fatal)? | ✅ 2026-10-27: Yes: without it no part number can be verified |
| P12 | Stop the run when more than 1% of rows can't be proven (`max_unproven_share: 0.01`)? | ✅ 2026-10-27: Yes: that usually means the file layout changed |
| P13 | Review lists only rows that stay in scope; the rest are counted in the log and the check report? | ✅ 2026-10-27: Yes |

## Build notes (2026-10-27)

Built on the user's go-ahead after P1–P13 were approved (the plan was written up afterwards: [plans/008](../plans/008_part_number_integrity.md)).

| Where | What |
|---|---|
| `config/accessories.yaml` | `part_number:` block (column, check_column, suffix_column, restore, allowed_characters, max_unproven_share, export_as_text) |
| `pipeline/config_helpers.py` | Validates the block (`CONFG_` errors); reads `make&model` as the pipeline column `make_model` |
| `pipeline/accessory_helpers.py` | `read_accessories` keeps how Excel stored the cell (`part_number_stored_as`); `split_check_value`, `prove_part_number`, `suffix_hint`, `check_part_numbers`, `check_unproven_share`, `flag_part_numbers`; dedupe ignores the lineage columns; Part Number exported as Excel text |
| `config/messages.yaml` | `ACCESS_STGNG_PART_NUMBER_RESTORED`, `_MISMATCH`, `_UNVERIFIED_NUMBER`, `_UNVERIFIED`, `_INCONSISTENT`, `_SPLIT_RATE` |
| `pipeline/storage_helpers.py` | `append_row` rewrites a table when a row brings new columns (the run summary gained two) |
| Steps | `part_numbers` (after ingest, all rows) and `part_number_review` (after dedupe, flags for rows in scope) |
| Tests | `tests/test_part_number_helpers.py` (every case S1–S11), config cases in `test_config_helpers.py`, real-file checks in `test_accessories_end_to_end.py`; 193 passing |

Deviations from the idea text:
- P9 is two codes, because severity belongs to the code: `..._UNVERIFIED_NUMBER` (error) and `..._UNVERIFIED` (info).
- S8 (unexpected characters) uses `..._MISMATCH`, with the reason in `found`.
- The dict keeps `part_number_source` and `part_number_check` (P4).

Real run (2026-10-20 file): 24,396 rows; 23,692 `same`, 704 `restored` (3 parts), 0 not proven. In scope: 1 flag, `71200` → `000071200` on 12 rows, in `accessory_review.csv`. The export has 248 `000071200` cells across 12 sheets, all Excel text. The other 2 restored parts (405 rows) are only in rows left out earlier, so they're counted in the log, not flagged.
