# Phase 4: Core Pipeline Steps — Clarified Requirements

**Status:** Clarifications Confirmed (2026-09-24)  
**Source:** User input during Phase 3 completion review  
**Applies To:** Step 1 (Validation), Steps 2-4 (Transformation Pipeline)

---

## 1. Parent-Child Rollup Logic (Step 3)

### Clarification: Comment Concatenation Format

**Rule:** Child descriptions are appended to parent's comment field with specific format.

**Format Pattern:**
```
[Original parent comment text] Includes: [child description 1], [child description 2], ...
```

**Example:**

*Before Rollup:*
- Parent row: Description="Wheel & Tire Package", Comment="Priced as a set of 4 wheels."
  - Trim applicability: LX ✓, SPORT ✓, EX ✓
  - List Price: 1980, Labor: 1.2

- Child 1: Description="17\" Enkei Draco Wheels - Silver or Gloss Black", (no comment)
- Child 2: Description="Michelin X-ICE Snow Tires - 235/65/17", (no comment)

*After Rollup:*
- Single output row:
  - Description: "Wheel & Tire Package"
  - Comment: "Priced as a set of 4 wheels. Includes: 17\" Enkei Draco Wheels - Silver or Gloss Black, Michelin X-ICE Snow Tires - 235/65/17"
  - Trim applicability: LX ✓, SPORT ✓, EX ✓ (from parent)
  - List Price: 1980, Labor: 1.2 (from parent)

**Implementation Details:**
- Original comment text is preserved first
- Add " Includes: " separator
- Comma-separated child descriptions (one per child)
- No bullets or numbering (flat comma-separated list)
- Special characters in descriptions preserved (quotes, hyphens, etc.)

**DQ Implications:**
- Flag if parent comment is empty (will result in comment = "Includes: ...")
- Log parent-child count in metadata (for audit trail)
- Track which children were aggregated into parent (in raw data sheet)

---

## 2. Raw Data Sheet Requirements (Step 4 Output)

### Clarification: Complete Audit Trail

**Goal:** Raw data sheet shows **all original extracted data** (parent AND child rows) before any rollup/reconciliation.

**What Goes in Raw Data Sheet:**
- ✅ All parent rows (as extracted from Excel)
- ✅ All child rows (as extracted from Excel)
- ✅ Metadata for each row:
  - Source file name
  - Source file model name
  - Source file year
  - Section where row was found (1.0 Packages, 2.0 Wheels, etc.)
  - Row number in source file
  - Row type: "parent" or "child"
  - If child: reference to parent row ID
  - EN/FR reconciliation status (MAPPED, EN_ONLY, FR_ONLY, DIVERGED)
  - All divergence flags (cost_divergence, part_number_divergence, etc.)

**Structure:**
```
Raw Data Sheet Columns (left to right):
├─ Source metadata (file, model, year, section, row_type, parent_id)
├─ EN values (Description, Part Number, Dealer Net, List Price, FRT, Installed Price, Trims, Comment)
├─ FR values (Description, Part Number, Dealer Net, List Price, FRT, Installed Price, Trims, Comment)
├─ Reconciliation status
├─ Divergence flags
└─ DQ warnings
```

**Purpose:**
- Full audit trail: trace any output row back to source
- Transparency: see exactly what was aggregated/reconciled
- Quality assurance: partner review of raw extractions
- Debugging: identify where data issues originated

**Raw Data Sheet Visibility:**
- Include ALL rows (parent, child, EN-only, FR-only, diverged)
- One row per source row (no aggregation in this sheet)
- Preserve exact values as extracted from Excel
- No transformations or normalizations

---

## 3. Testing Strategy (All Phases)

### Clarification: Unit Tests Required

**Approach:** Unit test each step independently + integration tests

**Why Unit Tests:**
- Verify each step's logic in isolation
- Catch bugs early (smaller scope = faster debugging)
- Enable regression testing (run units after changes)
- Document expected behavior

**Unit Test Scope by Step:**

#### **Step 1: Validation**
- ✅ Section detection (all 6 sections found, correct order?)
- ✅ Column validation (EN/FR headers match expected set?)
- ✅ Metadata extraction (model name, year extracted correctly?)
- ✅ Metadata extraction fallback (Level 1 top 5 rows, Level 2 regex)
- ✅ DQ logging (warnings logged for issues? severity correct?)
- ✅ Error handling (FATAL errors raised, validation continues on warnings)

#### **Step 2: Header Normalization**
- ✅ Section boundary detection (correct row numbers for each section)
- ✅ Trim column extraction (all trim columns identified, correct order)
- ✅ Header normalization (EN/FR headers mapped to canonical names)
- ✅ Section metadata storage (boundaries, trim_columns stored correctly)

#### **Step 3: Standardization & Rollup**
- ✅ Data cleanup (whitespace trimmed, types coerced)
- ✅ Parent-child detection (parent has price + trims, children don't)
- ✅ Child aggregation (descriptions concatenated with "Includes: " format)
- ✅ Orphan detection (rows with no applicable trims flagged)
- ✅ Numeric handling (parent values kept, child values ignored, empty parent flagged)
- ✅ Trim applicability inheritance (parent trim list used, child divergence flagged)

#### **Step 4: Transformation & Reconciliation**
- ✅ EN sheet melting (trims unpivoted to long format correctly)
- ✅ FR sheet melting (trims unpivoted to long format correctly)
- ✅ Reconciliation map application (EN/FR rows matched correctly)
- ✅ Divergence detection (cost, part number, trim divergences flagged)
- ✅ Merge confidence calculation (starts 1.0, penalties applied)
- ✅ Output row structure (both EN and FR columns present, merge_confidence added)

#### **Integration Tests**
- ✅ End-to-end: real Honda file through all 4 steps
- ✅ Output validation: columns present, row counts correct, no data loss

**Testing Data:**
- Use real sample files (Accord, Civic 4D from landing_zone/)
- Create minimal synthetic test cases (edge cases: empty comments, orphans, divergences)
- Version-control test data (small, representative samples)

**Test Coverage Target:** >80% per step (code coverage + behavior coverage)

---

## 4. Implementation Sequence (Recommendation)

**Based on the clarifications above, recommended order:**

1. **Step 1 (Validation)** [6-8 hours]
   - Tests: Section detection, column validation, metadata extraction (both fallback levels)
   - Output: Validated DataFrame + metadata dict + DQ warnings list

2. **Step 2 (Header Normalization)** [4-6 hours]
   - Tests: Section boundaries, trim column extraction, header mapping
   - Output: DataFrame with section-aware structure + section/trim metadata

3. **Step 3 (Standardization & Rollup)** [10-12 hours]
   - Tests: Parent-child detection, description concatenation format, orphan detection, trim inheritance
   - Output: Unified DataFrame (one row per part, all sections merged) + rollup metadata

4. **Step 4 (Transformation & Reconciliation)** [8-10 hours]
   - Tests: EN/FR melting, reconciliation map application, divergence detection, merge_confidence calculation
   - Output: Final transformation-ready DataFrame + confidence scores + raw data audit trail

**Total: ~40-44 hours (extends Phase 3 into Phase 4)**

---

## 5. Updated DQ Rules (from Clarifications)

| Rule | Trigger | Severity | Action |
|------|---------|----------|--------|
| `parent_comment_empty_rule` | Parent row has no original comment before rollup | WARNING | Log (child descriptions will create "Includes: ..." comment) |
| `parent_child_count_mismatch_rule` | Child count doesn't match aggregation result | WARNING | Log for audit |
| `orphan_parent_rule` | Parent row with zero applicable trims across all sections | WARNING | Flag for review |
| `child_divergent_trims_rule` | Child trim applicability differs from parent | WARNING | Flag; keep parent trims |
| `raw_data_completeness_rule` | Raw data sheet missing a source row | ERROR | Log and investigate |
| `merge_confidence_calculation_error_rule` | Merge confidence not in [0.0, 1.0] range | ERROR | Log and flag row |

---

## 6. Raw Data Sheet Schema (Detailed)

### Column Order (Left to Right)

```yaml
Source_Metadata:
  - source_file_name          # e.g., "26MY_ACCORD_APP_EN.xlsx"
  - source_model_name         # e.g., "Accord"
  - source_vehicle_year       # e.g., 2026
  - source_section            # e.g., "1.0 Packages and Kits"
  - source_row_number         # Original row in Excel file
  - row_type                  # "parent" or "child"
  - parent_row_id             # If child, points to parent row_id

EN_Original_Values:
  - en_description
  - en_part_number
  - en_dealer_net
  - en_list_price
  - en_frt
  - en_installed_price
  - en_trim_columns           # All trim applicability markers (LX, SPORT, EX, etc.)
  - en_comment

FR_Original_Values:
  - fr_description
  - fr_part_number
  - fr_dealer_net
  - fr_list_price
  - fr_frt
  - fr_installed_price
  - fr_trim_columns           # All trim applicability markers (LX, SPORT, EX, etc.)
  - fr_comment

Reconciliation_Metadata:
  - reconciliation_status     # MAPPED, EN_ONLY, FR_ONLY, DIVERGED
  - cost_match                # true/false
  - part_number_match         # true/false
  - trim_match                # true/false
  - merge_confidence          # 0.0-1.0

DQ_Metadata:
  - cost_divergence_flag      # true if EN cost ≠ FR cost
  - part_number_divergence_flag
  - description_divergence_flag
  - trim_divergence_flag
  - dq_warnings               # Comma-separated list of rule names that fired for this row
```

---

## 7. Metadata Propagation Through Steps

**Step 1 → Step 2 → Step 3 → Step 4:**

```python
metadata = {
  "group_key": "accord_2026",
  "model_name": "Accord",
  "vehicle_year": 2026,
  "source_file": "26MY_ACCORD_APP_EN.xlsx",
  
  # Step 1 output
  "validation_warnings": [...],
  "sheet_names": {"en": "26MY_ACCORD_APP_EN", "fr": "26MY_ACCORD_APP_FR"},
  
  # Step 2 output
  "section_boundaries": {"packages": (11, 56), "wheels": (57, 66), ...},
  "trim_columns": ["LX", "SPORT", "EX", "TOURING"],
  "section_structure": {...},
  
  # Step 3 output
  "parent_child_mapping": {123: [124, 125], 150: [151, 152]},  # parent_id: [child_ids]
  "rollup_metadata": {...},
  
  # Step 4 output
  "reconciliation_map": {...},
  "fr_data": <DataFrame>,  # For EN/FR join
}
```

---

## Status & Next Steps

**Clarifications Documented:** ✅  
**Ready for Implementation:** ✅ (awaiting Phase approach decision)

**Decision Needed:**
- [ ] **Option A:** Complete Phase 3 (Step 1 only, ~6-8 hours), then Phase 4 (Steps 2-4, ~32 hours)
- [ ] **Option B:** Extended Phase 4 (Steps 1-4 together, ~40-44 hours)

---

**Last Updated:** 2026-09-24  
**Clarifications Source:** User feedback during Phase 3 review
