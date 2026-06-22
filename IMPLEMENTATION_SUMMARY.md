# Model Number Lookup Integration - Implementation Summary

## Overview
Successfully integrated model number lookup service into accy_v2 pipeline. The integration adds vehicle details enrichment with model numbers based on OEM-specific matching criteria.

---

## Files Created

### 1. Core Keyword Extraction
**File:** `accy_v2/core/helpers/keyword_extractor.py`
- **Purpose:** Extract and parse vehicle keywords from sheet names and trim data
- **Key Features:**
  - Sheet name parsing (YYYY_ModelName_Language format)
  - Fuel type keyword detection (EV, PHEV, etc.)
  - Composite trim parsing with underscore and dash delimiters
  - Abbreviation library support (e.g., "-p" → "premium")
  - Case-insensitive matching with deduplication
  - Comprehensive error handling and debug logging

**Class:** `KeywordExtractor`
**Main Methods:**
```python
extract_from_sheet_name(sheet_name) → {model_keywords, fuel_type}
extract_from_trim(trim_value) → [keywords]
combine_keywords(model_keywords, trim_keywords, fuel_type) → [all_keywords]
```

### 2. Pipeline Steps

#### Step 3.5 - Extract Vehicle Year

**Mitsubishi:** `accy_v2/oems/mitsubishi/pipeline/step3_5_extract_vehicle_year.py`
- Extracts 4-digit year from sheet name prefix (YYYY_...)
- Validates year is in reasonable range (1900-2100)
- Stores in `meta_data["vehicle_year"]`

**Mazda:** `accy_v2/oems/mazda/pipeline/step3_5_extract_vehicle_year.py`
- Checks for "model_year" column in data (CSV-specific)
- Falls back to sheet_name parsing if needed
- Handles CSV grouping by model

#### Step 4.5 - Model Number Enrichment & Validation

**Mitsubishi:** `accy_v2/oems/mitsubishi/pipeline/step4_5_model_enrichment.py`
- For each row (after trim melting in Step 4):
  1. Extract model keywords from sheet_name
  2. Extract trim keywords from trim column
  3. Call `search_models_by_description()` with combined keywords
  4. Validate exactly 1 match found
  5. Exclude rows with 0 or >1 matches
  6. Add `model_number` and `vehicle_year` columns

**Mazda:** `accy_v2/oems/mazda/pipeline/step4_5_model_enrichment.py`
- Same logic as Mitsubishi but with Mazda-specific model extraction

**Key Behaviors:**
- **0 matches:** DQ warning logged, row excluded
- **1 match:** ✓ Row kept with model_number populated
- **>1 matches:** DQ warning logged (ambiguous), row excluded
- **Lookup error:** DQ warning logged, row excluded

### 3. Base Pipeline Updates

**File:** `accy_v2/core/base_pipeline.py`
- Added abstract methods:
  - `run_step3_5_extract_vehicle_year()`
  - `run_step4_5_model_enrichment()`
- Updated `run()` method to call new steps in sequence:

```
Step 1 → Step 2 → Step 3 → Step 3.5 (Extract Year)
  → Step 4 (Transform/Melt) → Step 4.5 (Model Enrichment)
  → Step 5 (Output) → Write
```

### 4. OEM Pipeline Updates

**Mitsubishi Orchestrator:** `accy_v2/oems/mitsubishi/pipeline/orchestrator.py`
- Implements `run_step3_5_extract_vehicle_year()`
- Implements `run_step4_5_model_enrichment()`
- Imports new step modules

**Mazda Orchestrator:** `accy_v2/oems/mazda/pipeline/orchestrator.py`
- Same implementations as Mitsubishi
- Uses Mazda-specific step logic

---

## Configuration Updates

### Mitsubishi Config
**File:** `accy_v2/oems/mitsubishi/config/mitsubishi_config.json`

Added `model_lookup_rules` section:
```json
{
  "model_lookup_rules": {
    "Mitsubishi": {
      "sheet_name_format": "YYYY_ModelName_Language",
      "fuel_type_keywords": ["EV", "PHEV", "HEV", "FCEV"],
      "trim_abbreviation_library": {
        "p": "premium",
        "n": "noir",
        "m": "midnight",
        "s": "sport"
      },
      "fields": ["trim", "model", "fuel_type"],
      "trim_column": "trim_level",
      "exclude_keywords": []
    }
  }
}
```

### Mazda Config
**File:** `accy_v2/oems/mazda/config/mazda_config.json`

Added `model_lookup_rules` section with Mazda-specific settings

---

## Data Flow Example

### Input (After Step 4 Melting)
```
Sheet: "2026_Outlander_ES_EN"
Trim Column: "ES_GT-P"

Model keywords: ["outlander", "es"]
Fuel type: None
Trim keywords: ["es", "gt", "premium"]
Combined: ["outlander", "es", "gt", "premium"]
```

### Processing
```
search_models_by_description(
  make="Mitsubishi",
  year=2026,
  keywords=["outlander", "es", "gt", "premium"]
)
```

### Output Options
```
0 matches:  DQ Warning logged → Row EXCLUDED
1 match:    model_number="CO45-B" → Row KEPT with column added ✓
>1 matches: DQ Warning logged → Row EXCLUDED
```

---

## Key Features Implemented

### ✅ Exact Word Matching for Keywords
- Using word boundaries (regex `\b...\b`)
- "SE" ≠ "SEL"
- Applied to both model keywords and EV filtering

### ✅ OEM-Specific Configuration
- Each make has own `trim_abbreviation_library`
- Each make defines `fuel_type_keywords`
- Each make specifies `trim_column` name

### ✅ Composite Trim Parsing
Examples:
```
"ES"        → ["es"]
"ES_FWD"    → ["es", "fwd"]
"ES_GT-P"   → ["es", "gt", "premium"]  (if p→premium in library)
"ES-XYZ"    → ["es-xyz"]  (no match, kept as-is with warning)
```

### ✅ Fuel Type Handling
```
Sheet: "2026_Outlander_PHEV_EN"
Model keywords: ["outlander"]
Fuel type: "PHEV"
Search with: ["outlander", "phev"]
```

### ✅ Data Quality Reporting
All failures logged to DQ report:
- No model number found
- Multiple/ambiguous matches
- Keyword extraction failures
- Lookup errors
- Include row details for investigation

### ✅ Empty String Handling
- Filtered after all splits
- Whitespace stripped from all components
- Invalid keywords logged

### ✅ Case Normalization
- All keywords converted to lowercase
- Case-insensitive matching in lookup
- Consistent DQ logging

---

## Testing Recommendations

### Unit Tests
1. `KeywordExtractor.extract_from_sheet_name()`
   - Valid formats: "2026_Outlander_ES_EN"
   - Invalid formats: missing segments, non-numeric year
   - Fuel type detection: "2026_Model_PHEV_EN"

2. `KeywordExtractor.extract_from_trim()`
   - Simple: "ES" → ["es"]
   - Composite: "ES_GT-P" → ["es", "gt", "premium"]
   - Unmatched abbrev: "ES-XYZ" → ["es-xyz"] (warning logged)
   - Edge cases: empty strings, nulls, whitespace

3. `KeywordExtractor.combine_keywords()`
   - Deduplication: ["es", "es", "fwd"] → ["es", "fwd"]
   - Order preservation: first occurrence kept
   - Fuel type addition: present and correct

### Integration Tests
1. Step 3.5 extracts year and populates meta_data
2. Step 4.5 receives enriched data from Step 4
3. DQ warnings logged correctly for all failure scenarios
4. Final output has `model_number` and `vehicle_year` columns
5. Rows excluded correctly (0 or >1 matches)

### End-to-End Tests
1. Sample Mitsubishi Excel file with multiple trims
2. Verify each trim gets correct model_number
3. Verify DQ report captures all excluded rows
4. Verify final output has only complete rows

---

## Known Limitations & Future Enhancements

### Current Limitations
1. **Make extraction:** Hardcoded per OEM (works because each pipeline is OEM-specific)
2. **Abbreviation library:** Must be manually defined in config
3. **Fuel type keywords:** Must be listed in config
4. **Year extraction:** Assumes YYYY at start of sheet_name (Mitsubishi) or model_year column (Mazda)

### Future Enhancements
1. **Fuzzy matching:** Handle typos/partial matches in trim names
2. **Confidence scoring:** Return confidence level for matches
3. **Multiple year support:** If row has multiple possible years
4. **Interactive resolution:** UI to resolve ambiguous matches manually
5. **Learning:** Track which keyword combinations work best
6. **Performance caching:** Cache lookup results during batch processing

---

## Files Modified

| File | Change |
|------|--------|
| `core/base_pipeline.py` | Added abstract methods + updated run() |
| `oems/mitsubishi/pipeline/orchestrator.py` | Implemented new methods |
| `oems/mazda/pipeline/orchestrator.py` | Implemented new methods |
| `oems/mitsubishi/config/mitsubishi_config.json` | Added model_lookup_rules |
| `oems/mazda/config/mazda_config.json` | Added model_lookup_rules |

## Files Created

| File | Purpose |
|------|---------|
| `core/helpers/keyword_extractor.py` | Core keyword extraction logic |
| `oems/mitsubishi/pipeline/step3_5_extract_vehicle_year.py` | Year extraction for Mitsubishi |
| `oems/mitsubishi/pipeline/step4_5_model_enrichment.py` | Model lookup enrichment for Mitsubishi |
| `oems/mazda/pipeline/step3_5_extract_vehicle_year.py` | Year extraction for Mazda |
| `oems/mazda/pipeline/step4_5_model_enrichment.py` | Model lookup enrichment for Mazda |

---

## Next Steps

1. **Customize abbreviation libraries** - Update `trim_abbreviation_library` in each OEM config based on your vehicle data
2. **Customize fuel type keywords** - Ensure all applicable fuel types are listed
3. **Test with sample data** - Run pipeline on representative Excel/CSV files
4. **Validate DQ reports** - Check that excluded rows are correctly identified
5. **Extend to other OEMs** - Create step files for Honda, Kia, Toyota, etc.

---

**Status:** ✅ Implementation Complete
**Ready for:** Testing and Configuration
**Last Updated:** 2026-06-22
