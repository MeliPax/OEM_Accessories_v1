# Honda Pipeline Modernization Project

**Version:** v2.7.0 (MINOR feature release)  
**Status:** Planning Complete, Ready for Implementation  
**Created:** 2026-09-23  
**Target Branch:** `feature/honda-pipeline-modernization` (from dev)  

---

## Project Overview

Port the Honda accessory pipeline from legacy monolithic scripts into the modular accy_v2 architecture. This enables Honda to benefit from:
- Shared core utilities (column mapper, DQ logger, pipeline logger)
- Unified model lookup via VehicleSearchEngine
- Config-driven (YAML) settings
- Consistent output format across all OEMs

**Scope:** Replace `scripts/honda_processor.py` with modular `accy_v2/oems/honda/pipeline/` implementation.

---

## Key Architecture Features

✅ **5-Layer Pipeline Integration**
- Layer 1: Data Ingestion (validation, header normalization)
- Layer 2: Data Transformation (section-based, trim melting)
- Layer 3: Model Lookup (VehicleSearchEngine integration)
- Layer 4: Output Filtering (DQ reporting, Excel generation)
- Layer 5: Support Systems (config, translators, loggers)

✅ **Section-Based Processing** (Honda-unique)
- 6 sections per Excel file: Packages, Electronics, Interior, Exterior, Cargo, General
- Config-driven section detection (EN/FR patterns)
- Section-aware trim extraction

✅ **EN/FR Reconciliation** (Honda-unique)
- Separate `*_APP_EN` and `*_APP_FR` sheets
- Composite part number normalization (left-priority for "or"/"ou" variants)
- Reconciliation map with confidence scoring
- DQ tracking for divergences (cost, part count, part numbers)

✅ **Packages/Kits Rollup** (Honda-unique)
- Parent-child detection and aggregation
- Numeric values: keep parent (flag if empty)
- Descriptions: concatenate into comments
- Trim applicability: keep parent (flag if children diverge)

✅ **Batch Processing**
- Directory-based scanning (YYYY-MM folders)
- Multi-file orchestration
- Per-file error quarantine
- Batch-level aggregation & reporting

---

## Timeline & Phases

| Phase | Name | Duration | Status |
|-------|------|----------|--------|
| 1 | Foundation & Setup | Weeks 1–2 | Ready to start |
| 2 | Design Docs & Utilities | Weeks 2–3 | Ready to start (parallel to Phase 3) |
| 3 | Configuration & Validation | Weeks 3–4 | Ready to start (parallel to Phase 4) |
| 4 | Core Pipeline Steps | Weeks 4–6 | Blocked on Phase 3 |
| 5 | Model Lookup & Enrichment | Weeks 6–7 | Blocked on Phase 4 |
| 6 | Output & DQ Reporting | Weeks 7–8 | Blocked on Phase 5 |
| 7 | Testing & Documentation | Weeks 8–12 | Blocked on Phase 6 |

**Total Effort:** ~156 hours (~10 weeks @ 15h/week or ~7 weeks @ 22h/week)

---

## Critical Decisions Made ✅

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Architecture | Extend accy_v2 5-layer pattern | Aligned with existing system; no core changes needed |
| Config Format | YAML (vs JSON) | More readable for nested section structure |
| EN/FR Handling | Separate sheets + reconciliation | Preserves data integrity; enables independent validation |
| Rollup Logic | Parent-driven aggregation | Matches user spec; simplifies data model |
| Model Lookup | Reuse VehicleSearchEngine | No code duplication; inherits all OEM capabilities |
| Batch Orchestration | Multi-file wrapper | Handles Honda's unique single-model-per-file pattern |
| Output Schema | Raw data sheet + confidence | Enables full audit trail; meets user requirements |

---

## Coverage Assessment

✅ **Fully Covered (10/10 challenge areas addressed)**
- Section-level complexity & rollup logic
- Trim detection & applicability
- EN/FR reconciliation & composite part numbers
- Batch processing & error handling
- Model lookup integration
- Output schema & metadata propagation
- State management across steps
- Testing & validation strategy

⚠️ **Minor Gaps (all actionable)**
1. Encoding strategy — Test with real files; add config if needed
2. Trim family matching algorithm — Design during Phase 2
3. DQ rule specifications — Formalize during Phase 2
4. Batch reporting JSON schema — Create during Phase 2
5. Composite part number sync architecture — Implement in Phase 2 utilities

---

## Prerequisites for Phase 1

**Before starting implementation:**

- [ ] Honda feature branch created: `feature/honda-pipeline-modernization` (from dev)
- [ ] Real Honda Excel files available for testing (from `landing_zone/honda/2026/2026-05/`)
- [ ] Sample files confirm:
  - EN/FR sheet naming patterns (e.g., `*_APP_EN`, `*_APP_FR`)
  - Exact section identifier text (Section I headings in both languages)
  - Encoding (UTF-8, Latin-1, etc.)
  - Composite part number examples (EN: "50977-565-45BH or 50977-565-45SH", FR: "50977-565-45BH ou 50977-565-45SH")

---

## Files to Create/Modify

### New Files (Honda-specific)
```
accy_v2/oems/honda/
├── __init__.py
├── orchestrator.py
├── config/
│   ├── section_patterns.yaml
│   ├── reconciliation.yaml
│   ├── trim_config.yaml
│   └── pipeline.yaml
└── pipeline/
    ├── __init__.py
    ├── step1_validation.py
    ├── step2_header_normalization.py
    ├── step3_standardization.py
    ├── step3_5_extract_vehicle_year.py
    ├── step4_transformation.py
    ├── step4_5_model_enrichment.py
    └── step5_output.py

accy_v2/run_honda.py
accy_v2/model_lookup/configs/honda_translator.yaml
accy_v2/model_lookup/configs/honda_classification.yaml
```

### Modified Files (shared utilities)
```
accy_v2/core/helpers/           ← New utility functions
  normalize_composite_part_number()
  validate_section_structure()
  extract_trim_family()

accy_v2/core/helpers/dq_logger.py  ← Add Honda-specific DQ rules
```

---

## Success Criteria

✅ Phase 1 Complete
- [ ] Directory structure created
- [ ] Config scaffolds in place
- [ ] Run script working (error expected; data not yet processed)

✅ Phase 7 Complete
- [ ] All 4 OEM pipelines pass regression testing (zero regressions vs. current)
- [ ] Honda pipeline processes real data successfully
- [ ] DQ reports generated with all rule categories populated
- [ ] Raw data sheet with EN/FR merge confidence created
- [ ] Documentation complete (README, config reference, DQ handbook, troubleshooting guide)

---

## Next Steps

1. ✅ Review & approve planning (DONE)
2. ⏳ Confirm prerequisites (real Honda files, sheet patterns)
3. ⏳ Create feature branch
4. ⏳ Begin Phase 1 (Foundation & Setup)

**Contact:** See NAVIGATION.md for how to move through this project.
