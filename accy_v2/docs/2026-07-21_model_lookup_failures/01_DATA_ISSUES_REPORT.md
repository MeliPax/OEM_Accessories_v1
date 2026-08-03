# Hyundai Model Lookup Failures - Analysis Report

**Report Date:** 2026-07-21
**Analysis of:** hyundai_31898074_20260721_201311.xlsx
**Total Issues:** 89 failed model lookups + 1 trim applicability failure

---

## Executive Summary

The pipeline processed **89 model lookup failures** across Hyundai and Genesis vehicles. **88 failures are all TRIM/KEYWORD failures** (same root cause across all years 2024-2026), with **1 trim applicability failure** (empty trim columns).

**Key Finding:** The failures follow a **clear pattern** — they are NOT random errors but systematic gaps in either:

1. Database coverage (missing records for certain trim combinations)
2. Translator configuration (drivetrain abbreviations not properly mapped)
3. Search algorithm scoring (scores too low for certain keyword combinations)

---

## Failure Distribution

### By Model (Top Failures)

| Model                                               | Count | Root Cause Pattern                                                                  |
| --------------------------------------------------- | ----- | ----------------------------------------------------------------------------------- |
| Santa Fe                                            | 18    | Missing Hybrid/ICE/Edition combinations (Lux, XRT, Pref HEV, Ult Calli, HEV NHL Ed) |
| Tucson                                              | 15    | Missing N-Line, PHEV, XRT, Night Edition combinations                               |
| Kona                                                | 10    | Missing N-Line, Sport, Trend combinations                                           |
| Santa Cruz                                          | 9     | Missing Pref, Ult, XRT combinations                                                 |
| Kona EV                                             | 7     | Missing Trend, Ult, N-Line combinations (+ 1 trim applicability)                    |
| Ioniq 5                                             | 5     | Missing Lux, Ult, N combinations                                                    |
| Elantra                                             | 5     | Missing Ult, N-Line combinations (N trim issue resolved in recent commit)           |
| Other (G70, G90, Palisade, Ioniq 6/9, GV60, Sonata) | 15    | Missing Advanced, Prestige, Performance combinations                                |

### By Issue Type

```
❌ Model lookup failures: 88 (100% - same root cause)
❌ Trim applicability failure: 1 (2026 Kona EV - empty trim columns)
```

### By Year

- **2024:** 27 failures
- **2025:** 32 failures
- **2026:** 30 failures

**Pattern:** Failures are **consistent across all years** for the same model+trim combinations.
**Implication:** This is not a year-specific data issue; it's a fundamental configuration/database gap.

---

## Root Cause Analysis

### Root Cause #1: Drivetrain Abbreviations Not Fully Recognized

**Status:** 🟠 PARTIAL - Translator exists but not universally working

The translator in `hyundai_translator.json` DOES include:

```json
"fuel_drivetrain": {
  "hev": "hybrid",
  "phev": "plug-in",
  "ev": "electric"
}
```

**BUT the database IS missing:**

- `ICE` (Internal Combustion Engine) - NOT in translator, NOT in database descriptions
- `EDT.HEV` (Edition Hybrid) - Special abbreviation, translator doesn't handle it
- Database descriptions use **full words** ("Hybrid", "Electric", "Plug-in Hybrid") but not the abbreviations

**Examples of failures:**

- Input: "Santa Fe Pref HEV" → Translated: "Santa Fe preferred hybrid" → Database has "Santa Fe 1.6T Preferred Hybrid AWD 7-Pass" ✅ **Should match**
- Input: "Santa Fe XRT" → Translated: "Santa Fe xrt" → Database has "Santa Fe 2.5T xrt AWD 7-Pass" ✅ **Should match**
- Input: "Tucson Pref*" → Translated: "Tucson pref*" (wildcard not handled) → Database has "Tucson Preferred" ❌ **May not match due to wildcard**

**Conclusion:** The translator entries are correct, but **search scoring or keyword matching** might be rejecting these as "not confident enough."

### Root Cause #2: Inconsistent Trim Name Formatting in Database vs Input

**Status:** 🔴 CONFIRMED

The database uses **varied nomenclature**:

- "Ultimate Calligraphy" but input says "Ult Calli"
- "Preferred" but input says "Pref" or "Pref*"
- "N-Line Ultimate" but input sometimes says just "N-Line"
- "Luxury" but input says "Lux"

**Examples:**

- DB: `Tucson Luxury AWD` vs Input: `Tucson Lux` → Translator should convert "lux" → "luxury" ✅
- DB: `Palisade Urban 8 Passenger` vs Input: `Palisade Urban` → Should match ✅
- DB: `Santa Fe 2.5T xrt AWD` vs Input: `Santa Fe XRT` → Should match ✅

**Conclusion:** The **translator IS defined for these**, but the search algorithm may not be scoring them high enough (adaptive score threshold for 4+ candidates).

### Root Cause #3: Scoring Too Strict for Multi-Keyword Searches

**Status:** 🟡 LIKELY

The adaptive scoring in `search_engine.py` requires:

- 1 candidate: any score
- 2-3 candidates: score ≥ 12
- 4+ candidates: score ≥ 14

When searching for "Santa Fe Pref HEV" (3 keywords):

- MODEL="santa fe" (score 10)
- TRIM_VARIANT="pref" (score 4)
- DRIVETRAIN="hev" → "hybrid" (score 2)
- **Total: 16** ✅ Should pass

But if the algorithm is **not properly classifying or weighting** the translated keywords, the score might be lower than expected.

### Root Cause #4: Input File Has Unusual Abbreviations

**Status:** 🔴 CONFIRMED

Input file uses abbreviations not in the translator:

- `Pref*` and `Trend*` (wildcards) - These should be handled by cleaning the asterisk first
- `Edt.HEV` (Edition Hybrid) - Not explicitly in translator (maps to "ed"+"hev" separately, not "edt.hev")
- `w/` (with) - **This IS handled** in translator → "with"

**Example:**

- "Pref*" is not the same as "Pref" if the asterisk isn't stripped before translation
- The translator maps "pref" → "preferred", but if the input is literally "pref*", it won't match

**Conclusion:** Input data may need **preprocessing to clean special characters** before classification.

---

## Database Coverage Analysis

### What's Actually in the Database

**Santa Fe:**

- ✅ Has records for: 1.6T Luxury, Preferred, Preferred Hybrid, Ultimate, Ultimate Calligraphy, etc.
- ❌ Missing: Some specific year/trim combinations may not exist
- Sample descriptions:
  - "Santa Fe 1.6T Luxury Hybrid AWD 7-Pass"
  - "Santa Fe 2.5T Ultimate Calligraphy AWD 6-Pass"
  - "Santa Fe 2.5T xrt AWD 7-Pass"

**Tucson:**

- ✅ Has records for: Preferred, Luxury, N-Line, Hybrid, Night Edition Hybrid, XRT
- ✅ All core trims are present in database
- Sample descriptions:
  - "Tucson Luxury AWD"
  - "Tucson Hybrid N-Line AWD"
  - "Tucson 1.6T Night Edition hybrid AWD"
  - "Tucson xrt"

**Kona:**

- ✅ Has 139 records
- ✅ All trims including N-Line are present
- ✅ Sports, Trend package variants are present

**Genesis G70/G90:**

- ✅ Advanced, Prestige models ARE in database
- ✅ 2.0T, 3.5T engine variants ARE in database
- ✅ e-SC trim IS in database

**Conclusion:** **The database DOES contain most of these combinations.** The issue is **search not finding them**, likely due to scoring or keyword matching.

---

## Severity Assessment

### 🔴 Critical (Affects Output)

- **Model lookup failures:** 88 rows excluded from output because search returns None
- **Impact:** Approximately 88 parts are not shown for their applicable vehicle trims

### 🟡 Medium (Input Data Issue)

- **Trim applicability:** 1 row has empty trim columns (2026 Kona EV)
- **Impact:** 1 part (BFH14AP200 - Carpet Floor Mats) not applicable to any trim

### ✅ Non-Critical (Config/Data Quality)

- Incomplete NHL (Hockey Edition) database coverage (only 2 records)
- Some special abbreviations (EDT.HEV) not explicitly handled

---

## Patterns (Same Issue Type = Same Fix Needed)

### Pattern A: "Lux" (Luxury) Failures

**Affected:** Santa Fe, Tucson, Kona, Ioniq 5
**Years:** 2024, 2025 (all with "Lux")
**Status:** All **identical error pattern** - "No confident model number match"
**Why:** Translator has `"lux": "luxury"` ✅, database has "Luxury" ✅, but search not matching

**Solution:** Debug single failing case, apply fix to all "Lux" failures at once.

### Pattern B: "Pref*" and "Trend*" (Wildcards) Failures

**Affected:** Tucson only
**Years:** 2025, 2026
**Status:** 4 failures with `*` wildcard character
**Why:** Wildcard not stripped before processing

**Solution:** Add preprocessing to remove `*` from keywords before classification.

### Pattern C: "N-Line" Failures

**Affected:** Elantra (2025, 2026), Tucson, Kona, Sonata
**Years:** All years
**Status:** 9 failures, but **Elantra N (without -Line) DOES work** (resolved in commit 9788bf0)
**Why:** "N-Line" is different from "N" - database may have N-Line records but they're not matching

**Solution:** Same as Pattern A - debug one case, apply fix broadly.

### Pattern D: Hybrid-specific Failures ("HEV", "Pref HEV", "Ult Calli HEV", etc.)

**Affected:** Santa Fe (6), Tucson (4), Kona EV (2), Ioniq 5 (1)
**Years:** All years
**Status:** 13 failures with "HEV" in trim name
**Why:** Translator has "hev" → "hybrid", database has "Hybrid", but combinations not scoring high enough

**Example:** "Santa Fe HEV NHL Ed" has too many keywords, score drops below threshold

**Solution:**

1. Verify translator is being applied correctly
2. Check scoring for compound keywords
3. May need to ignore certain keywords (NHL, Ed) or weight them differently

### Pattern E: Drivetrain Prefix Failures ("ICE", "EDT.HEV")

**Affected:** Santa Fe, Palisade, Tucson
**Years:** 2026 only
**Status:** 2 failures
**Why:** These are abbreviations not in the translator

**Solution:** Add translations or update database to handle these.

---

## Verification Checklist

✅ **Database has the trim combinations:** Most failures are not due to missing database records
✅ **Translator has the abbreviation mappings:** Most failures should work with existing translator
⚠️  **Search algorithm is scoring/matching correctly:** Needs investigation
❌ **Input preprocessing handles special characters:** `*`, `.`, `/` not cleaned before processing

---

## Recommendations (Prioritized)

### 🥇 Priority 1: Debug Translator & Search Scoring (Affects 85+ failures)

**Why:** The translator exists, the database has the records, but searches still fail.

**Action:**

1. Add logging to `VehicleSearchEngine.search()` to show:
   - Original keywords: `['santa', 'fe', 'hev', 'nhl', 'ed']`
   - Translated keywords: `['santa', 'fe', 'hybrid', 'nhl', 'ed']`
   - Classified tokens: `{'MODEL': ['santa', 'fe'], 'DRIVETRAIN': ['hybrid'], ...}`
   - Computed score: `16`
   - Candidate count: `5`
   - Adaptive threshold: `14`
   - Final result: Pass/Fail reason
2. Run pipeline with logging enabled for 2-3 failing trims
3. Identify where the break happens (scoring? matching? classification?)
4. Fix the specific issue

### 🥈 Priority 2: Input Preprocessing (Affects 4 failures - "Pref*", "Trend*")

**Why:** Easy fix, clear root cause.

**Action:**

1. Update keyword extraction in `step2_header_normalization.py` or `step3_5_extract_vehicle_year.py`
2. Strip trailing `*` from keywords before passing to search
3. Test: "Pref*" → "Pref" → "preferred" (via translator) → matches database ✅

### 🥉 Priority 3: Add Missing Abbreviations to Translator (Affects 2-3 failures)

**Why:** `ICE`, `EDT.HEV` not defined.

**Action:**

1. Add to `hyundai_translator.json`:
   ```json
   "ice": "internal",  // or "gas" or "combustion"
   "edt": "edition",   // Already have "ed", but explicit mapping for EDT.HEV
   ```
2. Verify no conflicts with existing mappings

### 🔵 Priority 4: Cross-OEM Verification (Affects Mazda, Mitsubishi)

**Why:** Same translator/search system used by all OEMs.

**Action:**

1. Run Mazda pipeline, check if same failures occur
2. Run Mitsubishi pipeline, check if same failures occur
3. If YES: Fix is global, will benefit all OEMs
4. If NO: Issue is Hyundai-specific (translator, data quality, or config)

### ⚪ Priority 5: Database Gap Analysis (Affects < 5 failures)

**Why:** Only after Priority 1-3 are complete.

**Action:**

1. If still failing after fixing translator/scoring:
   - Check if specific year+trim+engine combinations actually exist in source data
   - Verify database was properly loaded with all records
   - Consider adding missing records to database

---

## Risk Assessment: Will These Fixes Break Anything?

### ✅ Safe Changes (No Risk of Regression)

1. **Input preprocessing (strip `*`):**

   - Only affects "Pref*" and "Trend*" keywords
   - Makes keywords more standard
   - Risk: VERY LOW (but test Mazda/Mitsubishi first)
2. **Add missing translator entries (ICE, EDT):**

   - Only adds new mappings, doesn't change existing ones
   - Risk: VERY LOW (verify no conflicts)

### 🟡 Medium-Risk Changes (Needs Testing)

1. **Debug/adjust search scoring:**

   - Might affect high-ambiguity searches (4+ candidates)
   - Need to test: Elantra N (4 candidates - just fixed), Mazda CX-5 (if multiple models)
   - Risk: MEDIUM (requires regression testing on all OEMs)
2. **Improve keyword classification:**

   - Changes how keywords map to semantic categories
   - Could affect scoring for all searches
   - Risk: MEDIUM (requires full pipeline test)

### 🟢 Very Safe Changes (No Regression Risk)

1. **Database additions:**
   - Only adds records, doesn't remove existing ones
   - Risk: VERY LOW

---

## Implementation Priority & Timeline

| Phase   | Action                              | Priority | Files                                               | Est. Time |
| ------- | ----------------------------------- | -------- | --------------------------------------------------- | --------- |
| Phase 1 | Add debug logging to search engine  | P1       | `search_engine.py`                                | 1 hour    |
| Phase 1 | Run pipeline with debug logging     | P1       | None (testing)                                      | 30 mins   |
| Phase 1 | Analyze debug output                | P1       | Analysis                                            | 1 hour    |
| Phase 2 | Implement fix (translator/scoring)  | P1       | `search_engine.py` OR `hyundai_translator.json` | 2-3 hours |
| Phase 2 | Add input preprocessing             | P2       | `step2_header_normalization.py`                   | 1 hour    |
| Phase 2 | Add missing translator entries      | P3       | `hyundai_translator.json`                         | 15 mins   |
| Phase 3 | Re-run Hyundai pipeline             | P1       | None (testing)                                      | 1 hour    |
| Phase 3 | Verify fix resolves failures        | P1       | Analysis                                            | 30 mins   |
| Phase 3 | Regression test: Mazda + Mitsubishi | P1       | None (testing)                                      | 1.5 hours |
| Phase 3 | Final validation                    | P1       | Output file review                                  | 30 mins   |

**Total estimated time:** 9.5 hours

---

## Success Criteria

✅ **Primary:** Model lookup failures reduced to < 10 (95%+ improvement)
✅ **Secondary:** Same issues in Mazda/Mitsubishi do NOT occur (no regression)
✅ **Tertiary:** All 2024/2025/2026 years show consistent results
✅ **Final:** DQ report shows no model lookup failures for Hyundai/Genesis

---

## Next Steps

**Immediately:**

1. Recommend Priority 1: Debug the search scoring with logging
2. Identify the exact failure point
3. Implement targeted fix

**Then:**
4. Test on full pipeline
5. Verify no regressions on other OEMs
6. Document the solution for future reference
