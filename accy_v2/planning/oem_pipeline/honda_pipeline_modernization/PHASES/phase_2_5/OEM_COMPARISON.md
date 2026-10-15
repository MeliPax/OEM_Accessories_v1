# OEM Data Cleaning Plans — Comparative Analysis

**Date:** 2026-10-15  
**Scope:** Hyundai, Genesis, Mitsubishi, Mazda  
**Format:** Config-based transformation pipelines (per-column operations)

---

## OVERVIEW: What All OEMs Share

All OEMs use the **SAME ARCHITECTURE**:
- **Config File:** `accy_v2/oems/{oem}/config/transformations.yaml`
- **Implementation:** `step3_standardization.py` (applies config operations)
- **Approach:** Per-column transformation pipelines (order matters)
- **Logging:** All transformations logged to DQ/pipeline logger

---

## DETAILED COMPARISON

### Common Operations (ALL OEMs)

| Operation | Applied To | Example |
|-----------|-----------|---------|
| **trim_whitespace** | ModelYear, ModelName, PartNumber, Description, Comments | `"  Racing  "` → `"Racing"` |
| **ensure_integer** | ModelYear | `"2026"` → `2026` |
| **validate_range** | ModelYear (2020-2100), MSRP, LaborHours (0-100) | Fails if out of range |
| **uppercase** | PartNumber | `"abc123"` → `"ABC123"` |
| **convert_to_float** | MSRP, DNET, LaborRate, LaborHours | `"123.45"` → `123.45` |
| **standardize_case** | ModelName, Description | `"SANTA FE"` → `"Santa Fe"` |

---

## OEM-SPECIFIC OPERATIONS

### Hyundai (FULL CLEANING)

**Features:**
- ✅ Abbreviation standardization (HEV→Hybrid, e-sc→Electric)
- ✅ Word deduplication (Hybrid Hybrid→Hybrid)
- ✅ Markup removal ((EN)/(FR) tags)
- ✅ Currency symbol removal ($, CAD, USD)
- ✅ French description support (Description_FR)

**Transformation Pipeline:**
```yaml
Description:
  operations:
    1. trim_whitespace
    2. standardize_case (title_case)
    3. standardize_abbreviations (config_file: translator.yaml)
    4. deduplicate_words
    5. remove_markup (tags: ["(EN)", "(FR)"])
  validation:
    - nullable: false
    - minimum_length: 5
```

**Example Flow:**
```
Raw:        "(EN) HEV  HEV HYBRID (FR)"
After #1:   "(EN) HEV HEV HYBRID (FR)"
After #2:   "(En) Hev Hev Hybrid (Fr)"
After #3:   "(En) Hybrid Hybrid (Fr)"      ← translator.yaml: HEV→Hybrid
After #4:   "(En) Hybrid (Fr)"
After #5:   "Hybrid"
Result:     "Hybrid" ✓
```

---

### Genesis (IDENTICAL TO HYUNDAI)

**Why identical?**
- Uses same config structure (DRY principle)
- Both are Hyundai Motor Group brands
- Same data quality issues

**Transformation Pipeline:** 100% identical to Hyundai

```yaml
# genesis/config/transformations.yaml is copy-paste of hyundai config
```

---

### Mitsubishi (SLIGHTLY DIFFERENT)

**Differences from Hyundai:**
| Aspect | Hyundai | Mitsubishi |
|--------|---------|-----------|
| **Abbreviations** | Yes (HEV→Hybrid, e-sc→Electric) | Yes (same translator.yaml) |
| **Word deduplication** | Yes | Yes |
| **Markup removal** | Yes (removes "(EN)"/"(FR)") | Yes (same) |
| **Currency symbols** | $, CAD, USD | $ only (no CAD/USD) |
| **Comments cleaning** | trim_whitespace only | trim_whitespace only |
| **French support** | Yes (Description_FR) | Yes (but note in config) |

**Key Note:** Config says "NO model lookup" but cleaning is identical
```yaml
# mitsubishi/config/transformations.yaml
# Note: Mitsubishi uses NO model lookup enrichment (use_model_lookup: false)
#       Source descriptions are English only; French is optional (no source)
```

**Practical Impact:** Mitsubishi data doesn't need model lookup because model numbers are already embedded in source data (no enrichment needed).

---

### Mazda (IDENTICAL APPROACH, DIFFERENT RATIONALE)

**Why Mazda also uses config-based approach:**
- Consistency with other OEMs
- Even though Mazda has `use_model_lookup: false`
- Same cleaning rigor applied

**Transformation Pipeline:** Same as Hyundai/Genesis/Mitsubishi

---

## GLOBAL SETTINGS (ALL OEMs)

Every `transformations.yaml` has:

```yaml
global:
  # Handle missing values during transformation
  missing_value_strategy:
    empty_string: "treat_as_null"      # "" → NULL
    "N/A": "treat_as_null"              # "N/A" → NULL
    "NA": "treat_as_null"               # "NA" → NULL
  
  # Log all transformation details for audit trail
  log_transformations: true             # DQ logging enabled
```

---

## COLUMN-BY-COLUMN BREAKDOWN

### ModelYear
```yaml
operations:
  - name: ensure_integer
  - name: validate_range
    min_value: 2020
    max_value: 2100
validation:
  nullable: false
```
**All OEMs:** Identical

---

### ModelName
```yaml
operations:
  - name: trim_whitespace
  - name: standardize_case
    format: title_case
validation:
  nullable: false
```
**All OEMs:** Identical

---

### PartNumber
```yaml
operations:
  - name: uppercase
  - name: trim_whitespace
validation:
  nullable: false
  pattern: "^[A-Z0-9-]+$"
```
**All OEMs:** Identical

---

### Description (MAIN CLEANING COLUMN)
```yaml
operations:
  - name: trim_whitespace
  - name: standardize_case
    format: title_case
  - name: standardize_abbreviations
    config_file: "${MODEL_LOOKUP_CONFIGS}/hyundai/translator.yaml"
  - name: deduplicate_words
  - name: remove_markup
    markup_tags: ["(EN)", "(FR)"]
validation:
  nullable: false
  minimum_length: 5
```

**All OEMs:** Identical (uses same translator.yaml)

**Key Transformations:**
1. ✅ Whitespace cleanup
2. ✅ Case standardization (Title Case)
3. ✅ Abbreviation expansion (HEV→Hybrid, N-line→N Line, etc.)
4. ✅ Duplicate word removal (caused by abbreviation expansion)
5. ✅ Language markup removal ((EN)/(FR) tags)

---

### Description_FR
```yaml
operations:
  - name: trim_whitespace
  - name: standardize_case
    format: title_case
  - name: standardize_abbreviations
  - name: deduplicate_words
  - name: remove_markup
    markup_tags: ["(EN)", "(FR)"]
validation:
  nullable: false
  minimum_length: 5
```

**All OEMs:** Identical to Description (same pipeline for both languages)

---

### MSRP
```yaml
operations:
  - name: convert_to_float
  - name: remove_currency_symbols
    symbols: ["$", "CAD", "USD"]  # Hyundai/Genesis
                   # or ["$"]      # Mitsubishi/Mazda
  - name: validate_range
    min_value: 0
    max_value: 1000000
validation:
  nullable: false
```

**Difference:** Hyundai/Genesis remove CAD/USD; Mitsubishi/Mazda only $ (currency context differs)

---

### DNET (Dealer Net)
```yaml
operations:
  - name: convert_to_float
  - name: remove_currency_symbols
    symbols: ["$", "CAD", "USD"]  # Hyundai/Genesis
                   # or ["$"]      # Mitsubishi/Mazda
validation:
  nullable: true  # Optional column
```

**All OEMs:** Same pattern as MSRP, but nullable=true

---

### LaborRate
```yaml
operations:
  - name: convert_to_float
validation:
  nullable: true
```

**All OEMs:** Identical

---

### LaborHours
```yaml
operations:
  - name: convert_to_float
  - name: validate_range
    min_value: 0
    max_value: 100
validation:
  nullable: false
```

**All OEMs:** Identical

---

### Comments & Comments_FR
```yaml
operations:
  - name: trim_whitespace
validation:
  nullable: true
```

**All OEMs:** Identical (minimal cleaning — just whitespace trim)

---

## MISSING FROM ALL OEMs

The following cleaning operations are **NOT** in any OEM config:

❌ Unicode normalization (smart quotes, unicode spaces)  
❌ Newline handling (literal \n in cells)  
❌ Composite part number splitting ("part1 or part2")  
❌ Placeholder marker detection (•, ✓, 0, 0.0)  
❌ Special character normalization  

**Why?** These issues don't occur in Hyundai/Genesis/Mitsubishi/Mazda data (or they were already pre-cleaned).

---

## STEP 3 IMPLEMENTATION

### Hyundai/Genesis (hyundai_genesis)
File: `accy_v2/oems/hyundai_genesis/pipeline/step3_standardization.py`

```python
def run(working_df, step2_result, config, meta_data, dq_logger, pipeline_logger):
    """Apply column mapping, enforce types, trim normalization, validate applicability"""
    
    col_mapping = step2_result["col_mapping"]
    valid_trim_cols = step2_result["valid_trim_cols"]
    
    df = _apply_col_mapping(working_df, col_mapping, valid_trim_cols)
    df = _enforce_data_types(df, config["col_data_type_dict"], group_key)
    df = _normalize_trim_values(df, valid_trim_cols)  # Strip whitespace, preserve case
    df = _validate_trim_applicability(df, valid_trim_cols, group_key, model_name, dq_logger)
    df = _drop_unwanted_columns(df, config, valid_trim_cols)
    
    return df
```

**Key Steps:**
1. ✅ Rename columns per mapping
2. ✅ Drop unmapped columns
3. ✅ Coerce types (to_string, to_float) with error handling
4. ✅ Normalize trim values (strip whitespace, preserve case)
5. ✅ Validate trim applicability (flag records with all-empty trims)
6. ✅ Drop unwanted columns (per config)

---

### Mitsubishi (mitsubishi)
File: `accy_v2/oems/mitsubishi/pipeline/step3_standardization.py`

```python
def run(working_df, step2_result, config, meta_data, pipeline_logger):
    """Apply column mapping, enforce types, standardize trim values"""
    
    col_mapping = step2_result["col_mapping"]
    valid_trim_cols = step2_result["valid_trim_cols"]
    
    df = _apply_col_mapping(working_df, col_mapping, valid_trim_cols)
    df = _enforce_data_types(df, config["col_data_type_dict"], sheet_name)
    df = _standardize_trim_values(df, valid_trim_cols)  # Force UPPERCASE (different from Hyundai)
    df = _drop_unwanted_columns(df, config, valid_trim_cols)
    
    return df
```

**Key Difference:** `_standardize_trim_values` forces uppercase (Mitsubishi uses X sentinels, not readable trim names)

---

### Mazda (mazda)
File: `accy_v2/oems/mazda/pipeline/step3_standardization.py`

**Same as Mitsubishi** (but Mazda doesn't use model lookup, so less critical)

---

## IMPLEMENTATION FLOW

All OEMs follow this pattern:

```
Step 2 Output (col_mapping, valid_trim_cols, normalized headers)
         ↓
    _apply_col_mapping()          ← Rename columns, drop unmapped
         ↓
   _enforce_data_types()           ← Coerce to int/float/string (catches errors)
         ↓
_normalize_trim_values()           ← Hyundai: strip; Mitsubishi: UPPERCASE
         ↓
_validate_trim_applicability()    ← Flag all-empty trim rows (Hyundai/Genesis only)
         ↓
_drop_unwanted_columns()          ← Remove columns per drop_columns config
         ↓
    Step 3 Output (cleaned df)
```

---

## Summary: What Existing OEMs DO Clean

| Category | Operation | Hyundai | Genesis | Mitsubishi | Mazda |
|----------|-----------|---------|---------|-----------|-------|
| **Strings** | Whitespace trim | ✓ | ✓ | ✓ | ✓ |
| **Strings** | Case standardization | ✓ | ✓ | ✓ | ✓ |
| **Strings** | Abbreviation expansion | ✓ | ✓ | ✓ | ✓ |
| **Strings** | Word deduplication | ✓ | ✓ | ✓ | ✓ |
| **Strings** | Markup removal | ✓ | ✓ | ✓ | ✓ |
| **Numbers** | Type conversion | ✓ | ✓ | ✓ | ✓ |
| **Numbers** | Currency symbol removal | ✓ | ✓ | ✓ | ✓ |
| **Numbers** | Range validation | ✓ | ✓ | ✓ | ✓ |
| **Trim** | Whitespace trim | ✓ | ✓ | ✓ | ✓ |
| **Trim** | Uppercase (Mitsubishi) | - | - | ✓ | ✓ |
| **Quality** | Trim applicability validation | ✓ | ✓ | - | - |

---

## Summary: What NO OEM Currently Cleans

| Issue Type | What's Missing | Why |
|-----------|-----------------|-----|
| **Encoding** | Unicode normalization (smart quotes) | No OEM data has this issue |
| **Formatting** | Newline removal (\n in cells) | Excel data pre-cleaned in source |
| **Parsing** | Composite part splitting ("X or Y") | Hyundai/Mitsubishi don't have this |
| **Markers** | Special character mapping (•,✓) | Not present in Korean/Japanese OEMs |
| **Sections** | Section-based data handling | Only Honda has sections |

---

## Recommendation for Honda

**Adopt the exact same pattern as Hyundai/Genesis** but ADD:

1. **Unicode Normalization** (new operation in Description)
   ```yaml
   - name: normalize_unicode
     from_chars: ["'", "'", """, """, "…"]
     to_chars: ["'", "'", '"', '"', "..."]
   ```

2. **Newline Removal** (new operation in Description & Comments)
   ```yaml
   - name: remove_newlines
     replace_with: " "
   ```

3. **Composite Part Number Handling** (new operation in PartNumber)
   ```yaml
   - name: split_composite
     delimiter: "or"
     action: "keep_first_priority_left"
   ```

4. **Trim Marker Mapping** (new operation in trim_columns)
   ```yaml
   - name: map_trim_markers
     mapping:
       "•": "applicable"
       "✓": "applicable"
       "0": null
       "0.0": null
       "N/A": null
   ```

**Result:** Honda uses exact same architecture as Hyundai, just with 4 additional operations for Honda-specific data issues.

