# Update STEP1_LOADING_PLAYGROUND.ipynb

## Overview
The notebook currently loads data from an outdated path. Update it to use the correct data source:

**Old:** `landing_zone/2026/Honda/` (relative path, old files)
**New:** `accy_v2/data/landing_zone/honda/may_2026/` (correct data source)

---

## Changes to Make

### Step 1: Replace the File Loading Cell

Find the cell that starts with:
```python
# Find all Honda files
landing_zone = Path("../../../landing_zone/2026/Honda")
```

**REPLACE IT WITH:**

```python
# ============================================================================
# LOAD CIVIC 5D FROM CORRECT DATA SOURCE (may_2026)
# ============================================================================

from pathlib import Path
import pandas as pd

landing_zone = Path("accy_v2/data/landing_zone/honda/may_2026")
civic_5d_file = landing_zone / "CVIC5D.xlsx"

print(f"Loading from: {landing_zone.resolve()}\n")

if not civic_5d_file.exists():
    print(f"[ERROR] File not found")
    exit(1)

print(f"[OK] File found: {civic_5d_file.name}")
print(f"  Size: {civic_5d_file.stat().st_size / (1024**2):.2f} MB")
print(f"  Location: {landing_zone.resolve()}\n")

# List all files
excel_files = list(landing_zone.glob("*.xlsx*"))
print(f"Total Honda files in may_2026: {len(excel_files)}\n")

for i, file in enumerate(excel_files, 1):
    size_mb = file.stat().st_size / (1024**2)
    print(f"{i:2d}. {file.name:<50} ({size_mb:.2f} MB)")
```

---

### Step 2: Add Data Verification Cell

Add a **NEW CELL** after the loading cell with:

```python
# ============================================================================
# VERIFY DATA INTEGRITY
# ============================================================================

# Load EN sheet
xl = pd.ExcelFile(civic_5d_file)
en_sheets = [s for s in xl.sheet_names if "_APP_EN" in s]

if en_sheets:
    en_sheet = en_sheets[0]
    df_civic = pd.read_excel(civic_5d_file, sheet_name=en_sheet)
    
    print(f"\nSheet: {en_sheet}")
    print(f"Data shape: {len(df_civic)} rows x {len(df_civic.columns)} columns\n")
    
    # Verify Racing Package exists
    racing_found = df_civic.astype(str).apply(
        lambda row: any("Racing" in str(val) for val in row.values),
        axis=1
    ).any()
    
    if racing_found:
        print("[OK] Racing Package - Type R found in data")
    else:
        print("[ERROR] Racing Package not found")
    
    print(f"[OK] Data loaded successfully from may_2026 landing zone")
else:
    print("[ERROR] No EN sheet found")
```

---

## What Changed

| Item | Before | After |
|------|--------|-------|
| Landing Zone Path | `../../../landing_zone/2026/Honda` | `accy_v2/data/landing_zone/honda/may_2026` |
| File Name | `civic 5d.xlsx` (lowercase) | `CVIC5D.xlsx` (uppercase) |
| Total Rows | 147 | **170** |
| Racing Package | ❌ Missing | ✅ Present (Row 12) |
| Last Modified | May 25 | Sep 28 13:10 |

---

## Verification

After updating, run the cells and you should see:

```
[OK] File found: CVIC5D.xlsx
  Size: 5.17 MB
  Location: C:\Users\paxm\...\accy_v2\data\landing_zone\honda\may_2026

Total Honda files in may_2026: 1

[OK] Racing Package - Type R found in data

[OK] Data loaded successfully from may_2026 landing zone
```

---

## Files Reference

**Complete updated code:**
- `UPDATED_LOADING_CODE.py` - Complete loading section
- `STEP1_LOADING_PLAYGROUND_UPDATED.py` - Full working example

**Original playground:**
- `STEP1_LOADING_PLAYGROUND.ipynb` - Current notebook (needs updating)
