# Model Number Lookup Integration - Readiness Checklist

## ✅ Implementation Status

### Code Ready
- [x] KeywordExtractor class implemented
- [x] Step 3.5 (Extract Year) for both OEMs
- [x] Step 4.5 (Model Enrichment) for both OEMs  
- [x] Base pipeline updated with new steps
- [x] OEM orchestrators updated
- [x] Import paths fixed (model_lookup accessible)

### Configuration Ready
- [x] Mitsubishi config with model_lookup_rules
- [x] Mazda config with model_lookup_rules
- [x] Year range validation in config
- [x] Abbreviation libraries defined
- [x] Fuel type keywords defined

### Run Scripts Updated
- [x] run_mitsubishi.py - paths corrected
- [x] run_mazda.py - paths corrected
- [x] sys.path includes model_lookup directory

---

## ⚠️ Pre-Flight Checks Before Running

### 1. **Database Data** 
**CRITICAL:** The model_lookup database must be populated with vehicle model data.

Check:
```bash
# Verify you can connect to the database
python -c "
from model_lookup.engine import create_engine_from_env
engine = create_engine_from_env()
print('Database connection OK')
"
```

**Action Required:** 
- Ensure `model_lookup/db/db_vehicle_models.csv` exists and contains model data
- OR ensure the database has been populated via `batch_save_manufacturer_models()`

### 2. **Test Data Preparation**

**Action Required:**
- Place a test Excel file in: `accy_v2/data/landing_zone/mitsubishi/`
  - Example: `2026_Outlander_ES_EN.xlsx`
  - Must follow format: YYYY_ModelName_Language.xlsx
  
OR

- Place a test CSV file in: `accy_v2/data/landing_zone/mazda/`
  - Must have columns: ModelYear, CarLineCode, TrimLevel, etc.

### 3. **Configuration Verification**

Check the config values match your vehicle data:

**Mitsubishi** (`accy_v2/oems/mitsubishi/config/mitsubishi_config.json`):
```json
{
  "model_lookup_rules": {
    "Mitsubishi": {
      "valid_year_range": {"min": 1900, "max": 2100},
      "fuel_type_keywords": ["EV", "PHEV", "HEV", "FCEV"],
      "trim_abbreviation_library": {
        "p": "premium",
        "n": "noir",
        "m": "midnight",
        "s": "sport"
      },
      "trim_column": "trim_level"
    }
  }
}
```

**Mazda** (`accy_v2/oems/mazda/config/mazda_config.json`):
```json
{
  "model_lookup_rules": {
    "Mazda": {
      "valid_year_range": {"min": 1900, "max": 2100},
      "fuel_type_keywords": ["EV", "PHEV", "HEV"],
      "trim_abbreviation_library": {
        "p": "preferred",
        "s": "sport"
      },
      "trim_column": "trim_level"
    }
  }
}
```

### 4. **Column Names**

Verify your Excel/CSV files have the expected columns:

**Mitsubishi Excel:**
- Sheet name format: `YYYY_ModelName_Language` (e.g., "2026_Outlander_ES_EN")
- Trim columns: With "X" values for applicable trims (e.g., ES, SEL, Limited)
- Description columns: English/French descriptions

**Mazda CSV:**
- Column: `ModelYear` (or similar, configured as "model_year")
- Column: `CarLineCode` (or similar, becomes model name)
- Column: `TrimLevel` (or similar, configured as "trim_level")

### 5. **Environment Variables**

Ensure `.env` file exists with database credentials:
```
DB_SERVER=your_server
DB_DATABASE=your_database
DB_USER=your_user
DB_PASSWORD=your_password
```

---

## 🚀 How to Run

### From Project Root:

**Mitsubishi Pipeline:**
```bash
python accy_v2/run_mitsubishi.py
# or with specific file
python accy_v2/run_mitsubishi.py "accy_v2/data/landing_zone/mitsubishi/2026_Outlander_EN.xlsx"
```

**Mazda Pipeline:**
```bash
python accy_v2/run_mazda.py
# or with specific file
python accy_v2/run_mazda.py "accy_v2/data/landing_zone/mazda/mazda_accessory_feed.csv"
```

### Expected Output:
- ✅ Process runs without errors
- ✅ DQ report generated: `accy_v2/output/dq_reports/{oem}/{run_id}/`
- ✅ Pipeline log generated: `accy_v2/output/pipeline_logs/{oem}/`
- ✅ Output files generated: `accy_v2/output/ready_to_upload/{oem}/{model_name}_EN.xlsx`

Each row in output should have:
- `vehicle_year` column (extracted from sheet name)
- `model_number` column (looked up from model_lookup database)
- All standard columns from original input

---

## 🔍 Troubleshooting

### Issue: "No model number found" - Most Rows Excluded

**Likely Causes:**
1. Database is empty (no vehicle models loaded)
2. Trim names in your file don't match keywords in database
3. Abbreviation library doesn't cover your abbreviations

**Fix:**
1. Populate model_lookup database:
   ```python
   from model_lookup.models.manufacture_module import batch_save_manufacturer_models
   from model_lookup.engine import create_engine_from_env
   
   engine = create_engine_from_env()
   batch_save_manufacturer_models(
       engine, 
       ["Mitsubishi"],  # or ["Mazda"]
       csv_path="db/db_vehicle_models.csv"
   )
   ```
2. Check DQ report for which keyword combinations are failing
3. Update `trim_abbreviation_library` in config

### Issue: "Ambiguous match" - Multiple Models Found

**Likely Causes:**
1. Keywords are too generic
2. Multiple trim combinations match the same model number

**Fix:**
1. Review DQ report to see which keywords matched
2. Add more specific keywords or package/style info
3. Adjust abbreviation library to be more specific

### Issue: "Year out of valid range"

**Likely Causes:**
1. Sheet name has invalid year (e.g., "99999_Model")
2. valid_year_range in config is too narrow

**Fix:**
1. Check sheet name format
2. Adjust `valid_year_range` in config if needed

### Issue: Import Error - "No module named 'model_lookup'"

**Fix:**
1. Run from project root: `python accy_v2/run_mitsubishi.py`
2. Don't run from inside accy_v2 directory
3. Check that sys.path is correctly set in run script

---

## 📊 Success Indicators

Once you run the pipeline successfully, you should see:

1. **Pipeline Log** (accy_v2/output/pipeline_logs/{oem}/)
   ```
   [2026-06-22 15:30:45] Sheet processing started: "2026_Outlander_ES_EN"
   [2026-06-22 15:30:45] Extracted vehicle_year: 2026
   [2026-06-22 15:30:46] Step 4 complete: 128 rows melted
   [2026-06-22 15:30:47] Step 4.5: 125 rows with valid model_number, 3 excluded
   [2026-06-22 15:30:48] Sheet complete: 128 → 125 records
   ```

2. **DQ Report** (accy_v2/output/dq_reports/{oem}/)
   - Contains warnings for excluded rows
   - Shows which trims failed to find model numbers
   - Lists lookup errors if any

3. **Output File** (accy_v2/output/ready_to_upload/{oem}/)
   - Excel file with model_number and vehicle_year columns
   - Only includes rows with successful lookups
   - Ready to upload to rate system

---

## ✋ When NOT Ready

Do NOT run if:
- ❌ model_lookup database is empty
- ❌ No test data files available
- ❌ Database credentials not configured
- ❌ Column names don't match expected format
- ❌ Python imports still failing (check error messages)

---

## Next Steps After First Run

1. **Review DQ Report** - Check for excluded rows and understand why
2. **Update Abbreviation Library** - Add any new abbreviations found in your data
3. **Adjust Year Range** - If you have data outside current range
4. **Tune Fuel Keywords** - Add any fuel types specific to your OEM
5. **Run Full Dataset** - Once validated with sample

---

**Status:** Ready for testing with proper data preparation  
**Last Updated:** 2026-06-22
