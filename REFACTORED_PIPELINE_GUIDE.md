# Refactored Pipeline Guide

## Overview

The pipeline has been refactored to use **actual data flow** instead of creating test files. Model numbers are now looked up in **batch** (one per unique trim) before melting, then applied to all matching rows.

**Key Changes:**
- ✓ No sample files created in landing_zone
- ✓ Efficient batch model lookup (one per trim, not per row)
- ✓ Model numbers populated directly in output files
- ✓ `model_number_status` column shows success/failure visibility
- ✓ Missing trims excluded from output with clear DQ logging

---

## Quick Start

### 1. Prepare Database (One-Time)

```bash
python populate_vehicle_database.py Mitsubishi Mazda
```

### 2. Add Data Files

Place source files in landing_zone:
```
accy_v2/data/landing_zone/mitsubishi/2026_Outlander_ES_EN.xlsx
accy_v2/data/landing_zone/mazda/2026_CX-90_ES_EN.xlsx
```

### 3. Run Pipeline

```bash
python run_pipeline.py mitsubishi
python run_pipeline.py mazda
```

### 4. Analyze Results

```bash
python analyze_pipeline_results.py mitsubishi
python analyze_pipeline_results.py mazda
```

---

## Data Flow

### Before (Old Approach)
```
Step 3 → Create test file in landing_zone → External lookup → Add to output
```

### After (Refactored)
```
Step 3: Standardization
  ↓ (trim columns: ES, SEL, Limited, etc.)
Step 3.5: Extract Year
  ↓ (vehicle_year added to meta_data)
Step 4: Transformation (Melt Trims)
  ├─ Identify unique trims: ["ES", "SEL", "Limited"]
  ├─ Each row now has: part_number, description, trim, language
  ↓
[NEW] Batch Model Lookup
  ├─ For EACH unique trim (not per row):
  │   ├─ Extract keywords from sheet_name + trim
  │   ├─ search_models_by_description()
  │   ├─ Result: {"ES": "CO45-B", "SEL": "CO45-C", "Limited": None}
  ├─ Missing trims logged to DQ report
  ↓
Step 4.5: Model Enrichment
  ├─ Add model_number column (map from trim)
  ├─ Add model_number_status column
  ├─ Exclude rows where trim is missing
  ↓
Step 5: Output
  ├─ Create Excel with sheet names: "Outlander_EN", "Outlander_FR"
  ├─ Columns include: model_number, vehicle_year, model_number_status
  ↓
Output File (Ready to Upload)
  └─ Only rows with successful model lookups
  └─ DQ Report shows what failed and why
```

---

## Understanding the Output

### Output Excel File
**Columns:**
- `model_name`: Vehicle model (e.g., "Outlander")
- `sheet_name`: Original source sheet identifier
- `part_number`: OEM part number
- `description`: Part description
- `msrp`, `dnp`, etc.: Pricing/timing data
- `vehicle_year`: Model year (e.g., 2026)
- `trim_level`: Trim name (e.g., "ES", "SEL")
- `model_number`: Captured model number (e.g., "CO45-B")
- `model_number_status`: "yes - Model number found" or "no - missing model number"

**Note:** All rows have `model_number_status = "yes"` because rows with failures are excluded.

### DQ Report
Shows all issues encountered:

```json
{
  "warnings": [
    {
      "sheet_name": "2026_Outlander_ES_EN",
      "rule_violated": "model_number_lookup_rule",
      "details": {
        "trim_name": "Limited",
        "vehicle_year": 2026,
        "model_name": "Outlander",
        "keywords_searched": ["outlander", "limited"],
        "lookup_result": "no_match_found",
        "message": "No model found for 2026 Outlander Limited",
        "rows_excluded": 12
      }
    }
  ]
}
```

---

## How Batch Lookup Works

### Example: 2026 Mitsubishi Outlander

**Input Data (after melt):**
```
part_number | trim     | rows
ACC-001     | ES       | 45
ACC-002     | ES       | 12
ACC-003     | SEL      | 38
ACC-004     | Limited  | 25
ACC-005     | Limited  | 8
```

**Unique Trims:** `["ES", "SEL", "Limited"]`

**Batch Lookup (3 lookups total, not 128):**

```python
For trim "ES":
  keywords = extract_keywords(sheet_name="2026_Outlander_ES_EN", trim="ES")
  # → ["outlander", "es"]
  result = search_models_by_description(make="Mitsubishi", year=2026, keywords=[...])
  # → Found: CO45-B
  mapping["ES"] = "CO45-B"

For trim "SEL":
  keywords = ["outlander", "sel"]
  result = search_models_by_description(...)
  # → Found: CO45-C
  mapping["SEL"] = "CO45-C"

For trim "Limited":
  keywords = ["outlander", "limited"]
  result = search_models_by_description(...)
  # → Not found or ambiguous
  mapping["Limited"] = None
  missing_trims.append("Limited")
```

**Apply Mapping (Step 4.5):**
```
ACC-001 ES       → model_number = "CO45-B" ✓ included
ACC-002 ES       → model_number = "CO45-B" ✓ included
ACC-003 SEL      → model_number = "CO45-C" ✓ included
ACC-004 Limited  → EXCLUDED (trim missing)
ACC-005 Limited  → EXCLUDED (trim missing)

DQ Report: Limited trim excluded, 33 rows affected
```

**Output:** 95 rows (all 3 ACC-001, ACC-002, ACC-003 parts for valid trims)

---

## Keyword Extraction

The `KeywordExtractor` class handles:

### Sheet Name Parsing
```
Sheet: "2026_Outlander_ES_EN"
→ Year: 2026
→ Model keywords: ["outlander", "es"]
→ Fuel type: None

Sheet: "2026_Outlander_PHEV_EN"
→ Year: 2026
→ Model keywords: ["outlander"]
→ Fuel type: "PHEV"
```

### Trim Parsing
```
Trim: "ES" → ["es"]
Trim: "ES_GT-P" → ["es", "gt", "premium"] (if "p" → "premium" in library)
Trim: "Limited-AWD" → ["limited", "awd"]
```

### Combined Keywords
```
Sheet: "2026_Outlander_PHEV_EN"
Trim: "ES_GT-P"
Result: ["outlander", "es", "gt", "premium", "phev"]
```

---

## Configuration

Edit `accy_v2/oems/{oem}/config/{oem}_config.json`:

```json
{
  "model_lookup_rules": {
    "Mitsubishi": {
      "valid_year_range": [2015, 2030],
      "fuel_type_keywords": ["EV", "PHEV", "HEV"],
      "trim_abbreviation_library": {
        "p": "premium",
        "s": "select",
        "g": "grand",
        "t": "touring"
      }
    }
  }
}
```

---

## Troubleshooting

### Issue: "No model numbers captured"

**Possible Causes:**
1. Database not populated: `python populate_vehicle_database.py Mitsubishi`
2. Trim names don't match database: Check DQ report for actual keywords searched
3. Year not in database range: Check `valid_year_range` in config

**Debug:**
```bash
python analyze_pipeline_results.py mitsubishi
# Look at "Sample Failure Details" to see keywords being searched
```

### Issue: "Ambiguous match" (>1 results)

**Cause:** Keywords too generic (e.g., "SE" matches both "SE" and "SEL")

**Fix:**
1. Make trim names more specific in source data
2. Add more keywords via abbreviation library or sheet name
3. Update fuel_type_keywords to disambiguate if needed

### Issue: "No keywords extracted"

**Cause:** Sheet name format not matching expected pattern

**Expected Format:** `YYYY_ModelName_Language` where:
- `YYYY` = 4-digit year
- `ModelName` = Model name (and optional fuel type keywords)
- `Language` = Language code (EN, FR, etc.)

**Valid Examples:**
- `2026_Outlander_ES_EN.xlsx`
- `2026_Outlander_PHEV_EN.xlsx`
- `2026_CX-90_EN.csv`

### Issue: Some rows excluded but I expected them

**Check DQ Report:**
```bash
python analyze_pipeline_results.py mitsubishi
```

Look at "Sample Failure Details" to see:
- Which trim failed
- What keywords were searched
- Why it failed (no match vs. ambiguous)

---

## Files Modified/Created

### New Files:
- `run_pipeline.py` - Main pipeline runner
- `analyze_pipeline_results.py` - Results analysis tool
- `REFACTORED_PIPELINE_GUIDE.md` - This guide
- `IMPLEMENTATION_PLAN_FINAL.md` - Detailed architecture

### Modified Files:
- `accy_v2/core/helpers/keyword_extractor.py` - Added `extract_keywords_for_model_lookup()`
- `accy_v2/oems/mitsubishi/pipeline/step4_5_model_enrichment.py` - Batch lookup implementation
- `accy_v2/oems/mitsubishi/pipeline/step5_output.py` - Preserve model_number_status column

### Removed/Deprecated:
- `setup_test_data.py` - No longer needed
- `test_model_lookup_pipeline.py` - Replaced by `run_pipeline.py`

---

## Performance Characteristics

### Batch Lookup Efficiency

**Old Approach (per-row):**
- 100 rows, 1 trim type = 100 database queries

**New Approach (per-unique-trim):**
- 100 rows, 1 trim type = 1 database query
- 200 rows, 3 trim types = 3 database queries

**Efficiency gain:** Up to 100x fewer database queries

---

## Next Steps

1. ✓ Prepare database: `python populate_vehicle_database.py Mitsubishi Mazda`
2. ✓ Add source files to landing_zone
3. ✓ Run pipeline: `python run_pipeline.py mitsubishi`
4. ✓ Analyze results: `python analyze_pipeline_results.py mitsubishi`
5. ✓ Review output files in `accy_v2/output/ready_to_upload/`
6. ✓ Upload to rate system

---

## Support

For issues, check:
1. DQ Report: `accy_v2/output/dq_reports/{oem}/`
2. Pipeline Log: `accy_v2/output/pipeline_logs/{oem}/`
3. This guide's "Troubleshooting" section
