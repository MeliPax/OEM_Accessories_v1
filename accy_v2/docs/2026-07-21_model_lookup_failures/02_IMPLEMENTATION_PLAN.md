# Implementation Plan: Fix 88 Model Lookup Failures in Hyundai Pipeline

**Plan Date:** 2026-07-21
**Scope:** Hyundai + Genesis model lookup failures
**Failures to Fix:** 88 model lookups + 1 trim applicability
**Risk Level:** MEDIUM (affects search algorithm used by all OEMs)

---

## Problem Statement (Quick Summary)

- **88 model lookups fail** across Hyundai and Genesis across all years (2024-2026)
- **Same trim keywords fail repeatedly** (e.g., "Lux" fails in Santa Fe, Tucson, Kona, Ioniq 5)
- **Database HAS the records**, translator HAS the mappings, but search doesn't find them
- **Root cause:** Unknown - likely scoring, keyword matching, or input preprocessing issue
- **Impact:** ~88 parts excluded from output because their vehicle trim combos don't get model numbers

---

## Approach: Debug First, Fix Second

We don't fully know WHY the search is failing. Rather than guess and potentially break things:

**Phase 1 (2 hours):** Add detailed logging to the search engine and run a test to capture the exact failure point
**Phase 2 (3-4 hours):** Implement the specific fix based on what Phase 1 reveals
**Phase 3 (3-4 hours):** Test, validate, regression test on other OEMs

---

## Phase 1: Debug & Diagnosis

### Step 1.1: Add Logging to Search Engine

**File:** `accy_v2/model_lookup/search_engine.py`
**Change Type:** Add logging (non-breaking)
**What to log:**

For each search, log:

```python
if self.logger:
    self.logger.debug(f"[SEARCH FLOW] Input: make={make}, year={year}, raw_keywords={raw_keywords}")
    self.logger.debug(f"[SEARCH FLOW] Translated: {translated}")
    self.logger.debug(f"[SEARCH FLOW] Classified: {classified}")
    self.logger.debug(f"[SEARCH FLOW] Filtered (ignored categories removed): {filtered_keywords}")
    self.logger.debug(f"[SEARCH FLOW] Score: {score} (computed from {classified})")
    self.logger.debug(f"[SEARCH FLOW] Candidate count: {candidate_count}")
    self.logger.debug(f"[SEARCH FLOW] Adaptive threshold: {min_score_required}")
    self.logger.debug(f"[SEARCH FLOW] Result: {'PASS' if score >= min_score_required else 'FAIL - score too low'}")
    if candidate_count > 1:
        self.logger.debug(f"[SEARCH FLOW] Candidates: {results['Description'].tolist()}")
```

**Rationale:** Trace the exact point where searches break.

### Step 1.2: Run Test Cases

Create a test script that searches for known-failing trims:

```python
test_cases = [
    ("Hyundai", 2024, ["santa", "fe", "lux"], "Santa Fe Lux"),  # Fails
    ("Hyundai", 2024, ["santa", "fe", "luxury"], "Santa Fe Luxury"),  # Does this pass?
    ("Hyundai", 2024, ["santa", "fe", "hev"], "Santa Fe HEV"),  # Fails
    ("Hyundai", 2024, ["santa", "fe", "hybrid"], "Santa Fe Hybrid"),  # Does this pass?
    ("Hyundai", 2024, ["tucson", "pref*"], "Tucson Pref*"),  # Fails (wildcard)
    ("Hyundai", 2024, ["tucson", "pref"], "Tucson Pref"),  # Does this pass?
    ("Genesis", 2024, ["g70", "2.0t", "advanced"], "G70 2.0T Advanced"),  # Fails
]

for make, year, keywords, description in test_cases:
    result = engine.search(make, year, keywords)
    if result:
        print(f"✅ {description}: PASS")
    else:
        print(f"❌ {description}: FAIL")
```

**Output:** Console logs + test result summary will show:

1. Which searches pass
2. At what step they fail (score? candidate count? matching?)
3. What the translated/classified keywords look like

### Step 1.3: Analyze Debug Output

Review logs to answer:

- [ ] Are keywords being translated correctly? (`lux` → `luxury`? `hev` → `hybrid`?)
- [ ] Are keywords being classified correctly? (Is "luxury" classified as TRIM, INTERIOR, or something else?)
- [ ] Is the score computed correctly? (Are category weights applied?)
- [ ] Is the score meeting the adaptive threshold?
- [ ] Are candidates being found in the database?
- [ ] Is the match quality low (many candidates)?

**Expected outcomes:**

- **If translation fails:** Keywords aren't in translator → Add to translator
- **If classification fails:** Translator output isn't recognized → Update classifier config
- **If scoring fails:** Weights too low → Adjust CATEGORY_WEIGHTS
- **If matching fails:** Database doesn't have these combos → Database issue
- **If all steps pass but still None:** Likely duplicate-code detection incorrectly rejecting

---

## Phase 2: Implement Fixes (Based on Phase 1 Results)

### Fix 2.1: Input Preprocessing (If `*` is the issue)

**File:** `accy_v2/oems/hyundai/pipeline/step2_header_normalization.py`
**Issue:** Keywords like "Pref*", "Trend*" have trailing `*` which doesn't match translator

**Change:**

```python
# In the keyword extraction section, add:
keywords = [kw.rstrip("*").strip() for kw in keywords]
```

**Where:** Wherever keywords are extracted from trim column cells before passing to search.

**Testing:**

- Before fix: "Pref*" → "pref*" (not in translator) → ❌
- After fix: "Pref*" → "pref" → "preferred" (via translator) → ✅

**Risk:** VERY LOW (only affects 4 failures, clear cause)

---

### Fix 2.2: Translator Update (If new abbreviations needed)

**File:** `accy_v2/model_lookup/configs/hyundai_translator.json`
**Issue:** `ice`, `edt.hev` not in translator

**Change:**

```json
{
  "fuel_drivetrain": {
    "hev": "hybrid",
    "phev": "plug-in",
    "ev": "electric",
    "ice": "ice"  // New - map to something database has
  },
  "abbreviations": {
    "edt": "edition"  // New - explicit mapping for EDT.HEV
  }
}
```

**Testing:**

- Verify no conflicts with existing mappings
- Run test: "Santa Fe Calli ICE" → should translate correctly

**Risk:** VERY LOW (only adds mappings, doesn't change existing ones)

---

### Fix 2.3: Search Scoring Adjustment (If score is too low)

**File:** `accy_v2/model_lookup/semantic/scorer.py`
**Issue:** Multi-keyword searches (4+ keywords) score too low

**Change (Example - actual change depends on Phase 1 diagnosis):**

```python
# If DRIVETRAIN keywords (hybrid, electric) are weighted too low:
CATEGORY_WEIGHTS = {
    "MODEL": 10,
    "TRIM_VARIANT": 6,
    "DRIVETRAIN": 4,  # Increase from 2 to 4? Or apply 2x multiplier?
    "ENGINE_SPEC": 3,
    ...
}
```

**Testing:**

- Run Phase 1 test cases again
- Verify scores increase
- Verify no regression on other searches (e.g., ambiguous searches)

**Risk:** MEDIUM (affects all searches, needs regression testing)

---

### Fix 2.4: Keyword Classification Update (If classification is wrong)

**File:** `accy_v2/model_lookup/configs/hyundai_classification.json`
**Issue:** Translated keywords not being recognized as valid categories

**Change (Example):**

```json
{
  "hybrid": "DRIVETRAIN",
  "plug-in": "DRIVETRAIN",
  "electric": "DRIVETRAIN",
  "luxury": "TRIM_LEVEL",
  "ultimate": "TRIM_LEVEL",
  ...
}
```

**Testing:**

- Verify translated keywords map to correct categories
- Run Phase 1 test cases

**Risk:** MEDIUM (affects classification for all searches)

---

### Fix 2.5: Search Algorithm Update (If duplicate-code detection is over-rejecting)

**File:** `accy_v2/model_lookup/search_engine.py` (lines 184-207)
**Issue:** Duplicate-code detection might be rejecting valid multi-keyword searches

**Change (Example - verify first!):**

```python
# If the issue is that normalized descriptions differ slightly:
# Instead of requiring EXACT match, allow 80% similarity?
# Or skip this check for certain keyword combinations?

# For now: no change, but document this as potential issue
```

**Testing:** Phase 1 logs will reveal if this is the issue

**Risk:** MEDIUM (can break duplicate-code detection if changed incorrectly)

---

## Phase 3: Testing & Validation

### Test 3.1: Re-run Full Hyundai Pipeline

```bash
cd accy_v2
python run_hyundai.py
```

**Expected output:**

- `_Data_Issues` sheet should have significantly fewer failures
- Target: < 10 failures remaining (95%+ improvement)

**Check:**

- [ ] 2024 Elantra Lux appears in output
- [ ] 2024 Santa Fe Hybrid entries appear
- [ ] 2025 Tucson N-Line appears
- [ ] 2026 Kona EV Trend appears
- [ ] No new failures introduced

### Test 3.2: Regression Test - Mazda Pipeline

```bash
cd accy_v2
python run_mazda.py
```

**Expected output:**

- Same sheet count as before (no change expected)
- Same model coverage
- **No new failures**

**Check:**

- [ ] CX-5, CX-50, CX-90 sheets present
- [ ] Row counts match previous run
- [ ] No increase in `_Data_Issues` for Mazda

### Test 3.3: Regression Test - Mitsubishi Pipeline

```bash
cd accy_v2
python run_mitsubishi.py
```

**Expected output:**

- Same sheet count
- Same coverage
- **No new failures**

**Check:**

- [ ] Outlander, PHEV, RVR sheets present
- [ ] Row counts unchanged
- [ ] No increase in `_Data_Issues` for Mitsubishi

### Test 3.4: Manual Spot Check

Open the new Hyundai output file in Excel:

- [ ] Check `elantra_EN` sheet: Do rows exist for Lux trim?
- [ ] Check `santa_fe_EN` sheet: Do rows exist for Hybrid entries?
- [ ] Check `tucson_EN` sheet: Do rows exist for N-Line?
- [ ] Check `_Data_Issues` sheet: Are there 0-5 failures (vs 89)?
- [ ] Check `_Report` sheet: Do model profiles show correct row counts?

---

## Rollback Plan

If Phase 2 fixes cause regressions:

1. **If only translator/config changed:**

   ```bash
   git checkout accy_v2/model_lookup/configs/
   ```
2. **If scoring changed:**

   ```bash
   git checkout accy_v2/model_lookup/semantic/scorer.py
   ```
3. **If search algorithm changed:**

   ```bash
   git checkout accy_v2/model_lookup/search_engine.py
   ```
4. **Re-run Hyundai pipeline to confirm rollback worked**

---

## Detailed File Changes (By Fix Type)

### If Issue is Input Preprocessing (Fix 2.1)

**File:** `accy_v2/oems/hyundai/pipeline/step2_header_normalization.py`
**Location:** Wherever keywords are cleaned/extracted
**Change:**

```python
# OLD:
keywords = [kw.lower().strip() for kw in row_keywords]

# NEW:
keywords = [kw.lower().strip().rstrip("*") for kw in row_keywords]
```

**Lines:** TBD based on Phase 1 findings

---

### If Issue is Translator (Fix 2.2)

**File:** `accy_v2/model_lookup/configs/hyundai_translator.json`
**Change:**

```json
{
  "categories": {
    "fuel_drivetrain": {
      "hev": "hybrid",
      "phev": "plug-in",
      "ev": "electric",
      "ice": "ice"  // NEW
    },
    "abbreviations": {  // NEW SECTION
      "edt": "edition"
    }
  }
}
```

**Testing:**

- Verify JSON is valid
- Run pipeline and check log

---

### If Issue is Scoring (Fix 2.3)

**File:** `accy_v2/model_lookup/semantic/scorer.py`
**Location:** CATEGORY_WEIGHTS dict
**Change (Example):**

```python
CATEGORY_WEIGHTS = {
    "MODEL": 10,
    "TRIM_VARIANT": 6,
    "DRIVETRAIN": 4,  # Changed from 2 to 4
    "ENGINE_SPEC": 3,
    "BODY_STYLE": 2,
    "SEATING": 1,
}
```

**Testing:**

- Verify minimum score thresholds still make sense
- Run test: Santa Fe Lux should score >= 12 (2-3 candidates)

---

### If Issue is Classification (Fix 2.4)

**File:** `accy_v2/model_lookup/configs/hyundai_classification.json`
**Change (Example):**

```json
{
  "trim_levels": {
    "lux": "TRIM_LEVEL",
    "luxury": "TRIM_LEVEL",
    "ult": "TRIM_VARIANT",
    "ultimate": "TRIM_VARIANT",
    ...
  },
  "drivetrain": {
    "hybrid": "DRIVETRAIN",
    "electric": "DRIVETRAIN",
    "plug-in": "DRIVETRAIN",
    ...
  }
}
```

**Testing:**

- Verify all keywords are mapped
- Run search with logging to see classified output

---

## Execution Checklist

### Pre-Implementation

- [ ] Save current Hyundai output file as backup
- [ ] Note current pipeline run time
- [ ] Create git branch: `git checkout -b fix/model-lookup-failures`

### Phase 1: Debug

- [ ] Add logging to `search_engine.py`
- [ ] Create test script
- [ ] Run pipeline with test script
- [ ] Analyze logs
- [ ] Document findings

### Phase 2: Fix

- [ ] Implement Fix 2.1 (input preprocessing) - if needed
- [ ] Implement Fix 2.2 (translator) - if needed
- [ ] Implement Fix 2.3 (scoring) - if needed
- [ ] Implement Fix 2.4 (classification) - if needed
- [ ] Implement Fix 2.5 (search algorithm) - only if necessary
- [ ] Review changes

### Phase 3: Test

- [ ] Run Hyundai pipeline
- [ ] Check output: < 10 failures in `_Data_Issues`
- [ ] Run Mazda regression test
- [ ] Run Mitsubishi regression test
- [ ] Manual spot-check in Excel
- [ ] Verify row counts
- [ ] Check report sheet

### Finalization

- [ ] Create git commit with detailed message
- [ ] Verify commit passes linting/tests (if applicable)
- [ ] Document solution in PR or ticket
- [ ] Archive debug logs
- [ ] Clean up temporary test files

---

## Success Metrics

| Metric                            | Target         | Current | Status |
| --------------------------------- | -------------- | ------- | ------ |
| Model lookup failures in Hyundai  | < 10           | 88      | ❌     |
| Failure reduction                 | 95%+           | 0%      | ❌     |
| Regression failures in Mazda      | 0 new          | Unknown | ?      |
| Regression failures in Mitsubishi | 0 new          | Unknown | ?      |
| Pipeline runtime (Hyundai)        | Same or faster | ~2 min  | ?      |
| Output file size                  | Similar        | 1.81 MB | ?      |

---

## Risk Matrix

| Change                           | Risk     | Mitigation                  | Rollback Time |
| -------------------------------- | -------- | --------------------------- | ------------- |
| Input preprocessing (strip`*`) | VERY LOW | Test "Pref*", "Trend*" only | 5 mins        |
| Add translator entries           | VERY LOW | Check for conflicts         | 2 mins        |
| Adjust scoring weights           | MEDIUM   | Regression test all OEMs    | 10 mins       |
| Update classification            | MEDIUM   | Test all categories         | 10 mins       |
| Change search algorithm          | HIGH     | Full pipeline test          | 20 mins       |

---

## Communication

**Report To:** User**Format:** GitHub issue or project log**Contents:**

1. Root cause identified
2. Fix applied
3. Test results
4. Failures resolved (before/after numbers)
5. Any remaining issues or notes

---

## Appendix: Quick Reference - File Locations

| File                                                            | Purpose                     |
| --------------------------------------------------------------- | --------------------------- |
| `accy_v2/model_lookup/search_engine.py`                       | Main search logic + logging |
| `accy_v2/model_lookup/semantic/scorer.py`                     | Scoring algorithm           |
| `accy_v2/model_lookup/configs/hyundai_translator.json`        | OEM abbreviations           |
| `accy_v2/model_lookup/configs/hyundai_classification.json`    | Keyword categories          |
| `accy_v2/oems/hyundai/pipeline/step2_header_normalization.py` | Keyword extraction          |
| `accy_v2/oems/hyundai/config/hyundai_config.json`             | OEM config                  |
| `accy_v2/model_lookup/db/db_vehicle_models.csv`               | Vehicle database            |
