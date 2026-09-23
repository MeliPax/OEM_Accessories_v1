# Phase 3: Configuration & Validation

**Duration:** Weeks 3–4  
**Effort:** ~24 hours  
**Status:** Ready to start (after Phase 1)  
**Dependencies:** Phase 1 (directory structure), Phase 2 (utilities available)  
**Parallel Work:** Can start immediately after Phase 1 completes

---

## Objectives

1. ✅ Populate config YAML files with actual data (from real Honda files)
2. ✅ Implement Step 1 (Validation & reconciliation metadata extraction)
3. ✅ Create/update translator and classifier configs for Honda

---

## Deliverables

### A. Config File Population

**`section_patterns.yaml`** — Populate with real section identifiers
- Must confirm with actual Honda Excel files from `landing_zone/honda/2026/2026-09/`
- Capture EN and FR text exactly
- Add comments for each section

**`reconciliation.yaml`** — EN/FR sheet patterns and rules
- Sheet naming patterns (confirm with real files)
- Composite part number rules (left-priority algorithm details)
- Matching priority levels (part number, cost, trims, comments)
- EN/FR divergence thresholds (cost variance %, part coverage %, etc.)

**`trim_config.yaml`** — Applicability markers and tokenization
- Confirm applicability markers with real files (["•", "T", "E"] or different?)
- Compound keyword rules (e.g., "EX-L" keeps hyphen)
- Confirm tokenization behavior

**`pipeline.yaml`** — Error handling and batch settings
- Error type → action mapping (FATAL, WARNING, QUARANTINE)
- Batch quarantine threshold
- Publication date extraction config

### B. Step 1 Implementation

Implement `accy_v2/oems/honda/pipeline/step1_validation.py`:

**Key Functions:**
1. Load Excel file (EN sheet only for now)
2. Validate sheet name (matches pattern)
3. Validate required columns present
4. Validate section structure (all 6 sections found, in order)
5. Extract metadata:
   - `model_name` (from file header metadata row)
   - `vehicle_year` (from file header metadata row)
   - `publication_date` (if present in file)
   - `section_boundaries` (row indices for each section)
   - `trim_columns` (detected per section)
6. Log validation results (DQ warnings for issues)

**Output:** `(validated_data, metadata, validation_warnings)`

**DQ Rules Used:**
- `section_missing_rule` — section identifier not found
- `section_order_divergence_rule` — sections out of order
- `header_not_found_rule` — column headers missing

### C. Translator & Classifier Configs

Create:
- `accy_v2/model_lookup/configs/honda_translator.yaml` (likely minimal for Honda)
- `accy_v2/model_lookup/configs/honda_classification.yaml` (trim/engine type classifications)

Based on existing Hyundai/Mazda patterns.

---

## Code Changes

### Files to Create

| File | Purpose |
|------|---------|
| `accy_v2/oems/honda/config/section_patterns.yaml` | Populated with real data |
| `accy_v2/oems/honda/config/reconciliation.yaml` | Populated with real data |
| `accy_v2/oems/honda/config/trim_config.yaml` | Populated with real data |
| `accy_v2/oems/honda/config/pipeline.yaml` | Populated with real data |
| `accy_v2/oems/honda/pipeline/step1_validation.py` | Full implementation |
| `accy_v2/model_lookup/configs/honda_translator.yaml` | Translator rules |
| `accy_v2/model_lookup/configs/honda_classification.yaml` | Token classifications |
| `accy_v2/tests/test_step1_validation.py` | Unit tests |

### Modified Files

| File | Change |
|------|--------|
| `accy_v2/oems/honda/orchestrator.py` | Call Step 1 in run() method |

---

## Validation Checklist

**Before Populating Config:**
- [ ] Real Honda Excel files available (from landing_zone/honda/2026/2026-09/)
- [ ] Confirm section identifier text (EN & FR) from actual files
- [ ] Confirm sheet naming patterns (EN & FR)
- [ ] Confirm applicability markers used in files
- [ ] Sample composite part numbers noted (for later verification)

**After Implementation:**
- [ ] All YAML config files populated & valid
- [ ] Step 1 implementation complete & passing unit tests (>80% coverage)
- [ ] Translator & Classifier configs created
- [ ] Step 1 successfully extracts:
  - [ ] Model name
  - [ ] Vehicle year
  - [ ] Section boundaries
  - [ ] Trim columns per section
  - [ ] Metadata in correct structure
- [ ] DQ warnings logged for validation issues
- [ ] Commit: "Phase 3: Configuration & Step 1 Validation — config population, metadata extraction"

---

## Integration with Step 1

Phase 3 Step 1 must:
1. Call `section_validation.validate_section_structure()` (from Phase 2 utilities)
2. Use `trim_config.yaml` to detect applicability markers
3. Populate metadata dict for downstream steps
4. Log all validation warnings to DQ logger

---

## Critical Input

**User Must Provide (before Phase 3):**
- [ ] Sample Honda Excel file for inspection
- [ ] Exact section identifier text (EN & FR)
- [ ] Sheet naming patterns currently used
- [ ] Applicability marker characters (confirm ["•", "T", "E"])
- [ ] Sample composite part numbers (EN & FR)

---

## Next Phase

Phase 3 complete → Phase 4 (Core Pipeline Steps) unblocked.

**Does NOT block Phase 2** — Phase 2 completes independently.

---

**Estimated Completion:** ~22 hours (config + Step 1 implementation + testing)  
**Actual Time:** (To be filled in after completion)
