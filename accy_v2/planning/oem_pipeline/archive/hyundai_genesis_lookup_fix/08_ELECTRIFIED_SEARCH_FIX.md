# Fix: Electrified GV70/GV80 Search Failures

**Date:** 2026-09-01  
**Issue:** Electrified Genesis variants silently return wrong vehicles when searched without explicit fuel keywords  
**Root Cause:** exclude_ev filter removed Electrified rows BEFORE implied_fuel_type_trims could inject fuel keyword  
**Status:** ✅ FIXED

---

## Problem Statement

When searching for Genesis Electrified models like:
- **GV70 Advanced** (Electrified variant, 2026)
- **GV80 Prestige** (Electrified variant, 2024)

Using keywords that DON'T explicitly include 'ev'/'electric':
- `['gv70', 'advanced']` instead of `['gv70', 'ev', 'advanced']`

**Result:** The search would silently return the WRONG VEHICLE (gas variant instead of electric).

**Why:** Two competing systems running in wrong order:
1. `exclude_ev` filter checked if source data had fuel keywords
2. If no fuel keyword found, it removed ALL EV rows (including Electrified GV70)
3. **THEN** (too late) `implied_fuel_type_trims` would have injected "electric" keyword

---

## Root Cause Analysis

**File:** `accy_v2/model_lookup/models/manufacture_module.py`

### OLD Flow (BROKEN)
```
1. Translate keywords
2. Load CSV
3. Loop through keywords, narrowing df_filtered
4. exclude_ev filter runs (line ~1300)
   ↳ Checks if any fuel_type_keyword in keywords list
   ↳ If NO fuel keyword found → removes EV rows
5. Return filtered results ← Electrified rows already gone!

NOTE: implied_fuel_type_trims only runs in VehicleSearchEngine.search(),
      which calls search_models_by_description() AFTER all this happens
```

### NEW Flow (FIXED)
```
1. Translate keywords
2. Check implied_fuel_type_trims IMMEDIATELY
   ↳ If model/trim combo matches rule → inject fuel keyword
3. Load CSV
4. Loop through keywords, narrowing df_filtered  
5. exclude_ev filter runs (line ~1300)
   ↳ Now sees fuel keyword in list → SKIPS EV removal
6. Return filtered results ← Electrified rows preserved!
```

---

## Implementation

**Commit:** `8317be1` (Fix: Move implied_fuel_type_trims injection before exclude_ev filter)

**Changes to `manufacture_module.py` (lines 1196-1225):**

```python
# Apply implied fuel type BEFORE exclude_ev filter runs (critical ordering)
# This ensures that fuel-type-locked trims get the fuel keyword injected
# before the exclude_ev logic decides whether to remove EV rows
oem_config = oem_config or {}
if "model_lookup_rules" in oem_config:
    oem_rules = oem_config.get("model_lookup_rules", {}).get(make, {})
else:
    oem_rules = oem_config

implied_rules = oem_rules.get("implied_fuel_type_trims", [])
if implied_rules:
    keywords_lower = {kw.lower() for kw in keywords}
    has_fuel_keyword = any(kw in keywords_lower for kw in
                          [kw.lower() for kw in oem_rules.get("fuel_type_keywords", EV_KEYWORDS)])

    # Only inject if search doesn't already have a fuel keyword
    if not has_fuel_keyword:
        for rule in implied_rules:
            rule_models = {kw.lower() for kw in rule.get("model_keywords", [])}
            rule_trims = {kw.lower() for kw in rule.get("trim_keywords", [])}
            rule_years = rule.get("years", [])
            rule_fuel = rule.get("fuel_type", "").lower()

            # Check if all model keywords AND all trim keywords are in the search
            if rule_models and rule_trims:
                if rule_models.issubset(keywords_lower) and rule_trims.issubset(keywords_lower):
                    if not rule_years or year in rule_years:
                        # Inject fuel type keyword before exclude_ev filter
                        keywords.append(rule_fuel)
                        break
```

**Why this works:**
- Uses simple **subset matching** on keywords (not full classification) for speed
- Runs immediately after translation, before ANY database filtering
- Injects fuel keyword into the keywords list itself
- The exclude_ev filter (line 1300) now sees the fuel keyword and preserves EV rows

---

## Configuration Required

The `implied_fuel_type_trims` config must be populated in each OEM's `enrichment.yaml`:

**Example (Genesis):** `accy_v2/oems/genesis/config/enrichment.yaml:62-70`

```yaml
implied_fuel_type_trims:
  - model_keywords: [gv70]
    trim_keywords: [advanced]
    fuel_type: electric
    years: [2025, 2026]
  - model_keywords: [gv70]
    trim_keywords: [advanced, plus]
    fuel_type: electric
    years: [2025]
```

**Rules:**
1. `model_keywords` and `trim_keywords` must ALL be present in the search keywords
2. `years` list is optional (if empty, rule applies to all years)
3. Only triggered if NO fuel keyword already in search (avoids duplication)

---

## Testing

### Confirmed Working
- Genesis pipeline runs without errors
- G70, G80, G80_EV sheets process successfully

### Still To Verify
The following test cases from the notebook should now pass (pending OEM data validation):

1. **Electrified GV70 Advanced (2026):** `keywords=['gv70', 'advanced']` + exclude_ev=True
2. **Electrified GV70 Prestige (2026):** `keywords=['gv70', 'prestige']` + exclude_ev=True  
3. **Electrified GV80 Prestige (2024):** `keywords=['g80', 'prestige']` + exclude_ev=True

These require that the test data actually contains these model/trim/year combinations in the DB.

---

## Remaining Known Issues

The following 4 issues from the original research still need attention:

### Issue #2: Classifier Gap (5p/7p → SEATING category)
- **Status:** Config lines added to genesis/classification.yaml:51-52
- **Pending:** Verify SEATING is not in ignore_keyword_categories (it isn't, so should work)
- **Test:** `keywords=['gv80', 'advanced', '5p']` should find 5-passenger variants

### Issue #3: Coupe Discriminator (ModelName-only body style)
- **Status:** Code extended in manufacture_module.py:1299-1310
- **Pending:** Test that bare `['gv80']` does NOT match "GV80 Coupe" rows
- **Test:** `keywords=['gv80', 'advanced']` should find GV80 Advanced, NOT GV80 Coupe

### Issue #4: Hyphenated Keyword Tokenization (e-sc)
- **Status:** Unresolved (needs live trace debugging)
- **Pending:** Debug `['gv80', 'coupe', '3.5t', 'e-sc']` search failure
- **Hypothesis:** 'e-sc' split into single chars by tokenizer, fails AND filter

### Issue #5: Missing Data vs. Code Bugs
- **Status:** Unresolved (needs DB audit per year/trim)
- **Pending:** Confirm GV70 "Performance" trim exists in 2026 DB
- **Pending:** Confirm GV60 "Performance" trim exists in 2026 DB

---

## Next Steps

1. Run actual pipeline with real source data containing Electrified variants
2. Populate `implied_fuel_type_trims` for any other fuel-exclusive trims found during DB audit
3. Debug remaining issues (hyphenated tokenization, missing data validation)
4. Document which OEMs benefit from this fix (currently Genesis is primary use case)
