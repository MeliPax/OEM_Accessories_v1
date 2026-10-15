# Phase 2 Detailed Report Analysis

## Overview

The enhanced Phase 2 report (`test_phase2_detailed_report.py`) provides comprehensive comparative analysis of both EN and FR sheets, enabling quick identification of classification issues and defects.

---

## Report Sections Explained

### SECTION 1: Global Record Type Comparison

**What it shows**: High-level summary of how many records fall into each category

**Key metrics**:
```
Record Type        EN    FR    Difference
─────────────────────────────────────────
child               8     0       -8
defect             20   118      +98
package_child      26    28      +2
package_parent      9     0       -9
parent             80     0      -80
─────────────────────────────────────────
TOTAL             143   146      +3
```

**Interpretation**:
- EN: Healthy distribution across all record types
- FR: Almost all rows classified as defects (118/146)
- FR is missing parent/child/package record classifications

**Action**: If global counts don't match, investigate Section 2 for which sections have issues.

---

### SECTION 2: Section-by-Section Breakdown

**What it shows**: Record type distribution within EACH section

Example:
```
Packages and Kits:
  Type            EN    FR    Status
  ─────────────────────────────
  defect           9     0     [DIFF]
  package_child   26     0     [DIFF]
  package_parent   9     0     [DIFF]
```

**Interpretation**:
- EN "Packages and Kits": 9 parents + 26 children + 9 defects = balanced
- FR "Groupes et ensembles": 0 parents + 0 children + 20 defects = all marked defective
- Issue is section-wide, not row-specific

**Action**: If a section shows all defects in FR, go to Section 4 to see which rows and why.

---

### SECTION 3: Defect Analysis - English Sheet

**What it shows**: Detailed breakdown of which rows are defects and their content

```
Packages and Kits: 9 defects
  Row  Part Number          Description
  ─────────────────────────────────────
  17   [EMPTY]              [EMPTY]
  21   [EMPTY]              [EMPTY]
  ...
```

**Interpretation**:
- EN defects are mostly empty rows (spacing, trim rows, etc.)
- These are EXPECTED and normal - not data quality issues
- Defects in EN are legitimate empty rows between package groups

**Action**: EN defects are acceptable. Check if FR defects have similar pattern.

---

### SECTION 4: Defect Analysis - French Sheet

**What it shows**: Detailed breakdown of FR defects with actual data

```
Groupes et ensembles: 20 defects
  Row  Part Number          Description
  ─────────────────────────────────────
  13   [EMPTY]              Ensemble de course à TypeR
  18   [EMPTY]              Ensemble de roues Enkei...
  ...
```

**KEY INSIGHT**: Rows have descriptions but NO part numbers!

**Interpretation**:
- FR rows are NOT truly defective - they have product data (description)
- The part_number column is NOT being normalized properly
- Root cause: Unicode/encoding issue with French column headers
  - File: `'Numéro de piéce'` (with accents)
  - Config: Mapping might not match exact encoding
  - Result: part_number column stays unnormalized, looks empty to classification logic

**Action**: This is the PRIMARY issue blocking FR support.

---

### SECTION 5: Defect Count Summary

**What it shows**: Side-by-side defect count comparison per section

```
Section                      EN Defects   FR Defects
───────────────────────────────────────────────────
Packages and Kits               9            0
Groupes et ensembles            0           20
Paint Pens                      2            0
Paint Pens (FR)                 0           14
...
```

**Interpretation**:
- EN and FR section names are different (expected)
- EN sections have ~1-9 defects (mostly empty rows)
- FR sections have 7-47 defects (rows with data not recognized)
- Pattern: Row counts differ (EN: 143, FR: 146) = different structure

---

## Current Status

### ✅ English Sheet (100% Working)
- 143 rows properly classified
- 80 parents, 26 package_children, 9 package_parents, 8 children, 20 defects
- Defects are legitimate empty rows
- Ready for Phase 3

### ❌ French Sheet (Blocked)
- 146 rows, almost all classified as defects
- Root cause: Part number column not normalizing
- Issue: Unicode encoding mismatch in config vs actual Excel file
- Blocking: Classification logic requires part_number to recognize rows

---

## Root Cause Analysis

### The Problem

French Excel file headers use accented characters:
```
Excel file has:    'Numéro de piéce'     (with specific accent encoding)
Config has:        'num´ro de pi´ce'     (different accent character)
                   ↓
                   Mapping doesn't match (case-insensitive, but unicode mismatch)
                   ↓
                   part_number column stays unmapped
                   ↓
                   Rows look like they have no part_number
                   ↓
                   Classification marks them all as defects
```

### Why It Matters

The `_classify_record_type()` function checks:
```python
has_part_number = _check_column("part_number", row, norm_names)
```

If `part_number` is not in `norm_names` dict, check fails, rows become defects.

---

## How to Use This Report

### For Debugging
1. Run: `python test_phase2_detailed_report.py`
2. Check Section 1 for overall difference
3. Go to Section 2 to identify which sections have issues
4. Jump to Section 4 to see detailed defect rows
5. Use row numbers to inspect original Excel data

### For Monitoring
- Compare EN vs FR column counts regularly
- Track defect counts per section
- Alert if defect count suddenly increases (indicates configuration change)

### For Testing
- Verify new changes don't break either sheet
- Use Section 5 defect summary to track improvements
- Defects should match between sheets once FR normalization is fixed

---

## Next Steps

### Priority 1: Fix FR Column Normalization
- Inspect exact Unicode bytes in FR Excel file
- Update `column_normalizations` with precise byte-for-byte matches
- Retest with comparison report

### Priority 2: Verify EN Still Works
- Run report after any config changes
- Ensure EN defect count stays at 20
- Ensure EN classification percentages unchanged

### Priority 3: Validate FR After Fix
- Expect FR defects to drop from 118 to ~20
- Expect parent/child counts to match EN
- Section 5 defect counts should be nearly identical

---

## Report Output Location

The detailed report includes:
1. ✅ Global EN vs FR comparison
2. ✅ Section-by-section breakdown
3. ✅ EN defect details with row numbers
4. ✅ FR defect details with row numbers
5. ✅ Defect count summary table
6. ✅ Diagnostic recommendations

Run anytime to validate Phase 2 across both languages.
