# 012 — Final Export Column Names: Design

**Status:** Idea — approved (E1–E6, 2026-10-29)
**Updated:** 2026-10-29
**Next:** completed with plan 012 once testing is signed off (OI-01)
**Links:** plan [012](../plans/012_final_export_columns.md) · changes the export of plan [003](../plans/003_accessory_model_matching.md)
**Summary:** A new set of column names for the accessory export, kept in config and marked as the final names at the end of the pipeline; Cost is dropped from the file.

## What was asked (2026-10-29)

> At the end of the pipeline, set a new set of column names. Add them to a config, to indicate that these are the final column names at the end of the pipeline.

| Today's header | New header | Pipeline column |
|---|---|---|
| Part Number | **Part** | `part_number` |
| Model | **ModelName** | `model_name_clean` |
| Description | Description | `product_description` |
| MSRP | **Price** | `msrp` |
| Cost | *(removed from the file for now)* | `cost` |
| Labour Time (hours) | **Hours** (E4) | `labor_time` |
| Comments | Comments | `comments` |
| Variant | Variant | `variant` |
| Year | Year | `applicable_year` |
| Model Number | **Model** | `model_number` |

## What exists today

- `config/accessories.yaml` → `export.columns` maps each pipeline column to its header in the Excel file, in order. The export step (`export_accessories`) writes only those columns, renamed to those headers. Nothing else sets headers.
- `config_helpers.load_accessory_config` checks that every listed column exists in the dict. It doesn't check that headers are unique.
- `Part Number` is written as Excel text (`@`). That setting follows the **column** (`part_number`), not the header, so a rename keeps it.

## Where the names go

**Option A (recommended): change `export.columns` in place**, with a comment marking it as the final column names. It is already the last step and the single place headers are set, so the change is config only.

Option B: a new file such as `config/output_columns.yaml`. This gives a second place to keep in step with `export.columns`, for no gain.

## Decisions

| # | Decision | Choice | By |
|---|---|---|---|
| E1 | The mapping above, in that order | As listed | User |
| E2 | Cost leaves the Excel file only; it stays in the dict and the review file, so it can come back with one config line | Remove from `export.columns` | User (remove for now); Claude (keep in the dict) |
| E3 | Where the names live | Option A: `export.columns` in `accessories.yaml`, commented as the final column names | User accepted the recommendation (asked for a plan) |
| E4 | `hours` is lowercase, unlike the other headers | `Hours`: capitalized like the other headers | User |
| E5 | Rename the block to `final_columns:` | Keep `export.columns:`; the comment says these are the final names | User |
| E6 | The new names apply to the Excel file only; the dict returned to the notebook keeps the pipeline names (`part_number`, `model_number`, ...) | Excel file only | User |

## Risks

- **`Model` changes meaning.** It was the model name; it becomes the model number. A person used to the old file, or anything reading the file by header, would pick up the wrong column. This is called out in the changelog and the README.
- Two columns given the same header would make an Excel sheet with duplicate headers. The plan adds a config check.
