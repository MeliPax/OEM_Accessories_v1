# 012 — Final Export Column Names: Plan

**Status:** Plan — waiting for approval
**Updated:** 2026-10-29
**Next:** user reviews plan 012 and decides E4–E6 (OI-15)
**Links:** idea [012](../ideas/012_final_export_columns_design.md) · changes the export of plan [003](003_accessory_model_matching.md)
**Summary:** The accessory export gets its final column names from `export.columns` in `accessories.yaml` (Part, ModelName, Description, Price, hours, Comments, Variant, Year, Model); Cost is left out of the file.

## Outcome

The Excel file written at the end of `run_accessories.py` (`output/vw_accessories_<run_id>.xlsx`) has these columns, in this order, on every sheet:

`Part` · `ModelName` · `Description` · `Price` · `hours` · `Comments` · `Variant` · `Year` · `Model`

The names are set in one place, `export.columns` in `config/accessories.yaml`, and a comment there marks them as the final column names. Cost is not in the file. It stays in the dict and the review file.

**Success criteria (real run, accessory file 2026-10-20)**

- [ ] Every sheet of the export has exactly the 9 headers above, in that order, and no `Cost` column.
- [ ] `Part` cells are still Excel text: `000071200` keeps its zeros.
- [ ] `Model` holds the model number on every row; `ModelName` holds the standard name (`Golf GTI`).
- [ ] Row and sheet counts don't change: 9,388 rows in 10 sheets.
- [ ] The run log's `EXPORTED` line lists the new headers.
- [ ] Two columns given the same header stop the run with a `CONFG_DUPLICATE_ENTRY` error naming the header.

---

## Phase F1 — Config and validation

- [ ] `config/accessories.yaml` `export.columns`: the new headers (E1); delete the `cost` line (E2). Comment: `FINAL COLUMN NAMES: the headers of the output file, in this order (pipeline column: header). A column left out is not in the file.` (E3).
- [ ] `config/accessories.yaml` line 33: the `export_as_text` comment says `Part` cells instead of `Part Number` cells.
- [ ] `pipeline/config_helpers.py` `load_accessory_config`: a header used twice in `export.columns` is a `CONFG_DUPLICATE_ENTRY` error (`export.columns: header "Model" is used by model_name_clean and model_number`).

**Done when:** the real config loads, and the duplicate-header case in `test_config_helpers.py` fails with its message.

## Phase F2 — Tests and docs

- [ ] `tests/test_config_helpers.py`: the expected last headers become `['Variant', 'Year', 'Model']`; add the duplicate-header test.
- [ ] `tests/test_accessories_end_to_end.py`: `Model Number` → `Model`, `Part Number` → `Part`, `Labour Time (hours)` → `hours`. Add a test that the headers are exactly the 9 above and `Cost` is absent.
- [ ] `README.md`: the export columns, with a note that `Model` is now the model number.
- [ ] `CHANGELOG.md`: the entry, calling out the `Model` change of meaning and Cost leaving the file.
- [ ] `planning/README.md`: Baseline (tests), the index rows for 012.

**Done when:** the full suite passes, and a real run gives the numbers in the success criteria.

Not changed: the export code (`export_accessories` already writes `export.columns` in order and keeps the text format on the part number column), the dict, the review file, and the notebook (E6).

---

## Tests

| File | Covers |
|---|---|
| `tests/test_config_helpers.py` | The real config's headers; a duplicate header is a config error |
| `tests/test_accessories_end_to_end.py` | Exact headers and order on the real file; no `Cost`; `Part` as text; `Model` filled on every row; `hours` below 10 on Golf GTI |

## To confirm at review

| # | Question | Proposed |
|---|---|---|
| E4 | `hours` is lowercase while the other headers are capitalized | Keep `hours` as asked |
| E5 | Rename the block `columns:` to `final_columns:` | Keep `columns:`; the comment marks it as final |
| E6 | Apply the names to the dict returned to the notebook too | Excel file only; the dict keeps the pipeline names |

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-10-29 | E1–E3 approved: the mapping, Cost out of the file, names in `export.columns` | User |

## Risks

| Risk | Mitigation |
|---|---|
| `Model` was the model name and is now the model number, so someone reads the wrong column | Called out in the changelog and README; `ModelName` sits next to `Part` so the two are easy to tell apart |
| Something outside the pipeline reads the export by its old headers | Nothing in this repo does (checked 2026-10-29); the changelog lists every renamed header |
| Cost is needed again | One line back in `export.columns`; the value is still in the dict |
