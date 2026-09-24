# Phase 3: Configuration & Data Validation — Requirements

**Status:** Requirements Confirmed (2026-09-24)  
**Phase:** 3 of 7 (Honda Pipeline Modernization)  
**Effort:** ~24 hours

---

## Overview

Phase 3 populates Honda configuration files with actual data extracted from sample files and implements Step 1 (Validation). This document captures the precise requirements for data handling, section structure, trim column promotion, and divergence detection.

---

## 1. Section Structure (CONFIRMED)

### Consistent Across All Models

All Honda models (Accord, Civic 4D, CR-V, Pilot, Odyssey, Prologue, Civic Hatch, Ridgeline, Passport) have exactly **6 sections**, in order:

```
1. 1.0 Packages and Kits
2. 2.0 Wheels and Wheel Accessories
3. 3.0 Exterior
4. 4.0 Interior
5. 5.0 Electrical
6. 6.0 Paint Pens
```

**Decision:** Do NOT support variable sections per model. All models follow this standard structure.

**Config Impact:**
- `section_patterns.yaml`: Define these 6 sections with EN/FR exact text
- `step1_validation.py`: Require all 6 sections present in order; fail if missing or reordered

**Verification (from sample files):**
- Accord: 6 sections at rows 11, 57, 67, 114, 125, 137
- Civic 4D: 6 sections at rows 11, 54, 66, 109, 123, 132
- CR-V: 6 sections at rows 11, 61, 73, 118, 132, 165
- Pilot: 6 sections at rows 11, 71, 81, 130, 150, 160

---

## 2. Column Structure & Trim Header Promotion

### Current File Structure

Each section has:
```
Row N:    [Section Header]  e.g., "1.0 Packages and Kits"
Row N+1:  Description | Part Number | Dealer Net | List Price | FRT | Installed Price | [Trim Columns] | Application
Row N+2:  (Data starts here)
```

**Issue:** "Application" becomes a header, pushing trim column names to appear as data in the display.

### Solution: Promote Trim Headers

**Output columns should be ordered as:**
```
Description | Part Number | Dealer Net | List Price | FRT | Installed Price | [TRIM_1] | [TRIM_2] | ... | [TRIM_N] | Comments
```

Where:
- `[TRIM_1], [TRIM_2], ..., [TRIM_N]` = All trim columns (LX, SPORT, EX, TOURING, etc.)
- Order of trim columns = left-to-right in the source file
- `Comments` = New column for notes/DQ info
- **"Application" is NOT an output column** — it's a structural marker in the source

**Implementation (Step 1-4):**
1. Detect trim column headers by finding all non-empty cells between "Installed Price" and "Application"
2. Extract trim names (trim column headers)
3. During Step 3 standardization: replace "Application" column with trim applicability data
4. During Step 4 output: promote trim columns to actual output column headers

**Config Impact:**
- `trim_config.yaml`: Define trim detection logic (columns after Installed Price, before Application)
- `step1_validation.py`: Extract and validate trim column names per section
- `step3_standardization.py`: Reshape applicability markers from Application column to trim columns
- `step4_transformation.py`: Ensure trim columns are output headers

---

## 3. EN/FR Reconciliation & Divergence Handling

### Priority & Alignment

**Requirement:** Same priority for both English and French.

- When reconciling EN and FR values: apply same rule to BOTH
- If right-side is selected (per requirements): use right-side for BOTH EN and FR
- Result: both EN and FR output rows have identical value

**Example:** If "Part Number" priority is left-side (prioritize EN left):
- EN part: "50977-565-45BH or 50977-565-45SH" → use "50977-565-45BH"
- FR part: "50977-565-45BH ou 50977-565-45SH" → use "50977-565-45BH"
- Both EN and FR output: "50977-565-45BH"

### Divergence Detection & Reporting

**Requirement:** Mark, report, and include divergence in output — do NOT exclude rows.

**Handling:**

1. **Divergence Types:**
   - **Cost Divergence:** List Price (EN) ≠ List Price (FR) = **ERROR** (zero tolerance)
   - **Dealer Net Divergence:** Dealer Net (EN) ≠ Dealer Net (FR) = **ERROR** (zero tolerance)
   - **FRT Divergence:** FRT (EN) ≠ FRT (FR) = **ERROR** (zero tolerance)
   - **Part Number Divergence:** EN part ≠ FR part after normalization = **WARNING**
   - **Description Divergence:** EN description ≠ FR description = **WARNING** (content difference expected, but needs review)

2. **Reporting:**
   - DQ logging: Record divergence type, values, and reconciliation decision
   - DQ rule: `cost_mismatch_rule`, `part_number_divergence_rule`, `description_divergence_rule`
   - Include in DQ sheet with severity level

3. **Output Behavior:**
   - ✅ **Include divergent rows** in output workbook (NOT excluded)
   - ✅ Mark in `merge_confidence` column (e.g., 0.75 = 75% confidence due to cost divergence)
   - ✅ Add DQ notes column with divergence details
   - ✅ Include full details in `raw_data` sheet (before reconciliation)
   - ✅ Workbook is "ready to upload" but requires human review of divergent rows

---

## 4. Composite Part Number Handling

### Priority Logic

**Requirement:** Same priority for both EN and FR.

**Rule:** **Left-priority** — use left-side before "or"/"ou" separator

**Examples:**
- EN: `"50977-565-45BH or 50977-565-45SH"` → `"50977-565-45BH"`
- FR: `"50977-565-45BH ou 50977-565-45SH"` → `"50977-565-45BH"`

**Implementation:**
- Create core utility: `normalize_composite_part_number(part_num, language: "EN"|"FR")`
- Split on case-insensitive "or" (EN) / "ou" (FR)
- Trim whitespace, take left side
- Handle edge cases: null, empty, malformed (see Phase 2 design doc)

**Config Impact:**
- `reconciliation.yaml`: `composite_part_number_priority: "left"`
- `step1_validation.py`: Apply normalization to all part numbers during ingestion

---

## 5. Applicability Markers (Trim Columns)

### Marker Values (CONFIRMED)

Found in the trim columns (after Installed Price, before Application):

```
✓   = Applicable (checkmark symbol, may encode as "✓", "•", "■", etc.)
N/A = Not Applicable
S   = Standard (accessory comes with trim)
T   = Tire Size Change (special condition)
E   = Exchange Standard Equipment (special condition)
```

**Legend from source file (Rows 5-8):**
- S = Standard (accessory comes with vehicle as standard for this trim)
- T = Tire Size Change (trim has different tire size)
- E = Exchange Standard Equipment (replaces factory standard equipment)
- N/A = Not Applicable (not available for this trim)

### Marker Detection

**Requirement:** Detect checkmark symbol (may be encoded differently per file).

**Implementation:**
- Read raw marker values from trim columns
- Normalize: checkmark variations (✓, •, ✔, check) → canonical "✓"
- Empty cells / spaces → treated as "N/A" (not applicable)
- Preserve S, T, E, N/A as-is

**Config Impact:**
- `trim_config.yaml`: Define all valid marker values and canonical form
- `step1_validation.py`: Detect and validate marker syntax
- `step3_standardization.py`: Normalize checkmark encoding

---

## 6. Metadata Extraction

### File-Level Metadata

Extract from the APP sheets (EN or FR):

- **Model Name:** (e.g., "Accord", "Civic", "CR-V", "Pilot", "Odyssey")
- **Model Year:** (e.g., 2026, 2025)

### Extraction Logic (Two-Level Fallback)

**Level 1 — Quick Scan (Top 5 Rows):**
1. Scan rows 1–5 of APP sheet
2. Look for keywords: "Model Name", "Model Year", "Nom du modèle", "Année modèle"
3. Extract adjacent cell value
4. If found → validate and use value, done

**Level 2 — Regex Search (If Level 1 Fails):**
1. Scan entire sheet for regex patterns:
   - Model Name: `(?i)(model\s*name|nom\s*du\s*modèle)\s*:?\s*([A-Za-z0-9\s\-]+)`
   - Model Year: `(?i)(model\s*year|année\s*modèle|MY|MY\d+)\s*:?\s*(\d{4})`
2. Extract matched group (captured value)
3. If found → validate and use value, done

**Validation & Failure:**
- Model Year must be in range 2020–2030
- Model Name must be non-empty (no format/list validation — accept any non-empty string)
- **If extraction fails at BOTH levels: raise DQ error, FAIL FILE** (metadata is required; no silent fallbacks)
- Log both attempts in DQ report so operator can debug

**Implementation (Step 1):**

```python
def extract_metadata(ws, sheet_name):
    """Extract model name and year from APP sheet.
    
    Two-level fallback (strict):
    1. Scan top 5 rows for keywords (quick, most common)
    2. Regex search entire sheet (thorough, if Level 1 fails)
    3. If both fail: raise error, fail file
    
    Args:
        ws: openpyxl worksheet object
        sheet_name: name of the sheet (for logging only)
    
    Returns:
        (model_name, model_year) tuple
        
    Raises:
        ValueError: if extraction fails at both levels
    """
    import re
    
    model_name = None
    model_year = None
    
    # Level 1: Top 5 rows - quick keyword scan
    for row_idx in range(1, 6):
        for cell in ws[row_idx]:
            if cell.value:
                cell_val = str(cell.value).lower()
                
                # Model Name keywords
                if "model name" in cell_val or "nom du modèle" in cell_val:
                    name_val = ws[row_idx][cell.column + 1].value
                    if name_val:
                        model_name = str(name_val).strip()
                
                # Model Year keywords
                if "model year" in cell_val or "année modèle" in cell_val:
                    year_val = ws[row_idx][cell.column + 1].value
                    if year_val:
                        model_year = str(year_val).strip()
        
        # Early exit if both found
        if model_name and model_year:
            return model_name, model_year
    
    # Level 2: Regex search entire sheet (if Level 1 incomplete)
    for row in ws.iter_rows(values_only=True):
        row_text = " ".join(str(cell or "") for cell in row)
        
        # Model Name regex (if not found yet)
        if not model_name:
            match = re.search(r"(?i)(model\s*name|nom\s*du\s*modèle)\s*:?\s*([A-Za-z0-9\s\-]+)", row_text)
            if match:
                model_name = match.group(2).strip()
        
        # Model Year regex (if not found yet)
        if not model_year:
            match = re.search(r"(?i)(model\s*year|année\s*modèle)\s*:?\s*(\d{4})", row_text)
            if match:
                model_year = match.group(2)
        
        # Exit early if both found
        if model_name and model_year:
            return model_name, model_year
    
    # Both levels failed - raise error
    if not model_name or not model_year:
        raise ValueError(
            f"Metadata extraction failed for sheet '{sheet_name}'. "
            f"Model Name found: {bool(model_name)}, Model Year found: {bool(model_year)}. "
            f"Checked: top 5 rows (keywords) and regex search (entire sheet)."
        )
    
    return model_name, model_year
```

**Config Impact:**
- `pipeline.yaml`: Metadata extraction keywords (EN/FR), regex patterns, validation rules
- `step1_validation.py`: Implement extraction logic with progressive fallback
- Metadata stored in file-level metadata dict for Step 3.5

**DQ Rules:**
- `metadata_extraction_rule`: Fires if Model Name or Year not found after all levels
- Severity: ERROR (file cannot be processed without metadata)
- Action: Fail file, log to DQ report

---

## 7. Sheet Naming Patterns

### Pattern (CONFIRMED)

**Format:** `{YEAR}MY_{MODEL}_APP_{LANG}`

**Examples:**
- `26MY_ACCORD_APP_EN` (Accord, 2026, English)
- `26MY_ACCORD_APP_FR` (Accord, 2026, French)
- `26MY_CIVIC_5D_APP_EN` (Civic 5D, 2026, English)

**Validation (Step 1):**
- Verify both EN and FR sheets exist for each model
- If missing EN or FR sheet: DQ error (cannot reconcile)
- Extract model name and year from sheet name for validation

---

## 8. Data Quality Rules (DQ Logging)

### Rules for Phase 3+ Validation

| Rule | Trigger | Severity | Action |
|------|---------|----------|--------|
| `missing_section_rule` | Section not found in file | FATAL | Fail file |
| `section_order_rule` | Sections out of order | WARNING | Log & continue |
| `missing_sheet_rule` | EN or FR sheet missing | FATAL | Fail file |
| `header_mismatch_rule` | Column headers differ from expected | WARNING | Log & continue |
| `cost_mismatch_rule` | EN List Price ≠ FR List Price | ERROR | Include row, mark divergence |
| `part_number_divergence_rule` | EN part ≠ FR part after normalization | WARNING | Include row, mark divergence |
| `marker_invalid_rule` | Trim marker not in {✓, N/A, S, T, E} | WARNING | Log & default to N/A |
| `metadata_extraction_rule` | Model Name or Year not found | ERROR | Fail file |
| `orphan_record_rule` | Row with no applicable trims across all sections | WARNING | Include row, flag for review |

---

## 9. Divergence Example (Full Scenario)

**EN Source Row (Accord, Packages section):**
```
Description: All-Weather Floor Mats (4-piece set)
Part Number: 08P17-30A-110
Dealer Net: 145.00
List Price: 189.99
FRT: 0.5
Installed Price: 287.48
Trim Columns (LX, SPORT, EX, TOURING):
  LX: ✓  SPORT: ✓  EX: N/A  TOURING: ✓
```

**FR Source Row (Same part):**
```
Description: Tapis toutes saisons (ensemble 4 pièces)
Num de pièce: 08P17-30A-110
Prix net: 145.00
Prix de liste: 209.99  <-- DIVERGENCE: 189.99 vs 209.99
T.F.F.: 0.5
Prix installé: 307.48
Trim Columns (LX, SPORT, EX, TOURING):
  LX: ✓  SPORT: ✓  EX: N/A  TOURING: ✓
```

**Output Behavior:**
1. ✓ Include row in output workbook (NOT excluded)
2. ✓ Use EN List Price: 189.99 (EN is primary per requirements)
3. ✓ Mark in DQ: `cost_mismatch_rule` — EN $189.99 vs FR $209.99, using EN value
4. ✓ Set merge_confidence: 0.75 (cost divergence detected)
5. ✓ Include in raw_data sheet with both EN and FR values, divergence marked
6. ✓ Human review required before final publishing

---

## 10. Config Files to Populate (Phase 3 Deliverable)

| File | Purpose | Status |
|------|---------|--------|
| `section_patterns.yaml` | Define 6 sections with EN/FR exact text | To create |
| `reconciliation.yaml` | EN/FR matching rules, composite part handling, cost rules | To create |
| `trim_config.yaml` | Trim marker definitions, tokenization, applicability logic | To create |
| `pipeline.yaml` | Error handling strategy, quarantine thresholds, metadata config | To create |
| `honda_translator.yaml` | Abbreviation mappings (create if needed) | To create |
| `honda_classification.yaml` | Token classifications (create if needed) | To create |

---

## Sign-Off

**Requirements Confirmed By:** User (makeville00@gmail.com)  
**Date:** 2026-09-24  
**Next Step:** Populate config files using these requirements

---

**Related Documents:**
- [Phase 1: Foundation & Setup](../PHASE_1_FOUNDATION.md)
- [Phase 2: Design Docs & Core Utilities](../PHASE_2_DESIGN_DOCS.md)
- [Honda Pipeline Modernization Plan](../HONDA_PIPELINE_MODERNIZATION.md)
