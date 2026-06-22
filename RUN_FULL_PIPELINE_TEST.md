# Complete Guide: Run Full Pipeline Test & Verify Model Number Captures

## 📋 Overview

This guide walks you through running the complete pipeline end-to-end and verifying that model numbers are captured for all records.

**Expected Result:** All (or nearly all) records should have `model_number` and `vehicle_year` columns populated.

---

## 🚀 Quick Start (3 Steps)

### Step 1: Setup Directories & Sample Data
```bash
python setup_test_data.py
```

**Output:** Creates landing_zone directories and sample test files

### Step 2: Populate Vehicle Database (One-time)
```bash
python -c "
import sys; from pathlib import Path
sys.path.insert(0, str(Path('model_lookup')))
sys.path.insert(0, '.')

from model_lookup.engine import load_env, create_engine_from_env
from model_lookup.models.manufacture_module import batch_save_manufacturer_models

load_env()
engine = create_engine_from_env()
batch_save_manufacturer_models(engine, ['Mitsubishi'], 'model_lookup/db/db_vehicle_models.csv')
print('Database populated!')
"
```

**Output:** `model_lookup/db/db_vehicle_models.csv` with vehicle models

### Step 3: Run Pipeline Test
```bash
python test_model_lookup_pipeline.py mitsubishi
```

**Output:** Complete pipeline execution with analysis report

---

## 📊 What You'll See

### Console Output Example:

```
================================================================================
MITSUBISHI PIPELINE TEST
================================================================================
File: accy_v2/data/landing_zone/mitsubishi/2026_Outlander_ES_EN.xlsx
Config: accy_v2/oems/mitsubishi/config/mitsubishi_config.json

✓ Pipeline execution completed

================================================================================
RESULTS ANALYSIS
================================================================================

DQ Report: accy_v2/output/dq_reports/mitsubishi/dq_report_abc123_20260622_153045.json

Total warnings in DQ report: 3
Model number lookup warnings: 3
  - No model found: 0
  - Ambiguous (multiple matches): 0
  - Lookup errors: 3

Output file: accy_v2/output/ready_to_upload/mitsubishi/Outlander_ES_EN.xlsx

Sheet 'Outlander_ES_EN':
  - Total records: 5
  - Records with model_number: 5          ← ALL CAPTURED!
  - Year range: 2026 - 2026

  Sample captured model numbers:
    - outlander_es / ES: CO45-B
    - outlander_es / SEL: CO45-C
    - outlander_es / Limited: CO45-D
    - outlander_es / ES: CO45-E
    - outlander_es / Limited: CO45-F

================================================================================
PIPELINE TEST SUMMARY
================================================================================
✓ Pipeline executed successfully

Next steps:
1. Check the DQ report for any excluded records
2. Review output file in: accy_v2/output/ready_to_upload/mitsubishi/
3. Verify model_number and vehicle_year columns are populated
```

---

## 🔍 Verify Model Number Capture

### Check Output File Directly

```python
import pandas as pd

# Read the output file
output_file = "accy_v2/output/ready_to_upload/mitsubishi/Outlander_ES_EN.xlsx"
df = pd.read_excel(output_file, sheet_name=0)

# Check what we captured
print(f"Total records: {len(df)}")
print(f"Records with model_number: {df['model_number'].notna().sum()}")
print(f"Records missing model_number: {df['model_number'].isna().sum()}")
print(f"Capture rate: {df['model_number'].notna().sum() / len(df) * 100:.1f}%")

# Show samples
print("\nSample captures:")
print(df[["model_name", "trim_level", "model_number"]].head(10))

# Show any that failed
if df['model_number'].isna().any():
    print("\nRecords without model_number:")
    print(df[df['model_number'].isna()][["model_name", "trim_level"]].head())
```

### Check DQ Report

```python
import json

# Read DQ report
dq_file = "accy_v2/output/dq_reports/mitsubishi/dq_report_*.json"  # Find latest
with open(dq_file, 'r') as f:
    dq = json.load(f)

# Analyze failures
warnings = dq.get('warnings', [])
model_warnings = [w for w in warnings if w.get('rule_violated') == 'model_number_lookup_rule']

print(f"Total model number lookup issues: {len(model_warnings)}")

for w in model_warnings:
    print(f"\nRow {w.get('record_index')}:")
    print(f"  Issue: {w.get('issue_description')}")
    print(f"  Details: {w.get('record_snapshot')}")
```

---

## 📈 Interpreting Results

### ✅ Excellent (95%+ capture)
```
Records with model_number: 95
Records missing model_number: 5
Capture rate: 95.0%
```
**Action:** All good! Ready for production

### ⚠️ Good (80-95% capture)
```
Records with model_number: 85
Records missing model_number: 15
Capture rate: 85.0%
```
**Action:** Review excluded records, update trim abbreviations if needed

### ⛔ Poor (<80% capture)
```
Records with model_number: 50
Records missing model_number: 50
Capture rate: 50.0%
```
**Action:** 
1. Check database is populated: `ls -la model_lookup/db/db_vehicle_models.csv`
2. Check trim names match database keywords
3. Review DQ report for error patterns

---

## 🔧 Common Issues & Fixes

### Issue 1: "No model found for 90% of records"

**Likely Cause:** Database is empty or trim names don't match

**Fix:**
```bash
# Verify database exists
ls -la model_lookup/db/db_vehicle_models.csv

# Check how many records are in database
wc -l model_lookup/db/db_vehicle_models.csv

# If empty or missing, repopulate:
python -c "
import sys; from pathlib import Path
sys.path.insert(0, str(Path('model_lookup')))
sys.path.insert(0, '.')
from model_lookup.engine import load_env, create_engine_from_env
from model_lookup.models.manufacture_module import batch_save_manufacturer_models
load_env()
engine = create_engine_from_env()
batch_save_manufacturer_models(engine, ['Mitsubishi'], 'model_lookup/db/db_vehicle_models.csv')
print('Done!')
"
```

### Issue 2: "Ambiguous match" for many records

**Likely Cause:** Your trim names are too generic (e.g., just "ES" when database has multiple "ES" variants)

**Fix:** Add more specific keywords or check if Package/Style columns can help distinguish

Update config (`accy_v2/oems/mitsubishi/config/mitsubishi_config.json`):
```json
{
  "model_lookup_rules": {
    "Mitsubishi": {
      "fields": ["trim", "model", "fuel_type", "package"],  // Add package
      "trim_abbreviation_library": {
        "p": "premium",
        "s": "sport",
        "n": "noir"  // Add more abbreviations
      }
    }
  }
}
```

Then run again: `python test_model_lookup_pipeline.py mitsubishi`

### Issue 3: "KeyError: Manufacturer not found"

**Likely Cause:** Mitsubishi database data not loaded

**Fix:**
```bash
# Check what's in the database
python -c "
import pandas as pd
df = pd.read_csv('model_lookup/db/db_vehicle_models.csv')
print('Unique manufacturers:', df['Manufacturer'].unique())
"

# If Mitsubishi is missing, populate it:
python -c "
import sys; from pathlib import Path
sys.path.insert(0, str(Path('model_lookup')))
sys.path.insert(0, '.')
from model_lookup.engine import load_env, create_engine_from_env
from model_lookup.models.manufacture_module import batch_save_manufacturer_models
load_env()
engine = create_engine_from_env()
batch_save_manufacturer_models(engine, ['Mitsubishi'], 'model_lookup/db/db_vehicle_models.csv')
"
```

### Issue 4: "ModuleNotFoundError: No module named 'model_lookup'"

**Likely Cause:** Running from wrong directory

**Fix:** Always run from project root
```bash
# ✓ Correct
cd /path/to/OEM_Accessories_v1
python test_model_lookup_pipeline.py mitsubishi

# ✗ Wrong - don't do this
cd /path/to/OEM_Accessories_v1/accy_v2
python run_mitsubishi.py
```

---

## 📁 Output Files to Review

After running the test, check these files:

### 1. **Final Output (Main Deliverable)**
```
accy_v2/output/ready_to_upload/mitsubishi/Outlander_ES_EN.xlsx
```
- Contains all records with model_number populated
- Ready to upload to rate system
- Check: Column "model_number" should be filled for all rows

### 2. **DQ (Data Quality) Report**
```
accy_v2/output/dq_reports/mitsubishi/dq_report_*.json
```
- Lists all warnings/issues
- Shows which rows failed model lookup and why
- Check: Should have zero "model_number_lookup_rule" warnings for success

### 3. **Pipeline Log**
```
accy_v2/output/pipeline_logs/mitsubishi/mitsubishi_*.log
```
- Detailed execution trace
- Check: Look for ERROR or FATAL entries

### Example Success Log:
```
[2026-06-22 15:30:45] ========== Pipeline Start ==========
[2026-06-22 15:30:45] Sheet: 2026_Outlander_ES_EN
[2026-06-22 15:30:46] Step 1 (Validation): 128 records validated
[2026-06-22 15:30:46] Step 2 (Header Normalization): Columns mapped
[2026-06-22 15:30:46] Step 3 (Standardization): Data normalized
[2026-06-22 15:30:47] Step 3.5 (Extract Year): vehicle_year = 2026
[2026-06-22 15:30:47] Step 4 (Transformation): 128 → 128 melted rows
[2026-06-22 15:30:48] Step 4.5 (Model Enrichment): 128 → 125 with model_number
[2026-06-22 15:30:49] Step 5 (Output): Output prepared
[2026-06-22 15:30:50] ========== Pipeline Complete ==========
```

---

## 🔄 Workflow for Full Pipeline Testing

### First Run:
1. `python setup_test_data.py` → Create directories
2. Database setup → Populate vehicle models
3. `python test_model_lookup_pipeline.py mitsubishi` → Run test
4. Review output and DQ report
5. If needed, adjust config and repeat step 3

### Subsequent Runs:
1. Update test file (or use existing)
2. `python test_model_lookup_pipeline.py mitsubishi`
3. Check capture rate
4. If <90%, troubleshoot per issues above

### Production:
1. Replace test file with actual data
2. `python test_model_lookup_pipeline.py mitsubishi`
3. Verify capture rate >95%
4. Upload output file to rate system

---

## ✅ Pre-Flight Checklist

Before running, verify:

- [ ] Project root contains: setup_test_data.py, test_model_lookup_pipeline.py
- [ ] Directories exist: accy_v2/data/landing_zone/mitsubishi/, accy_v2/data/landing_zone/mazda/
- [ ] Test data file exists: accy_v2/data/landing_zone/mitsubishi/*.xlsx or accy_v2/data/landing_zone/mazda/*.csv
- [ ] Database file exists: model_lookup/db/db_vehicle_models.csv (or can be created)
- [ ] .env file exists with database credentials
- [ ] Can import model_lookup: `python -c "from model_lookup.engine import create_engine_from_env"`
- [ ] Python version >= 3.8
- [ ] pandas, openpyxl installed: `pip install pandas openpyxl`

---

## 🎯 Success Criteria

**Pipeline is successful when:**
- ✅ Test script runs without exceptions
- ✅ Output file created in: accy_v2/output/ready_to_upload/
- ✅ model_number column populated for ≥95% of records
- ✅ vehicle_year column populated for 100% of records
- ✅ DQ report has ≤0-5 model_number_lookup_rule warnings

---

## 📞 Need Help?

1. **Check this document** - Common issues section
2. **Review logs** - accy_v2/output/pipeline_logs/
3. **Read DQ report** - accy_v2/output/dq_reports/
4. **Check QUICK_START.md** - Quick reference
5. **Check READINESS_CHECKLIST.md** - Detailed troubleshooting
6. **Check IMPLEMENTATION_SUMMARY.md** - Architecture details

---

## 🚀 Ready to Run?

```bash
# Step 1: Setup
python setup_test_data.py

# Step 2: Populate database (if needed)
python -c "..."  # See Step 2 above

# Step 3: Run pipeline
python test_model_lookup_pipeline.py mitsubishi

# Step 4: Check results
# Review: accy_v2/output/ready_to_upload/mitsubishi/
#         accy_v2/output/dq_reports/mitsubishi/
```

**Go!** 🚀
