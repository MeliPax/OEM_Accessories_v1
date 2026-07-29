# Pipeline Analysis & Column Name Fix Plan

**Date:** 2026-07-28  
**Status:** Analysis Complete - Ready for Implementation  

---

## Executive Summary

Recent database schema changes (StyleID removal, Package/TrimName semantic swap) have created a **critical mismatch** between:
- What the database provides (8-column CSV with TrimName holding trim levels)
- What the pipeline search logic expects (model name in Description field)

This causes **100% record exclusion** across all OEMs.

**Root Issue:** Description field contains only trim descriptors ("Essential Ivt", "Preferred Dct") without model names ("Elantra", "G80", "CX-5").

**Solution Strategy:** Create a new column that combines Description + TrimName + ModelNumber context for searchability, OR modify search logic to be OEM-aware and use multiple columns for matching.

---

## Current Database Structure (After StyleID Removal)

### 8-Column Schema
```
Column         | Type      | Content                      | Example
─────────────────────────────────────────────────────────────────────
Description    | string    | Trim descriptor + features   | "Essential Ivt"
Drivetrain     | string    | Drive type                   | "FRONT_WHEEL_DRIVE"
Manufacturer   | string    | OEM name (uppercase)         | "HYUNDAI"
ModelNumber    | string    | OEM model code               | "EL74MF20A100"
ModelYear      | integer   | Year                         | 2022
Package        | integer   | ADS style ID (not trim!)     | 424279
PassDoors      | integer   | Door count                   | 4
TrimName       | string    | TRIM LEVEL (was model name!) | "Essential"
```

### Critical Issue: Column Semantics Changed

| Column | Old Meaning | New Meaning | Issue |
|--------|------------|------------|-------|
| **Package** | Trim string ("Essential") | Numeric style ID (424279) | Pipeline search expects string |
| **TrimName** | Base model name (e.g., "nameWoTrim") | Trim level ("Essential", "Preferred") | Pipeline expects model name here |
| **Description** | Not used | Trim descriptor only | Missing model name for search |

### Example Data Flow

**Input (Excel):**
```
Sheet: 2024_elantra
Trim_1: Ess
Trim_2: Pref
Trim_3: Lux
```

**Database has:**
```
Description    | Manufacturer | ModelNumber    | ModelYear | TrimName | Package
─────────────────────────────────────────────────────────────────────────────
Essential Ivt  | HYUNDAI      | ELCS4V2BES00   | 2024      | Essential| 449710
Preferred Ivt  | HYUNDAI      | ELCS4V2BPR00   | 2024      | Preferred| 449711
Luxury Ivt     | HYUNDAI      | ELCS4V2BLU00   | 2024      | Luxury   | 449712
```

**Pipeline Search Attempt:**
```
Search for: ["elantra", "essential"]
In: Description field
Found: "elantra" ✗ (NOT in "Essential Ivt")
Result: 0 candidates → Record excluded
```

---

## The Pipeline Process (Current Flow)

### Step-by-Step Breakdown

```
1. LOAD
   └─ Excel file (OEM-specific sheet)
      └─ E.g., Hyundai: Master sheet with all models

2. VALIDATE (Step 1)
   └─ Check headers, required fields, data integrity

3. NORMALIZE (Step 2)
   └─ Standardize column names
   └─ Handle Excel quirks (merged cells, etc.)

4. STANDARDIZE (Step 3)
   └─ Convert to common format
   └─ Extract year from column headers
   └─ Create vehicle_year metadata

5. GROUP (Step 3.5)
   └─ Group by (year, model)
   └─ E.g., "2024_elantra", "2024_tucson"
   └─ Each group gets own metadata (model_name, year, manufacturer)

6. TRANSFORM (Step 4)
   └─ Melt trim columns into rows
   └─ Create (model, trim, accessory) combinations
   └─ E.g., 95 rows × 6 trim cols → 424 rows (after melt)

7. MODEL LOOKUP ENRICHMENT ⚠️ BROKEN (Step 4.5)
   ├─ Extract unique trims from melted data (e.g., ['Ess', 'Pref', 'Lux'])
   ├─ Extract model keywords from data (e.g., ['elantra'])
   ├─ Translate trim keywords (e.g., 'Ess' → 'Essential')
   ├─ Create search keywords (e.g., ['elantra', 'essential'])
   ├─ Call search_models_by_description(keywords=['elantra', 'essential'])
   │  └─ Search database for Description containing ALL keywords
   │     └─ Expected: Find "Elantra Essential Ivt" or similar
   │     └─ Actual: NOT FOUND (Description has no "elantra")
   ├─ Add model_number column (empty if not found)
   └─ Add model_number_status column ("yes - found" or "no - not found")

8. OUTPUT FILTERING ⚠️ 100% EXCLUSION (Step 5)
   └─ Drop rows where model_number_status = "no - not found"
   └─ RESULT: 424 rows → 0 rows output ← ALL EXCLUDED

9. WRITE
   └─ Generate Excel output with (almost) no data
```

---

## Why Search Fails: The Critical Mismatch

### What Pipeline Expects
```
Pipeline thinks:
  - Description = "Elantra Essential Ivt" (model + trim + transmission)
  - Can search for model keywords + trim keywords in Description
  - One search returns both model AND trim match
```

### What Database Actually Has
```
Current schema:
  - Description = "Essential Ivt" (trim + transmission ONLY, no model)
  - TrimName = "Essential" (trim level)
  - ModelNumber = "ELCS4V2BES00" (encoded model, not human-readable)
  
Search fails:
  - Looking for "elantra" in "Essential Ivt" ✗
  - "elantra" not present anywhere in that row
  - Result: 0 candidates
```

---

## Fix Plan: 3-Track Approach

### Track A: Database Augmentation (Recommended)

**Goal:** Add model name to Description at the database level

**Implementation:**
1. Create `ModelName` helper column (derived from ModelNumber)
2. For each OEM, implement `extract_model_name_from_model_number()`:
   - Hyundai: "ELCS4V2BES00" → "Elantra" (EL = Elantra)
   - Genesis: "I5EW5ZE4PRLR" → "Ioniq5" (I5 = Ioniq5)
   - Mazda: "JYBBP5EX3C0" → "Mazda3" (JYB = Mazda3)
   - Mitsubishi: "COEV-X" → "Outlander"
   - Honda: "RZ2H7VKY" → "Accord"
3. Create new `SearchableDescription`: `f"{ModelName} {Description}"`
   - E.g., "Elantra Essential Ivt"
4. Update search to use SearchableDescription instead of Description

**Pros:**
- ✅ Database becomes self-contained and searchable
- ✅ No search logic changes needed
- ✅ All OEMs benefit immediately
- ✅ Clear, maintainable approach

**Cons:**
- ⚠️ CSV slightly larger (one extra column)
- ⚠️ Need OEM-specific ModelNumber parsers

**Timeline:** 2-3 hours implementation + migration

---

### Track B: Multi-Column Search (Alternative)

**Goal:** Modify search logic to match model keywords against multiple columns

**Implementation:**
1. Change `search_models_by_description()` to also check:
   - Extract model prefix from ModelNumber
   - Check TrimName against trim keywords
   - Combine Description + TrimName for matching
2. Create OEM-specific search strategies

**Pros:**
- ✅ No database changes needed
- ✅ Can be implemented faster

**Cons:**
- ❌ Search logic becomes complex and OEM-specific
- ❌ Harder to maintain and debug
- ❌ Fragile (depends on ModelNumber format)

**Timeline:** 1-2 hours but higher risk

---

### Track C: Hybrid Approach (Best Long-Term)

**Goal:** Combine both approaches for robustness

**Phase 1 (Immediate):** Implement Track A
- Add model name to Description
- Get pipeline working again

**Phase 2 (Future):** Add Track B as fallback
- Multi-column search for edge cases
- Graceful degradation

---

## Recommended Implementation: Track A

### Step 1: Add ModelName Column to CSV

**File:** `accy_v2/model_lookup/db/db_vehicle_models.csv`

**New Structure (9 columns):**
```
Description,Drivetrain,Manufacturer,ModelNumber,ModelYear,Package,PassDoors,TrimName,ModelName
Essential Ivt,FRONT_WHEEL_DRIVE,HYUNDAI,EL74MF20A100,2022,424279,4,Essential,Elantra
Preferred Ivt,FRONT_WHEEL_DRIVE,HYUNDAI,EL74IF20A200,2022,424281,4,Preferred,Elantra
```

### Step 2: Create ModelNumber Parser for Each OEM

**File:** `accy_v2/model_lookup/models/manufacture_module.py`

```python
def extract_model_name_from_model_number(model_number: str, manufacturer: str) -> str:
    """Extract human-readable model name from OEM model code."""
    
    if manufacturer == "HYUNDAI":
        # Hyundai: First 2 chars = model code
        # EL = Elantra, TU = Tucson, SA = Santa Fe, etc.
        prefix = model_number[:2].upper()
        hyundai_codes = {
            "EL": "Elantra", "TU": "Tucson", "SA": "Santa Fe",
            "SO": "Sonata", "VE": "Venue", "KO": "Kona", "EX": "Excel"
        }
        return hyundai_codes.get(prefix, "Unknown")
    
    elif manufacturer == "GENESIS":
        # Genesis: First 2 chars = model code
        # I5 = Ioniq5, G70 = G70, G80 = G80, etc.
        prefix = model_number[:2].upper()
        genesis_codes = {
            "I5": "Ioniq5", "G7": "G70", "G8": "G80", "GV": "GV70"
        }
        return genesis_codes.get(prefix, "Unknown")
    
    # ... (similar for Mazda, Mitsubishi, Honda)
```

### Step 3: Create Migration Script

**File:** `accy_v2/model_lookup/migrate_add_model_name.py`

```python
def migrate_database():
    df = pd.read_csv('db/db_vehicle_models.csv')
    
    # Add ModelName column
    df['ModelName'] = df.apply(
        lambda row: extract_model_name_from_model_number(
            row['ModelNumber'], 
            row['Manufacturer']
        ),
        axis=1
    )
    
    # Create SearchableDescription
    df['SearchableDescription'] = df['ModelName'] + ' ' + df['Description']
    
    # Save
    df.to_csv('db/db_vehicle_models.csv', index=False)
```

### Step 4: Update Search Logic

**File:** `accy_v2/model_lookup/models/manufacture_module.py`

**Function:** `search_models_by_description()`

**Change:**
```python
# OLD:
results = df[df['Description'].str.contains(pattern, case=False, na=False)]

# NEW:
results = df[df['SearchableDescription'].str.contains(pattern, case=False, na=False)]
```

### Step 5: Update Test Assertions

**Files affected:**
- `test_fetch_vehicle.py` - Update expected Description format
- `test_search_engine.py` - Update search test cases
- `test_ads_integration.py` - Verify SearchableDescription populated

---

## Impact Analysis by Component

### Components Affected
| Component | Impact | Change Required |
|-----------|--------|-----------------|
| **Database (CSV)** | HIGH | Add ModelName column, populate, use SearchableDescription |
| **ADS Mapper** | NONE | No change (Description still from ADS) |
| **ADS Service** | NONE | No change |
| **Search Engine** | MEDIUM | Use SearchableDescription instead of Description |
| **Pipeline Step 4.5** | NONE | No change (already passes keywords correctly) |
| **OEM Pipelines** | NONE | No change (backward compatible) |
| **Tests** | MEDIUM | Update search expectations |

### Backward Compatibility
- ✅ No breaking changes to pipeline interface
- ✅ No changes to ingestion (ADS API → mapper → CSV)
- ✅ Existing search keywords still work
- ✅ New column is additive (old code still works)

---

## Testing Strategy

### Test Cases (Before/After Migration)

**Test 1: Hyundai 2024 Elantra Essential**
```
Before: 0 candidates ✗
After: Find ELCS4V2BES00 and related rows ✓
```

**Test 2: Genesis 2024 G80 Advanced**
```
Before: 0 candidates ✗
After: Find G80 Advanced rows ✓
```

**Test 3: Mazda 2024 CX-5 Preferred**
```
Before: 0 candidates ✗
After: Find CX-5 Preferred rows ✓
```

### Metrics to Validate
- ✅ All 1,143 database rows have ModelName populated
- ✅ SearchableDescription format is correct
- ✅ Search returns >0 candidates for all test trims
- ✅ Pipeline output records > 0 (not 100% excluded)
- ✅ No regression in existing passing tests

---

## Implementation Timeline

### Day 1: Analysis & Preparation
- [ ] Review ModelNumber formats for each OEM (30 min)
- [ ] Create ModelNumber parser functions (45 min)
- [ ] Write and test migration script (45 min)

### Day 2: Migration & Testing
- [ ] Backup current CSV (5 min)
- [ ] Run migration script (5 min)
- [ ] Verify all 1,143 rows populated (15 min)
- [ ] Update search_models_by_description() (15 min)
- [ ] Run smoke tests (15 min)
- [ ] Run full test suite (30 min)

### Day 3: Validation
- [ ] Run Hyundai pipeline end-to-end (1 hour)
- [ ] Run Genesis pipeline end-to-end (1 hour)
- [ ] Verify output records > 0 (30 min)
- [ ] Document any OEM-specific quirks (30 min)

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| **Wrong ModelNumber parsing** | Create lookup table per OEM; validate results spot-check |
| **CSV data loss** | Backup before migration; keep original copy |
| **Search regression** | Run full test suite; compare old vs new results |
| **Performance** | One additional string column; negligible impact |
| **OEM-specific edge cases** | Test each OEM independently; document quirks |

---

## Appendix: OEM ModelNumber Formats

### Hyundai (Examples: ELCS4V2BES00)
- Chars 1-2: Model code (EL=Elantra, TU=Tucson, SA=Santa Fe, etc.)
- Chars 3-7: Platform/variant
- Chars 8-9: Year
- Chars 10-11: Region
- Chars 12: Checksum

### Genesis (Example: I5EW5ZE4PRLR)
- Chars 1-2: Model (I5=Ioniq5, G7=G70, G8=G80, GV=GV70)
- Rest: Variant/region

### Mazda (Example: JYBBP5EX3C0)
- Chars 1-3: Manufacturer code (JYB=Mazda)
- Chars 4-5: Model (P5=Mazda3, etc.)
- Rest: Variant

### Mitsubishi (Example: COEV-X)
- CO = Outlander code
- Format varies; needs validation

### Honda (Example: RZ2H7VKY)
- First 2-3 chars encode model
- Needs validation

---

## Success Criteria

✅ Pipeline search returns >1 candidate for each trim  
✅ Records excluded due to lookup < 5% (was 100%)  
✅ Hyundai pipeline output > 400 rows (was 0)  
✅ Genesis pipeline output > 150 rows (was 0)  
✅ All NOT_FOUND warnings eliminated from logs  
✅ No regression in other pipeline components  

---

## Questions for Clarification

1. Do we have OEM model code documentation/tables?
2. Should ModelName be derived (as proposed) or ingested from ADS?
3. Which OEMs are priority (Hyundai first, then Genesis, Mazda, Mitsubishi)?
4. Should we keep old Description column for reference?

---

**Next Step:** Approve implementation plan and I'll begin Step 1 today.
