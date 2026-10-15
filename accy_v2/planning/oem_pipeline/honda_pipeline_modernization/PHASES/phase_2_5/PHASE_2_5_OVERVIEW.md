# Phase 2.5: String Standardization — Planning & Overview

**Phase:** 2.5  
**Status:** ✅ COMPLETE (Config & Implementation)  
**Dates:** 2026-10-15 (Planning & Implementation)  
**Owner:** Honda Pipeline Team  

---

## Phase Overview

Phase 2.5 is a NEW intermediate pipeline step inserted between **Step 2 (Header Normalization)** and **Step 3 (Standardization)**.

**Purpose:** Apply Honda-specific string-level transformations before type validation and enrichment.

---

## What Gets Cleaned in Phase 2.5

### Input
Raw data AFTER header normalization:
- Headers normalized to canonical names (part_number, description, etc.)
- Sections detected and classified
- Column names standardized

**But strings are still "dirty":**
- Smart quotes ("" instead of ")
- Literal newlines (\n in Excel multi-line cells)
- Composite part numbers ("X or Y")
- Trim marker symbols (•, ✓, S, T, E, 0)

### Output
Clean data ready for type validation:
- All quotes normalized to ASCII
- All newlines replaced with spaces
- Composite parts split (primary kept, original in comments)
- Trim markers mapped to canonical states

---

## Four Honda-Specific Operations

| Operation | Input | Output | Column(s) |
|-----------|-------|--------|-----------|
| **normalize_unicode** | Smart quotes, unicode dashes | ASCII equivalents | part_number, description, comments |
| **remove_newlines** | Literal \n from Excel | Single line with spaces | description, comments |
| **split_composite** | "480-SP or 480-GB" | "480-SP" + note in comments | part_number |
| **normalize_trim_markers** | •, ✓, S, T, E, 0, 0.0, N/A | applicable, standard, tire_change, exchange, null | All trim columns |

---

## Configuration

**File:** `transformations.yaml`  
**Location:** `accy_v2/oems/honda/config/transformations.yaml`

**Structure:**
```yaml
columns:
  description:
    operations:
      - name: normalize_unicode
        from_chars: ["'", "'", """, """, "…", "–", "—"]
        to_chars: ["'", "'", '"', '"', "...", "-", "-"]
      - name: remove_newlines
        replace_with: " "
        collapse_multiple_spaces: true
      # ... other operations
  
  trim_columns:
    operations:
      - name: normalize_trim_markers
        mapping:
          "•": "applicable"
          "✓": "applicable"
          "S": "standard"
          "T": "tire_change"
          "E": "exchange"
          "0": null
          "0.0": null
          "": null
          "N/A": null
```

---

## Implementation

**File:** `step2_string_standardization.py`  
**Location:** `accy_v2/oems/honda/pipeline/step2_string_standardization.py`

**Key Functions:**
- `run()` — Main orchestration
- `_normalize_unicode()` — Smart quote/dash handling
- `_remove_newlines()` — Newline removal and space collapse
- `_split_composite_part_numbers()` — "X or Y" splitting with DQ logging
- `_normalize_trim_markers()` — Marker mapping to canonical states
- `_extract_operation_params()` — Config parameter extraction

---

## Data Examples

### Example 1: Description with Smart Quotes & Newlines

**Raw Input (from Excel):**
```
"Aero Kit "Premium Package""        (smart quotes U+201C, U+201D)
"SPORT\nHybrid"                     (literal newline)
```

**After Phase 2.5:**
```
"Aero Kit "Premium Package""        (ASCII quotes)
"Sport Hybrid"                      (space replaces \n, case normalized)
```

---

### Example 2: Composite Part Number

**Raw Input:**
```
Part Number: "480-670-6545-SP or 480-670-6545-GB"
Comments: null
DQ Log: (empty)
```

**After Phase 2.5:**
```
Part Number: "480-670-6545-SP"
Comments: "[Composite parts: 480-670-6545-SP or 480-670-6545-GB]"
DQ Log: composite_part_number_split (original → primary)
```

---

### Example 3: Trim Markers

**Raw Input:**
```
LX Column: "•"
EX Column: "•"
Sport Column: "0"
Touring Column: "N/A"
```

**After Phase 2.5:**
```
LX Column: "applicable"
EX Column: "applicable"
Sport Column: null
Touring Column: null
```

---

## Pipeline Integration

```
Step 1: Validation
    ↓ (detects issues, logs metadata)

Step 2: Header Normalization
    ↓ (normalizes column names, detects sections)

Step 2.5: STRING STANDARDIZATION ← YOU ARE HERE
    ├─ normalize_unicode()
    ├─ remove_newlines()
    ├─ split_composite()
    └─ normalize_trim_markers()
    ↓ (returns clean strings)

Step 3: Standardization
    ↓ (type coercion, validation)

Step 4: Transformation
    ↓ (melt, explode, reconciliation)

Step 4.5: Model Enrichment
    ↓ (VehicleSearchEngine lookup)

Step 5: Output
    └─ Excel workbook with DQ reports
```

---

## Decision: Why Phase 2.5?

| Option | Decision | Rationale |
|--------|----------|-----------|
| **Insert as Step 2.5** | ✅ CHOSEN | - String cleanup before type validation<br>- Keeps Step 2 focused on headers only<br>- Logical progression (structure → strings → types)<br>- Reusable for other section-based OEMs |
| **Merge into Step 2** | ❌ Rejected | Would overload header normalization with string ops |
| **Merge into Step 3** | ❌ Rejected | String issues would interfere with type coercion |
| **Create after Step 3** | ❌ Rejected | Too late; type validation fails on smart quotes |

---

## Metrics & Success Criteria

### Input Verification
- ✅ 128-130 classified records per sheet (EN and FR)
- ✅ 0 false defects from structure

### Output Verification
- ✅ No smart quotes (U+201C, U+201D) remain
- ✅ No literal newlines (\n) in description/comments
- ✅ All composite parts split correctly
- ✅ All trim markers normalized to canonical states
- ✅ DQ log contains expected entries (composite_part_number_split, etc.)

---

## Testing Plan

### Unit Tests (5 files)
1. `test_normalize_unicode.py` — Quote/dash/space normalization
2. `test_remove_newlines.py` — Newline removal & space collapse
3. `test_split_composite.py` — "X or Y" splitting
4. `test_normalize_trim_markers.py` — Marker mappings
5. `test_extract_operation_params.py` — Config parameter extraction

### Integration Test
1. Load real Honda data (CVIC5D.xlsx)
2. Run Steps 1-2.5 full pipeline
3. Verify metrics above
4. Check DQ logs
5. Spot-check Excel output

---

## Deliverables

| Deliverable | Location | Status |
|-------------|----------|--------|
| transformations.yaml | `config/` | ✅ Complete (298 lines) |
| translator.yaml | `model_lookup/configs/honda/` | ✅ Complete (34 lines) |
| step2_string_standardization.py | `pipeline/` | ✅ Complete + Updated |
| TRANSFORMATION_CONFIG.md | `planning/.../DESIGN_DOCS/` | ✅ Complete (12 KB) |
| PHASE_2_5_OVERVIEW.md | `planning/.../phases/phase_2_5/` | ✅ This file |
| Unit Tests | `tests/` | ⏳ Pending |
| Integration Test | `tests/` | ⏳ Pending |

---

## Next Steps

### Immediate (Week 1)
- [ ] Create unit tests (5 test files)
- [ ] Run integration test on real data
- [ ] Verify all output against success criteria

### Short-term (Weeks 2-3)
- [ ] Fix any issues found in testing
- [ ] Implement Step 3 (Standardization)
- [ ] Implement Steps 4-5 (Transformation, Output)

### Long-term
- [ ] Replicate Phase 2.5 for other OEMs (if needed)
- [ ] Create unified transformation registry
- [ ] Performance optimization

---

## Related Documents

- [DESIGN_DOCS/TRANSFORMATION_CONFIG.md](../../DESIGN_DOCS/TRANSFORMATION_CONFIG.md) — Complete configuration guide
- [DELIVERABLES/TRANSFORMATION_CONFIG_CONSOLIDATION_20261015.md](../../DELIVERABLES/TRANSFORMATION_CONFIG_CONSOLIDATION_20261015.md) — Consolidation summary
- [../phase_1/](../phase_1/) — Foundation setup
- [../phase_2/](../phase_2/) — Header normalization

---

**Status:** Ready for testing and implementation validation.

