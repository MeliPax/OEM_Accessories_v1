# Part Number Fallback Feature

**Status:** ✅ Implemented & Tested  
**Implementation Date:** 2026-10-15  
**Component:** Step 2 - Header Normalization  
**Impact Level:** High (Improves data quality for parent records)

---

## Overview

The **Part Number Fallback Feature** enables parent records with missing part numbers in the official "part number" column to use placeholder product codes from column 1 as a fallback, improving data completeness and accuracy.

### Problem Statement

In Honda Excel files:
- Column 1 (`unnamed_1`) contains placeholder product codes (e.g., "08LXX-E09-XXXX")
- Column 3 (official "part number" column) is sometimes empty
- Records with this pattern were previously classified as **defects** instead of legitimate **parents**

### Solution

- **During classification:** Check column 1 as a fallback for part numbers
- **After classification:** Populate the official part number column with column 1 data for parent records
- **Logging:** Track all fills as cleaning activities (not warnings)

---

## Architecture & Design

### Classification Enhancement

When determining if a row is a parent, the system now checks:

```python
has_part_number = (
    "part number column has data"  # Column 3
    OR
    "column 1 has placeholder code"  # Column 1 fallback
)
```

**Key Function:** `_check_part_number_with_fallback(row, norm_names)`

Returns tuple: `(has_data: bool, fallback_value: str or None)`

### Data Hydration

After classification, parent records that used the fallback are post-processed:

**Key Function:** `_fill_part_numbers_from_fallback(df, record_types, ...)`

For each parent record:
1. Check if column 1 has data and column 3 is empty
2. Copy column 1 value to column 3
3. Log the activity: `Row {idx}: Filled missing part number from column 1: '{value}'`

### Safety Mechanisms

✅ **Subsection Label Protection**
- Subsection labels are identified BEFORE this logic runs
- They are excluded from parent processing entirely
- Not affected by fallback logic

✅ **No Conflicts with Existing Logic**
- Additive change: only affects rows that would otherwise be defects
- Non-destructive: doesn't modify existing valid part numbers
- Reversible: all fills are logged

✅ **Audit Trail**
- Debug-level logs for each filled row
- Info-level summary at step completion
- Metadata tracking for downstream analysis

---

## Implementation Details

### Modified Functions

| Function | Change | Purpose |
|----------|--------|---------|
| `_check_part_number_with_fallback()` | NEW | Check part number with column 1 fallback |
| `_classify_record_type()` | ENHANCED | Use fallback check during classification |
| `_fill_part_numbers_from_fallback()` | NEW | Post-process to hydrate part numbers |
| `run()` | ENHANCED | Call post-processor after classification |

### Control Flow

```
Step 2: Header Normalization
├─ Phase 1: Extract & normalize headers
├─ Phase 2: Classify each row
│  ├─ Check part number (WITH FALLBACK)
│  └─ Return record type (parent, child, defect, subsection_label, etc.)
├─ Phase 3: Fill part numbers from fallback
│  ├─ For each parent record:
│  │  ├─ If col1 has data AND col3 is empty
│  │  └─ Copy col1 → col3
│  └─ Log fills
└─ Phase 4: Build parent index & return
```

---

## Test Coverage

### Test Scenario: `test_part_number_fallback.py`

**Test Cases:**

| Row | Scenario | Expected Result | Status |
|-----|----------|-----------------|--------|
| 2 | Normal parent (col3 filled) | Unchanged, col3='123456' | ✅ PASS |
| 3 | Fallback parent (col1 filled, col3 empty) | Classified as parent, col3='08LXX-E02-XXXX' | ✅ PASS |
| 4 | Subsection label (col1 + desc, no col3) | subsection_label, col3 empty | ✅ PASS |
| 5 | Child (col1 + desc, prices empty) | child, col3 unchanged | ✅ PASS |

**Summary:**
- Classification accuracy: 4/4 correct
- Data hydration: 1/1 fills applied
- No conflicts: Subsection labels unaffected
- All evaluations passed ✅

---

## Logging Output

### Debug Level

```
[DEBUG] Row 3: Filled missing part number from column 1: '08LXX-E02-XXXX' (parent)
```

Logged for each row filled, includes:
- Row index
- Fallback value used
- Record type (parent/package_parent)

### Info Level

```
[INFO] Phase 2: Recovered 1 part numbers from column 1 fallback
```

Summary at step completion showing total fills.

---

## Data Quality Impact

### Before This Feature

| Metric | Value |
|--------|-------|
| Records with col1 + empty col3 | N |
| Classified as defects | N |
| Correctly identified as parents | 0 |

### After This Feature

| Metric | Value |
|--------|-------|
| Records with col1 + empty col3 | N |
| Classified as defects | 0 |
| Correctly identified as parents | N |
| Defect rate improvement | -100% for this pattern |

---

## Column Structure Reference

| Index | Name | Content | Role |
|-------|------|---------|------|
| 0 | `unnamed_0` | Usually empty | Padding |
| 1 | `unnamed_1` | Placeholder codes (08LXX-E09-XXXX) | **Fallback source** |
| 2 | `unnamed_2` | Usually empty | Padding |
| 3 | `description` | Product description | Primary identifier |
| 4 | `part number` | Official part number | **Primary source** |
| 5-8 | Price columns | Dealer Net, List Price, FRT, Installed Price | Pricing |
| 9+ | Trim columns | Applicability markers | Trim data |

---

## Edge Cases Handled

✅ **Both columns have data** → Use official part number, ignore fallback  
✅ **Only official has data** → Use official (normal case)  
✅ **Only fallback has data** → Use fallback (this feature)  
✅ **Neither has data** → No part number (defect, unaffected)  
✅ **Subsection labels** → Excluded before this logic (protected)  

---

## Backward Compatibility

✅ **No breaking changes**
- Existing parent/child classification unchanged
- Defect detection logic unchanged
- Only affects previously-defective rows that can be salvaged
- All changes are additive

---

## Future Enhancements

- **Pattern validation:** Validate that fallback values match expected format (e.g., `^\d{2}[A-Z]{3}\d-[A-Z]\d{2}-[A-Z]{4}$`)
- **Confidence scoring:** Track which fills came from fallback for output metadata
- **Cross-OEM generalization:** Apply similar logic to other OEMs if column 1 patterns exist

---

## Related Documentation

- [DESIGN_RULES.md](DESIGN_RULES.md) - Core architectural rules
- [step2_header_normalization.py](../../oems/honda/pipeline/step2_header_normalization.py) - Implementation
- [test_part_number_fallback.py](../../../test_part_number_fallback.py) - Unit test

---

## Sign-Off

**Feature:** Part Number Fallback from Column 1  
**Status:** ✅ Ready for Production  
**Tested:** Yes (synthetic data + logic verification)  
**Documented:** Yes (this file + code comments)  
**Last Updated:** 2026-10-15
