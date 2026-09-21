# Fix: Absolute Paths Leak into Output Files (Excel + DQ Reports)

**Status:** Implemented  
**Branch:** `chore/hardcoded-path-fix`  
**Date Created:** 2026-08-27

## Problem

Output deliverables contain absolute local file paths instead of project-relative paths:

1. **Excel `_Report` sheet**: "Source File" cell shows full `C:\Users\paxm\OneDrive - PBS SYSTEMS\...\accy_v2\data\landing_zone\mitsubishi\Accessory Guide.xlsx`
2. **DQ Report JSON**: `source_file` field (top-level and per-record) contains the same absolute path

This makes deliverables non-portable and leaks local directory structure to users outside the dev environment.

## Solution Implemented

### Core Utility: `core/helpers/path_utils.py` (new)

Three functions for safe path conversion:

- **`get_project_root()`** — walks up from module location looking for `run_pipeline.py`, marks the `accy_v2/` directory
- **`to_relative_path(absolute_path)`** — strips project root, returns relative path with forward slashes (e.g., `accy_v2/data/landing_zone/file.xlsx`); returns original unchanged if path falls outside project root (handles edge cases like `"ADS API"` sentinel string gracefully via `except ValueError`)
- **`to_absolute_path(relative_path)`** — inverse operation for future read-back scenarios

### Changes

| File | Change |
|---|---|
| `accy_v2/core/helpers/output_writer.py` | Convert `source_file` to relative form before writing to Excel `_Report` sheet (line 176) |
| `accy_v2/core/helpers/dq_logger.py` | Convert `source_file` once in `__init__` (line 18), so both `log_warning()` records and `write_dq_report()` JSON payload use the relative form |

**Why single conversion in `__init__`?** Centralizes the conversion once per logger instance rather than at each use site, reducing risk of an absolute path slipping through a future third call.

**Why `to_relative_path()` handles non-paths gracefully?** `refresh_db_ads.py` creates `DQLogger(run_id, source_file="ADS API")` — a sentinel string, not a filesystem path. The utility's `except ValueError` fallback returns such strings unchanged, so no breakage.

## What Was NOT Changed (by design)

- **Internal file I/O** (`base_pipeline.py:171-175`): `config["output"]["ready_to_upload_path"]` etc. remain absolute — required for actual `Path(...).mkdir()` and `pd.ExcelWriter(file_path, ...)` calls.
- **Pipeline logs** (`pipeline_logger.py`): Still logs absolute `file_path` — these are internal developer/ops diagnostic logs, not shared deliverables, so not in scope.

## Verification

### Manual Test (required before merge)

```bash
cd accy_v2

# Run Mitsubishi pipeline
python run_mitsubishi.py

# Inspect output Excel (should have relative path in _Report sheet)
# Open: accy_v2/output/ready_to_upload/mitsubishi/mitsubishi_<run_id>_<timestamp>.xlsx
#   → _Report sheet, "Source File" row should read: accy_v2/data/landing_zone/mitsubishi/<filename>

# Inspect DQ report JSON (should have relative paths)
# Open: accy_v2/output/dq_reports/mitsubishi/dq_report_<run_id>_<timestamp>.json
#   → "source_file" field (top-level) should read: accy_v2/data/landing_zone/mitsubishi/<filename>
```

### Automated Checks

No new tests required — the fix is transparent to existing test suites. The changes affect only the *display* of paths in output; all file I/O uses absolute paths internally.

## Impact

✅ Excel deliverables now portable and shareable (no local path leakage)  
✅ DQ reports now portable (same fix)  
✅ All OEMs covered (Mitsubishi, Hyundai, Mazda, Honda) via shared module fix  
✅ Backward compatible (file I/O unchanged, only output display differs)  
✅ Edge case safe (`"ADS API"` and non-path strings pass through unchanged)  

