# Honda Pipeline Steps 2-3 Architecture
**Date:** 2026-10-15  
**Status:** Design Document (Ready for Implementation)  
**Scope:** Align Honda Steps 2-3 with standard OEM pattern (Hyundai/Genesis/Mazda/Mitsubishi)

---

## Problem Statement

Honda's current pipeline design diverges from standard OEM pattern:
- **Section-based processing**: 6 separate sections per sheet, different headers per section
- **Wide-format columns**: Trim columns (LX, EX, Sport, etc.) are separate columns, not data values
- **Parent/child separation**: Parent and child records kept separate through output

**Goal:** Align Honda with standard OEM architecture while handling Honda-specific parent/child and section-based structure.

---

## Solution: Two-Step Refactoring

### Step 2: Header Normalization → Return Metadata Dict

**Current behavior:** Returns `Tuple[pd.DataFrame, Dict]`  
**New behavior:** Returns `Dict[str, Any]` (standard OEM pattern)

**Output structure:**
```python
{
    "col_mapping": {
        0: None,                # Column 0 unused
        1: None,                # Column 1 unused  
        2: "description",       # Description
        3: "part_number",       # Part number
        4: "dealer_net",        # Dealer net
        5: "list_price",        # List price
        6: "frt",               # Freight
        7: "installed_price",   # Installed price
        8: "application",       # Application
        9: None,                # Unused/trim
        10: None,               # Unused/trim
        11: None,               # Unused/trim
        12: None,               # Unused/trim
        13: None,               # Unused/trim
        14: None,               # Unused/trim
        15: None,               # Unused/trim
        16: None,               # Unused/trim
    },
    "valid_trim_cols": ["LX", "EX", "Sport", "Touring", "SI", "Type-R"],
    "trim_validation_log": {}
}
```

**Responsibilities:**
- Extract and normalize headers from all sections
- Build col_mapping: map numeric column indices (0-16) to canonical column names
- Identify valid_trim_cols: extract trim column names from section headers
- Update meta_data in-place with parent/child classification (record_type_counts, parent_row_index, record_types)
- Return metadata dict for Step 3 to use

**Files to modify:**
- `accy_v2/oems/honda/pipeline/step2_header_normalization.py` - Change return type, build col_mapping dict
- `accy_v2/oems/honda/pipeline/orchestrator.py` - Implement run_step2_header_normalization() stub

---

### Step 3: Standardization → Wide-Format Output with Parent/Child Resolved

**Current behavior:** Returns modified dataframe with section-based processing  
**New behavior:** Returns single wide-format DataFrame with EN/FR combined, parent/child resolved

**Output structure example:**
```
   part_number  description        description_fr  dealer_net  list_price   frt  installed_price      LX      EX    Sport  Touring  language
0  25CIV-ENK    Exterior Package    Ensemble Ext.    1200.00     1800.00  25.00         1825.00       •       •       •        •         EN
1  25CIV-ENK    Exterior Package    Ensemble Ext.    1200.00     1800.00  25.00         1825.00       •       •       •        •         FR
2  25CIV-STL    Steel Package       Paquet Acier     800.00      1200.00  15.00         1215.00       •              •                 EN
3  25CIV-STL    Steel Package       Paquet Acier     800.00      1200.00  15.00         1215.00       •              •                 FR
```

**Responsibilities:**
1. Apply col_mapping (from Step 2 result) to rename/drop columns
2. Forward-fill parent/child data: child rows inherit pricing from parents
3. Enforce data types (prices to float, etc.)
4. Normalize trim values (strip whitespace, preserve markers: •, S, T, E, etc.)
5. Combine EN+FR: if called with EN and FR separately, output language-specific DataFrames
6. Return: Wide-format DataFrame (not melted), ready for Step 4

**Orchestration pattern (per section):**
```python
# Load both EN and FR sheets in Step 1
working_df_en, meta_en = run_step1_validation(df_en, ...)
working_df_fr, meta_fr = run_step1_validation(df_fr, ...)

# Step 2: shared column mapping
step2_result = run_step2_header_normalization(working_df_en, ...)

# Step 3: run SEPARATELY for EN and FR
standardized_en = run_step3_standardization(working_df_en, step2_result, ...)
standardized_fr = run_step3_standardization(working_df_fr, step2_result, ...)

# Collect for Step 4
results_dict["EN"] = standardized_en
results_dict["FR"] = standardized_fr
```

**Files to modify:**
- `accy_v2/oems/honda/pipeline/step3_standardization.py` - Add parent/child forward-fill, handle EN/FR

---

## Key Design Decisions

| Decision | Reasoning |
|----------|-----------|
| **Step 2 returns metadata dict only** | Matches Hyundai/Genesis pattern; base pipeline contract |
| **Step 3 called separately for EN and FR** | Allows processing each language independently; Step 4 merges |
| **Parent/child resolved in Step 3** | Children inherit pricing before output; ready for melting in Step 4 |
| **Sections hidden (flattened)** | Output is one DataFrame, not section-based; sections tracked in metadata only |
| **Trim columns preserved in Step 3** | Step 4 handles melting (wide → long); Step 3 stays focused on standardization |

---

## Implementation Phases

### Phase 1: Implement Step 2 Metadata
- [ ] Build col_mapping from section headers (map 0-16 → canonical names)
- [ ] Extract valid_trim_cols from section headers
- [ ] Return Dict[str, Any] with col_mapping, valid_trim_cols, trim_validation_log
- [ ] Update orchestrator stub to call step2_header_normalization.run()
- [ ] Test with real Honda data (CVIC5D.xlsx)

### Phase 2: Refactor Step 3 Standardization
- [ ] Apply col_mapping to rename/drop columns
- [ ] Add parent/child forward-fill logic
- [ ] Enforce data types
- [ ] Normalize trim values
- [ ] Return wide-format standardized_df

### Phase 3: Verify Step 4 Integration
- [ ] Ensure Step 4 receives both EN and FR outputs
- [ ] Verify Step 4 melts correctly
- [ ] End-to-end test with real Honda data

---

## Verification Checklist

**Step 2 Output:**
- [ ] Returns Dict with col_mapping, valid_trim_cols, trim_validation_log
- [ ] col_mapping maps all 17 columns (0-16)
- [ ] valid_trim_cols contains actual trim names (LX, EX, Sport, etc.)
- [ ] Metadata updated in-place with record_type_counts, parent_row_index

**Step 3 Output:**
- [ ] Receives col_mapping and valid_trim_cols from Step 2
- [ ] Applies col_mapping to rename/drop columns
- [ ] Forward-fills parent/child pricing correctly
- [ ] Enforces float type on price columns
- [ ] Preserves trim columns (not melted yet)
- [ ] Returns wide-format DataFrame

**Integration:**
- [ ] Step 2 output consumed correctly by Step 3
- [ ] Step 3 called separately for EN and FR
- [ ] Step 4 receives both EN and FR outputs
- [ ] End-to-end pipeline produces correct output structure

---

## Related Documents

- `accy_v2/planning/VERSIONING.md` - Versioning strategy
- `accy_v2/docs/SYSTEM_ARCHITECTURE.md` - Pipeline architecture overview
- `accy_v2/oems/hyundai/pipeline/` - Reference implementation (Hyundai pattern)
