# Honda Data Cleaning Plan — Input/Process/Output Analysis

**Date:** 2026-10-15  
**Status:** Planning Phase  
**Objective:** Design comprehensive data cleaning strategy for Honda using patterns from existing OEMs + actual Honda data inspection

---

## Executive Summary

Honda's section-based data structure requires cleaning at **three distinct phases**:
1. **Phase 1 (Step 1):** Raw validation — detect structural issues
2. **Phase 2 (Step 2-3):** Standardization — normalize strings, types, encoding
3. **Phase 3 (Step 4+):** Transformation — melt, rollup, reconciliation

This document maps cleaning needs across all three phases using existing OEM patterns.

---

## PART 1: COMPARATIVE OEM CLEANING PATTERNS

### Hyundai/Genesis — Reference Implementation

**Config-Based Approach:**
- `hyundai/config/transformations.yaml` — Per-column operation pipeline
- `step3_standardization.py` — Applies configured transformations
- Pattern: trim_whitespace → standardize_case → standardize_abbreviations → deduplicate_words → remove_markup

**Implemented Operations:**
| Operation | Where | Example |
|-----------|-------|---------|
| **Trim whitespace** | Description, ModelName, PartNumber | "  Racing Package  " → "Racing Package" |
| **Standardize case** | Description, ModelName (title case) | "racing PACKAGE" → "Racing Package" |
| **Abbreviation standardization** | Description (HEV→Hybrid, e-sc→electric) | Uses translator.yaml (per-OEM) |
| **Deduplicate words** | Description | "Hybrid Hybrid" → "Hybrid" |
| **Remove markup** | Description | "(EN)" / "(FR)" tags stripped |
| **Type coercion** | Numeric columns | pd.to_numeric with error handling |
| **Trim applicability validation** | Trim columns | Flag records with all-empty trim columns |

**Error Handling:**
- Fatal: Cannot convert required column to declared type
- Warning: Trim applicability all-empty (excluded from output)

### Mitsubishi — Standardization Focus

**Differences from Hyundai:**
- Trim values forced to UPPERCASE (Mitsubishi uses "X" sentinels, not strings like "Preferred")
- No DQ logger integration (only PipelineLogger)
- No trim applicability validation (Mitsubishi has different trim structure)

**Code Pattern:**
```python
# Mitsubishi: force uppercase for trim sentinels
df[col] = df[col].apply(lambda v: v.upper() if isinstance(v, str) and v.strip() else v)

# Hyundai: preserve case (trim values are meaningful strings)
df[col] = df[col].apply(lambda v: str(v).strip() if isinstance(v, str) else v)
```

### Mazda — Minimal Cleaning (No Model Lookup)

**Why Minimal:**
- Model numbers pre-embedded in source data (no VehicleSearchEngine lookup)
- Less stringent standardization needed (internal reconciliation only)
- Config: `mazda_config.yaml` (simpler, fewer columns)

---

## PART 2: HONDA RAW DATA INSPECTION — Input Analysis

### Data Sample (26MY_CIV5D_APP_EN, rows 10-30)

**Actual Issues Found:**

1. **Newlines in Trim Names (Row 12)**
   ```
   Trim header cell value: "SPORT \nHybrid"  [contains literal \n]
   Should be:              "Sport Hybrid"     [newline removed, normalized case]
   ```
   - **Impact:** Header extraction fails if not stripped
   - **Root Cause:** Excel multi-line cell (Alt+Enter input)

2. **Special Unicode Characters (Row 12-13)**
   ```
   "16\" Enkei M52" → uses curly unicode quote (U+201D), not ASCII "
   "Platinum White Pearl (NH-883P)" → smart quotes, special symbols
   "Solar Reflection Silver" → various unicode spaces
   ```
   - **Impact:** String matching fails; encoding issues in downstream tools
   - **Fix:** Normalize to ASCII equivalents during Step 2

3. **Composite Part Numbers with Delimiters (Row 19)**
   ```
   Part Number: "480-670-6545-SP or 480-670-6545-GB"
   Should split to:
     - 480-670-6545-SP
     - 480-670-6545-GB
   OR use first value + note "or" in Comments
   ```
   - **Impact:** Duplicate-detection logic fails; part number matching breaks
   - **Rule:** Prioritize left value per existing config; note "or" cases in DQ

4. **Placeholder/Marker Characters (Column 9, Row 12-26)**
   ```
   "0"      → numeric placeholder (not trim value)
   "0.0"    → float placeholder
   "•"      → bullet applicability marker
   "✓"      → checkmark (unicode U+2713)
   ```
   - **Impact:** Confused with actual trim applicability values
   - **Fix:** Detect during validation; filter per section rules

5. **Empty Rows Between Data (Row 17, 21, 25)**
   ```
   All NaN → Separator between product groups
   ```
   - **Impact:** Should not count as data; currently causes 15+ false defects
   - **Fix:** Skip during classification (already implemented in Phase 2)

6. **Package Rollup Structure (Rows 18-24, 22-30)**
   ```
   Row 18: "25CIV-ENK-WTPK"  ← Package parent with part_number + prices
           "16° Enkei M52 Wheels & Michelin X-ICE Snow Tire Package"
           dealer_net=1596.56, list_price=2028
   
   Row 19: "480-670-6545-SP or 480-670-6545-GB"  ← Child 1 (wheels)
           "16" Enkei M52 Wheels - Silver or Gloss Black"
           NO prices (NaN)
   
   Row 20: "34417"  ← Child 2 (tires)
           "Michelin X-ICE Snow Tires - 215/55/16"
           NO prices (NaN)
   ```
   - **Impact:** Parent-child relationship must be detected and validated
   - **Fix:** Implemented in Phase 2 classification logic

7. **Comments with Newlines & Special Formatting (Row 26)**
   ```
   Comments: "Priced as a set of 4 wheels. \n\nIncludes body coloured front..."
   Should become: "Priced as a set of 4 wheels. Includes body coloured front..."
   ```
   - **Fix:** Normalize whitespace; strip excess newlines

### Data Quality Metrics

| Metric | Value | Status |
|--------|-------|--------|
| Total Rows | 171 | ✓ Within bounds (150-170) |
| Empty Rows | ~17 | ✓ Data cleanup, not defects |
| Rows with data | 128-130 | ✓ Classified correctly |
| Unicode issues | ~8-10 | ⚠️ Needs cleaning |
| Composite part numbers | ~3-5 | ⚠️ Needs splitting |
| Newline in headers | ~1-2 | ⚠️ Header extraction issue |

---

## PART 3: CLEANING STRATEGY — Process Design

### Three-Phase Approach (aligned with existing pipeline)

#### **Phase 1: Validation (Step 1)**
*Goal: Detect structural issues early; log for audit trail*

**Config Addition:** `upstream.yaml` → data_quality section

```yaml
data_quality:
  # Character encoding checks
  encoding_check:
    allowed_characters: "ASCII + common_unicode_symbols"
    suspicious_patterns:
      - "smart_quotes"      # U+201C, U+201D
      - "unicode_spaces"    # U+00A0, U+2000-200B
      - "multi_byte_chars"  # Non-UTF8
    action: "log_warning"   # Don't fail; flag for review

  # Row structure validation
  row_checks:
    - name: "empty_row_detection"
      rule: "Skip rows with all NaN or all whitespace"
      action: "skip"  # Don't count as defect

    - name: "placeholder_marker_detection"
      rule: "Trim columns with only '0', '0.0', '•', '✓' are not trim values"
      markers: ["0", "0.0", "•", "✓", "N/A"]
      action: "normalize_to_empty"

  # Content validation
  content_checks:
    - name: "composite_part_numbers"
      pattern: ".*\\s(or|ou)\\s.*"  # Detects "part1 or part2"
      action: "log_warning"
      note: "Will be split in Phase 2"
```

**Implementation:** `step1_validation.py` additions
```python
def _detect_encoding_issues(df):
    """Flag unicode/encoding problems for audit trail"""
    issues = []
    for col in df.columns:
        for idx, val in df[col].items():
            if isinstance(val, str):
                if has_smart_quotes(val):
                    issues.append({
                        'row': idx, 'col': col, 
                        'issue': 'smart_quotes',
                        'value': val
                    })
    return issues

def _detect_newlines_in_strings(df):
    """Flag literal \n in headers and descriptions"""
    # Used during header extraction validation
```

---

#### **Phase 2: Standardization (Step 2-3)**
*Goal: Normalize strings, types, encodings; prepare for transformation*

**Config Addition:** New file `standardization.yaml` (mirrors Hyundai pattern)

```yaml
columns:
  description:
    operations:
      - name: normalize_unicode
        from_chars: ["'", "'", """, """]  # Smart quotes
        to_chars: ["'", "'", '"', '"']     # ASCII equivalents
      - name: remove_newlines
        description: "Strip literal \\n from cell values"
      - name: normalize_whitespace
        collapse_multiple_spaces: true
      - name: trim_whitespace
      - name: standardize_case
        format: title_case
      - name: remove_markup
        markup_tags: ["(EN)", "(FR)"]
    validation:
      nullable: false
      minimum_length: 3

  part_number:
    operations:
      - name: split_composite
        delimiter: "or"  # Handle "part1 or part2"
        action: "keep_first_priority_left"
        note_in_comments: "Composite part number: {original}"
      - name: uppercase
      - name: trim_whitespace
    validation:
      nullable: false
      pattern: "^[A-Z0-9\\-]+$"

  dealer_net:
    operations:
      - name: numeric_conversion
        coerce_errors: "raise"  # Fail if non-numeric
      - name: validate_range
        min: 0
        max: 50000  # Upper bound for Honda parts
    validation:
      nullable: true
      type: float

  list_price:
    operations:
      - name: numeric_conversion
      - name: validate_range
        min: 0
        max: 50000
    validation:
      nullable: true
      type: float

  # TRIM COLUMNS (special handling)
  trim_columns:
    operations:
      - name: normalize_markers
        mapping:
          "•": "applicable"
          "✓": "applicable"
          "S": "standard"
          "T": "tire_change"
          "E": "exchange"
          "0": null
          "0.0": null
          "": null
          "N/A": null
      - name: preserve_case  # Keep original if meaningful trim value
      - name: skip_if_all_placeholder_markers
    validation:
      # Don't require non-null; trim columns can be empty

  comments:
    operations:
      - name: normalize_newlines
        replace_with: " "
      - name: trim_whitespace
      - name: collapse_multiple_spaces
    validation:
      nullable: true
      minimum_length: 5
```

**Implementation:** Create `step2_string_standardization.py`

```python
def run(df, config, meta_data, dq_logger, pipeline_logger):
    """Pre-step3: Normalize strings, encodings, and placeholder markers"""
    
    df = _normalize_unicode(df, config['unicode_mappings'])
    df = _remove_newlines(df)
    df = _normalize_whitespace(df)
    df = _split_composite_part_numbers(df, config, dq_logger)
    df = _normalize_trim_markers(df, config)
    
    return df

def _normalize_unicode(df, unicode_map):
    """Replace smart quotes, unicode spaces with ASCII"""
    for col in df.columns:
        df[col] = df[col].replace(unicode_map, regex=True)
    return df

def _split_composite_part_numbers(df, config, dq_logger):
    """Handle 'part1 or part2' → keep part1, note in comments"""
    original_composite = df[df['part_number'].str.contains('\\s(or|ou)\\s', regex=True)]
    
    for idx, row in original_composite.iterrows():
        parts = row['part_number'].split(' or ')
        primary = parts[0].strip()
        
        dq_logger.log_info(
            issue_description=f"Composite part number split",
            detail=f"Original: '{row['part_number']}' → Primary: '{primary}'",
            row_idx=idx
        )
        
        df.at[idx, 'part_number'] = primary
        df.at[idx, 'comments'] = f"{row.get('comments', '')} [Composite: {row['part_number']}]"
    
    return df

def _normalize_trim_markers(df, config):
    """Map special characters to canonical trim states"""
    trim_cols = config['trim_columns']
    marker_map = config['trim_marker_mapping']
    
    for col in trim_cols:
        df[col] = df[col].map(lambda v: marker_map.get(v, v) if pd.notna(v) else None)
    
    return df
```

---

#### **Phase 3: Classification & Transformation (Step 3-4)**
*Goal: Detect parent/child, melt to long format, prepare for lookup*

**Existing Step 3 Enhancement:**

```python
def _classify_record_type(row, config, section_name):
    """Determine if row is parent, child, subsection_label, or defect"""
    
    # PARENT: has description + part_number + (price OR child markers follow)
    has_description = pd.notna(row.get('description')) and row['description'].strip()
    has_part_number = pd.notna(row.get('part_number')) and row['part_number'].strip()
    has_price = pd.notna(row.get('dealer_net')) or pd.notna(row.get('list_price'))
    
    if has_description and has_part_number and has_price:
        return 'parent'
    
    # CHILD: has description + part_number but NO price (parent part provides it)
    if has_description and has_part_number and not has_price:
        return 'child'
    
    # SUBSECTION_LABEL: has description but no part_number or price
    if has_description and not has_part_number and not has_price:
        return 'subsection_label'
    
    # Skip completely empty rows (data cleanup, not defect)
    if not has_description and not has_part_number:
        return None  # Omit from record_types dict
    
    # DEFECT: missing product identification
    return 'defect'
```

---

## PART 4: INPUT/PROCESS/OUTPUT FLOW DIAGRAM

```
┌─────────────────────────────────────────────────────────────────┐
│                    PHASE 1: VALIDATION                          │
├─────────────────────────────────────────────────────────────────┤
│ INPUT:                                                          │
│   - Raw Excel file (26MY_CIV5D_APP_EN)                          │
│   - 171 rows, 17 columns, mixed data quality                    │
│                                                                  │
│ PROCESS:                                                        │
│   1. Detect encoding issues (smart quotes, unicode spaces)      │
│   2. Detect newlines in headers                                 │
│   3. Detect composite part numbers                              │
│   4. Detect empty rows (not counted as defects)                 │
│   5. Detect placeholder markers in trim columns                 │
│                                                                  │
│ OUTPUT:                                                         │
│   - Validation report (DQ log)                                  │
│   - Meta: encoding_issues=10, composite_parts=5, empty_rows=17  │
│   - File passes validation (not fatal errors)                   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│               PHASE 2: STANDARDIZATION                          │
├─────────────────────────────────────────────────────────────────┤
│ INPUT:                                                          │
│   - Validated df (128-130 data rows)                            │
│   - Contains unicode issues, newlines, composite parts          │
│                                                                  │
│ PROCESS (new step2_string_standardization.py):                  │
│   1. Normalize unicode (smart quotes → ASCII)                   │
│   2. Remove newlines from descriptions & trim names             │
│   3. Normalize whitespace (collapse, trim)                      │
│   4. Split composite part numbers (keep first, note in comment) │
│   5. Map trim markers (•,✓,0,0.0 → canonical states)            │
│   6. Type coercion (numeric columns → float, validate range)    │
│   7. Standardize case (title case for descriptions)             │
│   8. Remove markup tags ((EN)/(FR))                             │
│                                                                  │
│ OUTPUT:                                                         │
│   - Standardized df (clean strings, normalized types)           │
│   - DQ log: composite_parts_split=5, marker_normalizations=42   │
│   - Ready for Phase 3 (classification/rollup)                   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│          PHASE 3: CLASSIFICATION & TRANSFORMATION               │
├─────────────────────────────────────────────────────────────────┤
│ INPUT:                                                          │
│   - Standardized df (clean, normalized)                         │
│   - Still in wide format (one row per product, trims as columns)│
│                                                                  │
│ PROCESS (enhanced step3_standardization.py):                    │
│   1. Classify each row (parent/child/subsection_label/defect)   │
│   2. Validate parent-child relationships                        │
│   3. Detect orphaned children (parents missing)                 │
│   4. Flag trim applicability mismatches (child vs parent)       │
│   5. Validate rollup prices (sum children vs parent)            │
│                                                                  │
│ OUTPUT:                                                         │
│   - Classification metadata (record_types per row)              │
│   - DQ log: orphan_records=0, rollup_mismatches=0               │
│   - Parent/child structure validated & ready for melt           │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│              PHASE 4: TRANSFORMATION (Melt)                     │
├─────────────────────────────────────────────────────────────────┤
│ INPUT:                                                          │
│   - Classified wide-format df                                   │
│   - Columns: description, part_number, list_price, ...,         │
│              Sport, Touring, Touring Hybrid, Type R             │
│                                                                  │
│ PROCESS (enhanced step4_transformation.py):                     │
│   1. For each parent record, melt trim columns to rows          │
│   2. Create (part, trim_level) pairs                            │
│   3. Explode parent-child into separate rows (if needed)        │
│   4. Reconcile EN/FR versions (if applicable)                   │
│                                                                  │
│ OUTPUT:                                                         │
│   - Long-format df (one row per accessory-trim combo)           │
│   - Columns: part_number, description, trim_level, price,       │
│              source_file, section, model_year, vehicle_model    │
│   - Ready for model lookup enrichment                           │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│           PHASE 5: MODEL LOOKUP & OUTPUT                        │
├─────────────────────────────────────────────────────────────────┤
│ INPUT:                                                          │
│   - Long-format df (enrichment-ready)                           │
│   - Trim levels extracted (Sport, Touring Hybrid, Type R)       │
│                                                                  │
│ PROCESS (step4.5_model_enrichment.py):                          │
│   1. Tokenize trim level into keywords                          │
│   2. Query VehicleSearchEngine (make=Honda, year=2026, keywords) │
│   3. Resolve model numbers from DB                              │
│   4. Add merge confidence scores                                │
│                                                                  │
│ OUTPUT:                                                         │
│   - Final enriched df (with model_number, model_status)         │
│   - Written to Excel output (flat table)                        │
│   - DQ report (confidence scores, lookup misses)                │
└─────────────────────────────────────────────────────────────────┘
```

---

## PART 5: IMPLEMENTATION ROADMAP

### Configuration Files Required

1. **`accy_v2/oems/honda/config/schemas/upstream.yaml`** (UPDATE)
   - Add `data_quality` section with checks (encoding, newlines, composite parts)

2. **NEW: `accy_v2/oems/honda/config/standardization.yaml`**
   - Per-column transformation pipelines (mirrors Hyundai pattern)
   - Unicode mappings, trim marker mappings, validation rules

### Code Files Required

1. **`accy_v2/oems/honda/pipeline/step2_header_normalization.py`** (ALREADY EXISTS)
   - No changes needed; already handles header extraction

2. **NEW: `accy_v2/oems/honda/pipeline/step2_string_standardization.py`** (BEFORE step3)
   - Normalize unicode, remove newlines, split composite parts, map markers
   - **Or incorporate into step2** if preferred (consolidate normalization)

3. **`accy_v2/oems/honda/pipeline/step3_standardization.py`** (UPDATE)
   - Enhance classification logic (already done in Phase 2)
   - No additional changes needed for cleaning

### Testing Strategy

1. **Unit Tests:**
   - `test_unicode_normalization.py` — Smart quotes, unicode spaces
   - `test_newline_removal.py` — Descriptions, comments, headers
   - `test_composite_part_split.py` — "part1 or part2" handling
   - `test_trim_marker_normalization.py` — •, ✓, 0, 0.0 mappings

2. **Integration Tests:**
   - Run Phase 1-5 on CVIC5D.xlsx (actual data)
   - Verify 128-130 classified records (no false defects)
   - Verify 0 orphan records, 0 rollup mismatches
   - Inspect final output for clean strings & proper encoding

3. **Manual QA:**
   - Spot-check output Excel for:
     - No smart quotes (all normalized)
     - No literal newlines in cells
     - Composite parts properly split
     - Comments properly formatted

---

## PART 6: BENEFITS & RISK MITIGATION

### Benefits of This Approach

✅ **Follows existing patterns** — Uses Hyundai/Genesis config structure  
✅ **Config-driven, not hardcoded** — Easy to adjust without code changes  
✅ **Early detection** — Encoding/newline issues caught at validation time  
✅ **Auditable** — DQ log tracks every transformation  
✅ **Reusable** — Pattern can apply to other OEMs with different data formats  

### Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Composite part split loses information | Note original in Comments column + DQ log |
| Unicode normalization breaks encoding | Use well-tested Python unicodedata library + test vectors |
| Placeholder markers misidentified | Config-driven mapping; test against all known markers |
| Phase 2 still has false defects | Classification logic already fixed; cleaning removes noise |

---

## Summary: Three-Phase Cleaning Strategy for Honda

| Phase | Step | Input | Process | Output | New/Updated |
|-------|------|-------|---------|--------|------------|
| **1** | Step 1 | Raw Excel | Detect issues (encoding, newlines, composite) | Validation report, DQ log | UPDATE upstream.yaml |
| **2** | Step 2 | Validated df | Normalize unicode, split composite, map markers | Clean df, standardized | NEW standardization.yaml + NEW step2_string_standardization.py |
| **3** | Step 3 | Clean df | Classify rows, detect parents/children | Classification metadata | (Already done in Phase 2) |
| **4** | Step 4 | Classified df | Melt wide→long, explode rollups | Long-format df | (Existing step4, no changes) |
| **5** | Steps 4.5-5 | Long format | Model lookup, enrich, format output | Final Excel output | (Existing, no changes) |

**Effort Estimate:**
- Config updates: ~4 hours (standardization.yaml, upstream.yaml updates)
- Code implementation: ~8 hours (string standardization logic, unit tests)
- Integration testing: ~4 hours (full pipeline test, manual QA)
- **Total: ~16 hours**

---

