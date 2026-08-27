# Universal OEM Configuration Framework Roadmap

**Vision:** Establish a standardized, automatable, enforceable pattern for building and validating OEM pipelines across all manufacturers.

**Status:** In Progress (Phase 1: Mitsubishi)  
**Date:** 2026-08-27  

---

## Executive Vision

Currently, each OEM pipeline is built independently with:
- ✗ Different quality assurance approaches
- ✗ Inconsistent translator-classifier alignment
- ✗ Manual validation per OEM
- ✗ No automated safety nets

**Goal:** Build a universal framework that:
- ✓ Standardizes all OEM configs
- ✓ Automates validation via contract tests
- ✓ Prevents entire bug classes (e.g., translator-classifier misalignment)
- ✓ Reduces new OEM onboarding from ~2 days to ~4 hours
- ✓ Makes DQ assurance consistent and auditable

---

## Multi-Phase Roadmap

### Phase 1: Mitsubishi Translator-Classifier Alignment (THIS WEEK)
**Status:** In Progress  
**Folder:** `mitsubishi_translator_classifier_alignment/`

Fix the Mitsubishi-specific gap where translator outputs aren't recognized by classifier.

- [ ] Phase 1: Config changes (5 min)
- [ ] Phase 2: Contract test (30 min)
- [ ] Phase 3: E2E validation (1 hour)

**Deliverable:** Proven pattern + test framework  
**Next gate:** Mitsubishi Phase 3 validation passes

---

### Phase 2: Hyundai Translator-Classifier Alignment (NEXT WEEK)
**Status:** Not Started  
**Folder:** `hyundai_translator_classifier_alignment/` (to be created)

Apply the same pattern to Hyundai.

- [ ] Audit translator-classifier alignment (identify gaps)
- [ ] Apply Phase 1-3 from Mitsubishi pattern
- [ ] E2E validation on Hyundai data

**Expected effort:** 1-2 hours (reuse Mitsubishi pattern)  
**Next gate:** Hyundai validation passes

---

### Phase 3: Genesis Translator-Classifier Alignment (FOLLOWING WEEK)
**Status:** Not Started  
**Folder:** `genesis_translator_classifier_alignment/` (to be created)

Apply the same pattern to Genesis.

- [ ] Audit translator-classifier alignment
- [ ] Apply Phase 1-3 from Mitsubishi pattern
- [ ] E2E validation on Genesis data

**Expected effort:** 1-2 hours (reuse Mitsubishi pattern)  
**Next gate:** Genesis validation passes

---

### Phase 4: Establish Universal Framework (SPRINT AFTER)
**Status:** Not Started  
**Folder:** New docs in `accy_v2/docs/`

Generalize the pattern across all OEMs and make it enforceable.

**Deliverables:**

#### A. Automated Contract Test Generator
**File:** `accy_v2/model_lookup/tests/test_translator_classifier_contract.py`

```python
def test_oem_translator_classifier_contract(oem_name):
    """Automatically test any OEM's translator-classifier alignment."""
    # Load translator.yaml + classification.yaml
    # For each translator rule, verify output is in classifier
    # Report gaps with specific recommendations
```

**Usage in CI:**
```bash
for oem in mitsubishi hyundai genesis future_oem:
    pytest test_oem_translator_classifier_contract[$oem]
```

#### B. OEM Configuration Standards Document
**File:** `accy_v2/docs/OEM_CONFIGURATION_STANDARDS.md`

Define universal requirements:
1. Translator-Classifier alignment (automated test)
2. DQ logging + categorization (standardized categories)
3. Downstream schema mapping (via YAML)
4. Enrichment rules (via enrichment.yaml)
5. Classification schema (via classification.yaml)

**Usage:** Reference for new OEM onboarding, audit checklist

#### C. OEM Pipeline Patterns Guide
**File:** `accy_v2/docs/OEM_PIPELINE_PATTERNS.md`

Document reusable patterns:
- Translator-Classifier Alignment (how to audit, how to fix)
- Output Column Mapping (Mitsubishi's downstream.yaml pattern)
- Enrichment Layers (Phase 7 model lookup enrichment)
- DQ Logging & Categorization (ADS integration)

**Usage:** Quick reference for engineers building new OEM pipelines

#### D. CI/CD Integration
**File:** `.github/workflows/test_all_oems.yml` (or equivalent)

Automated enforcement:
```yaml
test_all_oems:
  - For each OEM:
    - Run translator-classifier contract test
    - Run OEM-specific regression tests
    - Report any gaps
    - Fail build if gaps found
```

**Benefit:** Zero silent failures across all OEMs

---

## OEM Coverage Timeline

```
Week 1  [THIS WEEK]
├─ Mitsubishi ✓ (Phase 1-3)
│
Week 2  [NEXT WEEK]
├─ Hyundai ○ (Phase 1-3)
│
Week 3  [FOLLOWING WEEK]
├─ Genesis ○ (Phase 1-3)
│
Week 4  [SPRINT AFTER]
├─ Universal Framework ○ (Phase 4)
│   ├─ Auto test generator
│   ├─ Standards documentation
│   ├─ CI/CD enforcement
│   └─ Onboarding guide update
│
Future (As needed)
├─ New OEM #1 (use universal framework)
├─ New OEM #2 (use universal framework)
└─ ... (reuse, don't rebuild)
```

---

## Expected Outcomes

### After Mitsubishi + Hyundai + Genesis (Week 3)
- ✓ 3 OEMs have passed contract tests
- ✓ Pattern proven across multiple OEMs
- ✓ No translator-classifier gaps remaining
- ✓ Silent data corruption risks eliminated

### After Universal Framework (Week 4)
- ✓ Automated test generator eliminates manual auditing
- ✓ CI/CD enforces standards across all OEMs
- ✓ New OEM onboarding reduced from 2 days → 4 hours
- ✓ Standards documented for all engineers
- ✓ Pattern reusable for future OEMs

### Long-term
- ✓ Zero translator-classifier alignment bugs
- ✓ Consistent DQ standards across all OEMs
- ✓ Fast, reliable new OEM onboarding
- ✓ Reduced maintenance burden (patterns, not one-offs)

---

## Success Metrics

| Metric | Baseline | Target | Timeline |
|--------|----------|--------|----------|
| OEMs with passing contract test | 0/3 | 3/3 | Week 3 |
| Translator-classifier gaps | Unmeasured | 0 | Week 3 |
| Manual OEM audit time | ~2 hours | Automated | Week 4 |
| New OEM onboarding time | ~2 days | ~4 hours | Week 4 |
| CI/CD coverage for OEM tests | 0% | 100% | Week 4 |

---

## Files to Create/Modify

| Phase | Folder | Files | Type |
|-------|--------|-------|------|
| 1 | `mitsubishi_translator_classifier_alignment/` | PROPOSAL.md, IMPLEMENTATION.md, README.md, FOLLOW_UP.md | Proposal + Implementation |
| 2 | `hyundai_translator_classifier_alignment/` | (same template as Mitsubishi) | Proposal + Implementation |
| 3 | `genesis_translator_classifier_alignment/` | (same template as Mitsubishi) | Proposal + Implementation |
| 4 | `accy_v2/docs/` | OEM_CONFIGURATION_STANDARDS.md, OEM_PIPELINE_PATTERNS.md | Documentation |
| 4 | `accy_v2/model_lookup/tests/` | test_translator_classifier_contract.py | Automated testing |
| 4 | `.github/workflows/` | test_all_oems.yml (or equivalent) | CI/CD |

---

## Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Each OEM fix is independent, could diverge | Low | Document the pattern first (Week 1), apply consistently |
| Automated testing catches edge cases we miss | Low | Manual review gate before universal framework |
| CI/CD enforcement breaks existing pipelines | Low | Pilot on Mitsubishi first, validate before enforcing |
| Framework doesn't generalize to future OEM | Medium | Review framework after Genesis phase, adjust if needed |

---

## Decision Gates

**After Mitsubishi Phase 3:**
```
Passed? → Proceed to Hyundai
Failed? → Fix Mitsubishi, resolve before expanding
```

**After Hyundai Phase 4:**
```
Passed? → Proceed to Genesis
Failed? → Audit pattern, determine if Mitsubishi success was anomaly
```

**After Genesis Phase 5:**
```
Passed? → Establish universal framework
Failed? → Investigate OEM-specific issues, document exceptions
```

**Before CI/CD enforcement (Phase 4):**
```
All 3 OEMs passing? → Enable CI/CD contract tests
Any failures? → Debug, fix, re-test before enforcement
```

---

## Next Steps (Immediate)

1. **Review this roadmap** (you're reading it now ✓)
2. **Approve Mitsubishi Phase 1-2** (see `mitsubishi_translator_classifier_alignment/PROPOSAL.md`)
3. **Implement Mitsubishi Phase 1-3** (see `mitsubishi_translator_classifier_alignment/IMPLEMENTATION.md`)
4. **After Mitsubishi passes:** Create Hyundai proposal folder (copy Mitsubishi template, audit results)

---

## Questions?

- **How long will this take?** ~4 weeks total for all OEMs + framework (1-2 hours per OEM, 4-6 hours for framework)
- **Do we stop current work?** No, this runs in parallel. Each OEM fix is isolated.
- **Will this break existing OEMs?** No, changes are additive (new configs, no code changes to shared paths)
- **What if a future OEM is very different?** Framework documents patterns and exceptions, adapt as needed.

---

## Related Initiatives

- **Phase 7 (Mitsubishi Model Lookup):** Depends on Mitsubishi alignment fix
- **Data Quality Standards:** This framework is a key DQ enforcement mechanism
- **OEM Onboarding Playbook:** Will reference this framework in step-by-step guide
- **CI/CD Pipeline Improvements:** Contract tests are part of broader test automation
