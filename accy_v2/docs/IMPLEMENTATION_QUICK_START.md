# Implementation Quick Start Guide

**Status:** Ready for execution  
**Priority:** CRITICAL (blocking all OEM pipelines)  
**Timeline:** 2-3 days to complete  

---

## What's Wrong (In 30 Seconds)

The database Description field has **no model names**:
- Database: `"Essential Ivt"` (trim descriptor only)
- Search looking for: `["elantra", "essential"]`
- Result: 0 candidates → all records excluded

---

## The Fix (In 30 Seconds)

Add model names back to the database:
- Database: `"Elantra Essential Ivt"` (model + trim descriptor)
- Search for: `["elantra", "essential"]`
- Result: Found! ✓

---

## Implementation Checklist

### Phase 1: Preparation (1 hour)
- [ ] Review OEM ModelNumber formats
- [ ] Extract model code patterns (EL→Elantra, etc.)
- [ ] Create model code lookup table per OEM

### Phase 2: Database Migration (1 hour)
- [ ] Backup current CSV
- [ ] Write `extract_model_name_from_model_number()` function
- [ ] Add ModelName column to CSV (1,143 rows)
- [ ] Verify all rows populated

### Phase 3: Code Updates (30 minutes)
- [ ] Update `search_models_by_description()` to use ModelName
- [ ] Update search field from Description → ModelName + Description

### Phase 4: Testing (1.5 hours)
- [ ] Smoke test: Hyundai Elantra search
- [ ] Run Hyundai pipeline end-to-end
- [ ] Verify output records > 0 (not 100% excluded)
- [ ] Run test suite

### Phase 5: Validation (1 hour)
- [ ] Check all OEMs (Hyundai, Genesis, Mazda, Mitsubishi, Honda)
- [ ] Verify DQ logs show found (not not_found)
- [ ] Document any OEM-specific quirks

---

## Files to Create/Modify

```
accy_v2/model_lookup/
├── db/
│   └── db_vehicle_models.csv
│       ADD: ModelName column
│
├── models/
│   └── manufacture_module.py
│       ADD: extract_model_name_from_model_number()
│       MODIFY: search_models_by_description()
│
└── scripts/
    └── migrate_add_model_names.py (NEW)
        Migration script to populate ModelName
```

---

## OEM ModelNumber Code Tables

### Hyundai
```
EL → Elantra        IO → Ioniq        SO → Sonata
TU → Tucson         KO → Kona         VE → Venue
SA → Santa Fe       EX → Excel        VL → Veloster
```

### Genesis
```
I5 → Ioniq5         G7 → G70          GV → GV70
G8 → G80            GV8 → GV80        GV6 → GV60
```

### Mazda
```
JYB → Mazda3        JYC → CX-5        JYD → CX-9
JYA → Mazda6        JYE → CX-30       JYF → CX-50
```

### Mitsubishi
```
CO → Outlander      OU → Outlander    EC → Eclipse Cross
PS → Pajero Sport   DL → Delica
```

### Honda
```
CT → Civic          RG → Accord       RZ → CR-V
JF → HR-V           RL → Ridgeline    TL → Passport
```

---

## Code Template: Phase 2 Implementation

### Step 1: Extract Model Name Function

```python
def extract_model_name_from_model_number(model_number: str, manufacturer: str) -> str:
    """
    Extract human-readable model name from OEM model code.
    
    Examples:
        Hyundai "ELCS4V2BES00" → "Elantra"
        Genesis "I5EW5ZE4PRLR" → "Ioniq5"
        Mazda "JYBBP5EX3C0" → "Mazda3"
    """
    if not model_number:
        return "Unknown"
    
    manufacturer = manufacturer.upper()
    
    if manufacturer == "HYUNDAI":
        prefix = model_number[:2].upper()
        codes = {
            "EL": "Elantra", "IO": "Ioniq", "SO": "Sonata",
            "TU": "Tucson", "KO": "Kona", "VE": "Venue",
            "SA": "Santa Fe", "EX": "Excel"
        }
        return codes.get(prefix, "Unknown")
    
    elif manufacturer == "GENESIS":
        prefix = model_number[:2].upper()
        codes = {
            "I5": "Ioniq5", "G7": "G70", "G8": "G80",
            "GV": "GV70"  # May need 3-char prefix for GV70 vs GV80
        }
        return codes.get(prefix, "Unknown")
    
    elif manufacturer == "MAZDA":
        prefix = model_number[:3].upper()
        codes = {
            "JYB": "Mazda3", "JYC": "CX-5", "JYD": "CX-9",
            "JYA": "Mazda6", "JYE": "CX-30"
        }
        return codes.get(prefix, "Unknown")
    
    elif manufacturer == "MITSUBISHI":
        # Mitsubishi format varies more; may need different parsing
        if model_number.startswith("CO"):
            return "Outlander"
        elif model_number.startswith("EC"):
            return "Eclipse Cross"
        # ... etc
        return "Unknown"
    
    elif manufacturer == "HONDA":
        # Honda format: typically first 2-3 chars
        prefix = model_number[:2].upper()
        codes = {
            "CT": "Civic", "RG": "Accord", "RZ": "CR-V",
            "JF": "HR-V"
        }
        return codes.get(prefix, "Unknown")
    
    return "Unknown"
```

### Step 2: Migration Script

```python
import pandas as pd
from pathlib import Path

def migrate_add_model_names():
    """Add ModelName column to existing database."""
    
    csv_path = Path("accy_v2/model_lookup/db/db_vehicle_models.csv")
    
    # Backup
    backup_path = csv_path.with_suffix(f".backup.{datetime.now().isoformat()}.csv")
    print(f"Backing up to: {backup_path}")
    csv_path.read_text()  # Verify readable
    csv_path.rename(backup_path)  # Move original
    
    # Load
    df = pd.read_csv(backup_path)
    print(f"Loaded {len(df)} records")
    
    # Add ModelName
    df['ModelName'] = df.apply(
        lambda row: extract_model_name_from_model_number(
            row['ModelNumber'], 
            row['Manufacturer']
        ),
        axis=1
    )
    
    # Verify
    unknown_count = (df['ModelName'] == 'Unknown').sum()
    if unknown_count > 0:
        print(f"⚠️  WARNING: {unknown_count} unknown model names")
        print(df[df['ModelName'] == 'Unknown'][['Manufacturer', 'ModelNumber']].head(10))
    
    # Save
    df.to_csv(csv_path, index=False)
    print(f"✓ Saved {len(df)} records to {csv_path}")
    print(f"✓ New schema: {df.columns.tolist()}")
    
    return backup_path

# Run migration
if __name__ == "__main__":
    backup = migrate_add_model_names()
```

### Step 3: Update Search Function

```python
def search_models_by_description(
    make: str, year: int, keywords: list[str], 
    csv_path: str = None, ...
) -> pd.DataFrame:
    """Search vehicle models in database."""
    
    df = load_existing_csv(csv_path)
    
    # Filter by manufacturer and year
    df_filtered = df[df["Manufacturer"].str.lower() == make.lower()].copy()
    df_filtered = df_filtered[df_filtered["ModelYear"] == year]
    
    # Search: NOW USE ModelName + Description instead of just Description
    for keyword in keywords:
        # Create combined search field
        search_field = df_filtered["ModelName"] + " " + df_filtered["Description"]
        
        # Search for keyword
        pattern = build_word_boundary_pattern(keyword)
        df_filtered = df_filtered[
            search_field.str.contains(pattern, case=False, na=False, regex=True)
        ]
    
    return df_filtered
```

---

## Testing Commands

### Test 1: Hyundai Elantra Essential
```python
from accy_v2.model_lookup.models.manufacture_module import search_models_by_description

results = search_models_by_description(
    make="Hyundai",
    year=2024,
    keywords=["elantra", "essential"],
    csv_path="accy_v2/model_lookup/db/db_vehicle_models.csv"
)

print(f"Found {len(results)} candidates")
# Expected: > 0 (was 0 before fix)
# Should show: Description='Essential Ivt', ModelName='Elantra', ModelNumber='ELCS4V2BES00'
```

### Test 2: Full Pipeline
```bash
cd accy_v2/oems/hyundai
python -c "from pipeline.orchestrator import HyundaiPipeline; p = HyundaiPipeline(); p.run('./data/landing_zone/hyundai/Hyundai.xlsx')"
```

### Test 3: Check Output Records
```python
import pandas as pd

# Check English output
en_output = pd.read_excel("output/processed_accessories/hyundai_en.xlsx")
print(f"Hyundai EN output: {len(en_output)} records")
# Expected: >400 (was 0 before fix)

# Check if model_number column populated
if 'model_number' in en_output.columns:
    found = (en_output['model_number'] != '').sum()
    print(f"  With model_number: {found} records")
```

---

## Success Validation Checklist

### Before Fix
```
Pipeline output: 0 records (all excluded)
Pipeline logs: [NOT_FOUND] for all trims
Database: Description="Essential Ivt" (no model name)
Search result: 0 candidates for any trim
```

### After Fix
```
✓ Pipeline output: >400 records (Hyundai)
✓ Pipeline logs: No [NOT_FOUND] errors
✓ Database: ModelName="Elantra" (populated)
✓ Search result: >1 candidate per trim
✓ All rows have model_number populated
```

---

## Rollback Procedure (If Needed)

```bash
# Restore from backup
cp db_vehicle_models.backup.*.csv db/db_vehicle_models.csv

# Revert code changes
git checkout accy_v2/model_lookup/models/manufacture_module.py

# Re-run pipeline
# (will fail again, but data preserved)
```

---

## Questions Before Starting?

1. **OEM Format Confirmation:** Are the ModelNumber code tables above correct for your data?
2. **Priority:** Should we start with Hyundai only, or all OEMs simultaneously?
3. **Testing:** Do you want unit tests written before migration?
4. **Rollout:** Should we migrate to production immediately, or test first?

---

## Next Steps

1. **Review** this guide and the detailed plan (`PIPELINE_ANALYSIS_AND_FIX_PLAN.md`)
2. **Confirm** ModelNumber code tables are correct for your OEM data
3. **Approve** implementation approach
4. **Execute** phases 1-5 above

Once approved, I can complete all phases today.

**Ready to proceed? 🚀**
