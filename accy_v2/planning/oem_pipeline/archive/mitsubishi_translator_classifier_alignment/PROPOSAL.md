# Proposal: Mitsubishi Translator-Classifier Alignment
**Status:** Draft  
**Date:** 2026-08-27  
**Scope:** Mitsubishi OEM only  
**Effort:** 2-3 hours (Phase 1-2), extensible to other OEMs later  
**Risk Level:** Low (OEM-isolated)

---

## Executive Summary

Mitsubishi's keyword translation system has a structural gap: the translator converts abbreviations (e.g., `gt-p: gt premium`, `phev: plug-in hybrid`) but the classifier doesn't recognize all translated outputs. This causes:

1. **Production bug**: Multi-word translated tokens become UNCLASSIFIED → silent search failures or wrong results
2. **Maintenance burden**: Keyword variations (e.g., `gt-p` vs `gt-premium`) require manual tracking in multiple config files
3. **Inconsistent handling**: Same concept (e.g., "GT Premium") exists in classifier as three different forms (`gt`, `GT Premium`, `gt-premium`)

**Proposed fix:** Three-phase alignment to ensure translator outputs → classifier acceptance, validated end-to-end on Mitsubishi data first.

---

## Problem Statement

### Current Behavior

**Translator** (`translator.yaml`):
```yaml
gt-p: gt premium
gt-premium: gt premium
phev: plug-in hybrid
```

**Classifier** (`classification.yaml`):
```yaml
token_map:
  gt: TRIM
  GT Premium: TRIM              # Original case
  gt-premium: TRIM              # Hyphenated variant
  phev: ENGINE_TYPE             # ❌ "plug-in hybrid" is missing!
  plug-in hybrid: ENGINE_TYPE   # ❌ This doesn't exist
```

### Root Cause

- Translator outputs multi-word forms (e.g., "plug-in hybrid")
- Classifier only has original abbreviations (e.g., "phev")
- **No contract enforcement** between translator output and classifier input
- When "phev" is translated to "plug-in hybrid", classification fails → token becomes UNCLASSIFIED → ENGINE_TYPE signal is lost

### Business Impact

**Scenario: Mitsubishi Outlander PHEV ES**
1. User batch has: `"Outlander Plug-In Hybrid ES"`
2. Translator converts `"plug-in hybrid"` → `"plug-in hybrid"` (already expanded)
3. Classifier looks for `"plug-in hybrid"` → NOT FOUND (only has `phev`)
4. Token drops from classification → ENGINE_TYPE category loses weight
5. Search returns wrong model number (gas Outlander instead of PHEV)
6. ❌ **Silent data corruption** — no error, wrong answer

---

## Proposed Solution

### Phase 1: Classification Fix (5 minutes)

**Goal:** Add missing translator outputs to Mitsubishi's classifier.

**Changes:**

| File | Change | Reason |
|------|--------|--------|
| `classification.yaml` | Remove `GT Premium: TRIM` | Replace with canonical form |
| `classification.yaml` | Remove `gt-premium: TRIM` | Both translate to "gt premium" |
| `classification.yaml` | Add `gt premium: TRIM` | Matches translator output |
| `classification.yaml` | Add `plug-in hybrid: ENGINE_TYPE` | Matches translator output for `phev` |

**Result after:**
```yaml
token_map:
  gt: TRIM
  gt premium: TRIM              # Canonical form (both gt-p and gt-premium translate to this)
  le: TRIM
  # ... other trims ...
  phev: ENGINE_TYPE
  plug-in hybrid: ENGINE_TYPE   # Now available for when phev is expanded
```

**Risk:** Minimal — only adds/replaces within Mitsubishi's isolated config.

---

### Phase 2: Contract Test (30 minutes)

**Goal:** Prevent regression; ensure translator outputs always exist in classifier.

**Implementation:** Add test in `accy_v2/model_lookup/tests/test_search_engine.py`:

```python
def test_mitsubishi_translator_classifier_contract():
    """
    Contract test: Every translator output must exist in classifier.
    Prevents silent token loss when translator expands abbreviations.
    """
    from accy_v2.model_lookup.semantic.translator import Translator
    from accy_v2.model_lookup.semantic.classifier import Classifier
    
    translator = Translator(oem="Mitsubishi", config_path="...")
    classifier = Classifier(oem="Mitsubishi", config_path="...")
    
    test_inputs = [
        "gt-p", "gt-premium", "phev", "plug-in hybrid",
        "s-awc", "phev outlander", "es sel gt"
    ]
    
    for test_input in test_inputs:
        translated = translator.translate_token(test_input)
        # Every token that comes out of translator must be classifiable
        result = classifier.classify_tokens([translated], ...)
        assert result["UNCLASSIFIED"] == 0, \
            f"Translator output '{translated}' not found in classifier for input '{test_input}'"
```

**What this catches:**
- Future translator rules added without corresponding classifier entries
- Translator changes that produce unmapped outputs
- Classification regressions

---

### Phase 3: End-to-End Validation (1 hour)

**Goal:** Confirm fix resolves production issues on real Mitsubishi data.

**Test execution:**
1. Run `python run_mitsubishi.py` with Phase 1 config changes
2. Measure success metrics:
   - ✓ 2026/2025 "gt_s-awc" searches now resolve (were NOT_FOUND before)
   - ✓ 2026/2025 PHEV "gt-p" searches show correct diagnostic (TRIM_VARIANT_NOT_FOUND, not silent wrong result)
   - ✓ Outlander PHEV ES output shows `fuel_type=phev` (Phase 7 enrichment working)
3. Compare before/after:
   - NOT_FOUND count (should decrease)
   - False positive count (should stay ≤ baseline)
   - Diagnostic reasons are specific, not generic

**Success criteria:**
- Zero silent data corruption cases
- All existing passing tests still pass
- No regression in other OEM pipelines (Hyundai, Genesis) — they use same `search_engine.py` code path

---

## Risk Analysis (OEM-Isolated)

| Risk | Severity | Mitigation | Residual |
|------|----------|-----------|----------|
| Homonym collisions (e.g., `n` means different things in Mitsubishi vs Hyundai) | N/A | OEM configs are separate; no collision possible | None |
| Temporal data inconsistency (DB has old spellings) | Medium | Accept mixed spellings in DB; canonicalization is query-time only | Low — query-time matching handles both forms |
| False positives (canon. form matches wrong vehicle) | Medium | A/B test on real Mitsubishi data; measure false-positive rate | Low — caught in Phase 3 validation |
| Audit trail lost | Low | Log (original, canonical) tuple in DQ output for debugging | Low — only affects support, not functionality |
| Contract test gives false security | Low | Contract test only checks *existence*, not semantic correctness | Low — integration tests catch semantic errors |

**Overall Risk:** **LOW** — Changes are Mitsubishi-only, isolated from other OEMs, validated end-to-end before rollout.

---

## What We Can't Handle (Intentionally Out of Scope)

1. **Vendor inconsistencies within Mitsubishi data** — if ADS and official Mitsubishi specs use different names for the same vehicle, translator can't unify them (needs mapping layer)
2. **True typos vs. intentional variants** — translator can't distinguish `"gt-pp"` (typo) from `"gt-pp"` (new trim)
3. **Future Mitsubishi spec changes** — when Mitsubishi renames/adds trims, translator.yaml must be manually updated

These are features/data issues, not architecture issues.

---

## Applicability to Other OEMs

**Mitsubishi:** ✓ Specific fix needed (Phase 1-2)  
**Hyundai:** ? Audit needed — may have same gap or may be compliant already  
**Genesis:** ? Audit needed — may have same gap or may be compliant already  

**Decision:** Implement for Mitsubishi first, validate, then decide per-OEM whether same fix applies.

---

## Files to Modify

| File | Phase | Change | Impact |
|------|-------|--------|--------|
| `accy_v2/model_lookup/configs/mitsubishi/classification.yaml` | 1 | Replace translator outputs | Mitsubishi search only |
| `accy_v2/model_lookup/tests/test_search_engine.py` | 2 | Add contract test | Mitsubishi test coverage |
| (Run end-to-end test) | 3 | Validate on real data | Mitsubishi data quality |

No changes to shared code (`search_engine.py`, `manufacturer_module.py`).

---

## Timeline

| Phase | Time | Blocker? | Next Gate |
|-------|------|----------|-----------|
| 1: Classification fix | 5 min | No | Phase 1 code review ✓ |
| 2: Contract test | 30 min | No | Phase 2 test passes ✓ |
| 3: E2E validation | 1 hour | **YES** | Phase 3 success metrics ✓ |

**Total:** 1.5-2 hours if all phases pass.

---

## Success Criteria

- [x] Phase 1: Classification.yaml has all translator outputs
- [x] Phase 2: Contract test added and passing
- [x] Phase 3: E2E run shows:
  - NOT_FOUND cases decrease (at least 2026/2025 gt_s-awc resolve)
  - False-positive rate unchanged or lower
  - Diagnostic reasons are specific (not generic NOT_FOUND)
  - No regression in Hyundai/Genesis tests

---

## Decision Required

**Approve Phase 1-2 now** (minimal risk, catches bugs):
- Config fix (5 min)
- Contract test (30 min)
- Can be merged immediately after review

**Defer Phase 3** until next scheduled Mitsubishi run, or run now depending on pipeline schedule.

---

## Appendix: Example Walkthrough

**Scenario:** User searches for "Mitsubishi Outlander Plug-In Hybrid ES"

**Before (Current - Broken):**
1. Input: "plug-in hybrid" 
2. Translator sees "phev" rule, but input doesn't match → stays as "plug-in hybrid"
3. Classifier looks for "plug-in hybrid" → NOT IN TOKEN_MAP (only has `phev`)
4. Token marked UNCLASSIFIED
5. ENGINE_TYPE signal lost → search confusion

**After (Proposed):**
1. Input: "plug-in hybrid"
2. Translator sees input is already expanded → no change
3. Classifier looks for "plug-in hybrid" → FOUND: `plug-in hybrid: ENGINE_TYPE`
4. Token classified correctly
5. Search works as intended ✓

---

## References

- [Phase 7: Mitsubishi Model Lookup (Git commit 8642ec2)](https://github.com/...) — Enrichment architecture that depends on correct classification
- `docs/SYSTEM_ARCHITECTURE.md` — Model lookup pipeline overview
- `accy_v2/model_lookup/ARCHITECTURE.md` — Translator and classifier workflow