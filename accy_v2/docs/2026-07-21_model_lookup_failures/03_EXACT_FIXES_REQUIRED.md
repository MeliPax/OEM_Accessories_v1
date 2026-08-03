# Exact Fixes Required: Entry-by-Entry Instructions

**Date:** 2026-07-21
**Scope:** Fixes to make based on root cause analysis
**Files to Modify:** 3 config files + 1 Python file

---

## Overview of Required Changes

Based on the 89 failures analysis, **3 main issues need fixing**:

1. **Input Preprocessing:** Strip trailing `*` from keywords ("Pref*" → "Pref")
2. **Translator Entries:** Add missing translations for new abbreviations
3. **Classification Entries:** Add keyword classifications for proper semantic matching

---

## FIX #1: Input Preprocessing (2 Keywords Affected)

**Failures This Fixes:** "Pref*" and "Trend*" (4 failures total)
**Why It's Needed:** Asterisks prevent exact matching in translator
**Risk Level:** 🟢 VERY LOW

### Step 1.1: Identify Where Keywords Are Extracted

**File:** `accy_v2/oems/hyundai/pipeline/step2_header_normalization.py`

Find the section where keywords are extracted from trim column cells (look for something like):

```python
# Find lines that extract keywords from headers or trim cells
# Common patterns:
# - keywords = [cell.lower().strip() for cell in ...]
# - trim_keywords = extract_from_trim_column(cell)
```

### Step 1.2: Add Asterisk Stripping

**Exact Change Required:**

**BEFORE:**

```python
keywords = [keyword.lower().strip() for keyword in keywords]
```

**AFTER:**

```python
keywords = [keyword.lower().strip().rstrip("*").strip() for keyword in keywords]
```

**Explanation:**

- `.rstrip("*")` removes trailing asterisks: "Pref*" → "Pref"
- `.strip()` removes any spaces after asterisk removal
- `.lower()` ensures lowercase matching

### Step 1.3: Test This Fix

After making the change:

```python
# Test in Python interpreter or test file:
test_keywords = ["pref*", "trend*", "pref", "trend"]
cleaned = [k.lower().strip().rstrip("*").strip() for k in test_keywords]
print(cleaned)  # Should output: ['pref', 'trend', 'pref', 'trend']
```

---

## FIX #2: Hyundai Translator Entries (3 New Entries)

**Failures This Fixes:** ICE, EDT.HEV, and similar abbreviations (3-5 failures)
**Why It's Needed:** Input file uses abbreviations not in translator
**Risk Level:** 🟢 VERY LOW

### File: `accy_v2/model_lookup/configs/hyundai_translator.json`

### Step 2.1: Add "ice" Translation

**Location:** After line 20 (in `"fuel_drivetrain"` section)

**BEFORE (current state):**

```json
"fuel_drivetrain": {
  "hev": "hybrid",
  "phev": "plug-in",
  "ev": "electric"
}
```

**AFTER (add new entry):**

```json
"fuel_drivetrain": {
  "hev": "hybrid",
  "phev": "plug-in",
  "ev": "electric",
  "ice": "combustion"
}
```

**Why:** Maps "ICE" (Internal Combustion Engine) to "combustion" for classification

### Step 2.2: Add "edt" Translation

**Location:** In `"trim_levels"` section (after line 15)

**BEFORE (current state):**

```json
"trim_levels": {
  "pref": "preferred",
  "ess": "essential",
  "calli": "calligraphy",
  "lux": "luxury",
  "ult": "ultimate",
  "adv": "advanced",
  "ed": "edition",
  "pkg": "package",
  "pckg": "package"
}
```

**AFTER (add new entry):**

```json
"trim_levels": {
  "pref": "preferred",
  "ess": "essential",
  "calli": "calligraphy",
  "lux": "luxury",
  "ult": "ultimate",
  "adv": "advanced",
  "ed": "edition",
  "edt": "edition",
  "pkg": "package",
  "pckg": "package"
}
```

**Why:** Maps "EDT" (Edition) abbreviation to "edition" (already have "ed" but explicit mapping helps)

### Step 2.3: Add "plug-in" (with hyphen) If Not Present

**Location:** In `"data_artifacts"` section (around line 36)

**BEFORE (current state):**

```json
"data_artifacts": {
  "plug-in": "plug-in"
}
```

**AFTER (already correct, NO CHANGE NEEDED)**

```json
"data_artifacts": {
  "plug-in": "plug-in"
}
```

**Note:** This is ALREADY in the translator, so no action needed here.

### Step 2.4: Final Hyundai Translator Should Look Like

```json
{
  "make": "Hyundai",
  "version": "1.0",
  "description": "Hyundai-specific keyword translation rules, organized by category for maintainability. Flattened into one lookup table at load time. Applied before classification.",
  "categories": {
    "trim_levels": {
      "pref": "preferred",
      "ess": "essential",
      "calli": "calligraphy",
      "lux": "luxury",
      "ult": "ultimate",
      "adv": "advanced",
      "ed": "edition",
      "edt": "edition",
      "pkg": "package",
      "pckg": "package"
    },
    "fuel_drivetrain": {
      "hev": "hybrid",
      "phev": "plug-in",
      "ev": "electric",
      "ice": "combustion"
    },
    "body_style": {
      "coupe": "coupe",
      "5p": "5p",
      "7p": "7p"
    },
    "technology": {
      "nhl": "nhl",
      "xrt": "xrt",
      "e-sc": "e-sc",
      "elsd": "elsd"
    },
    "range_options": {
      "long": "long"
    },
    "data_artifacts": {
      "plug-in": "plug-in"
    },
    "Extras": {
      "w/": "with"
    }
  }
}
```

---

## FIX #3: Hyundai Classification Entries (5 New Entries)

**Failures This Fixes:** Translated keywords not being recognized (50+ failures)
**Why It's Needed:** Translated outputs need semantic classification
**Risk Level:** 🟡 MEDIUM

### File: `accy_v2/model_lookup/configs/hyundai_classification.json`

### Step 3.1: Add "plug-in" Classification

**Location:** In `"token_map"` section (after line 34, in POWERTRAIN_TYPE area)

**BEFORE (current state around line 34-37):**

```json
"hev": "POWERTRAIN_TYPE",
"hybrid": "POWERTRAIN_TYPE",
"phev": "POWERTRAIN_TYPE",
"ev": "POWERTRAIN_TYPE",
```

**AFTER (add new entry):**

```json
"hev": "POWERTRAIN_TYPE",
"hybrid": "POWERTRAIN_TYPE",
"phev": "POWERTRAIN_TYPE",
"plug-in": "POWERTRAIN_TYPE",
"ev": "POWERTRAIN_TYPE",
"electric": "POWERTRAIN_TYPE",
```

**Why:**

- "plug-in" is the translated output from "phev", needs classification
- "electric" is the translated output from "ev", needs classification

### Step 3.2: Add "combustion" Classification

**Location:** In `"token_map"` section (add new category or add to ENGINE_SPEC)

**Option A - Add to ENGINE_SPEC:**

```json
"combustion": "ENGINE_SPEC",
```

**Option B (Better) - Create new category:**

```json
"combustion": "DRIVETRAIN",
"ice": "DRIVETRAIN",
```

**Recommendation:** Use Option A (combustion as ENGINE_SPEC is simpler)

### Step 3.3: Add "edition" Classification (If Not Present)

**Check if already exists:** Look for `"edition"` in token_map

**Current state (line 61):**

```json
"edition": "PACKAGE",
```

**Status:** ✅ ALREADY PRESENT - NO CHANGE NEEDED

### Step 3.4: Add "calligraphy" Classification (If Not Present)

**Check if already exists:** Look for `"calligraphy"` in token_map

**Current state (line 25):**

```json
"calligraphy": "TRIM",
```

**Status:** ✅ ALREADY PRESENT - NO CHANGE NEEDED

### Step 3.5: Final Hyundai Classification Changes

**Add these lines to the token_map section (around line 37, after "ev": "POWERTRAIN_TYPE",):**

```json
"plug-in": "POWERTRAIN_TYPE",
"electric": "POWERTRAIN_TYPE",
"combustion": "ENGINE_SPEC",
```

**Complete updated section should look like:**

```json
"hev": "POWERTRAIN_TYPE",
"hybrid": "POWERTRAIN_TYPE",
"phev": "POWERTRAIN_TYPE",
"plug-in": "POWERTRAIN_TYPE",
"ev": "POWERTRAIN_TYPE",
"electric": "POWERTRAIN_TYPE",
"1.6t": "ENGINE_SPEC",
"2.0l": "ENGINE_SPEC",
"2.0t": "ENGINE_SPEC",
"2.5l": "ENGINE_SPEC",
"2.5t": "ENGINE_SPEC",
"3.3t": "ENGINE_SPEC",
"3.5t": "ENGINE_SPEC",
"combustion": "ENGINE_SPEC",
"turbo": "ENGINE_SPEC",
```

---

## FIX #4: Genesis Translator Entries (1 New Entry)

**Failures This Fixes:** Genesis performance and electrified models (3-5 failures)
**Why It's Needed:** Genesis-specific vehicles need proper abbreviation handling
**Risk Level:** 🟢 VERY LOW

### File: `accy_v2/model_lookup/configs/genesis_translator.json`

### Step 4.1: Verify "electrified" Is Mapped

**Current state (line 26):**

```json
"electrified": "electric",
```

**Status:** ✅ ALREADY PRESENT - NO CHANGE NEEDED

### Step 4.2: Add "ev" Translation

**Location:** In `"fuel_drivetrain"` section (after line 27)

**BEFORE (current state):**

```json
"fuel_drivetrain": {
  "2.0t": "2.0t",
  "2.5t": "2.5t",
  "3.3t": "3.3t",
  "3.5t": "3.5t",
  "3.8": "3.8",
  "5.0": "5.0",
  "5.0l": "5.0",
  "e-sc": "e-sc",
  "electrified": "electric",
  "awd": "awd",
  "rwd": "rwd"
}
```

**AFTER (add new entry):**

```json
"fuel_drivetrain": {
  "2.0t": "2.0t",
  "2.5t": "2.5t",
  "3.3t": "3.3t",
  "3.5t": "3.5t",
  "3.8": "3.8",
  "5.0": "5.0",
  "5.0l": "5.0",
  "e-sc": "e-sc",
  "electrified": "electric",
  "ev": "electric",
  "awd": "awd",
  "rwd": "rwd"
}
```

**Why:** Maps "EV" abbreviation to "electric" for Genesis vehicles

---

## FIX #5: Genesis Classification Entries (2 New Entries)

**Failures This Fixes:** Genesis EV and performance models (3-5 failures)
**Why It's Needed:** Translated keywords need classification
**Risk Level:** 🟡 MEDIUM

### File: `accy_v2/model_lookup/configs/genesis_classification.json`

### Step 5.1: Add "electric" and "ev" Classifications

**Location:** In `"token_map"` section (around line 30-40, in ENGINE_TYPE area)

**Current state (line 30):**

```json
"electrified": "ENGINE_TYPE",
```

**Add these lines after:**

```json
"electric": "ENGINE_TYPE",
"ev": "ENGINE_TYPE",
```

**Why:**

- "electric" is the translated output from "electrified" and "ev"
- "ev" itself should be classified

### Step 5.2: Complete Updated Section

**Add these lines to token_map (around line 30, after electrified line):**

```json
"electrified": "ENGINE_TYPE",
"electric": "ENGINE_TYPE",
"ev": "ENGINE_TYPE",
```

---

## Summary of All Changes

### Change Summary Table

| File                              | Lines | Change                                  | Type   | Risk        |
| --------------------------------- | ----- | --------------------------------------- | ------ | ----------- |
| `step2_header_normalization.py` | ?     | Strip`*` from keywords                | Code   | 🟢 VERY LOW |
| `hyundai_translator.json`       | 8, 14 | Add "ice" and "edt" entries             | Config | 🟢 VERY LOW |
| `hyundai_classification.json`   | 37-38 | Add "plug-in", "electric", "combustion" | Config | 🟡 MEDIUM   |
| `genesis_translator.json`       | 26    | Add "ev" entry                          | Config | 🟢 VERY LOW |
| `genesis_classification.json`   | 31-32 | Add "electric", "ev" entries            | Config | 🟡 MEDIUM   |

### Total Changes Required

- **1 Python file:** 1 line (add `.rstrip("*")`)
- **2 JSON translator files:** 2 new entries total
- **2 JSON classification files:** 5 new entries total

**Estimated edit time:** 15-20 minutes

---

## Validation Checklist Before Changes

Before making any changes, verify:

- [ ] Git status is clean (no uncommitted changes)
- [ ] You have a backup of current config files
- [ ] You have the latest version of the files

```bash
# From accy_v2 directory:
cd accy_v2
git status
git diff
```

---

## Format Verification

### JSON Syntax Validation

After each JSON edit, verify the JSON is valid:

```python
import json

# For Hyundai translator
with open('model_lookup/configs/hyundai_translator.json') as f:
    data = json.load(f)
    print("✅ hyundai_translator.json is valid")

# For Hyundai classification
with open('model_lookup/configs/hyundai_classification.json') as f:
    data = json.load(f)
    print("✅ hyundai_classification.json is valid")

# For Genesis translator
with open('model_lookup/configs/genesis_translator.json') as f:
    data = json.load(f)
    print("✅ genesis_translator.json is valid")

# For Genesis classification
with open('model_lookup/configs/genesis_classification.json') as f:
    data = json.load(f)
    print("✅ genesis_classification.json is valid")
```

---

## Implementation Order

1. **First:** Add asterisk stripping to Python file (Step 1)
2. **Second:** Update translator files (Steps 2 & 4)
3. **Third:** Update classification files (Steps 3 & 5)
4. **Last:** Verify JSON validity before running pipeline

This order ensures:

- Input preprocessing happens first (lowest risk)
- Translator updates happen before classification (translation prerequisite)
- Classification updates happen last (depends on translator)

---

## Rollback Instructions

If any change causes issues:

```bash
# Rollback to previous commit
git checkout HEAD -- accy_v2/model_lookup/configs/
git checkout HEAD -- accy_v2/oems/hyundai/pipeline/step2_header_normalization.py

# Verify rollback
git status
```

---

## Next: Testing Guide

See `04_TESTING_GUIDE.md` for detailed testing instructions after making these changes.
