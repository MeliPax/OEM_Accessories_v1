# Phase 2: Design Docs & Core Utilities

**Duration:** Weeks 2–3  
**Effort:** ~20 hours  
**Status:** Ready to start  
**Dependencies:** Phase 1 (directory structure)  
**Parallel Work:** Phases 3 & 4 can start concurrently (use stubs from Phase 2 until complete)

---

## Objectives

1. ✅ Create detailed design documents for complex logic
2. ✅ Implement core utility functions in `accy_v2/core/helpers/`
3. ✅ Create DQ rule specifications catalog
4. ✅ Create batch reporting JSON schema

---

## Deliverables

### A. Design Documents (4 docs)

Create in `DESIGN_DOCS/` folder:

**1. Composite Part Number Normalization** — `composite_part_number_normalization.md`
- Algorithm: left-priority splitting on "or" (EN) / "ou" (FR)
- Edge cases: null, empty, malformed
- Examples: EN "50977-565-45BH or 50977-565-45SH" → "50977-565-45BH"
- Unit test cases

**2. Trim Generalization & Multi-Identification** — `trim_generalization_algorithm.md`
- Problem: "Sport" trim should match ["Sport AWD", "Sport FWD", "Sport Hybrid"]
- Algorithm: prefix matching + family grouping
- Integration with VehicleSearchEngine
- Examples & fallback strategy

**3. DQ Rule Specifications** — `dq_rule_specifications.md`
- All rule names (e.g., `orphan_record_rule`, `rollup_verification_rule`, `section_mismatch_rule`, etc.)
- Message templates for each rule
- When rule fires, what it means, how to fix
- Severity levels (INFO, WARNING, ERROR, CRITICAL)

**4. Batch Reporting JSON Schema** — `batch_reporting_schema.md`
- Structure of `batch_summary_dq.json`
- Aggregation metrics (files processed, reconciliation success rate, etc.)
- File-level vs. batch-level details
- Example JSON output

### B. Core Utility Functions

Create in `accy_v2/core/helpers/` (new module or extend existing):

**`composite_part_number.py`**
```python
def normalize_composite_part_number(part_num: str, language: str) -> str:
    """
    Normalize composite part numbers (e.g., "part1 or part2").
    
    Args:
        part_num: Raw part number (may contain "or"/"ou")
        language: "EN" or "FR"
    
    Returns:
        Single normalized part number (left-priority)
    """
    # Implementation: split on "or" (EN) / "ou" (FR), take first, strip, validate
```

**`section_validation.py`**
```python
def validate_section_structure(df: pd.DataFrame, section_config: dict) -> dict:
    """
    Validate section structure (boundaries, headers, count).
    
    Returns:
        {
            "valid": bool,
            "errors": [list of issues],
            "section_boundaries": [(start_row, end_row), ...],
        }
    """
```

**`trim_helpers.py`**
```python
def extract_trim_family(trim_name: str, model_name: str) -> list:
    """
    Extract trim family variants (e.g., "Sport" → ["Sport AWD", "Sport FWD"]).
    
    Returns:
        List of possible trim matches for database search
    """
    # Stub: full implementation in Phase 5 (model lookup integration)
```

### C. DQ Rule Specifications

Document all rules with names, templates, severity:

```markdown
## DQ Rules Catalog

### Validation Rules (Section I–II)
- `section_missing_rule` — Section identifier not found in file
- `section_count_mismatch_rule` — Expected 6 sections, found N
- `section_order_divergence_rule` — Sections out of expected order
- `header_not_found_rule` — Column headers not found in section
- `orphan_record_rule` — Part has no trims marked (applicability_markers empty)
- `invalid_trim_marker_rule` — Trim marker not in allowed set

### Rollup Rules (Section I–B)
- `rollup_verification_rule` — Child count vs. rolled up count mismatch
- `parent_child_trim_mismatch_rule` — Child trim applicability diverges from parent
- `parent_missing_numeric_rule` — Parent numeric value (price, labor) is empty

### Reconciliation Rules (Section III)
- `en_fr_divergence_rule` — Cost or part count mismatch between EN/FR
- `composite_part_number_normalization_rule` — Composite part number normalized
- `part_mapping_confidence_rule` — EN/FR mapping confidence low (<85%)
- `en_only_part_rule` — Part has no FR equivalent
- `fr_only_part_rule` — Part in FR but no EN equivalent (anomaly)

### Transformation Rules (Section IV–V)
- `trim_parsing_error_rule` — Trim extraction failed
- `cost_mismatch_rule` — EN/FR cost variance >15%
- `part_count_mismatch_rule` — Part availability divergence (coverage <90%)

### Model Lookup Rules (Section V)
- `model_lookup_not_found_rule` — VehicleSearchEngine returned 0 candidates
- `model_lookup_low_confidence_rule` — Confidence < 0.7
- `trim_normalization_rule` — Trim normalized (e.g., "CR-V" → "crv")
```

### D. Batch Reporting Schema

Document `batch_summary_dq.json` structure:

```json
{
  "batch_id": "2026-09",
  "batch_folder": "landing_zone/honda/2026/2026-09/",
  "processing_timestamp": "2026-09-23T14:30:00Z",
  "files_processed": 3,
  "reconciliation_metrics": {
    "total_parts": 4500,
    "parts_successfully_mapped": 4450,
    "en_only_parts": 30,
    "fr_only_parts": 20,
    "cost_mismatches": 12,
    "part_number_divergences": 5
  },
  "summary_warnings": {
    "rollup_verification_rule": 2,
    "en_fr_divergence_rule": 5,
    "trim_parsing_error_rule": 1
  },
  "files_with_issues": [
    {
      "filename": "Accord_2027.xlsx",
      "model": "Accord",
      "year": 2027,
      "status": "PROCESSED_WITH_WARNINGS",
      "warning_count": 8,
      "recommended_action": "Review EN/FR cost mismatches; confirm part availability"
    }
  ]
}
```

---

## Code Changes

### New Files

| File | Purpose |
|------|---------|
| `DESIGN_DOCS/composite_part_number_normalization.md` | Design doc |
| `DESIGN_DOCS/trim_generalization_algorithm.md` | Design doc |
| `DESIGN_DOCS/dq_rule_specifications.md` | Design doc |
| `DESIGN_DOCS/batch_reporting_schema.md` | Design doc |
| `accy_v2/core/helpers/composite_part_number.py` | Utility functions |
| `accy_v2/core/helpers/section_validation.py` | Utility functions |
| `accy_v2/core/helpers/trim_helpers.py` | Utility functions (stubs) |
| `accy_v2/tests/test_composite_part_number.py` | Unit tests |
| `accy_v2/tests/test_section_validation.py` | Unit tests |

### Modified Files

| File | Change |
|------|--------|
| `accy_v2/core/helpers/__init__.py` | Import new utility modules |

---

## Validation Checklist

- [ ] All 4 design documents created in `DESIGN_DOCS/`
- [ ] Design docs reviewed & clear (no ambiguities)
- [ ] Core utility functions implemented with unit tests passing (>80% coverage)
- [ ] DQ rule catalog complete & linked in DECISIONS.md
- [ ] Batch reporting schema document created & example JSON valid
- [ ] All changes committed: "Phase 2: Design docs & core utilities — composite_part_number, section_validation, trim_helpers"

---

## Dependencies for Next Phases

Phases 3 & 4 depend on:
- ✅ Composite part number normalization utility (for Phase 4 reconciliation)
- ✅ Section validation utility (for Phase 3 Step 1)
- ✅ Design docs (reference, not blocking)
- ✅ DQ rule catalog (reference, not blocking)

---

## Notes

- Design docs are reference; code implements based on these specs
- Core utilities are foundational; all later phases use them
- Unit tests required for utilities (>80% coverage) before moving to Phase 3
- Trim family algorithm may be refined during Phase 5 (model lookup integration)

---

**Estimated Completion:** ~18 hours  
**Actual Time:** (To be filled in after completion)
