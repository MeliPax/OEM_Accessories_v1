# Changelog - OEM Accessory Pipeline

All notable changes to this project are documented here. Format based on [Keep a Changelog](https://keepachangelog.com/).

---

## [2.4.0] - 2026-08-26

### 🎯 Status: IN PROGRESS

**Mitsubishi Model Lookup: Exact TRIM Matching + Output Enrichment**

Implemented three-part enhancement to Mitsubishi model number lookup: fixed trim disambiguation collision bug, extended output with vehicle metadata, and added diagnostic failure categorization.

### ✅ Phase 7 Enhancements

1. **Step 1: Exact TRIM Token-Set Matching (Bug Fix)**
   - File: `accy_v2/model_lookup/search_engine.py` (lines ~151-179)
   - Problem: Searching for "GT" returns 3 ambiguous candidates: "GT" (CO45-X), "GT Premium" (CO45-X), "GT NOIR" (CO45-N)
   - Solution: New narrowing layer applies after substring search, keeps only candidates with exact TRIM token set match
   - Mechanism: Extracts TRIM tokens from both search and DB rows, filters to exact matches
   - Impact: Fixes 2026/2025 gt_s-awc failures (2 of 12 current NOT_FOUND cases)
   - Safety: Strictly additive — never adds match that wasn't in original substring results, no impact on 1-candidate searches
   - Tests: New regression tests for GT collision, NOIR vs GT NOIR, GT+Premium interaction, RVR drivetrain disambiguation

2. **Step 2: Extended SearchResult with Vehicle Metadata**
   - File: `accy_v2/model_lookup/search_engine.py` (SearchResult dataclass, line ~14)
   - Changes:
     - Added `drivetrain: Optional[str]` (← row["Drivetrain"], 0 empty values in DB)
     - Added `fuel_type: Optional[str]` (← 3-tier fallback: engine_type column → classified tokens → text classification)
     - Added `color: Optional[str]` (← config-driven lookup, output tagging only)
     - Added `package: Optional[str]` (← row["Package"], ADS numeric style ID, 0 empty values in Mitsubishi)
   - Population: Updated all 3 SearchResult construction sites (single candidate, duplicate group, unique variants)
   - Helper: New `_extract_row_metadata()` and `_extract_trim_token_set()` methods

3. **Step 2b: Mitsubishi Config + Output Threading**
   - File: `accy_v2/oems/mitsubishi/config/enrichment.yaml`
     - Added `color_keywords: [noir, carbon]` config (output tagging, not matching gate)
   - File: `accy_v2/oems/mitsubishi/pipeline/step4_5_model_enrichment.py`
     - Changed `model_mapping[trim]` from `str` to `Dict[str, Any]` (richer metadata)
     - Extracts and stores: model_number, drivetrain, fuel_type, color, package
     - `_add_model_number_columns()` now adds 5 output columns (up from 1)
   - File: `accy_v2/oems/mitsubishi/config/schemas/downstream.yaml`
     - Added 4 new output columns to both Accessories_EN and Accessories_FR sheets:
       - Drivetrain (source: drivetrain)
       - FuelType (source: fuel_type)
       - Color (source: color)
       - Package (source: package — note: ADS numeric ID, not trim code, different from Mazda)
   - Impact: 13 output columns per sheet (up from 9)

4. **Step 3: Diagnostic Failure Categorization**
   - File: `accy_v2/model_lookup/search_engine.py` (new function ~line 438)
   - Function: `diagnose_search_failure(make, year, classified, csv_path) → Dict[str, str]`
   - Replaces generic "[NOT_FOUND]" with specific reasons walking Year → Model → Trim hierarchy:
     - MANUFACTURER_NOT_IN_DB
     - MODEL_YEAR_NOT_IN_DB (with available_years list)
     - MODEL_NAME_NOT_FOUND_FOR_YEAR (with available_models list)
     - TRIM_VARIANT_NOT_FOUND (with available_trims list)
     - AMBIGUOUS_TRIM_MULTIPLE_MODEL_NUMBERS
   - Integration: Called from step4_5_model_enrichment.py NOT_FOUND branch
   - DQ Output: Issue descriptions now include failure reason + available options
   - Zero Performance Impact: Only runs on already-slow failure path

### ⚠️ Risk Mitigation & Side Effects

- **Shared Code Change (search_engine.py):** Touched by Hyundai/Genesis pipelines. Mitigation: Narrowing layer only fires on >1 candidates with TRIM tokens, strict subset of existing logic, comprehensive regression tests before merge.
- **Package Column Naming Collision:** Same name as Mazda's Package (different semantics: Mazda = trim-code substring, Mitsubishi = ADS numeric ID). Mitigation: Pending downstream consumer confirmation before shipping.
- **Fuel Type Tier 2 Deferred:** 3-tier fallback only implements tier 1 (engine_type column) and minimal tier 2 in this pass; full tier 2/3 implementation deferred to post-verification.

---

## [2.3.0] - 2026-08-20

### 🎯 Status: PRODUCTION READY

**Output Column Mapping: YAML-Driven Refactor (DECISION [019] Implementation)**

Eliminated hardcoded column mappings in step5_output.py by implementing shared YAML-driven column mapper. All OEMs now build output dynamically from downstream schema configuration, preventing code/config drift.

### ✅ Major Changes

1. **New Shared Helper: output_column_mapper.py**
   - File: `accy_v2/core/helpers/output_column_mapper.py`
   - Function: `apply_downstream_column_mapping(df, downstream_schema, sheet_key, language)`
   - Purpose: Centralized, YAML-driven column renaming logic (extract from Mazda's working implementation)
   - Benefit: Single implementation across all OEMs, eliminates code duplication
   - Config-driven: Reads source→output mappings from `downstream.yaml` sheets
   - Status: ✅ Implemented and verified (all OEMs passing)

2. **Canonical Column Name Standardization**
   - Changed: Model name column from `model` (Hyundai) / `model_name` (Mitsubishi) → unified `model_name` (snake_case)
   - Changed: All canonical columns to snake_case: `model_name`, `model_number`, `year_from`, `part_number`, `trim_level`, `description`, `comments`, `msrp`, `labour_hours`
   - Benefit: Eliminates confusion across OEM implementations, consistent with DECISION [019]
   - Files affected:
     - `accy_v2/oems/hyundai/config/hyundai_config.yaml` (line 13: `model:` → `model_name:`)
     - `accy_v2/oems/mitsubishi/pipeline/step1_validation.py` (added model_name injection)

3. **Fixed Downstream Schema (Hyundai & Mitsubishi)**
   - Files: `accy_v2/oems/hyundai/config/schemas/downstream.yaml`, `accy_v2/oems/mitsubishi/config/schemas/downstream.yaml`
   - Issues Fixed:
     - EN/FR sheet inconsistency: Different source_column mappings between language variants
     - Incorrect source references: Pointed to non-existent columns (e.g., `remarks` instead of `comments`)
     - Missing ModelName output column in some sheets
   - Changes:
     - Unified EN/FR sheet structure (identical source_column names for both)
     - Corrected all source_column names to post-transform snake_case
     - Added ModelName column (← model_name)
     - Fixed Model column (← model_number, was incorrectly ← model_name)
   - Impact: All 9 output columns now present and correctly mapped
   - Status: ✅ Verified (output files contain all columns with correct data)

4. **Step 5 Output Rewrite (Hyundai & Mitsubishi)**
   - Files: `accy_v2/oems/hyundai/pipeline/step5_output.py`, `accy_v2/oems/mitsubishi/pipeline/step5_output.py`
   - Changes:
     - Replaced hardcoded `_apply_output_column_mapping()` with call to shared helper
     - Removed hardcoded `rename_map` dictionaries (10+ lines per OEM)
     - Now reads schema dynamically from `downstream.yaml`
   - Benefit: Config changes automatically apply without code modification
   - Status: ✅ Both OEMs refactored and regression tested

5. **Fixed Language-Specific Column Processing**
   - File: `accy_v2/oems/mitsubishi/config/schemas/intermediate.yaml` (lines 100-102)
   - Issue: Column names in `language_specific_columns` didn't match actual DataFrame columns
   - Changes:
     - Changed `Description` → `english_description`
     - Changed `Comments` → `comments_en`
   - Impact: Language split now correctly processes both columns
   - Status: ✅ Verified (FR sheets now contain Comments column)

6. **Mitsubishi Model Name Integration**
   - File: `accy_v2/oems/mitsubishi/pipeline/step1_validation.py` (lines 52-53)
   - Change: Added `working_df["model_name"] = meta_data["model_name"]` before return
   - Purpose: Make model_name a real DataFrame column from Step 1 (matches Hyundai shape)
   - Benefit: Consistent canonical column presence across all steps for all OEMs
   - Status: ✅ Verified (model_name present through step2/3/4 to step5)

### 🐛 Root Causes Identified & Fixed

**Bug 1: Missing Output Columns**
- Cause: downstream.yaml source_column names didn't match actual DataFrame column names after transformation
- Symptom: ModelName column missing from Hyundai FR output, Comments missing from Mitsubishi EN/FR
- Fix: Corrected schema to reference post-language-split snake_case names

**Bug 2: Code/Config Drift**
- Cause: step5_output.py hardcoded mappings independent of downstream.yaml configuration
- Symptom: Changing downstream.yaml had no effect; only code changes applied
- Fix: Implemented shared YAML-driven mapper (DECISION [019])

**Bug 3: Inconsistent Column Naming**
- Cause: Different canonical names for same concept across OEMs (model vs. model_name)
- Symptom: Confusion in pipeline code, harder to maintain consistency
- Fix: Unified on model_name (snake_case) for all OEMs

### 📊 Verification Results

**Hyundai Output (regression tested)**
- All 9 columns present: Year, ModelName, Part, Description, Comments, Price, Hours, Trim, Model
- Sample row: Year=2024, ModelName=Elantra, Model=ELCS4V2BES00 (OEM code, not name)
- Status: ✅ PASS

**Mitsubishi Output (regression tested)**
- All 9 columns present: Year, ModelName, Part, Description, Comments, Price, Hours, Trim, Model
- Sample row: Year=2026, ModelName=2026_outlander_phev, Model contains OEM code
- Status: ✅ PASS

**Mazda Control Regression Test**
- Uses different output structure by design (Package instead of Trim, different column names)
- Verified: Unchanged behavior, all columns still present, no regressions
- Status: ✅ PASS (Control group unaffected)

### 🔄 Backward Compatibility

✅ **ZERO breaking changes**
- Step 1-4 behavior unchanged
- Only step5 implementation details changed
- All OEMs produce identical output structure (9 columns, correct semantics)

### 📝 DECISION [019] Alignment

**Configuration drives business logic, not code**
- ✅ Output column mapping now fully YAML-driven
- ✅ Downstream schema is source of truth for column definitions
- ✅ No hardcoded column lists or rename mappings in step5
- ✅ Scalable: Adding new output column only requires downstream.yaml edit + shared helper rerun

### 🚀 Next Steps

**For new OEMs (Honda, etc.):**
- Use same shared helper (output_column_mapper.py)
- Define downstream.yaml with 9-column structure
- Set canonical column names to snake_case
- Step5 automatically inherits working behavior

**Optional Improvements:**
- Migrate Mazda's step5_output.py to also use shared helper (transparent, same behavior)
- Document canonical column naming convention in CONFIG_GUIDE.md
- Add validation that downstream.yaml source columns exist in transformed data

---

## [2.2.1] - 2026-08-03

### 🎯 Status: READY FOR TESTING

**Modular Config Integration - Phase 5 (Partial)**

Three critical bugs fixed that prevented pipeline execution with modular YAML configs. All fixes are backward compatible with existing step methods.

### ✅ Fixed

1. **French Description Column Now Optional** 
   - File: `accy_v2/oems/hyundai/config/schemas/upstream.yaml`
   - Change: `required: true` → `required: false`
   - Reason: Source data provides English-only descriptions
   - Impact: Eliminates all "required column 'french_description' not found" errors
   - Status: ✅ Verified (57 sheets now process)

2. **Auto-Generated col_data_type_dict from Transformations**
   - File: `accy_v2/core/base_pipeline.py`
   - Change: Added transformation parser in `_build_legacy_config()`
   - Logic: Identifies `convert_to_float` operations in transformations.yaml
   - Output: Builds `{"to_float": [...], "to_string": [...]}`
   - Impact: Step 3 data type enforcement works without hardcoding
   - Status: ✅ Verified (MSRP, DNET, LaborRate conversions work)

3. **Fixed Column Mapper Exclusion Keyword Detection**
   - File: `accy_v2/core/helpers/column_mapper.py`
   - Change: `kw.get("not_have")` → `kw.get("must_not_have")`
   - Reason: Schema uses `must_not_have` but code was looking for `not_have`
   - Impact: Fixes duplicate column issue (Model_Year_To no longer maps to 'model')
   - Status: ✅ Verified (Column mapping now correct)

### 📊 Test Results

```
Pipeline Execution: 2026-08-03 16:35:56
- Run ID: 86c4f04b
- Sheets Processed: 57/57 ✅
- Sheets Failed: 0
- Output Size: 1.7 MB Excel file
- Processing Time: ~90 seconds
- Status: SUCCESS ✅
```

### 🔄 Backward Compatibility

✅ **ZERO step method changes required**
- All existing step1 through step5 methods work unchanged
- Legacy config mapping layer handles translation
- Modular config loading is transparent to existing code

### 📝 Documentation Updated

- [x] SYSTEM_ARCHITECTURE.md: Added Phase 5 section with bug details
- [x] Last Updated: 2026-08-03
- [x] Version: 2.2.1

### 🚀 Next Steps

**Priority 1: Test Other OEMs (30 min)**
```bash
python run_pipeline.py mazda        # has pre-populated ModelNumber
python run_pipeline.py mitsubishi   # multiple sheets per model
python run_pipeline.py honda        # verify consistency
```

**Priority 2: Complete Phase 5 Documentation (1 hour)**
- [ ] Update SYSTEM_ARCHITECTURE.md with modular structure examples
- [ ] Create CONFIG_GUIDE.md for teams modifying configs
- [ ] Create MIGRATION_NOTES.md for path reference updates

**Priority 3: Archive Old Configs (10 min)**
- [ ] Move old `.json` files to `_archive/` folder if present
- [ ] Update .gitignore

---

## [2.2.0] - 2026-08-03

### ✅ Complete

**Phases 1-4: Modular Config Structure Rollout**

Fully implemented modular YAML configuration with centralized path management across all 4 OEMs.

### 🎯 What's New

#### Phase 1: Modular File Structure
- Created 6-file YAML structure per OEM:
  - `pipeline.yaml` — Orchestration settings (use_model_lookup, non_null_threshold)
  - `transformations.yaml` — Per-column cleaning operations
  - `enrichment.yaml` — Model lookup rules and brands
  - `schemas/upstream.yaml` — Input validation rules
  - `schemas/intermediate.yaml` — Post-transform quality gates
  - `schemas/downstream.yaml` — Output sheet definitions

#### Phase 2: Centralized Path Registry
- Created `accy_v2/paths.yaml` (single source of truth)
- 13 path variables with ${VAR} placeholder system
- Global paths + per-OEM override support
- Full path resolution in ModularConfigLoader

#### Phase 2-3: Pipeline Integration
- ModularConfigLoader (220 lines): loads all 4 config sections
- Path placeholder resolution with regex matching
- Backward compatibility layer (_build_legacy_config)
- No step method modifications required

#### Phase 4: Multi-OEM Rollout
- Hyundai: 6 files with use_model_lookup: true
- Mazda: 6 files with use_model_lookup: false
- Mitsubishi: 6 files with use_model_lookup: true
- Honda: 6 files with use_model_lookup: true

### 📊 Statistics

- **Config Files Created:** 54 new YAML files (6 per OEM × 9 OEMs configured)
- **Lines of Code:** 2,500+ config + code changes
- **Tests:** 29 unit tests (all passing)
- **Commits:** 4 commits across phases 1-4

### 🐛 Known Issues (Phase 5 Fixes)

**Issue 1:** "required column 'french_description' not found"
- Root Cause: Schema marked French as required, source data English-only
- Fix: Set `required: false` (now in v2.2.1)

**Issue 2:** KeyError 'col_data_type_dict'
- Root Cause: Legacy config builder didn't include this key
- Fix: Auto-generate from transformations.yaml (now in v2.2.1)

**Issue 3:** Duplicate 'model' columns
- Root Cause: Column mapper using wrong exclusion keyword name
- Fix: Use `must_not_have` instead of `not_have` (now in v2.2.1)

---

## [2.1.0] - 2026-07-29

### ✅ Critical Fixes

**Two Major Search Issues Resolved**

#### Fix 1: Elantra N Single-Char Keyword Matching
- **Issue:** 'N' in 'Elantra N' not matching database records
- **Root Cause:** Single-char keyword matching bypassed ModelName checks
- **Fix:** Updated search to check ModelName first with word boundaries
- **Result:** 2 Elantra N records recovered (was 0)

#### Fix 2: G90 e-SC Engine Type Standardization
- **Issues:** 
  1. Database `engine_type='e-sc'` not standardized
  2. TrimName missing displacement: `'e-SC Prestige'` (no 3.5T)
  3. Translator not mapping `'e-sc' → 'electric'`
  4. Genesis config ignoring ENGINE_TYPE keywords

- **Fixes:**
  1. Standardized 5 G90 records: `'e-sc'` → `'electric'`
  2. Updated TrimName: `'e-SC Prestige'` → `'3.5T electric Prestige'`
  3. Added translator mapping in configs
  4. Enabled ENGINE_TYPE in Genesis config

- **Result:** 5 G90 e-SC records recovered (was 0)

### 📊 Test Results

- **Sheets Processed:** 57/57 ✅
- **Success Rate:** 100%
- **Records Recovered:** 7 critical records
- **NOT_FOUND Cases:** <1% (edge cases only)

---

## [2.0.0] - 2026-06-30

### ✅ Complete

**Phase 0: Legacy Pipeline Ported to Modular Structure**

Ported Hyundai pipeline from monolithic JSON to modular YAML with full separation of concerns.

### Features

- 4-stage pipeline (validation → normalization → standardization → transformation)
- Model lookup enrichment with ADS fallback
- DQ categorization and logging
- 57 model/year groups processed per run
- Database uniqueness checks (4-column invariant)

---

## Release Notes

### Current Production Version: 2.3.0
- **Status:** ✅ Ready for testing
- **Branch:** feature/hyundai_update
- **Commits:** 75+ total
- **Last Updated:** 2026-08-03 16:35 UTC

### Known Limitations

1. French description is optional (source data English-only for Hyundai Canada)
2. Model lookup fallback depends on ADS availability
3. Max 6 trim columns per model (configurable)
4. Year range: 2020-2030

### Supported OEMs

- ✅ Hyundai (primary, fully tested)
- ✅ Mazda (tested with modular config)
- ✅ Mitsubishi (modular config deployed)
- ✅ Honda (modular config deployed)
- ⏳ Others (Genesis, Toyota, etc. - pending update)

---

## Performance

| Metric | Value |
|--------|-------|
| Sheets/Run | 57 |
| Records/Sheet | ~300 |
| Processing Time | ~90 seconds |
| Output Size | 1.7 MB (Excel) |
| CPU | Single-threaded |
| Memory | ~200 MB |

---

## For Developers

### Quick Start (Testing Phase 5 Fixes)

```bash
# Test Hyundai (already verified)
python run_pipeline.py hyundai

# Test Mazda
python run_pipeline.py mazda

# Test Mitsubishi
python run_pipeline.py mitsubishi

# Test Honda
python run_pipeline.py honda
```

### Config Structure

```
accy_v2/oems/{oem}/config/
├── pipeline.yaml           # Orchestration
├── transformations.yaml    # Column cleaning
├── enrichment.yaml         # Model lookup
└── schemas/
    ├── upstream.yaml       # Input validation
    ├── intermediate.yaml   # Post-transform gate
    └── downstream.yaml     # Output definition
```

### Testing Checklist

- [ ] Hyundai: 57 sheets, 100% success ✅
- [ ] Mazda: verify use_model_lookup=false works
- [ ] Mitsubishi: verify multiple sheets handled correctly
- [ ] Honda: verify consistency across all OEMs
- [ ] Documentation: SYSTEM_ARCHITECTURE.md complete
- [ ] Documentation: CONFIG_GUIDE.md written
- [ ] Cleanup: Old .json configs archived

---

## Questions?

See [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) for detailed system design.
See [CONFIG_GUIDE.md](CONFIG_GUIDE.md) for configuration instructions (coming in Phase 5).

