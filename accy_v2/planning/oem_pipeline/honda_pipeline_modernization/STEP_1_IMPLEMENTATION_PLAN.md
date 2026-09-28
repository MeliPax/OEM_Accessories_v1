# Step 1: Validation & Metadata Extraction — Business Requirements & Implementation Plan

**Status:** Ready for Implementation  
**Phase:** Phase 3b  
**Effort Estimate:** 8-10 hours (validation + dual-sheet handling)  
**Dependencies:** Config files (section_patterns.yaml, pipeline.yaml) ✅ READY  
**Business Owner:** Accessory Platform Team  
**Success Criteria:** Load both EN/FR, extract all metadata, validate all 6 sections, pass DQ checks

---

## Business Problem & Requirements

### Why This Matters
- **Data Integrity:** Need to ensure file structure is valid BEFORE processing 155+ accessories
- **Bilingual Support:** Both English and French data must be loaded separately, then reconciled
- **Accuracy:** Section boundaries determine how 6 categories of accessories are parsed
- **Auditability:** Metadata extraction enables traceability (model, year, publication date)

### What We're Extracting & Why

| What | Why | Business Impact |
|------|-----|-----------------|
| **Sheet existence** | Both EN and FR required | Incomplete data if one sheet missing |
| **Model + Year** | Identifies vehicle variant | Can't match accessories to correct model |
| **Publication date** | Tracks data freshness | Need to know if data is current |
| **6 Section boundaries** | Each section needs separate processing | Wrong section ranges = wrong accessories |
| **Trim column headers** | Identifies which trims apply | Can't determine applicability without this |
| **DQ warnings** | Catches structural problems early | Prevents bad data downstream |

---

## Overview

**Step 1 transforms raw Excel → validated data ready for flattening.**

**Input:** Raw Excel workbook with EN sheet (`*_APP_EN`) and FR sheet (`*_APP_FR`)  
**Output:**
1. EN DataFrame (170 rows, 17 columns, raw)
2. FR DataFrame (170 rows, 17 columns, raw)
3. Metadata dictionary (sections, trims, model info)
4. DQ warnings list (validation results)

**Constraint:** Both sheets must be loaded and analyzed independently, then metadata merged for reconciliation

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

### Part 3: Section Detection (2-3 hours) — CRITICAL FOR DATA PARSING

**Business Requirement:** 
Every accessory belongs to ONE of 6 categories. Section boundaries MUST be accurate or accessories are misclassified.

**Expected Sections** (from config, confirmed in actual files):
1. **Packages and Kits** (bundled deals, 40-50 rows typically)
2. **Wheels and Wheel Accessories** (tire/wheel products, 10-20 rows)
3. **Exterior** (exterior trim/protection, 40-60 rows)
4. **Interior** (mats, seat covers, 15-25 rows)
5. **Electrical** (chargers, heated seats, 5-15 rows)
6. **Paint Pens** (touch-up paints, 10-20 rows)

**Total Expected:** 155-190 rows of actual accessories (vs. headers/footers)

---

- [ ] **Detect sections in EN sheet**
  - [ ] **Use regex pattern:** `^\d+\.\d+\s+(.+)$` to find section markers
  - [ ] For each section (packages, wheels, exterior, interior, electrical, paint_pens):
    - [ ] Search EN text from config: `"1.0 Packages and Kits"`, `"2.0 Wheels..."`, etc.
    - [ ] Identify **exact row number** of section marker
    - [ ] Calculate data range: (marker_row + 1) to (next_marker_row - 1)
    - [ ] Store in metadata: `section_boundaries["packages"] = {"en_row": 9, "data_start": 10, "data_end": 55}`
  - [ ] **Quality Gate:** Verify all 6 sections found
    - If any missing: FATAL error → cannot process file
    - Log: `missing_section_rule`
  - [ ] **Quality Gate:** Verify sections in correct order (1.0 < 2.0 < ... < 6.0)
    - If out of order: WARNING → log `section_order_rule` but continue
  - [ ] **Count rows per section**
    - Calculate total_rows = data_end - data_start + 1
    - This becomes important for reconciliation later

- [ ] **Detect sections in FR sheet** (INDEPENDENT PROCESSING)
  - [ ] Repeat same logic for FR sheet using FR text: `"1.0 Groupes et ensembles"`, etc.
  - [ ] Store in separate metadata: `fr_section_boundaries = {...}`
  - [ ] **Quality Gate:** Verify FR has same sections as EN
    - If FR missing a section: WARNING → log `fr_section_missing_rule` but continue with EN data

- [ ] **Store dual-sheet section structure in metadata**
  ```python
  metadata["section_structure"] = {
    "packages": {
      "en_row": 9,              # Row marker "1.0 Packages and Kits" in EN sheet
      "fr_row": 9,              # Row marker "1.0 Groupes..." in FR sheet (usually same)
      "data_start": 10,         # First data row (after marker)
      "data_end": 55,           # Last data row (before next section)
      "total_rows": 46,         # Number of accessories in this section
      "status": "found"         # "found" | "missing_en" | "missing_fr" | "mismatch"
    },
    "wheels": {"en_row": 56, "fr_row": 56, "data_start": 57, "data_end": 71, "total_rows": 15, "status": "found"},
    # ... etc
  }
  ```

### Part 4: Column Header Validation & Trim Detection (2-3 hours)

**Business Requirement:**
Each section has standard columns (Description, Part#, Prices) PLUS trim columns (which trims apply?).
Must identify all columns correctly to flatten data later.

#### Part 4a: Column Header Validation

- [ ] **Validate column headers in each section** (EN Sheet)
  - [ ] For each of 6 sections:
    - [ ] Get expected headers from config: `section_patterns.yaml` → `column_headers.en`
    - [ ] Expected: `["Description", "Part Number", "Dealer Net", "List Price", "FRT", "Installed Price"]`
    - [ ] Find header row location: (section marker row + 1) = header row
    - [ ] Read actual column headers from that row
    - [ ] Compare actual vs. expected
    - [ ] If mismatch: DQ log WARNING `header_mismatch_rule` → but continue processing
  
  - [ ] **Validate column headers in each section** (FR Sheet)
    - [ ] Repeat for FR sheet using FR expected headers: `section_patterns.yaml` → `column_headers.fr`
    - [ ] Expected: `["La description", "Numéro de pièce", "Prix net", "Prix de liste", "T.F.F.", "Prix installé"]`

#### Part 4b: Trim Column Detection (MOST CRITICAL)

**Why This Matters:**
Trim columns determine WHICH trims apply to WHICH accessories. Wrong detection = broken product applicability.

- [ ] **Identify trim columns in EN Sheet**
  - [ ] For each section:
    - [ ] Locate "Installed Price" column
    - [ ] **All columns AFTER "Installed Price"** = potential trim columns
    - [ ] Stop before: "Application", "Notes", "Remarks", empty columns
    - [ ] Extract column names: Read header row from those columns
    - [ ] Store in metadata: `trim_columns_per_section["packages"] = ["LX", "SPORT", "EX", "EX-L", "TOURING"]`
    - [ ] If NO trim columns found: DQ log WARNING `trim_header_missing_rule`

- [ ] **Identify trim columns in FR Sheet**
  - [ ] Repeat trim detection for FR sheet
  - [ ] Expected stop markers: "Application", "Notes", "Remarques"
  - [ ] Store separately: `fr_trim_columns_per_section = {...}`
  - [ ] Compare EN vs FR trim counts:
    - If EN has 5 trims but FR has 3: DQ log WARNING `trim_count_mismatch_rule`

- [ ] **Create dual-language trim mapping**
  ```python
  metadata["trim_columns"] = {
    "packages": {
      "en": ["LX", "SPORT", "EX", "EX-L", "TOURING"],
      "fr": ["LX", "SPORT", "EX", "EX-L", "TOURING"],  # Usually identical
      "count": 5
    },
    "wheels": {
      "en": ["LX", "SPORT", "EX"],
      "fr": ["LX", "SPORT", "EX"],
      "count": 3
    },
    # ... (4 more sections)
  }
  ```

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
