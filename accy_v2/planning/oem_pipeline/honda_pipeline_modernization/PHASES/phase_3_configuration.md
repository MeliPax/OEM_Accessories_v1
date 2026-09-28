# Phase 3: Configuration & Validation

**Duration:** Weeks 3–4  
**Effort:** ~24 hours  
**Status:** Ready to start (after Phase 1)  
**Dependencies:** Phase 1 (directory structure), Phase 2 (utilities available)  
**Parallel Work:** Can start immediately after Phase 1 completes

---

## Business Context

**Why Phase 3 Matters:**
- **Data Validation Gate:** First check that file structure is correct before investing in processing
- **Bilingual Processing:** Both EN and FR sheets must be loaded separately to enable independent validation and later reconciliation
- **Section Integrity:** 155+ accessories are categorized into 6 sections—wrong section boundaries = misclassification
- **Trim Accuracy:** Trim applicability (which trim can use which part) is foundational for output quality

**Success Definition:**
✅ Both EN and FR sheets loaded  
✅ All 6 sections detected with accurate row ranges  
✅ Trim columns identified per section per language  
✅ Metadata captured for: model, year, publication date, sheet names  
✅ DQ warnings logged for any structural issues  

---

## Objectives

1. **Populate config YAML files** with patterns extracted from actual Honda files (`landing_zone/honda/may_2026/`)
2. **Implement Step 1 module** to load, validate, and extract metadata from both EN and FR sheets
3. **Create translator & classifier configs** for Honda model lookup integration

---

## Deliverables

### A. Config File Population

**`section_patterns.yaml`** — Populate with real section identifiers
- Must confirm with actual Honda Excel files from `landing_zone/honda/2026/2026-09/`
- Capture EN and FR text exactly
- Add comments for each section

**`reconciliation.yaml`** — EN/FR sheet patterns and rules
- Sheet naming patterns (confirm with real files)
- Composite part number rules (left-priority algorithm details)
- Matching priority levels (part number, cost, trims, comments)
- EN/FR divergence thresholds (cost variance %, part coverage %, etc.)

**`trim_config.yaml`** — Applicability markers and tokenization
- Confirm applicability markers with real files (["•", "T", "E"] or different?)
- Compound keyword rules (e.g., "EX-L" keeps hyphen)
- Confirm tokenization behavior

**`pipeline.yaml`** — Error handling and batch settings
- Error type → action mapping (FATAL, WARNING, QUARANTINE)
- Batch quarantine threshold
- Publication date extraction config

### B. Step 1 Implementation: Load, Validate & Extract (Dual-Sheet)

Implement `accy_v2/oems/honda/pipeline/step1_validation.py`

**Critical: Handle EN and FR sheets independently, then merge metadata**

#### What to Extract (Business Requirements)

| Data Point | Why Needed | Where to Find |
|---|---|---|
| **Model Name** | Identifies vehicle variant (Civic, Accord, CR-V) | File headers or sheet name |
| **Vehicle Year** | Model year (2026, 2025) | Filename (26MY, 25MY) or file headers |
| **Publication Date** | Data freshness tracking | Footer rows or file metadata |
| **6 Section Boundaries** | WHERE each accessory category begins/ends | Row positions of "1.0 Packages", "2.0 Wheels", etc. |
| **Trim Columns per Section** | WHICH trims apply to WHICH parts | Column headers after "Installed Price" |
| **Column Name Mappings** | Enables standardization later | Row after section marker contains headers |

#### Key Functions to Implement

1. **`load_both_sheets(file_path)`** 
   - Find and load `*_APP_EN` sheet into `en_df`
   - Find and load `*_APP_FR` sheet into `fr_df`
   - Return: `(en_df, fr_df, sheet_info_dict)`
   - FATAL if either sheet missing

2. **`extract_model_and_year(file_path)`**
   - Try Level 1: Scan top 5 rows for "Model Name", "Year", "MY"
   - Try Level 2: Regex search entire file if Level 1 fails
   - Return: `{"model_name": "Civic 5D", "vehicle_year": 2026}`
   - FATAL if both fail

3. **`identify_section_boundaries(df)` — USE REGEX**
   - Pattern: `^\d+\.\d+\s+(.+)$` matches "1.0 Packages and Kits", "2.0 Wheels...", etc.
   - For EACH section marker found, record: marker_row, data_start, data_end, total_rows
   - Return: `{"Packages and Kits": {"marker_row": 9, "data_start": 10, "data_end": 55, ...}, ...}`
   - FATAL if any section missing

4. **`extract_trim_columns(df, section_boundaries)`** — PER SECTION
   - For each section, find "Installed Price" column
   - All columns AFTER that = potential trims
   - Stop before "Application", "Notes", empty cols
   - Return: `{"packages": ["LX", "SPORT", "EX"], "wheels": ["LX", "EX"], ...}`

5. **`validate_en_fr_consistency(en_metadata, fr_metadata)`**
   - Verify both sheets have same 6 sections
   - Verify section boundaries close (allow ±1 row variance)
   - Log WARNING if divergence detected
   - Return: reconciliation status

**Output:** 
```python
(en_df, fr_df), metadata, dq_warnings

# metadata structure:
{
  "vehicle": {"model_name": "Civic 5D", "year": 2026, "publication_date": "2026-05-04"},
  "sheets": {"en": "26MY_CIV5D_APP_EN", "fr": "26MY_CIV5D_APP_FR"},
  "sections": {
    "packages": {"en_row": 9, "fr_row": 9, "data_start": 10, "data_end": 55, "status": "found"},
    # ... (5 more)
  },
  "trim_columns": {
    "packages": {"en": ["LX", "SPORT", "EX"], "fr": ["LX", "SPORT", "EX"]},
    # ... (5 more)
  },
  "validation_status": "PASS" | "FAIL"
}

# dq_warnings examples:
[
  {"rule": "missing_sheet_rule", "severity": "FATAL", "message": "FR sheet not found"},
  {"rule": "section_missing_rule", "severity": "FATAL", "message": "Section '3.0 Exterior' not found"},
  {"rule": "trim_count_mismatch_rule", "severity": "WARNING", "message": "EN has 5 trims, FR has 4"}
]
```

**DQ Rules Implemented:**
- `missing_sheet_rule` — EN or FR sheet not found → FATAL
- `section_missing_rule` — Any of 6 sections not found → FATAL
- `section_order_rule` — Sections out of order → WARNING
- `header_mismatch_rule` — Expected columns not found → WARNING  
- `trim_header_missing_rule` — No trim columns detected → WARNING
- `trim_count_mismatch_rule` — EN/FR trim count differs → WARNING
- `en_fr_divergence_rule` — EN/FR section boundaries differ → WARNING

### C. Translator & Classifier Configs (for Model Lookup later)

**Purpose:** Enable VehicleSearchEngine to find correct vehicle models for trims

**Create:**
- `accy_v2/model_lookup/configs/honda_translator.yaml` — Abbreviation mappings
- `accy_v2/model_lookup/configs/honda_classification.yaml` — Trim token classifications

**Honda Translator Example:**
```yaml
# Map abbreviations → full words for model lookup
abbreviations:
  "EX-L": "EX-L"          # Keep compound terms with hyphen
  "Type R": "Type R"      # Keep multi-word terms
  "HondaSense": "Honda Sense"  # Normalize spacing
  "PHEV": "Plug-in Hybrid"
```

**Honda Classification Example:**
```yaml
# Classify trim keywords for model search engine
TRIM:
  - LX
  - EX
  - EX-L
  - SPORT
  - TOURING
  - Type R

DRIVETRAIN:
  - FWD
  - AWD
  - "All-Wheel Drive"

ENGINE_TYPE:
  - "2.0T"
  - "2.5T"
  - "1.5T"


MODEL:
  - Accord
  - Civic
  - CR-V
  - Ridgeline
  - Pilot
```

**Source:** Use patterns from real Honda files + existing Hyundai/Mazda configs as template

---

## Code Changes

### Files to Create/Update

| File | Status | Purpose |
|------|--------|---------|
| `accy_v2/oems/honda/config/section_patterns.yaml` | ✅ EXISTS | Confirm 6 sections, EN/FR patterns match reality |
| `accy_v2/oems/honda/config/reconciliation.yaml` | ⏳ NEEDS DETAILS | Sheet patterns, part# normalization rules, divergence thresholds |
| `accy_v2/oems/honda/config/trim_config.yaml` | ⏳ NEEDS DETAILS | Applicability markers (•, T, E, etc.), tokenization rules |
| `accy_v2/oems/honda/config/pipeline.yaml` | ⏳ NEEDS DETAILS | Error handling levels, batch quarantine settings |
| `accy_v2/oems/honda/pipeline/step1_validation.py` | ⏳ **PRIORITY** | Implement all 5 key functions (load, validate, extract sections, extract trims, validate EN/FR) |
| `accy_v2/model_lookup/configs/honda_translator.yaml` | ⏳ CREATE | Abbreviation mappings for Honda trims |
| `accy_v2/model_lookup/configs/honda_classification.yaml` | ⏳ CREATE | Token classification (TRIM, ENGINE_TYPE, DRIVETRAIN, MODEL) |
| `accy_v2/tests/test_honda_step1_validation.py` | ⏳ CREATE | Unit tests for section detection, metadata extraction, EN/FR validation |

### Modified Files

| File | Change | Why |
|------|--------|-----|
| `accy_v2/oems/honda/orchestrator.py` | Call Step 1: `(en_df, fr_df), metadata, warnings = step1_validation.validate_and_extract()` | Entry point for pipeline |
| `accy_v2/oems/honda/pipeline/step1_validation.py` | **MAJOR REWRITE:** Add dual-sheet handling, section detection, trim extraction, EN/FR validation | Core validation logic |

---

## Validation Checklist

**Before Populating Config:**
- [ ] Real Honda Excel files available (from landing_zone/honda/2026/2026-09/)
- [ ] Confirm section identifier text (EN & FR) from actual files
- [ ] Confirm sheet naming patterns (EN & FR)
- [ ] Confirm applicability markers used in files
- [ ] Sample composite part numbers noted (for later verification)

**After Implementation:**
- [ ] All YAML config files populated & valid
- [ ] Step 1 implementation complete & passing unit tests (>80% coverage)
- [ ] Translator & Classifier configs created
- [ ] Step 1 successfully extracts:
  - [ ] Model name
  - [ ] Vehicle year
  - [ ] Section boundaries
  - [ ] Trim columns per section
  - [ ] Metadata in correct structure
- [ ] DQ warnings logged for validation issues
- [ ] Commit: "Phase 3: Configuration & Step 1 Validation — config population, metadata extraction"

---

## Integration with Step 1

Phase 3 Step 1 must:
1. Call `section_validation.validate_section_structure()` (from Phase 2 utilities)
2. Use `trim_config.yaml` to detect applicability markers
3. Populate metadata dict for downstream steps
4. Log all validation warnings to DQ logger

---

## Critical Input

**User Must Provide (before Phase 3):**
- [ ] Sample Honda Excel file for inspection
- [ ] Exact section identifier text (EN & FR)
- [ ] Sheet naming patterns currently used
- [ ] Applicability marker characters (confirm ["•", "T", "E"])
- [ ] Sample composite part numbers (EN & FR)

---

## Next Phase

Phase 3 complete → Phase 4 (Core Pipeline Steps) unblocked.

**Does NOT block Phase 2** — Phase 2 completes independently.

---

**Estimated Completion:** ~22 hours (config + Step 1 implementation + testing)  
**Actual Time:** (To be filled in after completion)
