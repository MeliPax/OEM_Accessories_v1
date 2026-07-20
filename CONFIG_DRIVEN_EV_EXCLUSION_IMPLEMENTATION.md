# Config-Driven EV/Hybrid Exclusion — Implementation Summary

**Commit**: `e70d10d`  
**Date**: 2026-07-14  
**Status**: ✅ Complete & Tested

---

## What Was Fixed

The EV/hybrid exclusion logic in `search_models_by_description()` now:

1. **Reads from OEM config** instead of hardcoded constant `["EV", "PHEV"]`
2. **Translates fuel keywords** through the same translator used for search keywords (ensures vocab consistency)
3. **Handles multiple candidates gracefully** by not over-applying trim discriminators when a fuel type is explicitly requested
4. **Maintains backward compatibility** — callers not passing `oem_config` fall back to the hardcoded list unchanged

---

## Critical Bug Fixed

**The original reverted implementation had a silent failure:**

When `hyundai_translator.json` maps `hev`→`hybrid`, the config still listed `"HEV"` in `fuel_type_keywords`. The old code compared these untranslated config strings directly against already-translated keywords, causing:
- The "did user request fuel type?" check to always fail (never finding "HEV" in `['elantra', 'hybrid']`)
- The "strip fuel keywords from DB text" filter to strip literal `\bHEV\b` and `\bPHEV\b`, which don't match actual DB text like `"Elantra hybrid Luxury"`
- Result: **exclusion silently did nothing in both directions** — both test cases would have passed by accident

**This implementation:**
- Translates `fuel_type_keywords` through the translator BEFORE any comparison
- Both the "user requested?" check and the "strip text" filter now operate in the **same vocabulary** as the DB and search keywords
- Result: **exclusion actually works as intended**

---

## Implementation Details

### File Changes

**`accy_v2/model_lookup/models/manufacture_module.py`**
- Added `oem_config: dict = None` parameter to `search_models_by_description()`
- Replaced hardcoded fuel exclusion logic with config-driven version that translates keywords
- Updated `_get_trim_discriminator_keywords()` to exclude `POWERTRAIN_TYPE` tokens (fuel types handled separately)
- Added fuel-type-aware trim discriminator skipping (when user requests fuel type, skip trim filtering)

**`accy_v2/model_lookup/search_engine.py`**
- Added `oem_config=self.oem_config` to the call to `search_models_by_description()` (engine already holds the config)

### Key Logic

```python
# Translate fuel keywords through the same translator as search keywords
raw_fuel_keywords = oem_config.get("model_lookup_rules", {}).get(make, {}).get("fuel_type_keywords", EV_KEYWORDS)
fuel_type_keywords = translate_keywords([kw.lower() for kw in raw_fuel_keywords], translator) if translator else [kw.lower() for kw in raw_fuel_keywords]

# Check if user explicitly requested any fuel type (after translation)
search_kw_lower = [k.lower() for k in keywords]  # Already translated at this point
if exclude_ev and not any(kw in search_kw_lower for kw in fuel_type_keywords):
    # No fuel type keyword in search — exclude all configured fuel types
    for fuel_keyword in fuel_type_keywords:
        pattern = build_word_boundary_pattern(fuel_keyword)
        df_filtered = df_filtered[
            ~df_filtered["Description"].str.contains(pattern, case=False, na=False, regex=True)
        ]
```

---

## Verification Results

All test cases pass:

| Test | Query | Expected | Actual | Status |
|------|-------|----------|--------|--------|
| 1. Elantra Hybrid | `['elantra', 'hev']` | 4 Hybrid rows returned | ✅ 4 rows (ELHS4T1BLUHE, ELHS4T1BLUHM, EL74DF16I3AA, EL74DF16I3AC) | PASS |
| 2. Elantra Lux | `['elantra', 'luxury']` | 4 Non-Hybrid rows returned | ✅ 4 rows (no "hybrid" in descriptions) | PASS |
| 3. Backward Compat | `['elantra', 'phev']` (no oem_config) | Empty (no Hyundai PHEV) | ✅ 0 rows | PASS |
| 4. Mitsubishi Outlander | `['outlander', 'gt']` | 1 Non-PHEV row | ✅ CO45-X (no "PHEV") | PASS |
| 5. Mitsubishi Outlander PHEV | `['outlander', 'phev', 'gt']` | 1 PHEV row | ✅ COEV-X (has "PHEV") | PASS |

**Run verification yourself:**
```bash
python test_config_driven_ev_final.py
```

---

## Side Effects & Compatibility

### Mitsubishi Pipeline (Bonus Fix)
The same `VehicleSearchEngine` wrapper is used by Mitsubishi's pipeline. It now benefits from config-driven exclusion:
- Before: used hardcoded `["EV", "PHEV"]` only
- After: uses Mitsubishi's own `fuel_type_keywords` (from `mitsubishi_config.json`)
- Translation: `hev`/`mhev`→`hybrid`, `phev` stays `phev`
- Result: Mitsubishi's real DB text (`"Outlander PHEV GT awc"`) now correctly matches the exclusion logic

### Backward Compatibility
- Any direct caller of `search_models_by_description()` not passing `oem_config` gets the old behavior (hardcoded `EV_KEYWORDS` fallback)
- No existing tests or pipelines break

---

## Known Limitations & Future Work

### Genesis "Electrified" Models
- Genesis's translator maps `electrified`→`electric`, but no Genesis EV rows currently exist in the DB
- Once Genesis EV models are ingested, verify the actual ingested text (may be "Electrified" literal, or "Electric", or something else)
- If it doesn't match the translated keyword, re-verify the translator and fuel_type_keywords configuration

### Classification JSON Standardization (Deferred)
This implementation focuses on the EV exclusion logic working correctly. Reclassifying fuel-type tokens from `ENGINE_TYPE` to `POWERTRAIN_TYPE` in Mazda/Kia/Honda/etc. classification JSONs is a separate mechanical task left for a future PR.

---

## How to Use

**From the Hyundai pipeline** (automatic):
- Pipeline calls `VehicleSearchEngine` which now passes `oem_config`
- EV/hybrid exclusion reads from `accy_v2/oems/hyundai/config/hyundai_config.json`
- No code changes needed; pipeline already works

**Direct usage:**
```python
from model_lookup.models.manufacture_module import search_models_by_description
import json

with open("accy_v2/oems/hyundai/config/hyundai_config.json") as f:
    config = json.load(f)

results = search_models_by_description(
    make="Hyundai",
    year=2024,
    keywords=["elantra", "hev"],  # Will search for Elantra Hybrid (hev translated to "hybrid")
    csv_path="accy_v2/model_lookup/db/db_vehicle_models.csv",
    exclude_ev=True,
    configs_dir="accy_v2/model_lookup/configs",
    oem_config=config  # ← NEW: config-driven fuel keyword list
)
```

---

## Testing Artifacts

- `test_config_driven_ev_final.py` — Verification test suite (all 5 tests pass)
- Debug scripts in scratchpad (used during development, can be deleted)
- `accy_v2/model_lookup/IDEAS_EV_EXCLUSION_CONFIG_DRIVEN.md` — Original proposal document (for reference)

---

## Related Files & Context

- Prior reverted attempt: commit `5ebe2b2` (had the silent failure bug)
- Revert reason: commit `8781e1a` (asked for review before re-implementation)
- Duplicate-model feature (related discriminator logic): commit `2159045`
- Database standardization (exposed fuel-type filtering gap): commit `33e69c2`
