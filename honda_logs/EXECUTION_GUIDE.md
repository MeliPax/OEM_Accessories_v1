# Honda Pipeline - Execution & Debugging Guide

## What Was Done

I've fixed the pipeline code and added comprehensive logging to help debug issues:

### 1. Code Fixes

**Problem:** The pipeline was using the OLD STUB function that just set `model_number = trim name`

**Fixed In:**
- `scripts/honda_processor.py` (line ~1920)
- `scripts/honda_processor.ipynb` (Cell 4)

**Change:** Now calls `attach_model_number_with_matcher()` instead of `attach_model_number()`

### 2. Logging Added

The notebook now has logging at every critical step:

```
[MATCHER DEBUG] Starting model attachment for 217 rows
[MODEL ATTACHMENT] Processing 217 rows
[MODEL ATTACHMENT] Using matcher (db has 217 records)
[MATCHER DEBUG] Completed: 217/217 rows with model numbers
[MODEL ATTACHMENT] Sample model_numbers: ['YF9H5TK', 'FE2F5SJ', 'RS4H5RJS']
[EXCEL EXPORT] Saving sheet 'crv_2027': 217 rows x 7 cols
[EXCEL EXPORT] Column 'Model': 217 non-null values (sample: ['YF9H5TK', 'FE2F5SJ', ...])
```

## How to Run Now

1. **Open the notebook:**
   ```
   scripts/honda_processor.ipynb
   ```

2. **Run all cells** (Kernel → Restart & Run All)
   - This will execute the entire pipeline
   - Logging output will appear in the notebook

3. **Check the logs:**
   - **Console output** - See [MATCHER DEBUG] and [MODEL ATTACHMENT] messages
   - **honda_logs/debug.log** - Timestamped log file
   - **Output file** - Check `ready_to_upload/2026/Honda/Honda_Accessories-Upload_file-*.xlsx`

## What to Look For

### SUCCESS Indicators

You should see output like:

```
[MATCHER DEBUG] Starting model attachment for 217 rows
[MODEL ATTACHMENT] Using matcher (db has 217 records)
[MATCHER DEBUG] Completed: 217/217 rows with model numbers
[MODEL ATTACHMENT] Sample model_numbers: ['YF9H5TK', 'FE2F5SJ', 'RS4H5RJS']
[EXCEL EXPORT] Column 'Model': 217 non-null values
```

And the output Excel file should have:
- Column "Model" with values like: `YF9H5TK`, `FE2F5SJ`, `RS4H5RJS` (NOT trim names)
- 217 rows per model
- No NULL values in Model column

### FAILURE Indicators

Watch for these warning signs:

1. **Matcher never called:**
   ```
   [MODEL ATTACHMENT] Using stub (db is None)  ← PROBLEM: Database not loaded
   ```

2. **Zero model numbers attached:**
   ```
   [MATCHER DEBUG] Completed: 0/217 rows with model numbers  ← PROBLEM: Matching failed
   ```

3. **Trim names instead of codes:**
   ```
   [MODEL ATTACHMENT] Sample model_numbers: ['LX 2WD', 'EX', 'TOURING']  ← PROBLEM: Wrong column
   ```

4. **Excel has trim names in "Model" column:**
   ```
   [EXCEL EXPORT] Column 'Model': 217 non-null (sample: ['LX 2WD', 'EX', ...])  ← PROBLEM: Data not matched
   ```

## Troubleshooting Steps

### Step 1: Run the pipeline
```
1. Open scripts/honda_processor.ipynb
2. Click "Kernel → Restart & Run All"
3. Wait for completion
```

### Step 2: Check the logs
Look at the console output for any errors or warnings in the [MATCHER DEBUG] and [MODEL ATTACHMENT] lines.

### Step 3: Check output file
```
Open: ready_to_upload/2026/Honda/Honda_Accessories-Upload_file-*.xlsx
Check: Column "Model" should have codes like YF9H5TK, not trim names like LX
```

### Step 4: Debug if needed

If something fails, the logs will show exactly where:

- **No logs at all** → Notebook crashed or didn't run
- **[MATCHER DEBUG] missing** → Matcher function not called
- **0/217 rows with model numbers** → Matcher returned no matches
- **Trim names in model_numbers** → Wrong data source being used

## Log Files

All logs are saved to: `honda_logs/`

### File Structure
```
honda_logs/
├── debug.log              ← Latest run logs
├── pipeline_logger.py     ← Logging system
├── pipeline_hooks.py      ← Integration points
├── __init__.py
├── setup_logging.py
├── instrument_notebook.py
└── README.md
```

### Log Content

**debug.log** - Timestamped execution trace:
```
[2026-11-03 15:00:15] [MATCHER DEBUG] Starting model attachment for 217 rows
[2026-11-03 15:00:16] [MODEL ATTACHMENT] Using matcher (db has 217 records)
[2026-11-03 15:00:18] [MATCHER DEBUG] Completed: 217/217 rows with model numbers
...
```

## Next Actions

1. **Run the pipeline** with the notebook (all cells)
2. **Monitor the console output** for [MATCHER DEBUG] and [MODEL ATTACHMENT] messages
3. **Check the output file** to verify model numbers are populated
4. **If successful** - model numbers should be in the Excel file
5. **If failed** - the log messages will show exactly where it broke

## Questions?

The logging output will tell you:
- Which functions were called
- How many rows were processed
- Sample output values
- Any errors that occurred

Use this information to identify where the pipeline is failing.
