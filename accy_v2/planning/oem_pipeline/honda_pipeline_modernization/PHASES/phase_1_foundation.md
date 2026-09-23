# Phase 1: Foundation & Setup

**Duration:** Weeks 1–2  
**Effort:** ~12 hours  
**Status:** Ready to start  
**Dependencies:** None

---

## Objectives

1. ✅ Create Honda project directory structure in `accy_v2/oems/honda/`
2. ✅ Create config file scaffolds (will be populated in Phase 3)
3. ✅ Create run script (`accy_v2/run_honda.py`)
4. ✅ Integrate Honda into test suite
5. ✅ Create feature branch with all above committed

---

## Deliverables

### A. Directory Structure

Create:
```
accy_v2/oems/honda/
├── __init__.py
├── orchestrator.py (skeleton with docstrings)
└── config/
    ├── section_patterns.yaml (scaffold)
    ├── reconciliation.yaml (scaffold)
    ├── trim_config.yaml (scaffold)
    └── pipeline.yaml (scaffold)

accy_v2/oems/honda/pipeline/
├── __init__.py
├── step1_validation.py (scaffold)
├── step2_header_normalization.py (scaffold)
├── step3_standardization.py (scaffold)
├── step3_5_extract_vehicle_year.py (scaffold)
├── step4_transformation.py (scaffold)
├── step4_5_model_enrichment.py (scaffold)
└── step5_output.py (scaffold)
```

### B. Config File Scaffolds

Create YAML files with comments describing what each section will contain:

**`section_patterns.yaml`** — Section identification patterns
```yaml
# Will be populated in Phase 3 with actual section identifiers
sections:
  packages:
    en: "1.0 Packages and Kits"          # (placeholder)
    fr: "1.0 Groupes et ensembles"       # (placeholder)
  # ... 6 sections total
```

**`reconciliation.yaml`** — EN/FR sheet patterns and matching rules
```yaml
sheet_patterns:
  en: ["*_APP_EN", "*_EN"]                # (placeholder)
  fr: ["*_APP_FR", "*_FR"]                # (placeholder)
composite_part_number_strategy:
  priority: "left"                        # Keep left side of "or"/"ou"
  # ... details to be filled in Phase 3
```

**`trim_config.yaml`** — Applicability markers and tokenization
```yaml
trim_column_values:
  applicability_markers: ["•", "T", "E"]  # Case-insensitive
  not_applicable_markers: [" ", "", "N/A"]
tokenization:
  split_on: [" ", "-"]
  compound_keywords: ["EX-L", "Sport-L"]  # Keep these together
```

**`pipeline.yaml`** — Error handling and batch settings
```yaml
error_handling:
  FATAL: ["missing_section", "encoding_error"]
  WARNING: ["trim_parsing_error", "cost_mismatch"]
  quarantine_threshold: 0.10              # 10% errors before quarantine
batch_settings:
  scan_pattern: "**/*.xlsx"               # Directory scanning
  publication_date_extraction: true       # Extract from file headers
```

### C. Run Script

Create `accy_v2/run_honda.py`:
```python
#!/usr/bin/env python
"""
Honda Pipeline Orchestrator

Usage:
  python run_honda.py [options]

Options:
  --input DIR           Input directory (default: landing_zone/honda/)
  --output DIR          Output directory (default: output/)
  --batch-id ID         Batch ID (default: auto-generated from folder name)
  --dry-run             Don't write outputs
"""

# Imports
from accy_v2.oems.honda.orchestrator import HondaPipeline

# Main logic (minimal)
if __name__ == "__main__":
    pipeline = HondaPipeline()
    pipeline.run()
```

Pattern mirrors existing OEM run scripts (see `run_hyundai.py`, `run_mazda.py`).

### D. Test Suite Integration

Create/update test files:
- `accy_v2/tests/test_honda_pipeline.py` (stub with placeholder test classes)
- `accy_v2/tests/conftest.py` (add Honda fixtures if needed)
- Update main test runner to include Honda in regression tests

### E. Feature Branch

Create and commit:
```bash
git checkout dev && git pull
git checkout -b feature/honda-pipeline-modernization
# Commit all Phase 1 files
git push -u origin feature/honda-pipeline-modernization
```

---

## Code Changes

### Files to Create

| File | Size | Purpose |
|------|------|---------|
| `accy_v2/oems/honda/__init__.py` | 10 lines | Module marker |
| `accy_v2/oems/honda/orchestrator.py` | 100 lines | Skeleton with docstrings |
| `accy_v2/oems/honda/config/*.yaml` | 50 lines each | Config scaffolds (4 files) |
| `accy_v2/oems/honda/pipeline/*.py` | 50 lines each | Step stubs (7 files) |
| `accy_v2/run_honda.py` | 30 lines | Run script |
| `accy_v2/tests/test_honda_pipeline.py` | 100 lines | Test stubs |

**Total:** ~550 lines of boilerplate (mostly scaffolds & docstrings)

### Files to Modify

| File | Change | Impact |
|------|--------|--------|
| `accy_v2/__init__.py` | Import Honda module | Minimal (1 line) |
| `accy_v2/tests/conftest.py` | Add Honda test fixtures | Minimal (10–20 lines) |
| Main test runner | Add Honda to regression matrix | Minimal (5 lines) |

---

## Validation Checklist

- [ ] All directories created
- [ ] All config YAML files created (with comments describing placeholders)
- [ ] All step Python files created (with function stubs)
- [ ] Run script created and executable
- [ ] Test stubs created
- [ ] Feature branch created and pushed
- [ ] All changes committed with message: "Phase 1: Foundation & Setup — directory structure, config scaffolds, run script"
- [ ] `git status` shows clean working tree

---

## Next Phase

Phase 1 complete → Proceed to Phase 2 (Design Docs & Utilities) and Phase 3 (Configuration & Validation) in parallel.

**Blocking:** Nothing blocks Phases 2 & 3 (they only need directory structure, which Phase 1 provides)

---

## Notes

- All step files are scaffolds (function stubs with docstrings); actual implementation happens in Phases 3–6
- Config files are scaffolds with comments; actual values populated in Phase 3 (after verifying with real Honda files)
- Run script is minimal; orchestrator logic implemented in later phases
- No code will actually execute successfully until Phase 3 (validation) + Phase 4+ (transformation pipeline)

---

**Estimated Completion:** ~2 hours (folder creation + file scaffolding + testing)  
**Actual Time:** (To be filled in after completion)
