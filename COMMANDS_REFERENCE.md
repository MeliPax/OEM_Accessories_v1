# Quick Command Reference

## 📋 All Available Commands

### **1. Setup Test Environment**
```bash
python setup_test_data.py
```
Creates directories and sample test files.

---

### **2. Populate Vehicle Database** ⭐
```bash
# Single manufacturer
python populate_vehicle_database.py Mitsubishi

# Multiple manufacturers
python populate_vehicle_database.py Mitsubishi Mazda Honda

# See available manufacturers
python populate_vehicle_database.py --list

# Get help
python populate_vehicle_database.py --help
```

---

### **3. Run Pipeline Test**
```bash
# Test Mitsubishi
python test_model_lookup_pipeline.py mitsubishi

# Test Mazda
python test_model_lookup_pipeline.py mazda

# Test with specific file
python test_model_lookup_pipeline.py mitsubishi "accy_v2/data/landing_zone/mitsubishi/2026_Outlander_EN.xlsx"
```

---

## 🚀 Complete Workflow (3 Commands)

```bash
# 1. Setup
python setup_test_data.py

# 2. Populate database
python populate_vehicle_database.py Mitsubishi

# 3. Test
python test_model_lookup_pipeline.py mitsubishi
```

That's it! 🎉

---

## 📊 Output Locations

After running, check these directories:

```
# Test data input
accy_v2/data/landing_zone/mitsubishi/          ← Put your Excel files here
accy_v2/data/landing_zone/mazda/               ← Put your CSV files here

# Results output
accy_v2/output/ready_to_upload/mitsubishi/    ← Final output with model numbers
accy_v2/output/dq_reports/mitsubishi/         ← Quality report
accy_v2/output/pipeline_logs/mitsubishi/      ← Execution log

# Database
model_lookup/db/db_vehicle_models.csv         ← Vehicle model data
```

---

## 🔍 Verify Results

### Check if model numbers were captured
```python
import pandas as pd

df = pd.read_excel("accy_v2/output/ready_to_upload/mitsubishi/Outlander_ES_EN.xlsx")
print(f"Total: {len(df)}")
print(f"With model_number: {df['model_number'].notna().sum()}")
print(f"Capture rate: {df['model_number'].notna().sum()/len(df)*100:.1f}%")
```

### Check database is populated
```bash
wc -l model_lookup/db/db_vehicle_models.csv
```

---

## ⚡ Quick Reference Table

| Task | Command |
|------|---------|
| Setup | `python setup_test_data.py` |
| Add Mitsubishi | `python populate_vehicle_database.py Mitsubishi` |
| Add Mazda | `python populate_vehicle_database.py Mazda` |
| Add Multiple | `python populate_vehicle_database.py Mitsubishi Mazda Honda` |
| List Available | `python populate_vehicle_database.py --list` |
| Test Mitsubishi | `python test_model_lookup_pipeline.py mitsubishi` |
| Test Mazda | `python test_model_lookup_pipeline.py mazda` |
| Test Help | `python test_model_lookup_pipeline.py --help` |

---

## 📚 Documentation

- **Quick Start** → [QUICK_START.md](QUICK_START.md)
- **Full Guide** → [RUN_FULL_PIPELINE_TEST.md](RUN_FULL_PIPELINE_TEST.md)
- **Database Commands** → [DATABASE_COMMANDS.md](DATABASE_COMMANDS.md)
- **Troubleshooting** → [READINESS_CHECKLIST.md](READINESS_CHECKLIST.md)

---

## 🎯 Most Common Usage

```bash
# First time
python setup_test_data.py
python populate_vehicle_database.py Mitsubishi Mazda
python test_model_lookup_pipeline.py mitsubishi

# Check results
cd accy_v2/output/ready_to_upload/mitsubishi/
# Open the Excel file and verify model_number column is filled
```

That's it! No more long commands. Just simple, clear commands for each task.
