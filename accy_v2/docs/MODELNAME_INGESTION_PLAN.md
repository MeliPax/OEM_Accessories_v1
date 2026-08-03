# ModelName Ingestion & Database Refresh Plan

**Status:** Ready for Execution  
**Date:** 2026-07-28  
**Priority:** CRITICAL  
**Objective:** Capture ModelName in database to fix 0-candidate search failures  

---

## Overview

You've added `ModelName` extraction to `mapper.py`. This plan ensures it flows through the entire pipeline into the CSV database, and then verifies the fix works.

---

## Data Flow Path: Mapper → CSV

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. ADS API Response (from service.py)                           │
│    Raw JSON with style[] array containing trim objects           │
│    {                                                             │
│      "vehicleDescription": {                                    │
│        "style": [                                               │
│          {                                                      │
│            "bestModelName": "Elantra",       ← NEW SOURCE       │
│            "name": "Essential Ivt",                             │
│            "trim": "Essential",                                 │
│            "id": 449710,                                        │
│            ...                                                  │
│          }                                                      │
│        ]                                                        │
│      }                                                          │
│    }                                                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. mapper.py::ads_trim_to_row()                                 │
│    [Line 53] model_name = trim.get("bestModelName")             │
│    [Line 77] "ModelName": model_name or ""                      │
│                                                                 │
│    Returns dict:                                                │
│    {                                                            │
│      "Manufacturer": "HYUNDAI",                                │
│      "ModelYear": 2024,                                         │
│      "ModelNumber": "ELCS4V2BES00",                            │
│      "Description": "Essential Ivt",                            │
│      "TrimName": "Essential",                                   │
│      "Package": 449710,                                         │
│      "Drivetrain": "FRONT_WHEEL_DRIVE",                        │
│      "PassDoors": 4,                                            │
│      "ModelName": "Elantra"  ← ADDED BY YOUR CHANGE            │
│    }                                                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. mapper.py::ads_response_to_rows()                            │
│    Creates list of dicts from all style[] objects              │
│    [rows list with ModelName in each dict]                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. service.py::refresh_from_ads()                               │
│    [Line 110, 202, 266] calls ads_response_to_rows()            │
│    [Line 128, 142, 223, 277, 291] converts to pd.DataFrame()    │
│                                                                 │
│    DataFrame columns (including ModelName):                    │
│    [Manufacturer, ModelYear, ModelNumber, Description,         │
│     TrimName, Package, Drivetrain, PassDoors, ModelName]       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. refresh_db_ads.py                                            │
│    [Line 78] df = service.refresh_from_ads()                    │
│    [Line 83-88] save_vehicle_models_to_csv(df, ...)            │
│                                                                 │
│    Passes DataFrame with ModelName column to save function     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. manufacture_module.py::save_vehicle_models_to_csv()          │
│    [Line 273] Builds write_columns from existing + new columns  │
│                                                                 │
│    write_columns = sorted(set(existing_cols + df.columns))    │
│                                                                 │
│    Key line: df_valid = df_valid.reindex(                      │
│      columns=write_columns, fill_value=""                      │
│    )                                                            │
│    [Line 320] df_valid.to_csv(..., columns=write_columns)      │
│                                                                 │
│    This AUTOMATICALLY includes ModelName if present!           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 7. db_vehicle_models.csv                                        │
│    New schema (9 columns + ModelName = 10 columns total):       │
│                                                                 │
│    Description,Drivetrain,Manufacturer,ModelNumber,ModelYear,  │
│    Package,PassDoors,TrimName,ModelName                        │
│                                                                 │
│    Example rows:                                               │
│    Essential Ivt,FRONT_WHEEL_DRIVE,HYUNDAI,ELCS4V2BES00,2024,  │
│    449710,4,Essential,Elantra                                  │
│                                                                 │
│    ✓ ModelName now IN DATABASE!                               │
└─────────────────────────────────────────────────────────────────┘
```

---

## Why This Flow Works

1. **Mapper has access to data:** ADS API response includes `bestModelName` field ✓
2. **Your change extracts it:** `trim.get("bestModelName")` on line 53 ✓
3. **Dict includes it:** Line 77 adds `"ModelName": model_name or ""` ✓
4. **Service creates DataFrame:** `pd.DataFrame(rows)` includes all dict keys ✓
5. **Save function preserves it:** Dynamic column detection on line 273 ✓
6. **CSV gets written:** Includes ModelName in final file ✓

**No additional code changes needed** — your mapper.py change is sufficient! The rest of the pipeline automatically handles the new column.

---

## Step-by-Step Implementation Plan

### Phase 1: Verification (5 minutes)
Confirm mapper.py changes are correct

- [ ] Verify line 53: `model_name = trim.get("bestModelName")`
- [ ] Verify line 77: `"ModelName": model_name or ""`
- [ ] Confirm no syntax errors

**Action:**
```bash
cd accy_v2/model_lookup
python -m py_compile chrome_api/mapper.py
echo "✓ No syntax errors"
```

### Phase 2: Database Backup (2 minutes)
Archive current database before refresh

- [ ] Current CSV backed up automatically by refresh script
- [ ] Timestamp: `db_vehicle_models.{YYYY-MM-DD_HHMMSS}.csv` in archive/

**Action:**
```bash
# Already done by refresh_db_ads.py automatically
# But you can do it manually first if desired:
cp accy_v2/model_lookup/db/db_vehicle_models.csv \
   accy_v2/model_lookup/db/archive/db_vehicle_models.pre-modelname.csv
```

### Phase 3: Run Database Refresh (5-10 minutes)
Execute refresh with ModelName extraction enabled

**Command:**
```bash
cd accy_v2/model_lookup
python refresh_db_ads.py \
  --makes Hyundai Mazda Genesis Mitsubishi Honda \
  --years 2022 2023 2024 2025 2026 2027
```

**Expected Output:**
```
======================================================================
DATABASE REFRESH FROM ADS
======================================================================
Makes: Hyundai, Mazda, Genesis, Mitsubishi, Honda
Years: 2022, 2023, 2024, 2025, 2026, 2027
======================================================================

[1/4] Initializing ADS service...
      [OK] Credentials loaded and client initialized

[2/4] Archiving current database...
      [OK] Archived to: db_vehicle_models.2026-07-28_HHMMSS.csv

[3/4] Fetching data from ADS (this may take a moment)...
      [OK] Fetched 1143+ configurations

[4/4] Saving to database with validation...
      [OK] 1143+ records saved

======================================================================
[SUCCESS] DATABASE REFRESH COMPLETE
======================================================================
```

### Phase 4: Verify ModelName Was Captured (2 minutes)

**Check 1: Inspect CSV Header**
```bash
head -1 accy_v2/model_lookup/db/db_vehicle_models.csv
```

**Expected Output:**
```
Description,Drivetrain,Manufacturer,ModelNumber,ModelYear,Package,PassDoors,TrimName,ModelName
```

**Check 2: Count ModelName Values**
```bash
# Count non-empty ModelName entries
cut -d',' -f9 accy_v2/model_lookup/db/db_vehicle_models.csv | \
  grep -v "^ModelName$" | grep -v "^$" | wc -l
```

**Expected:** Should be close to total record count (e.g., 1100+)

**Check 3: Sample Data**
```bash
# Show first 5 data rows (skip header)
tail -n +2 accy_v2/model_lookup/db/db_vehicle_models.csv | head -5
```

**Expected Output:**
```
Essential Ivt,FRONT_WHEEL_DRIVE,HYUNDAI,EL74MF20A100,2022,424279,4,Essential,Elantra
Essential Manual,FRONT_WHEEL_DRIVE,HYUNDAI,EL74IF20A100,2022,424280,4,Essential,Elantra
Preferred Ivt,FRONT_WHEEL_DRIVE,HYUNDAI,EL74IF20A200,2022,424281,4,Preferred,Elantra
Preferred Ivt W/sun & Tech Package,FRONT_WHEEL_DRIVE,HYUNDAI,EL74IF20A283,2022,424282,4,Preferred,Elantra
Ultimate Ivt,FRONT_WHEEL_DRIVE,HYUNDAI,EL74IF20A400,2022,424283,4,Ultimate,Elantra
```

**Check 4: Verify All OEMs Have ModelName**
```bash
# Check unique manufacturers and sample model names
python3 << 'EOF'
import pandas as pd
df = pd.read_csv('accy_v2/model_lookup/db/db_vehicle_models.csv')
for mfr in sorted(df['Manufacturer'].unique()):
    df_mfr = df[df['Manufacturer'] == mfr]
    non_empty = (df_mfr['ModelName'] != '').sum()
    total = len(df_mfr)
    sample = df_mfr[df_mfr['ModelName'] != ''].iloc[0] if non_empty > 0 else None
    print(f"{mfr}: {non_empty}/{total} have ModelName", end="")
    if sample is not None:
        print(f" (e.g., {sample['ModelName']})")
    else:
        print(" (NONE!)")
EOF
```

**Expected Output:**
```
GENESIS: 159/159 have ModelName (e.g., G70)
HONDA: 217/217 have ModelName (e.g., Civic)
HYUNDAI: 384/384 have ModelName (e.g., Elantra)
MAZDA: 250/250 have ModelName (e.g., Mazda3)
MITSUBISHI: 133/133 have ModelName (e.g., Outlander)
```

### Phase 5: Test Search Now Works (3 minutes)

**Test 1: Python Search Test**
```python
import pandas as pd
from accy_v2.model_lookup.models.manufacture_module import search_models_by_description

# Test Hyundai Elantra Essential
results = search_models_by_description(
    make="Hyundai",
    year=2024,
    keywords=["elantra", "essential"],
    csv_path="accy_v2/model_lookup/db/db_vehicle_models.csv"
)

print(f"Hyundai Elantra Essential: {len(results)} candidates")
if len(results) > 0:
    print(f"  Sample: {results.iloc[0]['ModelNumber']}")
    print("  ✓ SEARCH WORKS!")
else:
    print("  ✗ STILL BROKEN")
```

**Expected Output:**
```
Hyundai Elantra Essential: 1 candidates
  Sample: ELCS4V2BES00
  ✓ SEARCH WORKS!
```

**Test 2: Test Multiple OEMs**
```python
test_cases = [
    ("Hyundai", 2024, ["elantra", "essential"]),
    ("Genesis", 2024, ["g70", "advanced"]),
    ("Mazda", 2024, ["cx-5", "preferred"]),
    ("Mitsubishi", 2024, ["outlander", "phev"]),
    ("Honda", 2024, ["civic", "lx"]),
]

for make, year, keywords in test_cases:
    results = search_models_by_description(make, year, keywords, ...)
    status = "✓" if len(results) > 0 else "✗"
    print(f"{status} {make} {year}: {len(results)} candidates")
```

### Phase 6: Run Pipeline (5-10 minutes)

Test that the full pipeline now works with ModelName in database

**Command:**
```bash
cd accy_v2/oems/hyundai
python -c "
from pipeline.orchestrator import HyundaiPipeline
pipeline = HyundaiPipeline()
result = pipeline.run('./data/landing_zone/hyundai/Hyundai.xlsx')
print(f'Pipeline exit code: {result}')
"
```

**Expected Behavior:**
- Pipeline logs show many models FOUND (not NOT_FOUND)
- Output Excel file has >400 rows (not 0)
- No 100% record exclusion

---

## Verification Checklist

After running all phases, verify:

- [ ] CSV header includes "ModelName" column
- [ ] 95%+ of records have ModelName populated (not empty)
- [ ] All OEMs have ModelName values (Hyundai, Genesis, Mazda, Mitsubishi, Honda)
- [ ] Search tests return >0 candidates (was 0 before)
- [ ] Hyundai pipeline output has >400 records (was 0)
- [ ] No "NOT_FOUND" warnings in pipeline logs (or dramatically reduced)

---

## Rollback (If Needed)

If something goes wrong:

```bash
# Restore previous database
cd accy_v2/model_lookup
cp db/archive/db_vehicle_models.*.csv db/db_vehicle_models.csv

# Revert mapper.py (if you want to undo the change)
git checkout chrome_api/mapper.py

# Re-run refresh without the change
python refresh_db_ads.py
```

---

## Why ModelName Fixes Everything

**Before:**
- Description: "Essential Ivt" (no model name)
- Search for: ["elantra", "essential"]
- Result: "elantra" NOT FOUND → 0 candidates → record excluded

**After:**
- Description: "Essential Ivt", ModelName: "Elantra"
- Search for: ["elantra", "essential"]
- Options:
  - Option A: Search includes ModelName field → "elantra" FOUND ✓
  - Option B: Combine Description + ModelName for search → works ✓
- Result: >1 candidate → record included ✓

---

## Timeline

| Phase | Task | Duration | Status |
|-------|------|----------|--------|
| 1 | Verify mapper changes | 5 min | |
| 2 | Backup database | 2 min | |
| 3 | Run refresh | 5-10 min | |
| 4 | Verify ModelName captured | 2 min | |
| 5 | Test search | 3 min | |
| 6 | Run full pipeline | 5-10 min | |
| **Total** | | **22-32 min** | |

---

## Questions Answered

**Q: Will ModelName automatically be saved to CSV?**  
A: Yes! The save function uses dynamic column detection (line 273 in manufacture_module.py). Any column in the DataFrame gets written to the CSV automatically.

**Q: Do I need to update the search function?**  
A: No changes required yet. The search function searches Description. Once we update it to search ModelName OR Description (or combined), it will work perfectly.

**Q: What if ADS doesn't have "bestModelName" for some records?**  
A: The code has `model_name or ""` fallback, so empty values are handled gracefully. Those records will have empty ModelName but won't cause errors.

**Q: Will this work for all OEMs?**  
A: Yes! The ADS API response includes "bestModelName" for all OEMs (Hyundai, Genesis, Mazda, Mitsubishi, Honda).

---

## Next Steps After Successful Refresh

1. **Update search function** to use ModelName in search (optional but recommended)
2. **Re-test pipeline** with multiple OEMs
3. **Monitor logs** for any issues
4. **Document in commit message** the ModelName addition

---

**Ready to execute? Run Phase 1 verification first, then proceed through phases 2-6.** 🚀
