# Phase 7: Testing & Documentation

**Duration:** Weeks 8–12  
**Effort:** ~32 hours  
**Status:** Ready to start (after Phase 6)  
**Dependencies:** Phase 6 (complete implementation)

---

## Deliverables

### A. Unit Tests

**Coverage Target:** >80% for each module

Test files:
- `test_composite_part_number.py` — Part number normalization
- `test_section_validation.py` — Section boundary detection
- `test_step1_validation.py` — Metadata extraction, schema validation
- `test_step2_header_norm.py` — Header normalization, trim detection
- `test_step3_standardization.py` — Rollup logic, parent-child detection
- `test_step4_transformation.py` — Reconciliation map, EN/FR join
- `test_step4_5_model_enrichment.py` — Trim tokenization, VehicleSearchEngine integration
- `test_step5_output.py` — Excel generation, schema validation

**Run:**
```bash
pytest accy_v2/tests/test_honda* -v --cov=accy_v2/oems/honda --cov-report=html
```

### B. Integration Tests

End-to-end pipeline with real Honda data:

**Test Setup:**
- Use real files from `landing_zone/honda/2026/2026-09/`
- Process full batch (all files)
- Verify output structure & content

**Validation:**
- [ ] All files processed successfully
- [ ] No crashes or unexpected exceptions
- [ ] Output Excel files generated (all 4 sheets)
- [ ] batch_summary_dq.json valid JSON
- [ ] DQ warnings populated (at least one file should have warnings)
- [ ] Model numbers populated (>90% of parts should have model_number)

**Run:**
```bash
python accy_v2/run_honda.py --input landing_zone/honda/2026/2026-09/ --output output/
```

### C. Regression Tests

Verify existing OEMs unaffected:

**Test Each OEM:**
- Run full pipeline (Hyundai, Genesis, Mazda, Mitsubishi)
- Compare output metrics (row counts, model_number success rate)
- Verify zero regressions vs. baseline

**Run:**
```bash
pytest accy_v2/tests/test_regression* -v
```

### D. Performance Testing

**Metrics to measure:**
- Time per file (target: <2 min per file, 10–13 files per batch)
- Memory usage (target: <1GB for batch of 13 files)
- Reconciliation engine performance (fuzzy matching should be <30% of total time)

**Optimization if needed:**
- Profile reconciliation engine (may add caching if >5min/batch)
- Optimize dataframe operations (vectorize where possible)

### E. Documentation

**README.md** — How to run Honda pipeline
```markdown
# Honda Pipeline

Usage:
  python accy_v2/run_honda.py [--input DIR] [--output DIR]

Features:
- EN/FR reconciliation with confidence scoring
- Packages/Kits rollup with quality validation
- VehicleSearchEngine integration (model lookup)
- Batch processing (multi-file directory scanning)

Output:
- main.xlsx (ready-to-download sheet)
- raw_data.xlsx (audit trail for review)
- batch_summary_dq.json (aggregated metrics)
```

**Config Reference** — How to configure Honda
```markdown
# Honda Configuration Guide

## section_patterns.yaml
Defines section identifiers (EN & FR)

## reconciliation.yaml
EN/FR matching rules, composite part number normalization

## trim_config.yaml
Applicability markers, tokenization rules

## pipeline.yaml
Error handling strategy, batch settings
```

**DQ Handbook** — How to interpret output & fix issues
```markdown
# Data Quality Handbook

## Understanding DQ Warnings

### section_missing_rule
What it means: Section not found in file
How to fix: Verify file structure; confirm section identifiers

### rollup_verification_rule
What it means: Package rollup child count mismatch
How to fix: Review parent-child relationships in source file

### en_fr_divergence_rule
What it means: EN/FR cost or part count divergence
How to fix: Confirm correct pricing; verify part lists with partner

[... more rules ...]
```

**Troubleshooting Guide**
- Common issues & solutions
- Error messages & recovery steps
- Performance tuning tips

### F. Handoff Package

**User-Facing Documents:**
1. Quick start guide (5-minute setup)
2. Operator manual (how to run, what to expect)
3. Data dictionary (output columns, metadata fields)
4. Partner communication template (sharing DQ findings)

**Developer-Facing Documents:**
1. Architecture overview (5-layer pipeline, Honda additions)
2. Code walkthrough (high-level flow through each step)
3. Extension guide (how to add new OEM, modify Honda)
4. Debugging guide (common breakpoints, how to instrument)

---

## Code Changes

**No new code** (implementation complete by Phase 6)

**Files to create/update:**
- Add unit tests (comprehensive coverage)
- Add integration tests (real data validation)
- Add regression tests (existing OEM comparison)
- Create documentation files (README, DQ handbook, etc.)

---

## Validation Checklist

### Testing
- [ ] All unit tests passing (>80% coverage)
- [ ] Integration test: full batch processes without errors
- [ ] Regression test: all 4 existing OEMs pass (zero regressions)
- [ ] Performance: batch processes in <25 min (2 min/file avg × 13 files)
- [ ] Model lookup success rate >90%

### Documentation
- [ ] README.md complete (usage, features, output)
- [ ] Config reference complete (all YAML sections documented)
- [ ] DQ handbook complete (all rules explained, fix guidance)
- [ ] Troubleshooting guide complete
- [ ] Quick start guide (5-minute setup)
- [ ] Operator manual (step-by-step for running pipeline)
- [ ] Data dictionary (all output columns documented)

### Handoff
- [ ] All documentation reviewed & clear
- [ ] Code comments updated (explain non-obvious logic)
- [ ] Commit: "Phase 7: Testing & Documentation — unit/integration/regression tests, comprehensive documentation"

---

## Final Checklist Before Release

- [ ] All 7 phases completed
- [ ] All tests passing (unit >80%, integration 100%, regression 100%)
- [ ] All documentation complete & reviewed
- [ ] Code review completed (team feedback incorporated)
- [ ] Branch ready for merge to dev
- [ ] Create tag: `honda-pipeline-v2.7.0` (before merging)
- [ ] Create release notes (summarizing changes, new features, known limitations)

---

## Post-Implementation

**After merge to dev:**
1. Verify CI/CD pipeline passes (all tests, linting, coverage)
2. Prepare for v2.7.0 release (update CHANGELOG, tag main)
3. Archive this project folder → `oem_pipeline/archive/honda_pipeline_modernization_v2.7.0/`
4. Update project status in `oem_pipeline/PROJECTS_INDEX.md`

---

**Estimated Completion:** ~30 hours  
**Actual Time:** (To be filled in after completion)
