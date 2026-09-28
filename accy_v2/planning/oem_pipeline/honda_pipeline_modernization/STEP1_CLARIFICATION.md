# STEP 1 CLARIFICATION: Data Loading & Metadata Extraction

**Last Updated:** 2026-09-28  
**Status:** CLARIFICATION BASED ON ACTUAL FILE INSPECTION

---

## IMPORTANT: Gap Between Documentation and Reality

The original notes (note.md) documented an **idealized process** expecting sheets named `*_APP_EN` and `*_APP_FR`. However, **actual Honda files have a different structure**. This document clarifies what we're actually working with.

---

## Actual Honda File Structure

### File Example: `2025 Honda Accessories - June25.xlsx`

**Total sheets:** 47

### Sheet Organization Pattern

```
Sheet Types Identified:
├── Template (metadata/structure template)
├── Model-Specific Sheets (one per model/trim)
│   ├── LoadFile sheets  (e.g., "LoadFile - Civic Sedan")
│   ├── Trim sheets      (e.g., "Si Civic Sedan", "Sport Civic Sedan")
│   └── Master sheets    (e.g., "Civic Sedan - Master")
└── (No dedicated EN/FR language split at sheet level)
```

### Sheet Examples from File

| # | Sheet Name | Type | Purpose |
|---|------------|------|---------|
| 1 | Template | Metadata | Structure template for new models |
| 2 | LoadFile - Civic Sedan | Data | Raw load file (232 rows, 8 cols) |
| 3 | Si Civic Sedan | Trim | Si variant data (113 rows, 7 cols) |
| 4 | Sport Civic Sedan | Trim | Sport variant data |
| 5 | LX Civic Sedan | Trim | LX variant data |
| 6 | SportHybrid - Civic Sedan | Trim | Hybrid variant |
| 7 | SportTouring - Civic Sedan | Trim | Sport Touring variant |
| 8 | Civic Sedan - Master | Master | Consolidated Civic Sedan data |
| 9-14 | ... (Civic Hatch variants) | ... | ... |
| ... | ... (other models) | ... | ... |
| 47 | Accord - Master | Master | Consolidated Accord data |

---

## Data Structure Within Sheets

### LoadFile Sheets (`LoadFile - {Model}`)
```
Columns: Year, Model, Description, Part, Cost, Price, Quantity, ...
Example row:
  2025, FE1E5SK, "16" Enkei M52 Wheels...", 25CIV-ENK-WTPK, 45.00, 129.99, ...
```

### Trim Sheets (`{Trim} {Model}`)
```
Columns: Model, Description, Part, Cost, Price, Qty, Install Price
Example row:
  FE1E5SK, "16" Enkei M52 Wheels...", 25CIV-ENK-WTPK, 45.00, 129.99, ...
```

### Master Sheets (`{Model} - Master`)
```
Consolidated data for all trims of a model
Typically includes all trim variants + all accessories
```

---

## Key Observations

### 1. No Explicit EN/FR Sheet Split
- **Expected (from notes):** Sheets named `*_APP_EN` and `*_APP_FR`
- **Actual:** No language-specific sheet naming convention
- **Implication:** Language handling (EN/FR) must be discovered or configured differently
  - Could be in different files (EN file vs FR file)
  - Could be within the same sheet via column naming
  - Need to verify with more files

### 2. Master Sheets vs Trim Sheets
- **Trim sheets:** Individual trim variants (e.g., "Si Civic Sedan")
- **Master sheets:** Consolidated by model (e.g., "Civic Sedan - Master")
- **Relationship:** Master likely = union of all trim data

### 3. Template Sheet
- Generic template for new models (119 rows, 12 columns)
- Contains column structure but not actual accessory data
- Likely used as a pattern for data entry

### 4. Naming Patterns for Models
Models appear consistently across files:
- **Civic:** Civic Sedan, Civic Hatchback
- **HR-V:** HRV (with variants)
- **Pilot:** Pilot (with variants)
- **Passport:** Passport (with variants)
- **Odyssey:** ODYSSEY (with variants)
- **Ridgeline:** Ridgeline (with variants)
- **CR-V:** CRV (with variants)
- **Accord:** Accord (with variants)

---

## Revised STEP 1 Process

Based on actual file structure:

### Phase 1: File Discovery & Validation

```python
Step 1.1: LOCATE FILES
  Input: Landing zone directory or single file path
  Output: List of Honda Excel files
  
Step 1.2: VALIDATE SHEET STRUCTURE
  Check that file contains:
    ✓ At least one "LoadFile" sheet OR
    ✓ At least one model-specific trim sheet
  Action: Skip file if no valid data sheets found
```

### Phase 2: Data Loading

```python
Step 2.1: IDENTIFY DATA SHEETS
  Scan all sheets and categorize:
    - LoadFile sheets: Pattern "LoadFile - *"
    - Master sheets: Pattern "* - Master"
    - Trim sheets: Everything else (excluding Template)
  
Step 2.2: LOAD PRIMARY DATA SHEET
  Strategy: Load one primary sheet (LoadFile or Master)
  Decision: Which sheet to prioritize?
    Option A: Load "LoadFile" sheets (primary source)
    Option B: Load "Master" sheets (consolidated)
    Option C: Load all sheets and merge
  
Step 2.3: CAPTURE METADATA
  For each sheet loaded:
    - Sheet name
    - Number of rows
    - Column names
    - Data type summary
```

### Phase 3: Metadata Extraction

```python
Step 3.1: VALIDATE DATA SIGNATURE
  Location: First few rows of data sheet
  Look for:
    ✓ "Honda Accessories" text
    ✓ Year pattern (2025, 2026, 2027)
    ✓ Model name (Civic, Accord, CR-V, etc.)
  - And store these are metadata for the file 
  
Step 3.2: EXTRACT PUBLICATION DATE
  Location: Last few rows of data sheet with data (non-null)
  Look for:
    ✓ Row containing "publication date"
    ✓ Date in format YYYY-MM-DD
  Validation: Must be valid date in expected year range
  
```

### Phase 4: Return Structured Output

```python
Metadata Dictionary:
{
  "file_path": "...",
  "file_name": "2025 Honda Accessories - June25.xlsx",
  "all_found_sheets": ["LoadFile - Civic Sedan", "Civic Sedan - Master", ...],
  "data_sheets": ["english_sheet": "26MY_CRV_APP_EN", "FR_sheet": "26MY_CRV_APP_EN"],
  "manufacture_validated": true,
  "model_year": 2025,
  "publication_date": "2025-06-15",
  "found_publication_date_string": true,
  "models_found": ["Civic", "CR-V", "Accord", ...],
  "row_counts": {
    "FR_Sheet": 156,
    "EN_Sheet": 232,
    ...
  }
}

Data Dictionary:
{
  "EN": { DataFrame of loaded data (if single language) },
  "FR": { DataFrame or None (if dual language needed) }
}
```

---

## Outstanding Questions for Clarification

### Q1: Language Handling (EN/FR)
**Current Finding:** No explicit EN/FR sheet split in files examined
**Questions:**
- Are there separate Honda files (EN vs FR)? -> yes they are they have format **MY_TEXT_APP_Lang - ** are numbers represeting the last two digits in the year, TEXT represents the model name, Alng represnt the short versio of the language EN or FR. (example: 26MY_CRV_APP_EN or 26MY_CRV_APP_FR). these are the dat sheets that we will focus on.
- Or is language handling column-based (e.g., "Description EN" vs "Description FR")? -> each sheet EN/FR has it's own data, so we will handle them accoridngly.
- Should we check column names for language indicators? no 

 to conclude: 
 - We will check both EN anf FR sheets to make sure that they all have those signature htat we are cheing for and store meta data for both for auditability.


