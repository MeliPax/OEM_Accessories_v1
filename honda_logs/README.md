# Honda Pipeline Logging System

This logging system provides comprehensive tracking of the Honda accessory pipeline execution.

## Files

- **pipeline_logger.py** - Core logging functionality
- **pipeline_hooks.py** - Integration points for logging calls
- **instrument_notebook.py** - Script to add logging to the notebook
- **__init__.py** - Package initialization

## How to Use

### 1. Add logging imports to your notebook

At the start of your notebook (before running the pipeline), add:

```python
from honda_logs import (
    log_pipeline_start,
    log_excel_loading,
    log_models_database_loading,
    log_data_extraction_start,
    log_data_extraction_complete,
    log_ready_to_load_start,
    log_ready_to_load_complete,
    log_model_attachment_complete,
    log_pipeline_complete,
)
```

### 2. Add logging calls in run_pipeline()

At the START of `run_pipeline()`:
```python
log_pipeline_start(input_dir, output_dir, make)
```

After loading excel files:
```python
excel_dict = load_excel_files_to_dict(input_dir)
log_excel_loading(len(excel_dict), excel_dict)
```

After loading honda_models database:
```python
honda_models_valid = honda_models_df[honda_models_df["ModelName"].notna()].copy()
log_models_database_loading(honda_models_df)
```

Before data extraction:
```python
log_data_extraction_start()
extracted_results, failures = data_extract_orchestrator(...)
```

After data extraction:
```python
log_data_extraction_complete(extracted_results, failures)
```

Before build_ready_to_load:
```python
log_ready_to_load_start(len(extracted_results))
create_ready_to_load_data(...)
```

After build_ready_to_load:
```python
log_ready_to_load_complete(final_model_dfs, report_rows)
```

At the END of `run_pipeline()`:
```python
log_pipeline_complete()
```

### 3. Add logging to model attachment

In `create_ready_to_load_data()`, after attaching model numbers:

```python
df_trim_before = df_trim.copy()
df_trim = attach_model_number_with_matcher(df_trim, honda_models_db)
log_model_attachment_complete(model_key, df_trim_before, df_trim)
```

## Log Output

Logs are saved to `honda_logs/<timestamp>/` with the following files:

- **pipeline.log** - Full execution log (human-readable)
- **steps.json** - Pipeline steps with timestamps
- **data_checks.json** - Data quality checks
- **errors.json** - All errors encountered

## Example Log Output

```
2026-11-03 14:00:15 | INFO     | Pipeline logging initialized - Run: 2026-11-03_14-00-15
2026-11-03 14:00:15 | INFO     | Log directory: honda_logs/2026-11-03_14-00-15
2026-11-03 14:00:16 | INFO     | [STEP] load_excel_files - COMPLETED | {"files_loaded": 7, "models": [...]}
2026-11-03 14:00:17 | INFO     | Honda models database: 217/507 records valid
2026-11-03 14:00:18 | INFO     | [STEP] data_extraction - COMPLETED | {"successful_models": 6, "failed_models": 0}
2026-11-03 14:00:25 | INFO     | Model numbers attached: 217/217 (100%)
```

## Debugging

### Check for Model Number Attachment Failures

Look in `data_checks.json` for `attach_model_number_with_matcher` entries. Each entry shows:
- `non_null_model_numbers` - How many rows got model numbers
- `sample_model_numbers` - Examples of actual model numbers assigned
- `unique_model_numbers` - Count of unique model codes

### Check for Trim Names Instead of Model Numbers

If output shows trim names (LX, EX, SPORT) instead of model codes (YF9H5TK), the issue is:
1. Model numbers weren't attached (check `non_null_model_numbers` is 0)
2. OR the wrong column is being exported (check `has_model_col` in output checks)

### Trace Vehicle Matching

Look in `pipeline.log` for `[VEHICLE MATCH]` entries to see individual match results.

## Automatic Instrumentation

To automatically add logging calls to the notebook:

```python
from honda_logs.instrument_notebook import instrument_notebook
instrument_notebook("scripts/honda_processor.ipynb")
```

This will modify the notebook to include all logging calls at the correct locations.
