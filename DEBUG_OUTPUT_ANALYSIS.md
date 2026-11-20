# Debug Analysis: Model Numbers Not Being Attached

## Current Status

**Last Output File:** `Honda_Accessories-Upload_file-2026-11-03_14-15-45.xlsx`

### What's Wrong

The output file still has **TRIM NAMES** instead of **MODEL NUMBERS**:

```
Model column values: 'LX 2WD', 'EX-L', 'LX AWD', 'AWD Sport'  ❌ WRONG (trim names)
Should be:         'YF9H5TK', 'FE2F5SJ', 'RS4H5RJS'         ✓ CORRECT (model codes)
```

### Root Cause

The matcher function is **NOT being called** - the code is using the stub function that returns trim names.

This happens when: `honda_models_db is None` in `create_ready_to_load_data()`

## How to Debug This

I've added a debug print statement to the notebook. When you run it, look for this output:

```
DEBUG: create_ready_to_load_data called with honda_models_db = DataFrame (None=False)
DEBUG: Database has 217 records
```

OR (if database is missing):

```
DEBUG: create_ready_to_load_data called with honda_models_db = NoneType (None=True)
```

---

## Step-by-Step Instructions

### 1. Run the Notebook with Debug Output

```
1. Open: scripts/honda_processor.ipynb
2. Kernel → Restart & Run All
3. Watch the console output
```

### 2. Look for These Messages in Console

**GOOD (database is being passed):**
```
DEBUG: create_ready_to_load_data called with honda_models_db = DataFrame (None=False)
DEBUG: Database has 217 records
[MODEL ATTACHMENT] Using matcher (db has 217 records)
[MATCHER DEBUG] Completed: 217/217 rows with model numbers
```

**BAD (database is None):**
```
DEBUG: create_ready_to_load_data called with honda_models_db = NoneType (None=True)
[MODEL ATTACHMENT] Using stub (db is None)
[MATCHER DEBUG] Completed: 0/217 rows with model numbers
```

### 3. Check Output File After Run

```
ready_to_upload/2026/Honda/Honda_Accessories-Upload_file-*.xlsx
```

- Look at the "Model" column
- Should show: `YF9H5TK`, `FE2F5SJ`, `RS4H5RJS`, etc.
- If still showing: `LX 2WD`, `EX`, `TOURING`, etc. → Matcher is not being called

---

## Possible Issues & Fixes

### Issue 1: Database Parameter Not Being Passed

**Symptom:** 
```
DEBUG: honda_models_db = NoneType (None=True)
```

**Fix:**
Check that `run_pipeline()` is passing the database:
```python
create_ready_to_load_data(
    extracted_results=extracted_results,
    config=config,
    output_dir=output_dir,
    honda_models_db=honda_models_valid,  # ← This must be present
)
```

### Issue 2: Database File Not Found

**Symptom:**
```
FileNotFoundError: models_catalogue/honda_models.csv not found
```

**Fix:**
Verify the file exists:
```
scripts/models_catalogue/honda_models.csv
```

Check it has data:
```python
import pandas as pd
df = pd.read_csv("scripts/models_catalogue/honda_models.csv")
print(f"Records: {len(df)}")
```

### Issue 3: Matcher Function Not Found

**Symptom:**
```
NameError: name 'attach_model_number_with_matcher' is not defined
```

**Fix:**
Verify the function is defined in the notebook. It should be in Cell with `match_vehicle` import.

---

## What to Do NOW

1. **Run the notebook** with the debug output
2. **Copy/paste the console output** here so I can see:
   - Whether database is being passed (None or DataFrame?)
   - What the matcher is returning
   - What's in the output file
3. **I'll diagnose** the exact issue based on the output

---

## Expected Success Criteria

When working correctly, you should see:

**Console Output:**
```
DEBUG: create_ready_to_load_data called with honda_models_db = DataFrame (None=False)
DEBUG: Database has 217 records
[MATCHER DEBUG] Starting model attachment for 217 rows
[MATCHER DEBUG] Completed: 217/217 rows with model numbers
```

**Output File (Model Column):**
```
YF9H5TK
YF9H5TK
FE2F5SJ
FE2F5SJ
RS4H5RJS
```

**Report Sheet:**
```
missing_model_number: False
rows_total: 217
```

---

## Summary

The code structure is correct, but something is preventing the database from being passed. The debug output will show exactly what's happening so we can fix it.

**Next step:** Run the notebook and share the console output.
