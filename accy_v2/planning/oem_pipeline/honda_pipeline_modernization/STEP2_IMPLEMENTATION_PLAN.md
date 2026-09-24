# Honda Step 2 Implementation Plan
**Date:** 2026-09-24  
**Status:** Ready to Start  
**Scope:** Data Standardization, Reconciliation, Transformation

---

## Executive Summary

**Step 2** takes validated Honda Excel data and prepares it for model lookup and output.

**Three Parts:**
1. **Part 7:** Header normalization + Section extraction
2. **Part 8:** Data standardization + Packages/kits rollup
3. **Part 9:** EN/FR reconciliation + Divergence tracking

**Input:** Validated Excel + metadata + section boundaries (from Step 1)  
**Output:** Clean, reconciled DataFrame ready for model lookup (Step 3)

**Estimated Effort:** 8-12 hours (1-2 days focused work)  
**Complexity:** Medium (rollup logic + reconciliation)

---

## Architecture: How Step 2 Fits

```
STEP 1: Validation (COMPLETE ✅)
  ├─ Load sheets, extract metadata, detect sections
  ├─ Validate columns, extract trims
  └─ Return: (en_df, fr_df), metadata, warnings

STEP 2: Standardization & Reconciliation (NEXT → YOU ARE HERE)
  ├─ Part 7: Extract section data, normalize headers
  ├─ Part 8: Clean data, detect parent-child, rollup packages
  ├─ Part 9: Match EN↔FR parts, track divergence
  └─ Return: unified_df, reconciliation_map, new_warnings

STEP 3+: Model Lookup & Output (Future)
  ├─ Enrich with model numbers
  ├─ Generate output Excel
  └─ Create DQ reports
```

---

## Part 7: Header Normalization & Section Extraction (2-3 hours)

### Objective
Extract clean data from each section using boundaries from Step 1.

### Input
- `en_df, fr_df` (raw DataFrames from Step 1)
- `section_structure` (section boundaries: en_row, fr_row for each section)
- `trim_columns` (trim column names per section)

### Logic

**For each section:**
```
1. Get section boundaries (en_row, fr_row)
2. Extract rows for that section (from boundary to next section)
3. Read header row (already found in Step 1)
4. Extract data rows below header
5. Map column headers to canonical names (Step 1 already has mappings)
6. Build clean DataFrame for section
```

### Output Structure
```python
section_data = {
    "packages": {
        "en_df": DataFrame([description, part_number, dealer_net, ...]),
        "fr_df": DataFrame([...]),
        "trim_columns": ["Civic", "Accord", "CR-V"],
    },
    "wheels": {
        "en_df": DataFrame([...]),
        "fr_df": DataFrame([...]),
        "trim_columns": ["LX", "EX"],
    },
    # ... (6 sections total)
}
```

### Edge Cases
- Section row = 0 (header in df.columns) → Use df.iloc[0] as header
- Section row > 0 (normal) → Use df.iloc[section_row + 1] as header
- FR section missing → Proceed with EN only, log warning
- No trim columns → Proceed without trims, log warning

### Testing
- [ ] Extract packages section correctly
- [ ] Extract all 6 sections with correct boundaries
- [ ] Headers mapped to canonical names
- [ ] Trim columns included as metadata
- [ ] FR missing section handled gracefully

---

## Part 8: Data Standardization & Rollup (3-4 hours)

### Objective
Clean data, detect parent-child relationships (for packages), aggregate.

### Input
- `section_data` (from Part 7)

### Logic

#### Step 8.1: Data Cleanup
**For each section:**
```python
1. Trim whitespace from all cells
2. Standardize types:
   - Description: string (title case)
   - Part Number: string (uppercase)
   - Costs (Dealer Net, List Price, FRT, Installed Price): float
3. Handle nulls: "" → None
4. Deduplicate: Remove exact duplicates
5. Sort: By description, then part number
```

#### Step 8.2: Parent-Child Detection (Packages Only)
**Problem:** Packages section has parent-child relationships:
- Parent: Main package with price, trims, description
- Children: Variant packages (e.g., "Package A - Sport trim specific")

**Detection Logic:**
```python
# Parent = has description + price + trims filled
# Child = has description but no price, or minimal price

is_parent = (description is not None) and (installed_price > 0) and (trims > 0)
is_child = (description is not None) and (installed_price == 0 or null)

# Mark each row:
row.relationship = "parent" | "child" | "standalone"
row.parent_id = reference_to_parent  # if child
```

#### Step 8.3: Rollup Aggregation (Packages Only)
**For each parent:**
```python
children = rows where row.parent_id == parent.id

# Rollup description (add child variants)
parent.description += " (" + ", ".join(child.descriptions) + ")"

# Rollup numeric (keep parent)
parent.dealer_net = parent.dealer_net  # unchanged
parent.list_price = parent.list_price  # unchanged

# Rollup trims (keep parent; verify children match)
if child.trims != parent.trims:
    log WARNING: "Child trim mismatch: {child.trims} vs {parent.trims}"

# Mark in output
parent.has_children = True
parent.child_count = len(children)
```

### Output Structure
```python
standardized_data = {
    "packages": {
        "en_unified": DataFrame([
            {description: "Package A (Sport, EX-L variants)", 
             part_number: "ABC123",
             dealer_net: 500.00,
             list_price: 750.00,
             has_children: True,
             child_count: 2},
            # ... (other packages, singles and parents)
        ]),
        "fr_unified": DataFrame([...]),
        "trim_columns": ["Civic", "Accord", "CR-V"],
        "rollup_metadata": {
            "parent_count": 3,
            "child_count": 5,
            "trim_mismatches": 0,  # WARNING count
        }
    },
    # ... (5 other sections: no rollup)
}
```

### Edge Cases
- Row with no trims (orphan) → Log WARNING "orphan_applicability"
- Cost divergence EN↔FR → Note in DQ, but don't aggregate yet (Step 9 handles)
- Empty section → Proceed, add to warnings

### Testing
- [ ] Data cleaned (trim, type, dedupe)
- [ ] Parent-child detected (packages)
- [ ] Rollup aggregation works (parent + children → single row)
- [ ] Trim mismatch flagged (WARNING)
- [ ] Orphan records identified (WARNING)

---

## Part 9: EN/FR Reconciliation (3-4 hours)

### Objective
Match EN and FR parts, track divergence, create unified output.

### Input
- `standardized_data` (from Part 8)

### Logic

#### Step 9.1: Build Reconciliation Map
**Goal:** For each EN part, find matching FR part (or mark EN-only/FR-only)

```python
reconciliation_map = {}

for section in sections:
    en_parts = standardized_data[section]["en_unified"]
    fr_parts = standardized_data[section]["fr_unified"]
    
    for en_row in en_parts:
        # Try to find matching FR part
        match = find_fr_match(en_row, fr_parts)
        
        reconciliation_map[en_row.id] = {
            "en_part_number": en_row.part_number,
            "fr_equivalent": match.part_number if match else None,
            "status": "MAPPED" | "EN_ONLY" | "FR_ONLY" | "DIVERGED",
            "cost_match": en_row.price ≈ fr_row.price (if match),
            "part_count_match": en_row.child_count == fr_row.child_count (if match),
            "confidence": 0.0-1.0,
            "dq_warnings": [...]
        }
```

#### Step 9.2: Matching Strategy
```python
def find_fr_match(en_row, fr_parts):
    """Find best matching FR part for EN row."""
    
    # Priority 1: Exact part number match (after normalization)
    normalized_en_pn = normalize_part_number(en_row.part_number)
    for fr_row in fr_parts:
        normalized_fr_pn = normalize_part_number(fr_row.part_number)
        if normalized_en_pn == normalized_fr_pn:
            return fr_row, confidence=0.95
    
    # Priority 2: Description match (both have same name)
    for fr_row in fr_parts:
        if similarity(en_row.description, fr_row.description) > 0.85:
            return fr_row, confidence=0.80
    
    # Priority 3: Cost match (same price ± tolerance)
    for fr_row in fr_parts:
        if abs(en_row.price - fr_row.price) < 10:  # $10 tolerance
            return fr_row, confidence=0.60
    
    # No match found
    return None, confidence=0.0
```

#### Step 9.3: Divergence Tracking
```python
# For matched parts, track how different they are:

divergences = []

if match:
    # Cost divergence
    if en_row.list_price != fr_row.list_price:
        divergences.append({
            "type": "cost_divergence",
            "en_price": en_row.list_price,
            "fr_price": fr_row.list_price,
            "variance_percent": (fr - en) / en * 100,
            "severity": "WARNING" if variance < 5% else "ERROR"
        })
    
    # Part count divergence (children)
    if en_row.child_count != fr_row.child_count:
        divergences.append({
            "type": "part_count_divergence",
            "en_count": en_row.child_count,
            "fr_count": fr_row.child_count,
            "severity": "WARNING"
        })
    
    # Trim mismatch
    if en_trims != fr_trims:
        divergences.append({
            "type": "trim_applicability_divergence",
            "en_trims": en_trims,
            "fr_trims": fr_trims,
            "severity": "WARNING"
        })
```

### Output Structure
```python
output = {
    "unified_data": {
        "section": DataFrame([
            {description: "...",
             part_number: "...",
             dealer_net: 500.00,
             list_price: 750.00,
             en_trim_1: "✓",
             en_trim_2: " ",
             fr_trim_1: "✓",
             fr_trim_2: "✓",
             merge_confidence: 0.95,  # How confident was the EN↔FR match?
             merge_status: "MAPPED"},  # MAPPED, EN_ONLY, FR_ONLY, DIVERGED
        ]),
    },
    "reconciliation_map": {
        # Full mapping details (not in output, but in metadata)
    },
    "divergence_report": {
        # All divergences found
    },
    "dq_warnings": [
        {rule: "en_fr_cost_divergence", severity: "WARNING", section: "packages", ...},
        {rule: "en_fr_part_count_mismatch", severity: "WARNING", ...},
        # ...
    ]
}
```

### Edge Cases
- EN part has no FR equivalent → Mark EN_ONLY, include in output
- FR part has no EN equivalent → Mark FR_ONLY, log as potential data issue
- Multiple FR matches → Use highest confidence score
- Cost divergence > 5% → Mark as ERROR (not just WARNING)
- Part count divergence → Mark as WARNING, flag for review

### Testing
- [ ] Part number matching works (exact + normalized)
- [ ] Description matching works (fuzzy similarity)
- [ ] Cost divergence detected and severity correct
- [ ] Trim applicability compared correctly
- [ ] EN-only and FR-only parts handled
- [ ] Confidence scores reasonable

---

## Integration & Return Value

### Main Orchestrator Update
```python
def validate(excel_file, config):
    # Step 1: Validation (existing)
    (en_df, fr_df), metadata, step1_warnings = _step1_validate(...)
    
    # Step 2: Standardization & Reconciliation (NEW)
    unified_data, reconciliation_map, step2_warnings = _step2_standardize_reconcile(
        en_df, fr_df, metadata, config
    )
    
    # Consolidate warnings
    all_warnings = step1_warnings + step2_warnings
    dq_warnings = _build_dq_warnings(all_warnings)
    
    # Return unified data for Step 3
    metadata["unified_data"] = unified_data
    metadata["reconciliation_map"] = reconciliation_map
    
    return (en_df, fr_df), metadata, dq_warnings
```

### Metadata Structure (Updated)
```python
metadata = {
    # From Step 1
    "model_name": "Accord",
    "vehicle_year": 2026,
    "en_sheet_name": "...",
    "fr_sheet_name": "...",
    "section_structure": {...},
    "trim_columns": {...},
    
    # NEW from Step 2
    "unified_data": {
        "packages": DataFrame(...),
        "wheels": DataFrame(...),
        # ... (6 sections)
    },
    "reconciliation_map": {...},
    "reconciliation_stats": {
        "total_parts": 45,
        "mapped_parts": 42,
        "en_only_parts": 2,
        "fr_only_parts": 1,
        "cost_divergence_count": 3,
        "mapping_confidence_avg": 0.92,
    },
    "validation_status": "PASS" | "PASS_WITH_WARNINGS" | "FAIL",
}
```

---

## Test Plan

### Unit Tests
1. **Header Normalization** (`test_part7_headers.py`)
   - Extract section boundaries
   - Map headers to canonical names
   - Handle sparse Excel (section_row == 0)

2. **Data Standardization** (`test_part8_standardization.py`)
   - Clean data (trim, type, dedupe)
   - Detect parent-child
   - Rollup aggregation

3. **Reconciliation** (`test_part9_reconciliation.py`)
   - Part number matching
   - Description similarity
   - Cost divergence detection
   - Confidence scoring

### Integration Test
- **End-to-End** (`test_e2e_step2.py`)
  - Load sample Honda file
  - Run Step 1 → Step 2
  - Verify unified output
  - Check reconciliation map

### Real Data Test
- Use actual 2026 Accord file
- Verify section extraction
- Check rollup accuracy
- Validate divergence detection

---

## Timeline & Milestones

| Milestone | Effort | Timeline |
|-----------|--------|----------|
| Part 7 (Headers) | 2-3h | Today/Tomorrow AM |
| Part 8 (Standardization) | 3-4h | Tomorrow |
| Part 9 (Reconciliation) | 3-4h | Day 3 |
| Testing + Fixes | 2-3h | Day 3 |
| **TOTAL** | **10-14h** | **3 days** |

---

## Deliverables

### Code
- `step2_standardization.py` (new file, ~300 lines)
  - `_normalize_headers()` (Part 7)
  - `_standardize_data()` (Part 8)
  - `_reconcile_en_fr()` (Part 9)

### Tests
- `test_part7_headers.py` (unit tests)
- `test_part8_standardization.py` (unit tests)
- `test_part9_reconciliation.py` (unit tests)
- `test_e2e_step2.py` (integration test)

### Documentation
- `STEP2_COMPLETION_REPORT.md` (completion report)
- Inline code comments + docstrings

---

## Success Criteria

- [x] All 3 parts implemented
- [x] All unit tests passing
- [x] End-to-end test passing
- [x] Real data test passing (if available)
- [x] Code review approved
- [x] Completion report documented
- [x] No hardcoded values (config-driven)
- [x] Structured logging on major steps
- [x] Error handling (FATAL/ERROR/WARNING)

---

## Ready to Start? ✅

**Prerequisites Met:**
- ✅ Step 1 complete and tested
- ✅ Architecture clear
- ✅ Config structure in place
- ✅ Test data available

**Next Action:** Begin Part 7 implementation

**Questions Before Starting?**
- Any clarifications on logic?
- Any concerns about approach?
- Ready to code now, or need more planning?
