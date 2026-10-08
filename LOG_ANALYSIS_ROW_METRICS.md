# Row Metrics Analysis - test_honda_en_fr_metadata.py

**Date:** 2026-10-08  
**File:** CVIC5D.xlsx (May 2026)  
**Test Run Log:** test_run_logs.txt

---

## Summary of Logged Metrics

### ENGLISH SHEET (26MY_CIV5D_APP_EN)

| Section | Total Rows | Valid Data | Empty | Publishing | Unclassified |
|---------|-----------|-----------|-------|-----------|--------------|
| Packages and Kits | 44 | 2 | 9 | 0 | **33** |
| Wheels and Wheel Accessories | 13 | 8 | 1 | 0 | **4** |
| Exterior | 48 | 7 | 1 | 0 | **40** |
| Interior | 17 | 9 | 1 | 0 | **7** |
| Electrical | 7 | 2 | 1 | 0 | **4** |
| Paint Pens | 14 | 3 | 2 | 2 | **7** |
| **TOTALS** | **143** | **31** | **15** | **2** | **95** |

### FRENCH SHEET (26MY_CIV5D_APP_FR)

| Section | Total Rows | Valid Data | Empty | Publishing | Unclassified |
|---------|-----------|-----------|-------|-----------|--------------|
| Groupes et ensembles | 48 | 6 | 10 | 0 | **32** |
| Jantes et accessoires de jantes | 13 | 8 | 1 | 0 | **4** |
| Extérieur | 47 | 5 | 1 | 0 | **41** |
| Intérieur | 17 | 7 | 1 | 0 | **9** |
| Électrique | 7 | 1 | 1 | 0 | **5** |
| Crayon de retouche de peinture | 14 | 3 | 2 | 2 | **7** |
| **TOTALS** | **146** | **30** | **16** | **2** | **98** |

---

## Key Finding: Missing Classification

**The Problem:**
- EN sheet: 143 total rows = 31 valid + 15 empty + 2 publishing = **95 rows unaccounted for** (66.4%)
- FR sheet: 146 total rows = 30 valid + 16 empty + 2 publishing = **98 rows unaccounted for** (67.1%)

These "unclassified" rows are neither:
- ❌ Counted as valid data rows
- ❌ Counted as empty rows
- ❌ Counted as publishing rows

**They exist in the data but are invisible in the metrics!**

---

## Current Classification Logic (from step1_validation.py)

```python
# Line 735-747: Row counting loop
for row_idx in range(data_start_row, data_end + 1):
    row = df.iloc[row_idx]
    
    if _is_publishing_row(row):
        publishing_rows += 1
    elif found_publishing_row:
        publishing_rows += 1
    elif _is_empty_row(row):
        empty_rows += 1
    elif _is_valid_data_row(row, product_cols, price_cols):
        valid_data_rows += 1
    # else: UNCOUNTED! No fallback category
```

**The Issue:** There is NO `else` clause for rows that don't fit any category. They're simply not counted.

---

## What Happens to Unclassified Rows?

These rows likely have:
1. **Some data, but not matching the "valid_data_row" criteria**
   - Description present but no Part Number
   - Part Number present but no Description
   - Only trim applicability markers (no product data)
   - Only price data, no description or part number

2. **Are not empty** (have at least some content)

3. **Are not publishing rows** (don't contain "publication", "last updated", etc.)

But they **fail the `_is_valid_data_row()` check** because:
```python
# Line 545: REQUIRES BOTH product columns to have data
if product_cols_with_data < len(product_cols):
    return False  # Row rejected
```

---

## Recommendation

To fix the metrics, we need to:

1. **Define a category for partial data rows**
   - Example: rows with Description OR Part Number (but not both)
   - Example: rows with any product or price information

2. **Add to row classification logic**
   ```python
   elif _is_valid_data_row(row, ...):
       valid_data_rows += 1
   elif _is_partial_data_row(row, ...):  # NEW
       partial_data_rows += 1
   else:
       other_rows += 1  # Final catch-all
   ```

3. **Update metrics output** to show:
   - valid_data_rows (complete records)
   - partial_data_rows (incomplete records)
   - empty_rows (no content)
   - publishing_rows (footer metadata)
   - total_rows (sum of all above)

---

## Files Generated

- `test_run_logs.txt` — Full console output from test run
- `LOG_ANALYSIS_ROW_METRICS.md` — This analysis document

---

## Next Step

**What should be counted as a "legitimate data row"?**

Option A: **STRICT** (current)
- Must have BOTH Part Number AND Description

Option B: **MODERATE**
- Must have Description OR Part Number (just one is enough)

Option C: **INCLUSIVE**
- Must have ANY product or price data

Please clarify your definition so we can adjust the `_is_valid_data_row()` logic accordingly.
