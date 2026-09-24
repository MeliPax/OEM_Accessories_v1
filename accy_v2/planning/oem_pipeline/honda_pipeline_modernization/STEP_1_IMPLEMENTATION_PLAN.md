# Step 1: Validation & Metadata Extraction — Implementation Plan

**Status:** Ready for Implementation  
**Phase:** Phase 3b  
**Effort Estimate:** 6-8 hours  
**Dependencies:** Config files (section_patterns.yaml, pipeline.yaml) ✅ READY

---

## Overview

Step 1 validates the Honda Excel file structure and extracts metadata needed by downstream steps (Steps 2-4).

**Input:** Raw Excel workbook (EN and FR sheets)  
**Output:** (validated_df, metadata_dict, dq_warnings_list)  
**Returns:** Validated data + extracted metadata + DQ log entries

---

## Implementation Checklist

### Part 1: Sheet Validation (1-2 hours)

- [ ] **Check EN/FR sheet existence**
  - [ ] Load workbook, list sheet names
  - [ ] Match against pattern: `*_APP_EN` and `*_APP_FR`
  - [ ] If both not found: raise FATAL error with message "Missing EN or FR sheet"
  - [ ] DQ logging: `missing_sheet_rule` if EN or FR missing

- [ ] **Load sheets into DataFrames**
  - [ ] Read EN sheet (all rows, all columns)
  - [ ] Read FR sheet (all rows, all columns)
  - [ ] Handle encoding: UTF-8 (safe default)
  - [ ] Skip empty leading rows (if any)

- [ ] **Extract sheet-level metadata**
  - [ ] Store EN sheet name in metadata
  - [ ] Store FR sheet name in metadata

### Part 2: Metadata Extraction (1-2 hours)

- [ ] **Implement two-level metadata extraction**
  
  **Level 1: Top 5 Rows (Quick Scan)**
  - [ ] Scan rows 1-5 of EN sheet
  - [ ] Look for keywords: "Model Name", "Model", "Year", "MY"
  - [ ] Look for FR keywords: "Nom du modèle", "Année modèle"
  - [ ] Extract adjacent cell values
  - [ ] If found → validate and store, then done
  
  **Level 2: Regex Search (If Level 1 Fails)**
  - [ ] If model_name or model_year still missing, scan entire sheet
  - [ ] Regex patterns (from pipeline.yaml):
    - EN model_name: `(?i)(model\s*name|nom\s*du\s*modèle)\s*:?\s*([A-Za-z0-9\s\-]+)`
    - EN model_year: `(?i)(model\s*year|année\s*modèle)\s*:?\s*(\d{4})`
  - [ ] Extract matched groups
  - [ ] If found → validate and store, then done
  
  **Fallback: FAIL**
  - [ ] If both levels fail: raise FATAL error
  - [ ] Error message: "Metadata extraction failed. Attempted: Level 1 (top 5 rows), Level 2 (regex search)"
  - [ ] DQ logging: `metadata_extraction_failed_rule`

- [ ] **Validate extracted metadata**
  - [ ] Model name: non-empty string
  - [ ] Model year: in range [2020, 2030]
  - [ ] If invalid: raise FATAL error with details
  - [ ] Store in metadata dict:
    ```python
    metadata = {
      "model_name": "Accord",
      "vehicle_year": 2026,
      "en_sheet_name": "26MY_ACCORD_APP_EN",
      "fr_sheet_name": "26MY_ACCORD_APP_FR",
    }
    ```

### Part 3: Section Detection (1-2 hours)

- [ ] **Detect sections in EN sheet**
  - [ ] Load section patterns from config: section_patterns.yaml
  - [ ] For each section (packages, wheels, exterior, interior, electrical, paint_pens):
    - [ ] Search for EN text (e.g., "1.0 Packages and Kits")
    - [ ] Record row number where section header found
    - [ ] Store in metadata: `section_boundaries = {"packages": 11, "wheels": 57, ...}`
  - [ ] Verify all 6 sections found
  - [ ] Verify sections in correct order (1 before 2, 2 before 3, etc.)
  - [ ] If any section missing: raise FATAL error, DQ log `missing_section_rule`
  - [ ] If out of order: DQ log WARNING `section_order_rule`

- [ ] **Detect sections in FR sheet**
  - [ ] Repeat for FR sheet using FR text patterns
  - [ ] Store in metadata: `fr_section_boundaries = {...}`
  - [ ] Verify same sections found as EN (if not: DQ log warning)

- [ ] **Store section structure in metadata**
  ```python
  metadata["section_structure"] = {
    "packages": {"en_row": 11, "fr_row": 11, "status": "found"},
    "wheels": {"en_row": 57, "fr_row": 57, "status": "found"},
    # ... etc
  }
  ```

### Part 4: Column Header Validation (1-2 hours)

- [ ] **Validate column headers in each section**
  - [ ] For each section:
    - [ ] Get expected headers from config: column_headers.en (Description, Part Number, Dealer Net, etc.)
    - [ ] Read header row of section (row after section header)
    - [ ] Compare actual vs. expected
    - [ ] If headers don't match: DQ log WARNING `header_mismatch_rule` (continue)
  - [ ] Trim columns appear after "Installed Price" (variable per section)
  - [ ] Extract trim column names and store in metadata

- [ ] **Detect trim columns per section**
  - [ ] For each section:
    - [ ] Find "Installed Price" column (or "Prix installé" for FR)
    - [ ] All non-empty columns after "Installed Price" until "Application" = trim columns
    - [ ] Extract trim column names (LX, SPORT, EX, TOURING, etc.)
    - [ ] Store in metadata: `trim_columns = ["LX", "SPORT", "EX", "TOURING"]`
    - [ ] If no trim columns found: DQ log WARNING `trim_header_missing_rule`

- [ ] **Normalize column names for processing**
  - [ ] Create standardized column name mapping:
    ```python
    column_mapping_en = {
      "Description": "description",
      "Part Number": "part_number",
      "Dealer Net": "dealer_net",
      "List Price": "list_price",
      "FRT": "frt",
      "Installed Price": "installed_price",
    }
    column_mapping_fr = {
      "La description": "description",
      "Numéro de pièce": "part_number",
      # ... etc
    }
    ```

### Part 5: DQ Logging Setup (30-60 min)

- [ ] **Initialize DQ logger**
  - [ ] Create DQ warnings list to accumulate issues
  - [ ] Log structure:
    ```python
    dq_warnings = [
      {
        "rule": "missing_section_rule",
        "severity": "FATAL",
        "section": "packages",
        "message": "Section '1.0 Packages and Kits' not found"
      },
      # ... more warnings
    ]
    ```

- [ ] **Log validation results**
  - [ ] FATAL errors: immediately raise exception
  - [ ] ERRORS: log and continue processing
  - [ ] WARNINGS: log and continue processing
  - [ ] INFO: log if verbose mode enabled

- [ ] **Test DQ logging**
  - [ ] Create test case with missing section → verify FATAL logged
  - [ ] Create test case with bad header → verify WARNING logged
  - [ ] Create test case with valid file → verify no warnings logged

### Part 6: Output & Return Values (30-60 min)

- [ ] **Return validated DataFrame**
  - [ ] Return EN sheet as-is (no transformation at Step 1)
  - [ ] Return FR sheet as-is (no transformation at Step 1)
  - [ ] For now: return both separately or as tuple
  - [ ] Note: Step 2 will handle section detection within DataFrames

- [ ] **Return metadata dictionary**
  - [ ] Include all extracted metadata:
    - [ ] model_name, vehicle_year
    - [ ] en_sheet_name, fr_sheet_name
    - [ ] section_boundaries (EN and FR)
    - [ ] trim_columns (per section)
    - [ ] column_mappings (standardized names)
    - [ ] validation_status: "PASS" or "FAIL"

- [ ] **Return DQ warnings list**
  - [ ] Complete list of all validation issues found
  - [ ] Empty list if validation passed

---

## Unit Test Cases

### Test 1: Valid File Structure
- **Input:** Real Accord file (EN + FR sheets, all 6 sections present)
- **Expected Output:** 
  - Validation passes
  - metadata["model_name"] = "Accord"
  - metadata["vehicle_year"] = 2026
  - metadata["section_boundaries"] populated (all 6 sections)
  - dq_warnings = []

### Test 2: Missing Section
- **Input:** Fake file missing section 3 (Exterior)
- **Expected Output:**
  - FATAL error raised
  - DQ logged: `missing_section_rule` with severity FATAL
  - Exception message includes section name

### Test 3: Metadata Extraction — Level 1 Success
- **Input:** File with "Model Name" in row 3, "Model Year" in row 4
- **Expected Output:**
  - model_name extracted from row 3
  - model_year extracted from row 4
  - No regex search needed

### Test 4: Metadata Extraction — Level 2 Fallback
- **Input:** File with metadata buried in row 50 (not in top 5 rows)
- **Expected Output:**
  - Level 1 fails silently
  - Level 2 regex finds metadata in row 50
  - Extraction succeeds

### Test 5: Metadata Extraction — Both Levels Fail
- **Input:** File with no model name or year anywhere
- **Expected Output:**
  - FATAL error raised
  - Error message lists both failed levels
  - DQ logged: `metadata_extraction_failed_rule`

### Test 6: Out-of-Order Sections
- **Input:** File with sections in order 1, 3, 2, 4, 5, 6 (3 and 2 swapped)
- **Expected Output:**
  - Detection still finds all 6 sections
  - DQ logged: `section_order_rule` with severity WARNING
  - Processing continues (warning only)

### Test 7: Column Header Mismatch
- **Input:** File with columns "Desc" instead of "Description"
- **Expected Output:**
  - DQ logged: `header_mismatch_rule` with severity WARNING
  - Processing continues
  - metadata includes note about header variance

### Test 8: Missing Trim Columns
- **Input:** File where a section has no trim columns
- **Expected Output:**
  - DQ logged: `trim_header_missing_rule` with severity WARNING
  - metadata["trim_columns"] = [] for that section
  - Processing continues

### Test 9: Year Validation (Out of Range)
- **Input:** Extracted year = 2019 (before 2020 range)
- **Expected Output:**
  - FATAL error: "Model year 2019 out of valid range [2020, 2030]"
  - DQ logged: `metadata_extraction_failed_rule`

### Test 10: EN/FR Sheet Mismatch
- **Input:** EN sheet has 6 sections, FR sheet has only 5
- **Expected Output:**
  - Detection notes difference
  - DQ logged: WARNING about EN/FR mismatch
  - Processing continues (will be flagged in Step 4 reconciliation)

---

## Implementation Notes

### Key Points
1. **Two-level metadata extraction is strict:** If both levels fail, STOP (FATAL)
2. **Section detection is strict:** All 6 sections required, or FATAL
3. **Column validation is lenient:** Warnings logged, processing continues
4. **DQ logging is comprehensive:** Every issue logged with severity level

### Code Structure
```
accy_v2/oems/honda/pipeline/step1_validation.py
├─ def validate(df, config) → (df, metadata, dq_warnings)
│  ├─ _load_sheets(workbook) → (en_df, fr_df)
│  ├─ _extract_metadata(en_df, fr_df, config) → metadata
│  │  ├─ _level_1_quick_scan(df) → (name, year)
│  │  ├─ _level_2_regex_search(df, config) → (name, year)
│  │  └─ _validate_metadata(name, year) → bool
│  ├─ _detect_sections(en_df, fr_df, config) → (boundaries, warnings)
│  └─ _validate_columns(en_df, fr_df, config) → (trim_cols, warnings)
```

### Dependencies
- `accy_v2/oems/honda/config/section_patterns.yaml` ✅
- `accy_v2/oems/honda/config/pipeline.yaml` ✅
- `accy_v2/core/logging/dq_logger.py` (shared utility)

### Testing Setup
- Test files: `accy_v2/tests/honda_step1_*.py`
- Fixture files: Sample Excel files in `accy_v2/tests/fixtures/honda/`
- Coverage target: >80%

---

## Success Criteria

✅ All unit tests pass  
✅ Real sample file (Accord) validates without error  
✅ Metadata extracted correctly (model name, year, sections, trims)  
✅ DQ warnings logged appropriately (FATAL, ERROR, WARNING)  
✅ Code review approved (readability, error handling, testing)

---

## Time Budget Breakdown

| Task | Est. Hours |
|------|-----------|
| Sheet validation | 1-2 |
| Metadata extraction (2-level) | 1-2 |
| Section detection | 1-2 |
| Column header validation | 1-2 |
| DQ logging setup | 0.5-1 |
| Output & return values | 0.5-1 |
| Unit tests (10 test cases) | 2-3 |
| **TOTAL** | **~8 hours** |

---

## Next Step

Once Step 1 is complete and tested, proceed to **Step 2: Header Normalization** (Phase 4).

---

**Created:** 2026-09-24  
**Status:** Ready to implement
