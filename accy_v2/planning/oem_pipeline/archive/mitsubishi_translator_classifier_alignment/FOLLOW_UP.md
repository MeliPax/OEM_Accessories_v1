# Follow-Up: Next Steps After Mitsubishi Validation

**Purpose:** Document the plan to extend this work to other OEMs and establish a universal framework.

**Timeline:** After Mitsubishi Phase 3 validation passes.

---

## Phase 4: Apply to Hyundai (Parallel Pattern)

**When:** After Mitsubishi testing is complete and successful  
**Effort:** 1-2 hours (reuse Mitsubishi pattern)  
**Scope:** Hyundai OEM configs only (isolated, like Mitsubishi)

### Steps

1. **Audit Hyundai translator-classifier alignment**
   - Extract all rules from `accy_v2/model_lookup/configs/hyundai/translator.yaml`
   - Cross-reference against `accy_v2/model_lookup/configs/hyundai/classification.yaml`
   - Identify gaps (translator outputs not in classifier)
   - Expected findings: Similar to Mitsubishi, likely abbreviations that expand to multi-word forms

2. **Apply Phase 1-3 (identical pattern)**
   - Phase 1: Add missing translator outputs to Hyundai's classification.yaml
   - Phase 2: Add contract test for Hyundai (copy Mitsubishi test, change OEM name)
   - Phase 3: E2E validation on Hyundai data (run `python run_hyundai.py`)

3. **Document in separate proposal folder**
   - Create: `accy_v2/planning/oem_pipeline/hyundai_translator_classifier_alignment/`
   - Copy structure from Mitsubishi proposal (reuse the template)
   - Adapt findings to Hyundai's specific keyword system

### Success Criteria

- [ ] Hyundai translator-classifier audit completed
- [ ] Gap list documented (what translator outputs are missing from classifier)
- [ ] Config changes applied
- [ ] Contract test added and passing
- [ ] E2E validation shows no regressions
- [ ] Genesis unchanged (no shared-code impact)

---

## Phase 5: Apply to Genesis (Parallel Pattern)

**When:** After Hyundai is complete  
**Effort:** 1-2 hours (same pattern)  
**Scope:** Genesis OEM configs only

### Steps (identical to Hyundai)

1. Audit translator-classifier alignment
2. Apply Phase 1-3 config fix
3. Document in `accy_v2/planning/oem_pipeline/genesis_translator_classifier_alignment/`

---

## Phase 6: Establish Universal Framework

**When:** After all three OEMs (Mitsubishi, Hyundai, Genesis) are validated  
**Effort:** 4-6 hours (architecture + documentation)  
**Scope:** System-wide design pattern

### Goal

Create a reusable, automatable pattern for:
1. Any new OEM onboarding
2. Future OEM audits
3. Regression prevention across all OEMs

### Components

#### A. Generalized Contract Test Generator

**Location:** `accy_v2/model_lookup/tests/test_translator_classifier_contract.py`

```python
def generate_contract_test(oem_name, translator_config, classifier_config):
    """
    Generate a contract test for any OEM.
    
    This function auto-generates test cases from translator rules
    and verifies all outputs are recognized by classifier.
    """
    # Load translator rules
    # Load classifier token map
    # For each rule, verify output exists in classifier
    # Return test result (pass/fail + gaps)
```

**Usage:**
```python
# In test_search_engine.py
test_mitsubishi_contract = generate_contract_test("Mitsubishi", ...)
test_hyundai_contract = generate_contract_test("Hyundai", ...)
test_genesis_contract = generate_contract_test("Genesis", ...)
```

#### B. OEM Pipeline Audit Checklist

**Location:** `accy_v2/docs/OEM_PIPELINE_PATTERNS.md`

Document the universal pattern:
1. Translator-Classifier Alignment (how to audit, how to fix)
2. When to apply it (new OEM onboarding, existing OEM audit)
3. Success criteria
4. Common failure modes + solutions

#### C. CI/CD Integration

Add to CI pipeline:
```yaml
# In CI config (e.g., .github/workflows/test.yml)
test_all_oems_translator_classifier_contract:
  - For each OEM:
    - Run generated contract test
    - Report any gaps
    - Fail build if gaps detected
```

This ensures:
- No new gaps introduced by config changes
- New OEMs are automatically audited
- Pattern is enforced system-wide

### Documentation

**Create:** `docs/OEM_CONFIGURATION_STANDARDS.md`

Standard practices for all OEMs:
1. Translator-Classifier alignment (must pass contract test)
2. DQ logging requirements
3. Output column mapping (via downstream.yaml)
4. Enrichment rules (via enrichment.yaml)
5. Classification schema (via classification.yaml)

**Result:** Future OEM onboarding becomes:
- Copy template configs from existing OEM
- Update for new OEM's keywords
- Run contract test → immediate validation
- Document gaps in proposal → audit them

---

## Timeline & Ownership

| Phase | Target OEM(s) | Timeline | Owner | Dependencies |
|-------|---|---|---|---|
| 1-3 | Mitsubishi | This week | [Engineer] | (none) |
| 4 | Hyundai | Next week | [Engineer] | Mitsubishi Phase 3 ✓ |
| 5 | Genesis | Following week | [Engineer] | Hyundai Phase 4 ✓ |
| 6 | System-wide | Sprint after | [Architect] | All OEMs Phase 1-3 ✓ |

---

## Success Metrics (End State)

✓ All three OEMs (Mitsubishi, Hyundai, Genesis) have passed contract test  
✓ Universal framework documented in codebase  
✓ CI/CD enforces contract test on all OEMs  
✓ New OEM onboarding reduced from ~2 days to ~4 hours  
✓ Translator-Classifier gaps caught automatically (zero silent failures)  

---

## Related Initiatives

- **Phase 7 (Mitsubishi Model Lookup):** Depends on this fix for correct enrichment
- **OEM Onboarding Template:** Will reference universal framework in step-by-step guide
- **Data Quality Standards:** Contract tests are a key DQ enforcement mechanism

---

## Notes

- Each OEM fix is **independent** (separate folders, separate configs, separate tests)
- Pattern is **identical across OEMs** (makes onboarding faster)
- Universal framework is a **meta-pattern** (how we build, audit, and validate OEM configs)
- No breaking changes to existing OEMs during this work

---

## Decision Gates

**After Mitsubishi Phase 3:**
- [ ] Validation successful → Proceed to Hyundai (Phase 4)
- [ ] Issues found → Investigate and fix before expanding to other OEMs

**After Hyundai Phase 4:**
- [ ] Validation successful → Proceed to Genesis (Phase 5)
- [ ] Issues or differences found → Adjust pattern documentation, then proceed

**After Genesis Phase 5:**
- [ ] All three OEMs passing → Establish universal framework (Phase 6)
- [ ] Deviations discovered → Document why, then universalize what applies
