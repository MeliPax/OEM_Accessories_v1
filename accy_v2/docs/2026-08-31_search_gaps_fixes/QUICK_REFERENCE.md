# Quick Reference — Search Gaps Fixes Summary

**For:** Quick status checks, stakeholder updates, audience-specific reading  
**Read time:** 5-10 minutes

---

## Fix Overview (At a Glance)

| Fix | File Changed | Issue | Solution | Impact |
|-----|--------------|-------|----------|--------|
| **A** | `search_engine.py` | 2026 Palisade Calli HEV: same ModelNumber, different Package | Add 3rd branch to grouping: if all Packages distinct, accept as variants | 1 warning ✅ |
| **B** | `keyword_extractor.py` + `classification.yaml` | "Night Edt.HEV": period never splits; "night" unclassified | Period-split regex (letters only); add `night: TRIM` to classification | 1+ warnings ✅ |
| **C** | `search_engine.py` + enrichment YAMLs + `step4_5_model_enrichment.py` | Tucson N-Line/Luxury: source omits fuel keyword; DB only has Hybrid | Config-driven allowlist; inject fuel type when rule matches | 3+ warnings ✅ |

---

## Results Summary

**NOT_FOUND Warnings Trend:**
- After full separation + compound-merge fix: 14 warnings
- After three search fixes (this work): 10 warnings ✅
- Expected after Tucson Luxury re-run: 9 warnings

**Breakdown of remaining 10 NOT_FOUND:**
- 7 true data gaps (require DB/ADS update)
- 1 pending re-run (Tucson Luxury 2024)
- 2 uncertain (under investigation)

---

## By Audience

### Developers Implementing Fixes
→ **Read:** [FIXES_DETAILED.md](FIXES_DETAILED.md)
- Problem definition
- Root cause analysis
- Code solution with exact line numbers
- Verification steps
- Regression testing

### Code Reviewers
→ **Read:** Sections in FIXES_DETAILED.md:
1. Executive summary table
2. Each Fix's "Root Cause" + "Solution" sections
3. "Verification" section (proof it works)
4. "Files Touched" summary

### Data Stewards / Issue Triage
→ **Read:**
1. This file (you're reading it)
2. [VERIFICATION_RESULTS.md](VERIFICATION_RESULTS.md) for metrics
3. Known Issues section (Tucson Luxury, Santa Fe gaps)

### Future OEM Extension
→ **Read:** Fix C section in [FIXES_DETAILED.md](FIXES_DETAILED.md)
- "How to Identify Candidates"
- "Configuration Template"
- "Pattern Reuse" section

### Architecture Review
→ **Read:** "Architecture Notes" in [FIXES_DETAILED.md](FIXES_DETAILED.md)
- Three-tier search strategy
- Configuration-over-code principle

---

## Fix Details (Condensed)

### Fix A: Palisade Calli HEV — Package Differentiation

**The Problem:**
```
2026 Palisade Calligraphy HEV has 2 DB rows:
  Row 1: ModelNumber=PAHW7G2DULCH, Package=480299
  Row 2: ModelNumber=PAHW7G2DULCH, Package=481523 (NHL Special Edition)
→ Result: NOT_FOUND (grouping logic rejected them)
```

**The Fix:**
- Add 3rd branch to `search_engine.py` ~line 335-365
- Check: if all candidates have distinct Package values, accept as variants
- ~30 lines added

**Verification:**
```
Before: search("Hyundai", 2026, ['palisade','calli','hev']) → None
After:  → SearchResult with packages=[480299, 481523] ✓
```

---

### Fix B: Night Edt.HEV — Compound Keywords

**The Problem:**
```
"Night Edt.HEV" trim label:
  Tokenize: ["Night", "Edt.HEV"]  ← period never splits
  Translate: ["Night", "Edt.HEV"]  ← "edt.hev" not in translator
  Classify: {UNCLASSIFIED}  ← "night" not in classification
→ Result: NOT_FOUND
```

**The Fix (2 parts):**
1. Regex in `keyword_extractor.py` line ~129: `r'(?<=[a-zA-Z])\.(?=[A-Za-z])'` → space
   - "Edt.HEV" → "Edt HEV" (preserves "1.6t", "2.0l")
2. Add `night: TRIM` to `hyundai/classification.yaml`

**Verification:**
```
Before: ["Night", "Edt.HEV"] → {UNCLASSIFIED}
After:  ["Night", "Edt", "HEV"] → {TRIM, PACKAGE, ENGINE_TYPE} ✓
```

---

### Fix C: Implied Fuel Type — Config Allowlist

**The Problem:**
```
Tucson N-Line (all years):
  DB state: only Hybrid rows (no gas variant)
  Source label: "N-Line" (no "HEV" keyword)
  Search result: 0 candidates (N-Line only as Hybrid)
→ Result: NOT_FOUND (even though trim exists)
```

**The Fix:**
Config entry in `enrichment.yaml`:
```yaml
implied_fuel_type_trims:
  - model_keywords: [tucson]
    trim_keywords: [n-line]
    fuel_type: hybrid
    years: [2024, 2025, 2026]
```

Logic in `search_engine.py` step 3.5:
- After classification, check MODEL/TRIM against rules
- If matched + no fuel keyword: inject configured fuel type
- Log DQ warning for auditability

**Verification:**
```
Before: ['tucson', 'n-line'] → NOT_FOUND
After:  → applies rule → injects 'hybrid' → finds TUHWDG1ANLHE ✓
        (works for all 3 years)
```

---

## Key Details

### Files Modified
```
accy_v2/core/helpers/keyword_extractor.py
accy_v2/model_lookup/search_engine.py
accy_v2/model_lookup/configs/hyundai/classification.yaml
accy_v2/oems/hyundai/config/enrichment.yaml
accy_v2/oems/genesis/config/enrichment.yaml
accy_v2/oems/hyundai_genesis/pipeline/step4_5_model_enrichment.py
```

### Commits
- **b88339a** — Implement: Fix A/B/C
- **2e341fd** — Docs: Pattern documentation

---

## Known Issues

### Issue 1: Tucson Luxury 2024 — Config Correction Pending ✅ Fixed
- Initial config used `lux` but translator converts to `luxury`
- **Status:** Corrected to `luxury` in final commit
- **Next:** Pipeline re-run to validate

### Issue 2: Santa Fe/Santa Cruz Data Gaps — Not Code
- 7 true data gaps: Santa Cruz 2026 entire year, Santa Fe/Tucson XRT variants
- **Status:** Flagged for data team (DB/ADS update needed)

### Issue 3: 2026 Santa Fe Calli ICE Search Failure — Under Investigation
- Two DB records exist but search fails
- **Status:** Requires investigation (user interrupted tool execution)

---

## Cross-OEM Deployment

**Current State:**
- Hyundai: Fix C rules populated (Tucson N-Line, Luxury)
- Genesis: Empty template available
- Mitsubishi/Mazda/Honda: Can extend as needed

**How to Extend:**
1. Query DB for fuel-locked trims
2. Add entry to `enrichment.yaml` with correct TRANSLATED keywords
3. Include years scope if applicable
4. Test via pipeline run

---

## Next Steps

1. **Immediate:** Re-run pipeline with Tucson Luxury 2024 fix
2. **Investigate:** 2026 Santa Fe Calli ICE (two records should match)
3. **Validate:** Cross-OEM regression (Mitsubishi, Mazda, Honda)
4. **Monitor:** DQ reports for `implied_fuel_type_rule` entries

---

## Reference

**Detailed Technical Docs:** [FIXES_DETAILED.md](FIXES_DETAILED.md)  
**Verification & Metrics:** [VERIFICATION_RESULTS.md](VERIFICATION_RESULTS.md)  
**Earlier Work:** `09_PACKAGE_DIFFERENTIATOR_AND_SEARCH_FIXES.md`
