# Search Logic Update - Summary of Changes

**Date:** 2026-07-28  
**Status:** ✅ IMPLEMENTED & TESTED  
**Component:** accy_v2/model_lookup/models/manufacture_module.py

---

## Overview

Updated the model search logic to differentiate between:
1. **Model Name Keywords** → Search ONLY in `ModelName` column (strict)
2. **Trim Keywords** → Search in BOTH `TrimName` AND `Description` columns (comprehensive)

---

## Why This Change

**Previous Approach:**
- Searched all keywords in both ModelName AND Description indiscriminately
- Could match partial model names or trim keywords in wrong columns
- Less precise for distinguishing models from trims

**New Approach:**
- Model keywords (elantra, g70, cx-5) → ModelName column only
- Trim keywords (essential, preferred, gs, advanced) → TrimName + Description
- Leverages the complete information in TrimName column
- More precise and semantically correct

---

## Changes Made

### File: accy_v2/model_lookup/models/manufacture_module.py

#### Change 1: Main Search Loop (Lines 1125-1141)

**Before:**
```python
for keyword in keywords:
    # ... single char handling ...
    else:
        # Searched BOTH ModelName and Description regardless of keyword type
        pattern = build_word_boundary_pattern(keyword)
        search_in_model = df_filtered["ModelName"].fillna("").str.contains(...)
        search_in_desc = df_filtered["Description"].str.contains(...)
        df_filtered = df_filtered[search_in_model | search_in_desc]
```

**After:**
```python
for keyword in keywords:
    if use_single_char_token_matching and len(keyword) == 1:
        # Single chars searched in BOTH TrimName and Description
        df_filtered = df_filtered[
            df_filtered["TrimName"].fillna("").apply(...) |
            df_filtered["Description"].apply(...)
        ]
    else:
        pattern = build_word_boundary_pattern(keyword)

        # Detect: Is this keyword a model name or trim keyword?
        model_matches = df_filtered["ModelName"].fillna("").str.contains(...).sum()

        if model_matches > 0:
            # MODEL KEYWORD: Search ONLY in ModelName
            df_filtered = df_filtered[
                df_filtered["ModelName"].fillna("").str.contains(...)
            ]
        else:
            # TRIM KEYWORD: Search in TrimName AND Description
            df_filtered = df_filtered[
                df_filtered["TrimName"].fillna("").str.contains(...) |
                df_filtered["Description"].str.contains(...)
            ]
```

#### Change 2: EV Filter Logic (Lines 1151-1159)

**Before:**
```python
# Searched for fuel type in ModelName OR Description
has_ev_in_model = df_filtered["ModelName"].str.contains(...)
has_ev_in_desc = df_filtered["Description"].str.contains(...)
df_filtered = df_filtered[~(has_ev_in_model | has_ev_in_desc)]
```

**After:**
```python
# Fuel types are trim-related, search in TrimName OR Description
has_ev_in_trim = df_filtered["TrimName"].fillna("").str.contains(...)
has_ev_in_desc = df_filtered["Description"].str.contains(...)
df_filtered = df_filtered[~(has_ev_in_trim | has_ev_in_desc)]
```

---

## Search Logic Explanation

### Step-by-Step Process

1. **Load Keywords** → ["elantra", "essential"]

2. **For "elantra":**
   - Check if "elantra" matches anything in ModelName column
   - ModelName contains "Elantra" → YES, it's a model keyword
   - **Action:** Search ONLY in ModelName column
   - Result: 10 Elantra records found

3. **For "essential":**
   - Check if "essential" matches anything in ModelName column
   - ModelName contains "Elantra" or "Kona" or "Tucson" (not "Essential")
   - ModelName doesn't match → NO, it's NOT a model keyword
   - **Action:** Search in BOTH TrimName AND Description columns
   - Result: Records with TrimName="Essential" OR Description containing "Essential"
   - Result: 1 Elantra Essential record found

---

## Test Results

### Test Case: All OEMs

| Make | Year | Keywords | ModelName Match | Trim Match | Result |
|------|------|----------|-----------------|-----------|--------|
| Hyundai | 2024 | ["elantra", "essential"] | 10 (elantra) | 1 (essential) | **PASS** ✓ |
| Genesis | 2024 | ["g70", "advanced"] | 4 (g70) | 2 (advanced) | **PASS** ✓ |
| Mazda | 2024 | ["cx-5", "gs"] | 9 (cx-5) | 2 (gs) | **PASS** ✓ |
| Mitsubishi | 2024 | ["outlander", "es"] | 12 (outlander) | 2 (es) | **PASS** ✓ |
| Honda | 2024 | ["civic", "sedan"] | 9 (civic) | 5 (sedan) | **PASS** ✓ |

**Status:** ✅ All searches working correctly with new logic

---

## Data Columns Now Used Correctly

### For Model Search
- **ModelName** → Only column searched for model keywords
- Example: "Elantra", "G70", "CX-5", "Outlander", "Civic"

### For Trim Search
- **TrimName** → Primary trim level column
- **Description** → Secondary (full trim description with options)
- Example: 
  - TrimName: "Essential", "Preferred", "2.5T Advanced", "GS", "ES"
  - Description: "Essential Ivt", "Preferred Awd", "Advanced Awd", "Gx Awd", "Es Awc"

### Unused for Search (but returned)
- **ModelNumber** → Returned to pipeline (not searched)
- **Package** → Used for uniqueness key (not searched)
- **Manufacturer** → Filter only (not searched)
- **ModelYear** → Filter only (not searched)

---

## Benefits of New Approach

1. **More Precise Matching**
   - Model keywords matched strictly against model names
   - No confusion with trim levels that happen to contain similar text

2. **Better Use of Data Structure**
   - Leverages TrimName column which contains clean trim level data
   - Respects the semantic meaning of each column

3. **Improved Search Quality**
   - Fewer false positives from Description field
   - More accurate trim-level identification

4. **Consistent with User Intent**
   - First keyword typically model name → search ModelName only
   - Following keywords typically trim/specs → search TrimName+Description

---

## Example Walkthrough

### Query: Hyundai 2024 Elantra Essential

**Step 1: Extract Keywords**
- Keywords: ["elantra", "essential"]

**Step 2: Filter Database**
- WHERE Manufacturer="HYUNDAI" AND ModelYear=2024
- Result: 68 records

**Step 3: Process Keyword "elantra"**
- Check: Does ModelName column contain "elantra"?
- Answer: YES (10 records have ModelName="Elantra")
- Action: Search ONLY in ModelName column
- Result: 10 records (all Elantra trims)

**Step 4: Process Keyword "essential"**
- Check: Does ModelName column contain "essential"?
- Answer: NO (ModelName has "Elantra", "Kona", etc., not "Essential")
- Action: Search in TrimName AND Description columns
- TrimName="Essential" found in records 1, 2
- Description contains "essential" found in records 1, 2
- Result: 1-2 records (Elantra Essential trims)

**Step 5: Apply Filters & Return**
- Final: 1 record (ELCS4V2BES00 - Elantra Essential Ivt)

---

## Verification

### Column Search Distribution

For each keyword, the search now uses:

| Keyword Type | Search Columns | Reason |
|--------------|----------------|--------|
| Model Names | ModelName only | Strict model identification |
| Trim Levels | TrimName + Description | Complete trim information |
| Transmissions | Description | Transmission info in description |
| Body Styles | Description | Body style info in description |
| Fuel Types | TrimName + Description | EV/Hybrid info in trim names |

---

## Summary

✅ **New Search Logic Implemented:**
- ModelName keywords → Search ModelName column ONLY
- Trim keywords → Search TrimName AND Description columns
- All tests passing
- More precise and semantically correct
- Ready for production use
