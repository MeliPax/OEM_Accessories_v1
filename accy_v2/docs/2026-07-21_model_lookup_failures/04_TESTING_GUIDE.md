# Testing Guide: How to Validate the Fixes

**Date:** 2026-07-21  
**Purpose:** Step-by-step instructions to test all fixes are working  
**Scope:** Unit tests, integration tests, and end-to-end pipeline tests  

---

## Overview of Testing Strategy

Testing happens in **3 phases**:

1. **Unit Testing** (5 min) — Validate individual config/code changes
2. **Integration Testing** (10 min) — Validate search engine with fixed configs
3. **End-to-End Testing** (60 min) — Full pipeline run and output validation

---

## Phase 1: Unit Testing (5 minutes)

### Test 1.1: JSON Syntax Validation

**Purpose:** Ensure all config files are valid JSON  
**Time:** 2 minutes

**Command:**
```bash
cd "c:\Users\paxm\OneDrive - PBS SYSTEMS\Desktop\Office\Projects\OEM Accessory project\OEM_Accessories_v1\accy_v2"

# Test each file
python -m json.tool model_lookup/configs/hyundai_translator.json > /dev/null && echo "✅ hyundai_translator.json valid"
python -m json.tool model_lookup/configs/hyundai_classification.json > /dev/null && echo "✅ hyundai_classification.json valid"
python -m json.tool model_lookup/configs/genesis_translator.json > /dev/null && echo "✅ genesis_translator.json valid"
python -m json.tool model_lookup/configs/genesis_classification.json > /dev/null && echo "✅ genesis_classification.json valid"
```

**Expected Output:**
```
✅ hyundai_translator.json valid
✅ hyundai_classification.json valid
✅ genesis_translator.json valid
✅ genesis_classification.json valid
```

**If any fail:** JSON syntax error - review the file for missing commas, quotes, or brackets.

---

### Test 1.2: Translator Entries Present

**Purpose:** Verify all new entries are in translator files  
**Time:** 1 minute

**Script:**
```python
import json
import sys

def check_translator_entries(filename, required_entries):
    """Check if translator has required entries."""
    with open(filename) as f:
        config = json.load(f)
    
    # Flatten all categories into single dict
    all_translations = {}
    for category, entries in config.get("categories", {}).items():
        all_translations.update(entries)
    
    missing = []
    for key, expected_value in required_entries.items():
        actual_value = all_translations.get(key)
        if actual_value != expected_value:
            missing.append(f"  ❌ '{key}': expected '{expected_value}', got '{actual_value}'")
        else:
            print(f"  ✅ '{key}': {expected_value}")
    
    return missing

# Test Hyundai translator
print("=" * 80)
print("HYUNDAI TRANSLATOR")
print("=" * 80)

hyundai_required = {
    "pref": "preferred",
    "hev": "hybrid",
    "phev": "plug-in",
    "ev": "electric",
    "ice": "combustion",  # NEW
    "edt": "edition",     # NEW
}

missing = check_translator_entries(
    "accy_v2/model_lookup/configs/hyundai_translator.json",
    hyundai_required
)

if missing:
    print("\n❌ Missing or incorrect entries:")
    for msg in missing:
        print(msg)
    sys.exit(1)
else:
    print("\n✅ All required translator entries present")

# Test Genesis translator
print("\n" + "=" * 80)
print("GENESIS TRANSLATOR")
print("=" * 80)

genesis_required = {
    "electrified": "electric",
    "e-sc": "e-sc",
    "ev": "electric",  # NEW
}

missing = check_translator_entries(
    "accy_v2/model_lookup/configs/genesis_translator.json",
    genesis_required
)

if missing:
    print("\n❌ Missing or incorrect entries:")
    for msg in missing:
        print(msg)
    sys.exit(1)
else:
    print("\n✅ All required translator entries present")
```

**Run this script:**
```bash
cd c:\Users\paxm\OneDrive - PBS SYSTEMS\Desktop\Office\Projects\OEM Accessory project\OEM_Accessories_v1
python test_translator_entries.py  # Save the script above with this name
```

**Expected Output:**
```
================================================================================
HYUNDAI TRANSLATOR
================================================================================
  ✅ 'pref': preferred
  ✅ 'hev': hybrid
  ✅ 'phev': plug-in
  ✅ 'ev': electric
  ✅ 'ice': combustion
  ✅ 'edt': edition

✅ All required translator entries present

================================================================================
GENESIS TRANSLATOR
================================================================================
  ✅ 'electrified': electric
  ✅ 'e-sc': e-sc
  ✅ 'ev': electric

✅ All required translator entries present
```

---

### Test 1.3: Classification Entries Present

**Purpose:** Verify all new classifications are in classification files  
**Time:** 1 minute

**Script:**
```python
import json
import sys

def check_classification_entries(filename, required_entries):
    """Check if classification has required entries."""
    with open(filename) as f:
        config = json.load(f)
    
    token_map = config.get("token_map", {})
    
    missing = []
    for key, expected_category in required_entries.items():
        actual_category = token_map.get(key)
        if actual_category != expected_category:
            missing.append(f"  ❌ '{key}': expected '{expected_category}', got '{actual_category}'")
        else:
            print(f"  ✅ '{key}': {expected_category}")
    
    return missing

# Test Hyundai classification
print("=" * 80)
print("HYUNDAI CLASSIFICATION")
print("=" * 80)

hyundai_required = {
    "hybrid": "POWERTRAIN_TYPE",
    "hev": "POWERTRAIN_TYPE",
    "phev": "POWERTRAIN_TYPE",
    "plug-in": "POWERTRAIN_TYPE",      # NEW
    "electric": "POWERTRAIN_TYPE",     # NEW
    "ev": "POWERTRAIN_TYPE",
    "combustion": "ENGINE_SPEC",       # NEW
}

missing = check_classification_entries(
    "accy_v2/model_lookup/configs/hyundai_classification.json",
    hyundai_required
)

if missing:
    print("\n❌ Missing or incorrect entries:")
    for msg in missing:
        print(msg)
    sys.exit(1)
else:
    print("\n✅ All required classification entries present")

# Test Genesis classification
print("\n" + "=" * 80)
print("GENESIS CLASSIFICATION")
print("=" * 80)

genesis_required = {
    "electrified": "ENGINE_TYPE",
    "electric": "ENGINE_TYPE",  # NEW
    "ev": "ENGINE_TYPE",        # NEW
}

missing = check_classification_entries(
    "accy_v2/model_lookup/configs/genesis_classification.json",
    genesis_required
)

if missing:
    print("\n❌ Missing or incorrect entries:")
    for msg in missing:
        print(msg)
    sys.exit(1)
else:
    print("\n✅ All required classification entries present")
```

**Run this script:**
```bash
python test_classification_entries.py  # Save the script above with this name
```

---

## Phase 2: Integration Testing (10 minutes)

### Test 2.1: Translator Functionality

**Purpose:** Test that translator properly converts keywords  
**Time:** 3 minutes

**Script:**
```python
from pathlib import Path
import sys

root = Path(
    r"c:\Users\paxm\OneDrive - PBS SYSTEMS\Desktop\Office\Projects\OEM Accessory project\OEM_Accessories_v1"
)
sys.path.insert(0, str(root / "accy_v2"))

from model_lookup.semantic.translator import load_oem_translator, translate_keywords

print("=" * 80)
print("TESTING TRANSLATOR: Hyundai")
print("=" * 80)

configs_dir = str(root / "accy_v2/model_lookup/configs")
hyundai_translator = load_oem_translator("Hyundai", configs_dir)

test_cases = [
    (["pref", "hev"], ["preferred", "hybrid"]),          # 2024 Santa Fe Pref HEV
    (["pref*"], ["preferred"]),                          # 2025 Tucson Pref* (with asterisk)
    (["lux"], ["luxury"]),                                # Santa Fe Lux
    (["ice"], ["combustion"]),                            # NEW: Santa Fe ICE
    (["edt", "hev"], ["edition", "hybrid"]),             # NEW: Edition Hybrid
    (["ult", "calli"], ["ultimate", "calligraphy"]),     # Santa Fe Ult Calli
]

all_pass = True
for raw, expected in test_cases:
    try:
        result = translate_keywords(raw, hyundai_translator)
        if result == expected:
            print(f"✅ {raw} → {result}")
        else:
            print(f"❌ {raw}: expected {expected}, got {result}")
            all_pass = False
    except Exception as e:
        print(f"❌ {raw}: ERROR - {e}")
        all_pass = False

print("\n" + "=" * 80)
print("TESTING TRANSLATOR: Genesis")
print("=" * 80)

genesis_translator = load_oem_translator("Genesis", configs_dir)

test_cases_genesis = [
    (["g70", "2.0t", "advanced"], ["g70", "2.0t", "advanced"]),
    (["g90", "3.5t", "e-sc"], ["g90", "3.5t", "e-sc"]),
    (["ev"], ["electric"]),                               # NEW: Genesis EV
    (["electrified"], ["electric"]),                      # Genesis Electrified
]

for raw, expected in test_cases_genesis:
    try:
        result = translate_keywords(raw, genesis_translator)
        if result == expected:
            print(f"✅ {raw} → {result}")
        else:
            print(f"❌ {raw}: expected {expected}, got {result}")
            all_pass = False
    except Exception as e:
        print(f"❌ {raw}: ERROR - {e}")
        all_pass = False

if all_pass:
    print("\n✅ All translator tests passed")
    sys.exit(0)
else:
    print("\n❌ Some translator tests failed")
    sys.exit(1)
```

**Run this script:**
```bash
python test_translator_functionality.py
```

**Expected Output:**
```
================================================================================
TESTING TRANSLATOR: Hyundai
================================================================================
✅ ['pref', 'hev'] → ['preferred', 'hybrid']
✅ ['pref*'] → ['preferred']
✅ ['lux'] → ['luxury']
✅ ['ice'] → ['combustion']
✅ ['edt', 'hev'] → ['edition', 'hybrid']
✅ ['ult', 'calli'] → ['ultimate', 'calligraphy']

================================================================================
TESTING TRANSLATOR: Genesis
================================================================================
✅ ['g70', '2.0t', 'advanced'] → ['g70', '2.0t', 'advanced']
✅ ['g90', '3.5t', 'e-sc'] → ['g90', '3.5t', 'e-sc']
✅ ['ev'] → ['electric']
✅ ['electrified'] → ['electric']

✅ All translator tests passed
```

---

### Test 2.2: Classification Functionality

**Purpose:** Test that classifier recognizes translated keywords  
**Time:** 3 minutes

**Script:**
```python
from pathlib import Path
import sys

root = Path(
    r"c:\Users\paxm\OneDrive - PBS SYSTEMS\Desktop\Office\Projects\OEM Accessory project\OEM_Accessories_v1"
)
sys.path.insert(0, str(root / "accy_v2"))

from model_lookup.semantic.classifier import load_classification_config, classify_tokens

print("=" * 80)
print("TESTING CLASSIFICATION: Hyundai")
print("=" * 80)

configs_dir = str(root / "accy_v2/model_lookup/configs")
hyundai_classifier = load_classification_config("Hyundai", configs_dir)

test_cases = [
    (["santa", "fe", "preferred", "hybrid"], {
        "MODEL": ["santa", "fe"],
        "TRIM": ["preferred"],
        "POWERTRAIN_TYPE": ["hybrid"]
    }),
    (["kona", "luxury"], {
        "MODEL": ["kona"],
        "TRIM": ["luxury"]
    }),
    (["tucson", "preferred"], {
        "MODEL": ["tucson"],
        "TRIM": ["preferred"]
    }),
    (["santa", "fe", "combustion"], {  # NEW: combustion should classify as ENGINE_SPEC
        "MODEL": ["santa", "fe"],
        "ENGINE_SPEC": ["combustion"]
    }),
]

all_pass = True
for tokens, expected_structure in test_cases:
    try:
        result = classify_tokens(tokens, hyundai_classifier)
        
        # Check that expected categories are present
        match = all(
            result.get(cat) == values 
            for cat, values in expected_structure.items()
            if values  # Only check non-empty categories
        )
        
        if match:
            print(f"✅ {tokens}")
            print(f"   → {result}")
        else:
            print(f"❌ {tokens}")
            print(f"   Expected: {expected_structure}")
            print(f"   Got: {result}")
            all_pass = False
    except Exception as e:
        print(f"❌ {tokens}: ERROR - {e}")
        all_pass = False

print("\n" + "=" * 80)
print("TESTING CLASSIFICATION: Genesis")
print("=" * 80)

genesis_classifier = load_classification_config("Genesis", configs_dir)

test_cases_genesis = [
    (["g70", "2.0t", "advanced"], {
        "MODEL": ["g70"],
        "ENGINE_TYPE": ["2.0t"],
        "TRIM": ["advanced"]
    }),
    (["gv60", "performance"], {
        "MODEL": ["gv60"],
        "TRIM": ["performance"]
    }),
    (["g80", "electric"], {  # NEW: electric should classify as ENGINE_TYPE
        "MODEL": ["g80"],
        "ENGINE_TYPE": ["electric"]
    }),
]

for tokens, expected_structure in test_cases_genesis:
    try:
        result = classify_tokens(tokens, genesis_classifier)
        
        match = all(
            result.get(cat) == values
            for cat, values in expected_structure.items()
            if values
        )
        
        if match:
            print(f"✅ {tokens}")
            print(f"   → {result}")
        else:
            print(f"❌ {tokens}")
            print(f"   Expected: {expected_structure}")
            print(f"   Got: {result}")
            all_pass = False
    except Exception as e:
        print(f"❌ {tokens}: ERROR - {e}")
        all_pass = False

if all_pass:
    print("\n✅ All classification tests passed")
    sys.exit(0)
else:
    print("\n❌ Some classification tests failed")
    sys.exit(1)
```

**Run this script:**
```bash
python test_classification_functionality.py
```

---

### Test 2.3: Search Engine with Fixed Configs

**Purpose:** Test that actual searches now work for failing cases  
**Time:** 4 minutes

**Script:**
```python
from pathlib import Path
import sys
import json

root = Path(
    r"c:\Users\paxm\OneDrive - PBS SYSTEMS\Desktop\Office\Projects\OEM Accessory project\OEM_Accessories_v1"
)
sys.path.insert(0, str(root / "accy_v2"))

from model_lookup.search_engine import VehicleSearchEngine

print("=" * 80)
print("TESTING SEARCH ENGINE: Failing Cases (Should Now Pass)")
print("=" * 80)

# Load configs
config_path = root / "accy_v2/oems/hyundai/config/hyundai_config.json"
with open(config_path) as f:
    config = json.load(f)

csv_path = str(root / "accy_v2/model_lookup/db/db_vehicle_models.csv")
configs_dir = str(root / "accy_v2/model_lookup/configs")

engine = VehicleSearchEngine(
    csv_path=csv_path,
    configs_dir=configs_dir,
    oem_config=config,
    ignore_keyword_categories=config["model_lookup_rules"]["Hyundai"].get("ignore_keyword_categories", []),
)

test_cases = [
    # (make, year, keywords, description, should_pass)
    ("Hyundai", 2024, ["santa", "fe", "lux"], "Santa Fe Lux", True),
    ("Hyundai", 2024, ["santa", "fe", "hev"], "Santa Fe HEV", True),
    ("Hyundai", 2024, ["santa", "fe", "preferred", "hev"], "Santa Fe Pref HEV", True),
    ("Hyundai", 2024, ["tucson", "pref"], "Tucson Pref (was Pref*)", True),
    ("Hyundai", 2024, ["kona", "n-line"], "Kona N-Line", True),
    ("Genesis", 2024, ["g70", "2.0t", "advanced"], "G70 2.0T Advanced", True),
    ("Genesis", 2026, ["gv60", "performance"], "GV60 Performance", True),
]

passed = 0
failed = 0

for make, year, keywords, description, should_pass in test_cases:
    result = engine.search(make, year, keywords, exclude_ev=True)
    
    if should_pass:
        if result:
            print(f"✅ {description}: Found {result.match}")
            passed += 1
        else:
            print(f"❌ {description}: Expected PASS but got None")
            failed += 1
    else:
        if result:
            print(f"❌ {description}: Expected FAIL but found {result.match}")
            failed += 1
        else:
            print(f"✅ {description}: Correctly returned None")
            passed += 1

print(f"\n{'=' * 80}")
print(f"Results: {passed} passed, {failed} failed")
print(f"{'=' * 80}")

if failed == 0:
    print("✅ All search engine tests passed")
    sys.exit(0)
else:
    print(f"❌ {failed} search engine tests failed")
    sys.exit(1)
```

**Run this script:**
```bash
python test_search_engine.py
```

---

## Phase 3: End-to-End Testing (60 minutes)

### Test 3.1: Full Pipeline Run

**Purpose:** Run the complete Hyundai pipeline and check output  
**Time:** 30 minutes

**Steps:**

1. **Backup current output:**
   ```bash
   cd c:\Users\paxm\OneDrive - PBS SYSTEMS\Desktop\Office\Projects\OEM Accessory project\OEM_Accessories_v1\accy_v2
   
   # If previous output exists, backup it
   if [ -f "output/ready_to_upload/hyundai/hyundai_latest.xlsx" ]; then
       cp output/ready_to_upload/hyundai/hyundai_latest.xlsx output/ready_to_upload/hyundai/hyundai_backup_pre_fix.xlsx
   fi
   ```

2. **Run the pipeline:**
   ```bash
   python run_hyundai.py
   ```

3. **Monitor the run:**
   - Watch for any errors in console
   - Pipeline should complete without crashing
   - Watch the pipeline log for any new errors

4. **Expected runtime:** ~2-3 minutes

**Success criteria:**
- ✅ Pipeline completes without errors
- ✅ Output file is created in `output/ready_to_upload/hyundai/`
- ✅ Output file size is similar to previous run (±20%)

---

### Test 3.2: Check _Data_Issues Sheet

**Purpose:** Verify failures are significantly reduced  
**Time:** 10 minutes

**Script:**
```python
import pandas as pd
from pathlib import Path

root = Path(
    r"c:\Users\paxm\OneDrive - PBS SYSTEMS\Desktop\Office\Projects\OEM Accessory project\OEM_Accessories_v1"
)

# Find the latest output file
output_dir = root / "accy_v2/output/ready_to_upload/hyundai"
output_files = sorted(output_dir.glob("hyundai_*.xlsx"), key=lambda x: x.stat().st_mtime, reverse=True)

if not output_files:
    print("❌ No output files found in output/ready_to_upload/hyundai/")
    exit(1)

latest_file = output_files[0]
print(f"Analyzing: {latest_file.name}")

# Read Data Issues sheet
try:
    dq = pd.read_excel(latest_file, sheet_name="_Data_Issues")
    print(f"\nTotal issues found: {len(dq)}")
except Exception as e:
    print(f"❌ Error reading _Data_Issues sheet: {e}")
    exit(1)

# Count by issue type
print("\nIssues by type:")
if len(dq) > 0:
    issue_counts = dq["Issue"].value_counts()
    for issue_type, count in issue_counts.head(10).items():
        print(f"  {count}: {issue_type[:80]}...")
else:
    print("  (No issues found - all lookups successful!)")

# Check for specific failures that should now be fixed
failing_keywords = ["lux", "pref", "hev", "ice", "edt", "n-line", "trend", "sport"]

print("\nStatus of previously failing keyword patterns:")
for kw in failing_keywords:
    if len(dq) > 0:
        matching_issues = dq[dq["Issue"].str.contains(kw, case=False, na=False)]
        if len(matching_issues) > 0:
            print(f"  ⚠️  '{kw}': {len(matching_issues)} failures still present")
        else:
            print(f"  ✅ '{kw}': No failures found (FIXED!)")
    else:
        print(f"  ✅ '{kw}': No failures found (FIXED!)")

# Success metric
print("\n" + "=" * 80)
if len(dq) < 10:
    print(f"✅ SUCCESS: Only {len(dq)} failures remaining (target: <10)")
    print("   This represents a 95%+ improvement from the original 89 failures")
elif len(dq) < 50:
    print(f"⚠️  PARTIAL SUCCESS: {len(dq)} failures remaining (target: <10)")
    print("   This is a 40%+ improvement, but more work may be needed")
else:
    print(f"❌ INSUFFICIENT IMPROVEMENT: {len(dq)} failures (target: <10)")
    print("   The fixes may not have addressed the root cause")
print("=" * 80)
```

**Run this script:**
```bash
python check_output_quality.py
```

**Expected Output:**
```
Analyzing: hyundai_XXXXXXXX_YYYYMMDD_HHMMSS.xlsx

Total issues found: 5

Issues by type:
  2: No confident model number match for...
  1: All trim columns empty...
  1: ...other issue

Status of previously failing keyword patterns:
  ✅ 'lux': No failures found (FIXED!)
  ✅ 'pref': No failures found (FIXED!)
  ✅ 'hev': No failures found (FIXED!)
  ✅ 'ice': No failures found (FIXED!)
  ✅ 'edt': No failures found (FIXED!)
  ✅ 'n-line': No failures found (FIXED!)
  ✅ 'trend': No failures found (FIXED!)
  ✅ 'sport': No failures found (FIXED!)

================================================================================
✅ SUCCESS: Only 5 failures remaining (target: <10)
   This represents a 95%+ improvement from the original 89 failures
================================================================================
```

---

### Test 3.3: Regression Test - Mazda Pipeline

**Purpose:** Ensure Mazda pipeline still works (no regressions)  
**Time:** 20 minutes

**Steps:**

1. **Run Mazda pipeline:**
   ```bash
   cd c:\Users\paxm\OneDrive - PBS SYSTEMS\Desktop\Office\Projects\OEM Accessory project\OEM_Accessories_v1\accy_v2
   python run_mazda.py
   ```

2. **Check for errors:**
   - Pipeline should complete without crashes
   - Check console for any new error messages

3. **Verify output quality:**
   ```python
   import pandas as pd
   from pathlib import Path
   
   root = Path(r"c:\Users\paxm\OneDrive - PBS SYSTEMS\Desktop\Office\Projects\OEM Accessory project\OEM_Accessories_v1")
   
   # Find latest Mazda output
   output_dir = root / "accy_v2/output/ready_to_upload/mazda"
   output_files = sorted(output_dir.glob("mazda_*.xlsx"), key=lambda x: x.stat().st_mtime, reverse=True)
   
   if output_files:
       latest = output_files[0]
       dq = pd.read_excel(latest, sheet_name="_Data_Issues")
       print(f"Mazda issues: {len(dq)} (should be similar to previous run)")
       if len(dq) < 20:
           print("✅ Mazda output quality is good")
       else:
           print("⚠️  Mazda has more failures than expected")
   ```

**Expected Result:**
- ✅ Pipeline completes without errors
- ✅ Output file size is similar to previous run
- ✅ Issue count in _Data_Issues is similar to previous run
- ✅ No new failures introduced

---

### Test 3.4: Regression Test - Mitsubishi Pipeline

**Purpose:** Ensure Mitsubishi pipeline still works (no regressions)  
**Time:** 15 minutes

**Steps:**

1. **Run Mitsubishi pipeline:**
   ```bash
   python run_mitsubishi.py
   ```

2. **Verify output quality:**
   ```python
   import pandas as pd
   from pathlib import Path
   
   root = Path(r"c:\Users\paxm\OneDrive - PBS SYSTEMS\Desktop\Office\Projects\OEM Accessory project\OEM_Accessories_v1")
   
   # Find latest Mitsubishi output
   output_dir = root / "accy_v2/output/ready_to_upload/mitsubishi"
   output_files = sorted(output_dir.glob("mitsubishi_*.xlsx"), key=lambda x: x.stat().st_mtime, reverse=True)
   
   if output_files:
       latest = output_files[0]
       dq = pd.read_excel(latest, sheet_name="_Data_Issues")
       print(f"Mitsubishi issues: {len(dq)} (should be similar to previous run)")
   ```

---

### Test 3.5: Manual Excel Spot-Check

**Purpose:** Visually verify output content looks correct  
**Time:** 10 minutes

**Steps:**

1. **Open latest Hyundai output file**
   ```bash
   cd c:\Users\paxm\OneDrive - PBS SYSTEMS\Desktop\Office\Projects\OEM Accessory project\OEM_Accessories_v1\accy_v2\output\ready_to_upload\hyundai
   # Open the latest .xlsx file with Excel
   ```

2. **Check each sheet:**

   | Sheet | Check |
   |-------|-------|
   | elantra_EN | ✅ Contains rows for N, N-Line, Ult trims |
   | santa_fe_EN | ✅ Contains rows for Luxury, Ultimate, Calligraphy trims |
   | santa_fe_EN | ✅ Contains hybrid entries (HEV) |
   | tucson_EN | ✅ Contains N-Line, Trend, Pref entries |
   | kona_EN | ✅ Contains N-Line, Sport, Trend entries |
   | _Data_Issues | ✅ Contains < 10 failures (down from 89) |
   | _Report | ✅ Shows model profiles with correct row counts |

3. **Random row verification:**
   - Pick 5 random rows from elantra_EN
   - Verify each has a Model Number assigned
   - Verify Year column shows 2024, 2025, or 2026
   - Verify Trim column matches description

---

## Summary: Testing Checklist

### Pre-Test Checklist
- [ ] Changes have been committed to git
- [ ] JSON files are valid (Test 1.1)
- [ ] Config entries are present (Tests 1.2, 1.3)

### Unit Tests (Phase 1)
- [ ] JSON syntax validation passed
- [ ] Translator entries present
- [ ] Classification entries present

### Integration Tests (Phase 2)
- [ ] Translator functionality test passed
- [ ] Classification functionality test passed
- [ ] Search engine test passed (specific failing cases now work)

### End-to-End Tests (Phase 3)
- [ ] Hyundai pipeline ran successfully
- [ ] _Data_Issues count reduced to < 10 (95%+ improvement)
- [ ] All failing keywords fixed:
  - [ ] "lux" failures resolved
  - [ ] "pref/pref*" failures resolved
  - [ ] "hev" failures resolved
  - [ ] "n-line" failures resolved
  - [ ] "trend/trend*" failures resolved
  - [ ] "sport" failures resolved
  - [ ] "ice" failures resolved (if present)
  - [ ] "edt" failures resolved (if present)
- [ ] Mazda pipeline works (no regressions)
- [ ] Mitsubishi pipeline works (no regressions)
- [ ] Manual Excel spot-check passed

---

## If Tests Fail

### Issue: JSON Syntax Error

**Solution:**
1. Check for missing commas, quotes, or brackets
2. Use an online JSON validator: https://jsonlint.com/
3. Verify all trailing commas are removed from last entry in object/array

### Issue: Translator/Classification Entries Missing

**Solution:**
1. Verify you saved the file (not just viewing in editor)
2. Check that entries are in the correct section
3. Verify spelling and quotes match exactly

### Issue: Search Engine Still Returns None

**Solution:**
1. Check if the database actually has records for this vehicle
2. Verify the translator is being applied (add logging)
3. Check if score is meeting adaptive threshold

### Issue: Hyundai Pipeline Crashes

**Solution:**
1. Check error message in console
2. Review recent config file changes for syntax errors
3. Verify CSV database is accessible
4. Check logs in `output/pipeline_logs/`

---

## Success Criteria Summary

| Metric | Target | How to Verify |
|--------|--------|---------------|
| JSON valid | 4/4 files | Test 1.1 |
| Translator entries | 100% | Test 1.2 |
| Classification entries | 100% | Test 1.3 |
| Translator functionality | 100% tests pass | Test 2.1 |
| Classification functionality | 100% tests pass | Test 2.2 |
| Search engine specific cases | All pass | Test 2.3 |
| Hyundai pipeline runs | No crashes | Test 3.1 |
| Failures reduced | <10 (from 89) | Test 3.2 |
| Mazda no regression | Similar to before | Test 3.3 |
| Mitsubishi no regression | Similar to before | Test 3.4 |
| Excel spot-check | Rows visible for all trims | Test 3.5 |

**All tests must pass** before considering the fix complete.
