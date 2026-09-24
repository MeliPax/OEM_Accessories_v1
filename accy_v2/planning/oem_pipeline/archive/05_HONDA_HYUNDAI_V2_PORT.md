# OEM Pipeline Modernization: Honda & Hyundai v2 Port

**Document:** Planning  
**Created:** June 26, 2026  
**Status:** Approved - Implementation Pending  
**Related:** `dev_workflow/01_CI_CD_STRATEGY.md`, `core/base_pipeline.py`

---

## Overview

Mitsubishi and Mazda have been fully ported into the `accy_v2` modular pipeline architecture. Honda and Hyundai still live in legacy flat scripts outside this structure. This document outlines the plan to bring both into `accy_v2/oems/{oem}/` so they share:

- Shared core utilities (column mapper, DQ logger, pipeline logger)
- Structured 5-step pipeline modules (step1 through step5)
- Unified configuration via JSON (no hardcoded settings)
- Consistent output format and naming
- Model lookup integration via `VehicleSearchEngine`

**Build sequence:** Hyundai first (~3–4 days), then Honda (~5–7 days).

---

## Current State

### Honda (Legacy: `scripts/honda_processor.py`)
- 3,298-line monolithic jupytext script
- 6 sections per Excel sheet (Packages, Electronics, Interior, Exterior, Cargo, General)
- Wide-format trim columns (X/blank) — but within each section
- French data in separate `*_APP_FR` sheet
- **Model number lookup: stub** (sets `model_number = trim`)
- No DQ logger, no pipeline logger

### Hyundai (Legacy: `source_code/hyundai_extract_utility.ipynb`)
- Flat Jupyter notebooks
- Single master Excel file with all models
- Per-row trim columns (`Trim 1`–`Trim 7`) with trim names
- EN/FR: separate column pairs in same sheet
- **Model number lookup: working** (Tags-based regex on separate CSV)
- No DQ logger, no pipeline logger

### Gold Standard (Mitsubishi & Mazda in `accy_v2/oems/`)
- Modular step files (step1.py through step5.py)
- Shared core utilities in `accy_v2/core/`
- JSON config (no hardcoded settings)
- `BasePipeline` base class and orchestrator per OEM
- Unified `VehicleSearchEngine` for model lookup
- DQ logger and pipeline logger baked in

---

## Key Design Decisions (Resolved)

| Decision | Hyundai | Honda |
|----------|---------|-------|
| Model lookup | ✅ Integrate into `db/db_vehicle_models.csv`, use `VehicleSearchEngine` | ✅ Same (integrate Honda models into shared DB) |
| Trim detection | ✅ **Dynamic** — regex `Trim \d+` + non-null check (no hardcoded list) | ✅ Config-driven via `section_config` |
| French handling | EN/FR column pairs in same sheet → split in step 4 | ✅ Separate `*_APP_FR` sheets → joined in step 4 |
| File loading | Single master Excel → group by (year, model) | ✅ **Directory-based** — `load_file()` scans all `.xlsx` files |
| Section extraction | N/A (flat row structure) | ✅ **Config-driven** — section keys/names in config JSON |

---

## Phase 1: Hyundai Port (~3–4 days)

### Files to Create

```
accy_v2/oems/hyundai/__init__.py
accy_v2/oems/hyundai/config/hyundai_config.json
accy_v2/oems/hyundai/pipeline/
  ├── __init__.py
  ├── orchestrator.py
  ├── step1_validation.py
  ├── step2_header_normalization.py
  ├── step3_standardization.py
  ├── step3_5_extract_vehicle_year.py
  ├── step4_transformation.py
  ├── step4_5_model_enrichment.py
  └── step5_output.py
accy_v2/run_hyundai.py
accy_v2/data/landing_zone/hyundai/.gitkeep
model_lookup/configs/hyundai_translator.json
```

### Step Sequence

**Step 1 — Validation**
- Port from `mastersheet_data_load()` in `hyundai_extract_utility.ipynb`
- Validate required columns present (FATAL if missing)
- Validate non-null columns (DQ warning + row exclusion)
- Validate data types (to_float columns)

**Step 2 — Header Normalization**
- Sanitize column names: strip whitespace, collapse newlines
- `map_all_columns()` using config keyword rules
- **Key: dynamic trim column detection**
  ```python
  import re
  trim_cols = [col for col in df.columns
      if re.match(r"^Trim\s+\d+$", col, re.IGNORECASE)
      and df[col].dropna().astype(str).str.strip().str.len().gt(0).any()]
  ```
- Store in `step2_result["valid_trim_cols"]`

**Step 3 — Standardization**
- Apply column rename from `col_mapping`
- Enforce data types

**Step 3.5 — Extract Vehicle Year**
- Extract from `config["year_column"]` (e.g., "Model Year From")
- Store in `meta_data["vehicle_year"]`

**Step 4 — Transformation**
- Melt detected trim columns → long format (one row per accessory+trim)
- Drop rows where trim is null/empty
- Split by language (EN/FR copies)

**Step 4.5 — Model Enrichment**
- Use `VehicleSearchEngine.search(make="Hyundai", year, keywords)`
- DQ warning for unmatched trims

**Step 5 — Output**
- Apply rate import column mapping
- Filter to required columns

### Prerequisite: Hyundai Model Data Migration

Before building the pipeline, migrate `database/dbs/Hyundai_models_db.csv` into `db/db_vehicle_models.csv`:

1. Read `Hyundai_models_db.csv` (Year, ModelNumber, Model, Trim, Tags)
2. Map to unified schema:
   - `Manufacturer` = "Hyundai"
   - `ModelYear` = Year
   - `ModelNumber` = ModelNumber
   - `Description` = Model (cleaned name)
   - `Description2` = Trim
   - `Package` = ""
   - `Style_ID` = ""
3. Append to `db/db_vehicle_models.csv` (deduplicate on Manufacturer+ModelYear+ModelNumber)
4. Regenerate `hyundai_keywords.json` using `build_manufacturer_keyword_vocab()`
5. Verify `hyundai_classification.json` (already built 2026-06-23)

### Test

```bash
cd accy_v2
python run_hyundai.py
# Should read: landing_zone/2026/Hyundia/may-2026/2026-5-1 HACC MAF DIST - 05122026.xlsx
# Should output: output/ready_to_upload/hyundai/, output/dq_reports/hyundai/
# Verify: one sheet per model+lang, _Report sheet present
```

---

## Phase 2: Honda Port (~5–7 days)

### Files to Create

```
accy_v2/oems/honda/__init__.py
accy_v2/oems/honda/config/honda_config.json
accy_v2/oems/honda/pipeline/
  ├── __init__.py
  ├── orchestrator.py
  ├── step1_validation.py
  ├── step2_header_normalization.py
  ├── step3_standardization.py
  ├── step3_5_extract_vehicle_year.py
  ├── step4_transformation.py
  ├── step4_5_model_enrichment.py
  └── step5_output.py
accy_v2/run_honda.py
accy_v2/data/landing_zone/honda/.gitkeep
model_lookup/configs/honda_translator.json
```

### Key Design: Directory-Based Multi-File Loading

Honda is **unique**: each vehicle model is a **separate Excel file** (unlike Mitsubishi where all models are sheets in one file).

**`HondaPipeline.load_file(directory_path)`** receives a **directory path**:
1. Scans directory for all `.xlsx` / `.xlsm` files
2. For each file:
   - Finds `*_APP_EN` sheet using `config["sheet_name_pattern"]`
   - Finds `*_APP_FR` sheet using `config["fr_sheet_pattern"]`
   - Reads both raw
   - Returns dict: `{en_sheet_name: raw_en_df, ...}`
   - Stores FR sheets in `self._fr_sheet_map = {en_name: raw_fr_df, ...}` for step 4

**`run_honda.py`** passes the **directory** to `pipeline.run()`.

### Step Sequence

**Step 1 — Validation**
- Extract model metadata from top-left cells
- Detect 6 section blocks (using `config["section_config"]["keys"]`)
- For each section: find header row, validate core columns
- Return: `{"sections": {"packages_and_kits": df, "electronics": df, ...}}`

**Step 2 — Header Normalization**
- For each section: promote header row, map column names
- Identify trim candidates (X/blank columns within section)
- Apply `trim_exclusion_keywords` filter
- `validate_trim_by_datatype()` per section
- Merge sections info (track valid trims across all sections)

**Step 3 — Standardization**
- **Packages/Kits section (Honda-specific):** parent-child rollup — collapse child descriptions into parent comments
- **Other sections:** forward-fill core columns, deduplicate on (description, part number)
- Pre-merge cleanup: remove empty/metadata rows
- Merge all 6 sections into one DataFrame
- Enforce data types

**Step 3.5 — Extract Vehicle Year**
- Year from `meta_data["model_year"]` (extracted in step 1)
- Validate against `config["valid_year_range"]`

**Step 4 — Transformation (EN + FR Integration)**
- Validate trim applicability (at least one "X" per row)
- Melt trim columns → long format
- **Load FR sheet** from `self._fr_sheet_map[sheet_name]`
- Run section extraction + merge on FR (reuse step 1/2/3 logic)
- Keep only `[part_number, description_fr, comments_fr]` from FR
- Left-join FR onto melted EN on `part_number`
- `_split_by_language()` → `{"EN": df, "FR": df}` with correct description/comments

**Step 4.5 — Model Enrichment**
- Extract unique trims from EN DataFrame
- Use `VehicleSearchEngine.search(make="Honda", year, keywords)`
- DQ warning for unmatched trims

**Step 5 — Output**
- Apply rate import column mapping
- Filter to required columns

### Config Structure (Config-Driven Sections)

`honda_config.json` includes:
```json
{
  "section_config": {
    "keys": ["1.0 ", "2.0 ", "3.0 ", "4.0 ", "5.0 ", "6.0 "],
    "names": {
      "1.0 ": "packages_and_kits",
      "2.0 ": "electronics",
      "3.0 ": "interior",
      "4.0 ": "exterior",
      "5.0 ": "cargo",
      "6.0 ": "general"
    },
    "special_processing": {
      "packages_and_kits": "parent_child_rollup"
    }
  },
  "trim_exclusion_keywords": ["electronics", "interior", "exterior", "cargo", "general"],
  ...
}
```

### Test

```bash
cd accy_v2
python run_honda.py
# Should read: landing_zone/2026/Honda/2026-05-04/ (all .xlsx files)
# Should output: output/ready_to_upload/honda/, output/dq_reports/honda/
# Verify: one sheet per model+lang, parent-child rollup in comments, model numbers populated
```

---

## Prerequisites

### Shared Utilities (Already Exist — Do Not Rebuild)

| Utility | Location |
|---------|----------|
| `BasePipeline` class | `accy_v2/core/base_pipeline.py` |
| `load_config()` | `accy_v2/core/config_loader.py` |
| `column_type_finder()`, `map_all_columns()`, `assert_required_columns()` | `accy_v2/core/helpers/column_mapper.py` |
| `promote_header_row()`, `clean_column_name()`, `strip_df_string_values()` | `accy_v2/core/helpers/header_helpers.py` |
| `identify_trim_candidates()`, `validate_trim_by_datatype()` | `accy_v2/core/helpers/trim_helpers.py` |
| `DQLogger` | `accy_v2/core/helpers/dq_logger.py` |
| `PipelineLogger` | `accy_v2/core/helpers/pipeline_logger.py` |
| `write_combined_output()` | `accy_v2/core/helpers/output_writer.py` |
| `KeywordExtractor` | `accy_v2/core/helpers/keyword_extractor.py` |
| `VehicleSearchEngine` | `accy_v2/model_lookup/search_engine.py` |

### Model Lookup Configs (Already Exist)

- `accy_v2/model_lookup/configs/hyundai_classification.json` (built 2026-06-23)
- `accy_v2/model_lookup/configs/hyundai_keywords.json` (built 2026-06-23)
- `accy_v2/model_lookup/configs/honda_classification.json` (built during setup)
- `accy_v2/model_lookup/configs/honda_keywords.json` (built during setup)

**Note:** Hyundai and Honda OEM-specific `_translator.json` files (abbreviation mappings) must be hand-curated from the legacy notebooks before building step 4.5.

---

## Verification Checklist

### Hyundai
- [ ] `run_hyundai.py` executes without error
- [ ] Output Excel has one sheet per model+language (e.g., "2026_elantra_EN", "2026_elantra_FR")
- [ ] `_Report` sheet exists with Run Summary + Model Profile tables
- [ ] `_Data_Issues` sheet created if DQ warnings present
- [ ] DQ JSON report in `output/dq_reports/hyundai/`
- [ ] Record counts match legacy notebook output
- [ ] Model numbers successfully looked up (not null, not identical to trim)

### Honda
- [ ] `run_honda.py` executes without error on `landing_zone/2026/Honda/2026-05-04/`
- [ ] One sheet per model EN/FR pair
- [ ] Package/Kits section: parent-child rollup correct (child descriptions in parent comments)
- [ ] Model numbers successfully looked up (stub replaced with real lookup)
- [ ] Trim applicability validation working (DQ warnings for rows with no trims)
- [ ] Record counts match legacy script output
- [ ] No duplicate rows in output

---

## Related Documents

- `dev_workflow/01_CI_CD_STRATEGY.md` — CI/CD pipeline and branch strategy
- `dev_workflow/02_AUTOMATED_CHECKS.md` — Linting, testing, security checks
- `dev_workflow/03_BRANCH_PROTECTION.md` — GitHub branch protection rules
- `dev_workflow/04_TEST_STRATEGY.md` — Unit and integration test structure

---

**Status:** Approved - Ready for Implementation  
**Next Step:** Begin Phase 1 (Hyundai Data Migration + Pipeline Build)
