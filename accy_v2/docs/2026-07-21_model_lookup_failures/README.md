# Model Lookup Failures Investigation & Fix Plan

**Analysis Date:** 2026-07-21  
**Status:** Ready for Implementation  
**Failures Analyzed:** 89 model lookups across Hyundai and Genesis  
**Expected Improvement:** 95%+ reduction (89 → <10 failures)  

---

## 📁 Document Structure

This folder contains a complete investigation and fix plan for 89 model lookup failures in the Hyundai/Genesis pipeline. Use these documents in order:

### 1. **00_EXECUTIVE_SUMMARY.txt** (Read First - 5 min)
**Purpose:** Quick overview and decision point  
**Contains:**
- Problem statement (88 failures, same pattern)
- Root cause hypothesis (5 possibilities ranked by likelihood)
- Recommended approach (3-phase fix plan)
- Confidence levels for success

**Action:** Start here to understand the big picture.

---

### 2. **01_DATA_ISSUES_REPORT.md** (Reference - 15 min)
**Purpose:** Detailed technical analysis of all 89 failures  
**Contains:**
- Complete failure distribution (by model, year, type)
- Root cause analysis with evidence
- Database coverage verification (database HAS the records)
- Severity assessment
- Failure patterns (same issue across years)
- Risk assessment for each potential fix

**Action:** Review to understand WHY failures are happening.

---

### 3. **02_IMPLEMENTATION_PLAN.md** (Reference - 20 min)
**Purpose:** Step-by-step implementation strategy  
**Contains:**
- Phase 1: Debug & diagnosis (add logging, identify exact issue)
- Phase 2: Implement fixes (5 specific fix types based on root cause)
- Phase 3: Testing & validation (unit, integration, end-to-end)
- Rollback procedures
- File locations and critical code sections

**Action:** Reference during implementation phase.

---

### 4. **03_EXACT_FIXES_REQUIRED.md** (Most Important - Use During Implementation)
**Purpose:** Entry-by-entry instructions for config file changes  
**Contains:**
- Exact line numbers and file locations
- Before/after code snippets
- **Precisely what to add to each file**
- JSON validation procedures
- Implementation order

**This is the GOLD STANDARD** - follow these instructions EXACTLY.

**Changes Required:**
1. **Hyundai Translator:** Add 2 entries ("ice", "edt")
2. **Hyundai Classification:** Add 3 entries ("plug-in", "electric", "combustion")
3. **Genesis Translator:** Add 1 entry ("ev")
4. **Genesis Classification:** Add 2 entries ("electric", "ev")
5. **Python Code:** 1 line change (strip asterisks from keywords)

**Total:** 5 files, 9 new entries, 1 code line

---

### 5. **04_TESTING_GUIDE.md** (Use After Making Changes)
**Purpose:** Complete testing procedures to validate all fixes work  
**Contains:**
- Phase 1: Unit tests (JSON validation, entry verification)
- Phase 2: Integration tests (translator, classifier, search engine)
- Phase 3: End-to-end tests (full pipeline run, output validation)
- Test scripts (copy-paste ready)
- Success criteria for each test
- Troubleshooting guide (if tests fail)

**Action:** Run all tests after making the 5 file changes.

---

## 🚀 Quick Start Guide

### For Managers/Reviewers
1. Read **00_EXECUTIVE_SUMMARY.txt** (5 min)
2. Skim **01_DATA_ISSUES_REPORT.md** (what are we fixing?)
3. Check **03_EXACT_FIXES_REQUIRED.md** (is it clearly specified?)

### For Implementation Engineers
1. Review **03_EXACT_FIXES_REQUIRED.md** (know exactly what to add)
2. Make changes to 5 files following the exact instructions
3. Run all tests in **04_TESTING_GUIDE.md**
4. Verify output improvements
5. Commit changes with reference to this plan

### For QA/Testing Teams
1. Review **04_TESTING_GUIDE.md** (know what to test)
2. Run all phases of testing
3. Verify success criteria
4. Sign off on improvements

---

## 📊 Key Metrics

### Before Fix
- Total failures: **89**
- Hyundai model lookup failures: **88**
- Trim applicability failures: **1**
- Affected models: 15+ (Santa Fe, Tucson, Kona, etc.)
- Failure pattern: Consistent across 2024, 2025, 2026

### Expected After Fix
- Total failures: **<10** (95%+ improvement)
- Same failure patterns fixed at once (not model-by-model)
- All 15+ affected models improved
- All years (2024, 2025, 2026) benefit from single fix

---

## 🔧 Changes Summary

### Files to Modify

| File | Change | Entries | Risk |
|------|--------|---------|------|
| `accy_v2/oems/hyundai/pipeline/step2_header_normalization.py` | Strip `*` from keywords | 1 line | 🟢 VERY LOW |
| `accy_v2/model_lookup/configs/hyundai_translator.json` | Add "ice", "edt" | 2 entries | 🟢 VERY LOW |
| `accy_v2/model_lookup/configs/hyundai_classification.json` | Add "plug-in", "electric", "combustion" | 3 entries | 🟡 MEDIUM |
| `accy_v2/model_lookup/configs/genesis_translator.json` | Add "ev" | 1 entry | 🟢 VERY LOW |
| `accy_v2/model_lookup/configs/genesis_classification.json` | Add "electric", "ev" | 2 entries | 🟡 MEDIUM |

**Total effort:** 15-20 minutes to make changes, 60 minutes to test

---

## ✅ Pre-Implementation Checklist

Before you start, verify:

- [ ] You have read **00_EXECUTIVE_SUMMARY.txt**
- [ ] You understand the root cause (config/classifier issue)
- [ ] You have **03_EXACT_FIXES_REQUIRED.md** open while making changes
- [ ] Git status is clean (no uncommitted changes)
- [ ] You have git configured to commit changes

```bash
cd "c:\Users\paxm\OneDrive - PBS SYSTEMS\Desktop\Office\Projects\OEM Accessory project\OEM_Accessories_v1"
git status  # Should show nothing, or only these docs
git log --oneline -5  # Verify recent commits
```

---

## 🧪 Testing Checklist

After making changes:

- [ ] Run Phase 1 tests (JSON validation) - 2 min
- [ ] Run Phase 2 tests (translator/classifier) - 8 min
- [ ] Run Phase 3 tests (search engine specific cases) - 5 min
- [ ] Run full Hyundai pipeline - 30 min
- [ ] Check _Data_Issues sheet (< 10 failures) - 5 min
- [ ] Regression test Mazda - 20 min
- [ ] Regression test Mitsubishi - 15 min
- [ ] Manual Excel spot-check - 10 min

**Total testing time:** ~95 minutes

---

## 📝 Implementation Notes

### Key Insights from Analysis

1. **Database IS complete** - The records exist, search isn't finding them
2. **Pattern is consistent** - Same trim fails across all years and models
3. **Root cause is systematic** - One fix will solve 80-90% of failures
4. **Risk is MEDIUM but manageable** - Changes are isolated, regression testing is built in

### Why This Approach Works

- **Translator entries** make sure abbreviations are converted to full words
- **Classification entries** ensure converted words are recognized as valid semantic tokens
- **Scoring adjustment** (if needed) gives high-confidence matches more credit
- **Input preprocessing** handles edge cases (trailing asterisks)

### If You Get Stuck

1. Check **04_TESTING_GUIDE.md** Troubleshooting section
2. Review the exact line numbers in **03_EXACT_FIXES_REQUIRED.md**
3. Verify JSON is valid using online JSON validator
4. Check Python syntax for the code change
5. Run individual tests to isolate the issue

---

## 📞 Questions?

### "Why 89 failures but only 5 files to change?"

The failures aren't independent - they're all manifestations of the same root cause. A trim keyword like "Lux" fails the same way whether it's in Santa Fe, Tucson, or Kona. One fix to the translator/classifier fixes it everywhere.

### "What if the tests fail after I make changes?"

See the Troubleshooting section in **04_TESTING_GUIDE.md**. Most common issues:
- JSON syntax errors (use online validator)
- Typos in keyword spelling (double-check against spec)
- Entry in wrong section (verify file structure)
- Code change in wrong location (search for context lines)

### "How confident are you this will work?"

- **Root cause identification:** 70% confident (MEDIUM)
- **Fix approach:** 95% confident (HIGH - fixes are well-defined)
- **Success rate:** 90% confident (fixes 85%+ of failures, but 5-10 may remain)

Confidence increases to 95%+ once Phase 1 unit tests pass.

---

## 🎯 Success Looks Like

### After Implementation

You run the Hyundai pipeline and:

1. **Pipeline completes successfully** - No crashes, normal runtime
2. **_Data_Issues sheet is nearly empty** - <10 failures instead of 89
3. **All failing keywords now work:**
   - "Lux" searches return results ✅
   - "Pref" and "Pref*" searches return results ✅
   - "HEV" searches return results ✅
   - "N-Line" searches return results ✅
   - "Trend" searches return results ✅
4. **No regressions** - Mazda and Mitsubishi pipelines unaffected
5. **Excel output looks good** - All expected trims visible in sheets

---

## 📋 Version Info

| Document | Version | Date | Status |
|----------|---------|------|--------|
| Executive Summary | 1.0 | 2026-07-21 | Ready |
| Data Issues Report | 1.0 | 2026-07-21 | Ready |
| Implementation Plan | 1.0 | 2026-07-21 | Ready |
| Exact Fixes Required | 1.0 | 2026-07-21 | Ready |
| Testing Guide | 1.0 | 2026-07-21 | Ready |

---

## Next Steps

1. **Read 00_EXECUTIVE_SUMMARY.txt** to understand the problem
2. **Review 03_EXACT_FIXES_REQUIRED.md** to see what needs to be added
3. **Make the 5 changes** to config files and Python code
4. **Run all tests** in 04_TESTING_GUIDE.md
5. **Verify success** (< 10 failures, all keywords working)
6. **Commit changes** with reference to this analysis

---

**Created:** 2026-07-21  
**Analysis by:** Claude Code (Model Lookup Failure Investigation)  
**Scope:** 89 Hyundai/Genesis model lookup failures  
**Complexity:** MEDIUM (5 files, 9 entries, 1 code line)  
**Estimated Fix Time:** 75-90 minutes (20 min changes + 60 min testing)  
