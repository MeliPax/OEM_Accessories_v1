# Bug Fix: Duplicate Group Resolution Configuration Path

**Commit**: `a284be6`  
**Date**: 2026-07-20  
**Severity**: High (blocked all multi-candidate Hyundai searches)

---

## The Bug

When searching for `Hyundai 2024 HEV with keywords ['elantra', 'hev']`, the `VehicleSearchEngine` returned `None` instead of a `SearchResult`, even though:

1. ✅ `search_models_by_description()` successfully returned 4 candidates
2. ✅ Score was 20 (passes adaptive gate of 14)
3. ✅ All 4 candidates normalized to the same vehicle
4. ✅ `allow_duplicate_model_numbers` was set to `True` in Hyundai's config

### Root Cause

In [search_engine.py:178](accy_v2/model_lookup/search_engine.py#L178), the code checked:

```python
if candidate_count > 1 and self.oem_config.get("allow_duplicate_model_numbers", False):
```

But `allow_duplicate_model_numbers` is nested under `model_lookup_rules.Hyundai`, not at the top level:

```
oem_config = {
  "non_null_threshold": 0.5,
  "use_model_lookup": true,
  ...
  "model_lookup_rules": {
    "Hyundai": {
      "allow_duplicate_model_numbers": True,  ← HERE, nested!
      ...
    }
  }
}
```

The `.get("allow_duplicate_model_numbers", False)` always returned `False`, so the duplicate resolution code (lines 180-201) never executed.

### Impact

- **Hyundai Elantra Hybrid**: Searched for `['elantra', 'hev']` returned `None` instead of `SearchResult`
- **All other multi-candidate scenarios**: Any search that returns >1 candidate never collapses them
- **Mitsubishi**: Same issue (uses same `VehicleSearchEngine`)

### Error Message User Saw

```
No confident model number match for Hyundai 2024 HEV with keywords: ['elantra', 'hev']
```

This happened because with `candidate_count=4`, confidence was computed as `0.0`, and since the duplicate group resolution code never ran, `None` was returned.

---

## The Fix

Updated [search_engine.py:178-179](accy_v2/model_lookup/search_engine.py#L178-L179) to navigate the correct nested path:

**Before:**
```python
if candidate_count > 1 and self.oem_config.get("allow_duplicate_model_numbers", False):
```

**After:**
```python
oem_allow_duplicates = self.oem_config.get("model_lookup_rules", {}).get(make, {}).get("allow_duplicate_model_numbers", False)
if candidate_count > 1 and oem_allow_duplicates:
```

This retrieves the OEM-specific setting from `model_lookup_rules.{make}`.

---

## Verification

After fix, searching for `['elantra', 'hev']`:

```
✓ SearchResult returned!
  model_number: ELHS4T1BLUHE
  match: Elantra hybrid Luxury
  model_numbers: ['ELHS4T1BLUHE', 'ELHS4T1BLUHM', 'EL74DF16I3AA', 'EL74DF16I3AC']
  confidence: 0.31
  score: 20
  candidate_count: 4
  is_duplicate_group: True
```

**Debug log output** (before fix would NOT show this):
```
[DEBUG] Resolved 4 candidates to single vehicle with multiple model numbers 
        (ignoring ['INTERIOR', 'EXTERIOR_COLOR']): 
        ['ELHS4T1BLUHE', 'ELHS4T1BLUHM', 'EL74DF16I3AA', 'EL74DF16I3AC']
```

---

## Why This Happened

The `allow_duplicate_model_numbers` configuration was added to the nested `model_lookup_rules` structure during pipeline development, but the `VehicleSearchEngine.search()` method wasn't updated to look in the nested location. The code was written for a flat top-level structure, but the actual config is nested by OEM.

---

## Side Effects

✅ **None — this is a pure bug fix**

- Both `Hyundai` and `Mitsubishi` pipelines now correctly use their own `allow_duplicate_model_numbers` settings
- Scoring and confidence are now correct
- All existing tests pass

---

## Related Commits

- `e70d10d` — Initial config-driven EV exclusion implementation (this bug was introduced as part of that feature, exposed once VehicleSearchEngine started receiving multi-candidate results)
- `a284be6` — This fix

---

## Testing

Run to verify:
```bash
python test_config_driven_ev_final.py
```

All 5 tests should pass, including Test 1 (Elantra Hybrid) which was previously failing silently.
