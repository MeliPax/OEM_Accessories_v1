# Phase 4: Core Pipeline Steps

**Duration:** Weeks 4–6  
**Effort:** ~32 hours  
**Status:** Ready to start (after Phase 3)  
**Dependencies:** Phase 3 (Step 1, config), Phase 2 (utilities)

---

## Objectives

Implement Steps 2–4 (data transformation pipeline + EN/FR reconciliation).

---

## Deliverables

### Step 2: Header Normalization (`step2_header_normalization.py`)

- Section detection (identify section headers)
- Header normalization per section (standardize column names)
- Trim column detection per section (case-insensitive, non-null check)
- Store section boundaries and trim mappings in metadata

**Input:** Validated raw data + metadata  
**Output:** Normalized dataframe + updated metadata

### Step 3: Standardization (`step3_standardization.py`)

- Data cleanup per section (trim whitespace, type coercion)
- **Packages/Kits rollup logic:**
  - Parent detection (has description + price + trims; children don't)
  - Child aggregation (concatenate descriptions into comments)
  - Numeric values (keep parent; flag if empty)
  - Trim applicability (keep parent; flag if children diverge)
  - DQ logging (orphaned children, parent-child mismatches)
- Produce unified dataframe (one row per unique part, all sections merged)
- Extract vehicle_year from metadata

**Input:** Normalized data + metadata  
**Output:** Standardized dataframe (EN only) + metadata

**DQ Rules:**
- `rollup_verification_rule`, `parent_child_trim_mismatch_rule`, `parent_missing_numeric_rule`

### Step 4: Transformation (`step4_transformation.py`) — COMPLEX

**Step 4a: EN/FR Reconciliation (NEW Step 1.5 logic, here)**
- Load FR sheet independently
- Normalize composite part numbers (both EN & FR) using Phase 2 utility
- Create reconciliation map:
  ```python
  reconciliation_map = {
    "EN_part_123": {
      "fr_equivalent": "FR_part_456",
      "status": "MAPPED" | "EN_ONLY" | "FR_ONLY" | "DIVERGED",
      "cost_match": True | False,
      "part_count_match": True | False,
      "confidence": 0.92,
      "dq_warnings": [...]
    }
  }
  ```
- Store in metadata for later use

**Step 4b: Trim Melting & Reconciliation-Aware Join**
- Melt EN trims → long format
- Melt FR trims → long format (separately)
- **Apply reconciliation map:**
  - For each EN part: lookup FR equivalent via map
  - If FR exists: join via reconciliation (not simple left-join)
  - If EN-only: mark in output (null for FR columns)
  - If FR-only: log as anomaly
- Produce output row with both EN and FR columns
- Add `merge_confidence` metadata column
- Track join quality (% successfully mapped)

**Input:** Standardized data (EN) + FR sheet (raw) + reconciliation_map  
**Output:** Long-format dataframe with EN/FR columns + metadata

**DQ Rules:**
- `en_fr_divergence_rule`, `composite_part_number_normalization_rule`, `part_mapping_confidence_rule`
- `en_only_part_rule`, `fr_only_part_rule`

---

## Code Changes

### Files to Create

| File | Purpose |
|------|---------|
| `step2_header_normalization.py` | Full implementation |
| `step3_standardization.py` | Full implementation (includes rollup logic) |
| `step4_transformation.py` | Full implementation (includes reconciliation) |
| `test_step2_*.py`, `test_step3_*.py`, `test_step4_*.py` | Unit tests |

### Modified Files

| File | Change |
|------|--------|
| `orchestrator.py` | Call Steps 2–4 in sequence |

---

## Testing

- Unit tests for each step (input/output validation)
- Integration tests: Step 1 → Step 2 → Step 3 → Step 4 (dataflow)
- Test with real Honda data from landing_zone/

---

## Critical Logic

**Reconciliation map creation (most complex):**
- Match EN and FR records by part number (exact), then cost, then trim applicability
- Use `composite_part_number` utility to normalize
- Calculate confidence scores (how sure are we EN & FR match?)
- Flag divergences (cost mismatch, part count mismatch, part number divergence)

**Rollup parent-child detection:**
- Parent: has non-null values in Description, List Price, Trims
- Child: missing values in Price/Trims, comes after parent
- Aggregate children into parent row

---

## Validation Checklist

- [ ] Step 2 successfully extracts section boundaries & trim columns
- [ ] Step 3 rolls up packages correctly (parent-child aggregation)
- [ ] Step 3 DQ rules fire correctly (orphan, trim mismatch, missing numeric)
- [ ] Step 4 creates reconciliation map (EN/FR matching)
- [ ] Step 4 melts trims to long format
- [ ] Step 4 applies reconciliation map (EN/FR join)
- [ ] Unit test coverage >80% for each step
- [ ] Integration test: full pipeline (Steps 1–4) with real data
- [ ] Commit: "Phase 4: Core Steps 2–4 — header normalization, standardization, reconciliation, transformation"

---

## Next Phase

Phase 4 complete → Phase 5 (Model Lookup) unblocked.

---

**Estimated Completion:** ~30 hours  
**Actual Time:** (To be filled in after completion)
