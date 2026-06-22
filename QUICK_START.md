# Quick Start - Model Number Lookup Pipeline Test

## 🚀 One-Command Test

```bash
# From project root, test Mitsubishi pipeline
python test_model_lookup_pipeline.py mitsubishi

# Or test Mazda pipeline
python test_model_lookup_pipeline.py mazda
```

The test script will:

1. ✓ Run the full pipeline
2. ✓ Analyze results
3. ✓ Show model number capture statistics
4. ✓ Display samples of successful captures
5. ✓ Report any failures and why

---

## 📋 Prerequisites (Before First Run)

### 1. **Database with Vehicle Models**

The lookup database must have vehicle model data. Check if it exists:

```bash
ls -la model_lookup/db/db_vehicle_models.csv
```

**If it doesn't exist, create it:**

```python
# Run this once to populate the database
python -c "
import sys
from pathlib import Path

project_root = Path.cwd()
sys.path.insert(0, str(project_root / 'model_lookup'))
sys.path.insert(0, str(project_root))

from model_lookup.engine import create_engine_from_env
from model_lookup.models.manufacture_module import batch_save_manufacturer_models

# Load environment
from model_lookup.engine import load_env
load_env()

engine = create_engine_from_env()

# Save Mitsubishi models
print('Fetching Mitsubishi models...')
batch_save_manufacturer_models(engine, ['Mitsubishi'], csv_path='model_lookup/db/db_vehicle_models.csv')

print('Database populated!')
"
```

### 2. **Test Data Files**

#### For Mitsubishi:

Create `accy_v2/data/landing_zone/mitsubishi/` directory and add an Excel file with format:

- **Filename:** `YYYY_ModelName_Language.xlsx` (e.g., `2026_Outlander_ES_EN.xlsx`)
- **Structure:**
  - Row 1, Column A: Model name (e.g., "Outlander ES")
  - Row 2: Column headers
  - Row 3+: Data rows with trim columns (ES, SEL, Limited, etc.) containing "X" for applicable trims
  - Columns: Part Number, Description (EN/FR), MSRP, DNP, Install Time, Labour Rate, Trim columns

#### For Mazda:

Create `accy_v2/data/landing_zone/mazda/` directory and add a CSV file with columns:

- `ModelYear`, `CarLineCode`, `TrimLevel`, `PartNumber`, `AccessoryName`, etc.

### 3. **Environment Setup**

Ensure `.env` file exists in project root with:

```
DB_SERVER=your_server
DB_DATABASE=your_database
DB_USER=your_user
DB_PASSWORD=your_password
```

---

## 📊 Running the Test

### Basic Test (Auto-discovers most recent file)

```bash
python test_model_lookup_pipeline.py mitsubishi
```

### Test with Specific File

```bash
python test_model_lookup_pipeline.py mitsubishi "accy_v2/data/landing_zone/mitsubishi/2026_Outlander_ES_EN.xlsx"
python test_model_lookup_pipeline.py mazda "accy_v2/data/landing_zone/mazda/mazda_data.csv"
```

---

## 📈 Understanding the Output

The test script will show:

### 1. Pipeline Execution

```
================================================================================
MITSUBISHI PIPELINE TEST
================================================================================
File: accy_v2/data/landing_zone/mitsubishi/2026_Outlander_ES_EN.xlsx
Config: accy_v2/oems/mitsubishi/config/mitsubishi_config.json

✓ Pipeline execution completed
```

### 2. Results Analysis

```
================================================================================
RESULTS ANALYSIS
================================================================================

DQ Report: accy_v2/output/dq_reports/mitsubishi/dq_report_abc123_20260622_153045.json

Total warnings in DQ report: 5
Model number lookup warnings: 3
  - No model found: 2
  - Ambiguous (multiple matches): 1
  - Lookup errors: 0

Sample 'No Match' Failures:
  - Row 45: No model number found for Mitsubishi 2026 keywords=['outlander', 'noir_special']
    trim_level: NOIR_SPECIAL

Sample 'Ambiguous Match' Failures:
  - Row 78: Ambiguous match (2 results) for keywords=['outlander', 'es']: ['CO45-B', 'CO45-C']

Output file: accy_v2/output/ready_to_upload/mitsubishi/Outlander_ES_EN.xlsx

Sheet 'Outlander_ES_EN':
  - Total records: 128
  - Records with model_number: 125
  - Year range: 2026 - 2026

  Sample captured model numbers:
    - outlander_es / ES: CO45-B
    - outlander_es / SEL: CO45-C
    - outlander_es / Limited: CO45-D
```

### 3. Summary

```
================================================================================
PIPELINE TEST SUMMARY
================================================================================
✓ Pipeline executed successfully

Next steps:
1. Check the DQ report for any excluded records
2. Review output file in: accy_v2/output/ready_to_upload/mitsubishi/
3. Verify model_number and vehicle_year columns are populated
4. Check READINESS_CHECKLIST.md for troubleshooting
```

---

## 🎯 What to Check

### ✅ Success Indicators

- `✓ Pipeline executed successfully`
- "Records with model_number" ≈ "Total records" (allow for 0-5% exclusion)
- "Model number lookup warnings" = 0 or very low

### ⚠️ Warning Signs

- "No model found" > 10% of records → Check database has data, trim names match
- "Ambiguous match" > 5% → Trim names are too generic
- "Lookup errors" > 0 → Database or config issue

---

## 🔧 Troubleshooting

### Issue: "No .xlsx files found in accy_v2/data/landing_zone/mitsubishi/"

**Fix:** Create directory and add test Excel file

```bash
mkdir -p landing_zone/mitsubishi
# Add your Excel file there
```

### Issue: "ModuleNotFoundError: No module named 'model_lookup'"

**Fix:** Run from project root, not from subdirectory

```bash
# ✓ Correct
cd /path/to/project && python test_model_lookup_pipeline.py mitsubishi

# ✗ Wrong
cd /path/to/project/accy_v2 && python run_mitsubishi.py
```

### Issue: "Could not read output file"

**Fix:** Check that pandas can read Excel (may need openpyxl):

```bash
pip install openpyxl
```

### Issue: Most rows excluded with "No model found"

**Fix:**

1. Verify database is populated:
   ```bash
   ls -la model_lookup/db/db_vehicle_models.csv
   wc -l model_lookup/db/db_vehicle_models.csv
   ```
2. Check trim names in your Excel match database keywords
3. Review DQ report for exact keywords being searched

### Issue: "Ambiguous match" errors

**Fix:**

1. Your trim names are too generic
2. Add more specific keywords (Package, Style)
3. Update abbreviation library in config

---

## 📁 Output Locations

After running the test, check:

1. **Pipeline Log:**

   ```
   accy_v2/output/pipeline_logs/mitsubishi/*.log
   ```
2. **DQ (Data Quality) Report:**

   ```
   accy_v2/output/dq_reports/mitsubishi/*.json
   ```
3. **Final Output (Ready to Upload):**

   ```
   accy_v2/output/ready_to_upload/mitsubishi/*.xlsx
   ```

---

## 🔄 Workflow

### First Time:

1. ✓ Run prerequisites (populate database)
2. ✓ Prepare test data file
3. ✓ Run: `python test_model_lookup_pipeline.py mitsubishi`
4. ✓ Review output and DQ report
5. ✓ Adjust config if needed (abbreviations, year range, etc.)

### Subsequent Runs:

1. ✓ Update test data file or use existing
2. ✓ Run: `python test_model_lookup_pipeline.py mitsubishi`
3. ✓ Analyze results
4. ✓ Repeat until satisfied

### Production:

1. ✓ Run on full dataset
2. ✓ Monitor DQ report for issues
3. ✓ Upload final output files to rate system

---

## 📞 Need Help?

1. Check **READINESS_CHECKLIST.md** for detailed troubleshooting
2. Review **IMPLEMENTATION_SUMMARY.md** for architecture
3. Check pipeline logs: `accy_v2/output/pipeline_logs/`
4. Review DQ report: `accy_v2/output/dq_reports/`

---

**Ready? Run:** `python test_model_lookup_pipeline.py mitsubishi`
