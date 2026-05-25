# Architecture and Design Decisions

This document captures significant design and architecture decisions made for the `OEMAccessories` pipeline project. Each entry explains the problem, decision, and rationale — helping future developers understand *why* things were built this way and preventing re-litigation of settled decisions.

## Table of Contents

1. Multi-OEM scalable architecture
2. Single JSON config file per OEM
3. Two-logger separation (dq_logger vs pipeline_logger)
4. Excel loaded with `header=None` to preserve raw row structure
5. Word-token column matching (not substring matching)
6. `__na__` sentinel in config for `pd.isna()` checks
7. `rate_import_column_mapping` uses `"description"` (post-language-split name)
8. Non-null violations: DQ warning + configurable threshold instead of always-FATAL

---

## [001] Multi-OEM scalable architecture

**Date:** 2026-05-18

**Context:** The initial pipeline was a one-off for Mitsubishi. But the business needs to handle multiple OEMs (Honda, Mazda, etc.), each with potentially different column names, business rules, and validation logic. Duplicating the entire pipeline per OEM would be unmaintainable.

**Decision:** Create a shared `core/` module containing the abstract pipeline and all common logic, then create OEM-specific modules under `oems/<oem_name>/` that override/configure behavior as needed.

**Rationale:**
- **Shared core:** All five pipeline steps, column mapping, data type enforcement, logging — these are generic across OEMs.
- **OEM-specific config:** Business rules (trim boundaries, required columns, output format) are entirely expressed in a single JSON config file per OEM, not code.
- **Minimal replication:** Each new OEM needs only a config file + an orchestrator class + an entry point script (~100 lines total).

**Files affected:**
- `core/base_pipeline.py` — defines the abstract 5-step pipeline contract
- `core/config_loader.py` — validates all configs match a standard schema
- `oems/<oem_name>/config/<oem_name>_config.json` — the complete business rules for one OEM
- `oems/<oem_name>/pipeline/orchestrator.py` — implements the abstract pipeline
- `run_<oem_name>.py` — entry point

---

## [002] Single JSON config file per OEM

**Date:** 2026-05-18

**Context:** Initially, column definitions, required columns, trim bounds, output mappings, and other business rules were scattered across the codebase. This made it hard for non-engineers to adjust rules and easy to make inconsistent changes.

**Decision:** All business rules for an OEM live in a single `<oem_name>_config.json` file. The pipeline loads it once and passes sections to each step.

**Rationale:**
- **Single source of truth:** All Mitsubishi rules in one place; no hunting through multiple files.
- **Non-engineer friendly:** OEM teams can adjust rules (e.g., add a required column) without touching Python.
- **Versioning:** Config changes are visible in git history and can be reviewed independently from code changes.
- **Validation:** A single `config_loader.py` ensures all configs have the required keys.

**Files affected:**
- `core/config_loader.py` — validates required keys
- `oems/mitsubishi/config/mitsubishi_config.json` — single config file
- All pipeline steps reference `config["key"]` instead of hard-coded values

---

## [003] Two-logger separation (dq_logger vs pipeline_logger)

**Date:** 2026-05-18

**Context:** The pipeline produces two distinct types of output: (1) data quality issues found *within* the data (null records, unprofitable parts), which stakeholders care about, and (2) execution events (sheet start, record counts, FATAL errors), which developers care about. Initially, both were mixed in one log.

**Decision:** Create two separate loggers:
- **dq_logger:** Accumulates data quality warnings and writes a JSON DQ report for stakeholders.
- **pipeline_logger:** Records execution events and writes a text log for developers.

**Rationale:**
- **Audience separation:** Stakeholders read DQ reports; developers read pipeline logs. Different formats, different details.
- **DQ report is structured:** JSON allows parsing and filtering by `rule_violated`, `sheet_name`, etc.
- **Pipeline log is human-readable:** Text format with timestamps is easy to grep and scan.
- **Prevents mixing concerns:** A null record is a data quality issue (goes to dq_logger), not a pipeline failure (goes to pipeline_logger).

**Files affected:**
- `core/helpers/dq_logger.py` — generates JSON DQ report
- `core/helpers/pipeline_logger.py` — generates text pipeline log
- `core/base_pipeline.py` — instantiates both and passes them to steps

---

## [004] Excel loaded with `header=None` to preserve raw row structure

**Date:** 2026-05-18

**Context:** OEM Excel files have a specific structure: Row 0 = model name, Row 1 = actual column headers, Row 2+ = data. Early validation needs to check this structure. If we load with `header=1`, pandas auto-sets headers and we lose row 0.

**Decision:** Load Excel files with `header=None`, so the raw row structure is preserved. Step 1 validation checks row structure and calls `promote_header_row()` to demote row 0 and promote row 1 as headers.

**Rationale:**
- **Structural validation:** We can check "does row 0 contain a model name?" before processing.
- **Early failure:** If the file structure is wrong, we fail fast (FATAL) before wasting time on data validation.
- **Clarity:** The pipeline explicitly shows: drop row 0, use row 1 as headers, process row 2+. No magic.

**Files affected:**
- `core/helpers/header_helpers.py` — `promote_header_row()` function
- `oems/mitsubishi/pipeline/step1_validation.py` — calls `promote_header_row()`
- `run_mitsubishi.py` — passes `header=None` to `pd.read_excel()`

---

## [005] Word-token column matching (not substring matching)

**Date:** 2026-05-19

**Context:** Column names come from OEMs in various formats ("Part Number", "PART_NUMBER", "Part #", etc.). The pipeline needs to recognize them. Initial implementation used substring matching: a column "Part Number" was split to "part_number", then checked if "part" and "number" were substrings of "part_number". This caused a bug: "french_description" contains the substring "en" (from "french"), so it would incorrectly match `english_description` before reaching `french_description`.

**Decision:** Split the lowercased column name by `_` to get word tokens. Match keywords against whole tokens, not substrings.

**Rationale:**
- **Eliminates false positives:** "en" as a token is not in ["french", "description"], so no collision.
- **More semantically correct:** "part" is a word in "part_number"; "en" is not a word in "french".
- **Handles variants better:** "part-number", "Part Number", "PART_NUMBER" all become the same token set after cleaning.

**Files affected:**
- `core/helpers/column_mapper.py` — `column_type_finder()` now splits by `_` and checks token membership

---

## [006] `__na__` sentinel in config for `pd.isna()` checks

**Date:** 2026-05-18

**Context:** The trim validation config needs to specify "expected values are either 'X', '', or null". Null is represented as `np.nan` in Python, but JSON doesn't have a null value type in the config syntax. Early attempts used `is_na` as a string, which couldn't be distinguished from a literal column value.

**Decision:** Use the string `"__na__"` in the config JSON to represent "check for pandas null with `pd.isna()`". At runtime, when building validation rules, `"__na__"` is interpreted as `pd.isna()` and checked accordingly.

**Rationale:**
- **JSON-serializable:** `"__na__"` is a plain string, so it's valid JSON.
- **Unambiguous:** Won't collide with actual column values (no real data contains the literal string `"__na__"`).
- **Self-documenting:** Future readers see `"__na__"` and understand it means "null".

**Files affected:**
- `oems/mitsubishi/config/mitsubishi_config.json` — `trim_validation_config.must_have_only.expected_value_types: ["X", "", "__na__"]`
- `core/helpers/trim_helpers.py` — `validate_trim_by_datatype()` interprets `"__na__"` as `pd.isna()`

---

## [007] `rate_import_column_mapping` uses `"description"` (post-language-split name)

**Date:** 2026-05-19

**Context:** Step 4 splits the data by language (EN/FR) and renames `english_description` → `"description"` and `french_description` → `"description"`. Step 5 receives these dataframes and needs to map columns to the output format. Initially, the config still referenced `english_description`, but that column no longer exists after Step 4.

**Decision:** The `rate_import_column_mapping` in the config now maps the post-language-split column names. After language split, both EN and FR dataframes have a column called `"description"`, so the mapping uses that key.

**Rationale:**
- **Matches runtime state:** By Step 5, the column is called `"description"`, so the mapping must reference that.
- **Simplifies Step 4:** Language split renames to a neutral name, avoiding duplicate keys in the mapping.
- **Clear handoff:** Each step receives the dataframe state it expects.

**Files affected:**
- `oems/mitsubishi/config/mitsubishi_config.json` — `rate_import_column_mapping: { "description": "Description", ... }`
- `oems/mitsubishi/pipeline/step4_transformation.py` — renames language-specific columns to `"description"`
- `oems/mitsubishi/pipeline/step5_output.py` — applies the mapping

---

## [008] Non-null violations: DQ warning + configurable threshold instead of always-FATAL

**Date:** 2026-05-19

**Context:** Initially, if a required non-null column had even one null record, the entire sheet was skipped (FATAL). This was too strict: a sheet with 130 valid records and 2 null records in MSRP would produce zero output, even though 98% of the data was usable.

**Decision:** If the null rate in a non-null column is **below a configurable threshold** (default 50%), log each null record as a DQ warning, exclude those rows, and continue processing. If the null rate is **at or above the threshold**, still skip the sheet as FATAL (structural problem).

**Rationale:**
- **Maximizes output:** Most sheets with a few stray nulls now produce output for the good records.
- **Data quality visibility:** Each null record is logged to the DQ report for stakeholder review.
- **Structural safety:** If >50% of a column is null, it's likely a format problem (wrong file, wrong column), so we still skip the sheet.
- **Configurable threshold:** Each OEM can set `"non_null_threshold"` in their config based on tolerance.

**Files affected:**
- `oems/mitsubishi/config/mitsubishi_config.json` — `"non_null_threshold": 0.5`
- `oems/mitsubishi/pipeline/step1_validation.py` — `_validate_non_null_columns()` now logs warnings and returns filtered dataframe instead of raising FATAL

---

## [009] Single combined output file per run with Report sheet

**Date:** 2026-05-19

**Context:** Initially, the pipeline wrote one Excel file per OEM model processed. For Mitsubishi with 11 models, this meant 22 files per run (EN + FR for each). Reviewers had to open multiple files to understand the overall data quality and cross-model patterns. Additionally, run-level metadata (source file, timestamp, total warnings) had no natural place to live.

**Decision:** Write a single combined Excel file per pipeline run (named `{oem}_{run_id}_{timestamp}.xlsx`) containing:
- **`_Report` sheet (first tab)** with three sections:
  1. **Run Summary** (key-value table): run_id, source file, generated timestamp, sheets processed/skipped, total DQ warnings
  2. **Model Profile** (data table): one row per processed model with records_in, records_out, DQ warnings delta
  3. **DQ Records** (data table): all flagged records with rule violated, issue description, and part number/description for quick review
- **Model sheets** (`{model}_{lang}`) containing the processed data frames, one per model/language combination

**Rationale:**
- **Single review artifact:** Stakeholders open one file per run instead of hunting for 22 files across folders.
- **Metadata in one place:** Run-level context (what was processed, when, how many issues) is visible immediately without separately reading logs.
- **Actionable summaries:** The Report sheet lists all problems in one place with context, enabling quick triage and prioritization.
- **Simpler output structure:** No proliferation of files; output folder stays clean.
- **Report sheet advantages:** Data quality reviewers can filter/sort issues by rule, model, or severity without switching between DQ JSON and data sheets.

**Trade-offs:**
- **Single file assumption:** Assumes reviewers review everything together. If separate OEM teams need isolated outputs, the config could be extended to support multiple output modes.

**Files affected:**
- `core/base_pipeline.py` — changed `run_step5_output()` return type to `Dict[str, pd.DataFrame]`; added `run_write_combined_output()` abstract method; collect frames and stats across all sheets, write once after loop
- `oems/mitsubishi/pipeline/step5_output.py` — split into `prepare_frames()` (returns frames, no write) and `write_combined_output()` (writes combined file + Report sheet)
- `oems/mitsubishi/pipeline/orchestrator.py` — implement both new methods
- `oems/mitsubishi/config/mitsubishi_config.json` — unchanged (same output paths, same column mappings)

---

## [010] Raw data folder inside OEMAccessories with per-OEM subfolders

**Date:** 2026-05-19

**Context:** Raw source files initially lived outside the project at `OEM Accessories_v1/landing_zone/`. The pipeline entry point required relative `../` path arguments that only worked if invoked from a specific working directory, making the project less portable and harder to use. Additionally, separation of code and data across folders meant a user had to manage file locations across two different places.

**Decision:** Create a `data/landing_zone/{oem}/` folder structure inside `OEMAccessories/`. Each OEM has its own subfolder where source Excel files are placed. The pipeline entry point auto-discovers the most recent file in the OEM folder, with optional explicit path overrides.

```
OEMAccessories/
└── data/
    └── landing_zone/
        ├── mitsubishi/
        │   └── Accessory Guide - February26.xlsx
        ├── honda/         (future)
        └── mazda/         (future)
```

**Rationale:**
- **Self-contained project:** Data and code live together; no external dependencies or relative paths needed for typical use.
- **OEM-per-subfolder pattern:** Mirrors the `oems/` and `output/` folder patterns — clear, scalable structure for adding new OEMs.
- **No year subfolder:** Year context is in the filename itself (`February26`); one active file per OEM per run. Simpler and less nesting.
- **Auto-discovery:** Entry point auto-discovers the latest file, reducing command-line boilerplate for daily use while keeping explicit paths available for overrides.
- **Git-friendly:** Raw data folder is in `.gitignore` (sensitive pricing data, large binaries), so only code is version-controlled.

**Trade-offs:**
- **File replacement:** Old files are replaced when new ones arrive (no built-in history). Users should manually archive old files if needed.
- **Single file per OEM assumption:** Pattern assumes one active file per OEM per run cycle. If multiple concurrent versions are needed, the structure can be extended with date-based subfolders.

**Files affected:**
- `OEMAccessories/data/landing_zone/` — new folder structure created
- `OEMAccessories/run_mitsubishi.py` — updated to auto-discover files in `data/landing_zone/mitsubishi/`
- `OEMAccessories/.gitignore` — exclude raw data from version control
- `README.md` — updated project structure diagram and running instructions
- `CHANGELOG.md` — documented the change

---

## Adding a New Decision

When a significant design or architecture decision is made, add a new entry to this document:

1. Increment the decision number
2. Include: Date, Context, Decision, Rationale, Files affected
3. Keep entries concise but complete — future readers should understand the decision without asking

Examples of decisions worth documenting:
- Architectural choices (what to abstract, how to structure)
- Trade-offs between approaches (why this solution over that)
- Constraints or assumptions (why we can't do X)
- Bug fixes that inform future design (what we learned)

Non-examples (don't document):
- Routine code changes
- Bug fixes that are obvious from the commit message
- Temporary debugging or exploration
