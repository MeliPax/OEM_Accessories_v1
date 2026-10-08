# Row Classification Definition - Decision History

**Current Date:** 2026-10-08  
**Current Issue:** Row metrics not matching actual data records (67% invisible rows)

---

## Previous Work & Commits

### Commit 1ba5ef4 (2026-09-29 09:15)
**Title:** Implement: Comprehensive data row counting and metadata logging

**Original Design Documentation:**
```
Requirements Confirmed:
✅ Valid data row criteria: At least ONE of product columns (Part Number, Description) 
   OR price columns (Cost, Hours, MSRP, FRT, Installed Price). 
   Captures rows even if some columns are missing (flags as data with potential quality issues).
```

**Implementation:** Simple check - if ANY key column has data, count as valid

---

### Commit dd076b5 (2026-09-29 09:23)
**Title:** Fix: Require BOTH part columns for valid data row classification

**Change Made:** Modified `_is_valid_data_row()` to be STRICTER

**Commit Message:**
```
- Updated _is_valid_data_row() to require BOTH product columns 
  (Part Number AND Description) to have data for a row to be considered valid
- Rows missing either Part Number or Description are now excluded 
  from valid_data_rows count
- Example impact: Packages section shows 32 valid rows (was 35) - 
  3 rows with incomplete part data now correctly excluded
- Ensures data quality by preventing incomplete product records 
  from being counted as valid data
```

**Result:** 
- More conservative counting
- Excludes rows with missing Part Number or Description
- ~3 rows per section were reclassified as invalid

---

## Current Problem (2026-10-08)

**Observation:** Row counts are **too conservative**
- EN: 31 valid data rows out of 143 total (21.7%)
- FR: 30 valid data rows out of 146 total (20.5%)
- **95-98 rows unclassified** (invisible in metrics)

**Root Cause:** The dd076b5 "fix" may have been **too strict**

---

## Row Classification Options

### Option A: STRICT (Current Implementation)
```python
def _is_valid_data_row(row, product_cols, price_cols):
    # BOTH Part Number AND Description must have data
    product_cols_with_data = 0
    for col_idx in product_cols:
        if has_data(col_idx):
            product_cols_with_data += 1
    
    if product_cols_with_data < len(product_cols):  # All product cols required
        return False
    
    # Price column is optional
    return True
```

**Result:** 31 valid rows in EN sheet  
**Issue:** Excludes rows like:
- "Description present, no Part Number" ❌
- "Part Number present, no Description" ❌
- "Only price/cost data, no description" ❌

---

### Option C: INCLUSIVE (Original Design)
```python
def _is_valid_data_row(row, product_cols, price_cols):
    # ANY product or price column with data
    all_key_cols = product_cols + price_cols
    for col_idx in all_key_cols:
        if has_data(col_idx):
            return True  # At least one key column has data
    
    return False
```

**Result:** Would count ~95-98 more rows as valid  
**Benefit:** Captures all rows with ANY useful data  
**Risk:** May be too permissive (includes incomplete records)

---

### Option A + C: COMBINED (Your Choice)

**Definition:** A row is valid if it has EITHER:

**1. Complete Record (Option A - STRICT):**
   - BOTH Part Number AND Description present
   - This is a "high-confidence" legitimate record

**OR**

**2. Any Data (Option C - INCLUSIVE):**
   - Description present (even without Part Number)
   - Part Number present (even without Description)
   - Price/Cost present (even without description)
   - Any combination of product/price data

**Implementation:**
```python
def _is_valid_data_row(row, product_cols, price_cols):
    # Check for complete record (both product columns)
    product_cols_with_data = count_product_cols_with_data(row, product_cols)
    
    if product_cols_with_data >= len(product_cols):  # Complete record
        return True  # Option A: strict = valid
    
    # Check for ANY data (Option C)
    all_key_cols = product_cols + price_cols
    for col_idx in all_key_cols:
        if has_data(col_idx):
            return True  # Option C: has any data = valid
    
    return False
```

**Result:**
- Counts all complete records (both Part Number + Description) ✓
- Counts all partial records (any product/price data) ✓
- Excludes only completely empty rows ✓

**Expected Impact on EN Sheet:**
- Before: 31 valid data rows (strict)
- After: ~110-115 valid data rows (A+C combined)
- Unclassified: Would drop from 95 to ~30-35

---

## Recommendation

**Your Choice: Option A + C Combined** makes sense because:

1. **High-confidence records** (Option A)
   - Complete part information: Part # + Description
   - Can be processed directly
   
2. **Partial records** (Option C)
   - Incomplete but still valuable
   - Can be flagged for review/completion
   - Better than losing the data entirely

3. **Data Quality Flag**
   - Could add a "data_completeness" field in metadata
   - Mark which rows are complete (A) vs partial (C)
   - Enables downstream DQ reporting

---

## Files to Modify

To implement Option A + C combined:

**File:** `accy_v2/oems/honda/pipeline/step1_validation.py`

**Function:** `_is_valid_data_row()` (lines 522-558)

**Change:** Add the combined logic shown above

**Test:** Run `python test_honda_en_fr_metadata.py` to verify new counts

---

## Summary

| Metric | Option A (Current) | Option A+C (Proposed) | Difference |
|--------|------------------|-------------------|-----------| 
| EN Valid Rows | 31 | ~110-115 | +79-84 rows |
| FR Valid Rows | 30 | ~105-110 | +75-80 rows |
| EN Coverage | 21.7% | 76-80% | Much better |
| FR Coverage | 20.5% | 72-75% | Much better |

**Confidence:** Option A+C should capture legitimate accessory data while maintaining quality standards through bifurcated counting.

