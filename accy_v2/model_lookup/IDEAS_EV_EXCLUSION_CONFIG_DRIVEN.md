# Proposal: Config-Driven EV Exclusion + POWERTRAIN_TYPE Standardization

**Status**: Proposed (Reverted for review before implementation)  
**Date Created**: 2026-07-14  
**Context**: User identified that EV exclusion is currently hardcoded instead of being driven by OEM configs. This proposal makes it config-driven and standardizes fuel-type token classification.

---

## Problem Statement

### Issue 1: Hardcoded EV Exclusion
- Current: `EV_KEYWORDS = ["EV", "PHEV"]` in `manufacture_module.py:35` (hardcoded constant)
- Problem: Ignores each OEM's own `fuel_type_keywords` already defined in their OEM config files
- Example: Hyundai/Genesis/Mitsubishi already define `FCEV`, Hyundai/Genesis also need `HEV`, but these are not excluded because they're not in the hardcoded list
- Impact: Non-EV searches (e.g., "Elantra Luxury" without HEV keyword) incorrectly return Hybrid variants

### Issue 2: Inconsistent Category Usage (POWERTRAIN_TYPE vs ENGINE_TYPE)
- Current state:
  - Only **Hyundai's** classification config uses `POWERTRAIN_TYPE` for fuel-type tokens
  - All other OEMs use lower-weighted `ENGINE_TYPE` (weight 8) instead of `POWERTRAIN_TYPE` (weight 10)
- Problem: 
  - POWERTRAIN_TYPE tokens are marked as critical discriminators and have higher weight
  - Fuel-type tokens on other OEMs don't benefit from this discriminator filtering
  - Inconsistent scoring across OEMs for the same token type
- Impact: Fuel-type filtering works correctly only for Hyundai, not for other OEMs like Mazda or Mitsubishi

---

## Root Cause Analysis

### Why It Matters
1. **Accessory Compatibility**: Hyundai internal note says fuel type is "critical for accessory compatibility"
2. **Discriminator Filtering**: The `_get_trim_discriminator_keywords()` function in `manufacture_module.py` treats POWERTRAIN_TYPE tokens as trim discriminators, excluding candidates with unwanted fuel-type variants
3. **Scoring Weight**: POWERTRAIN_TYPE gets weight 10 (higher importance) vs ENGINE_TYPE's weight 8

### Current State Survey

**Active OEM Configs** (already define `fuel_type_keywords`):
- **Hyundai**: `["EV", "PHEV", "HEV", "FCEV"]`
- **Genesis** (shares Hyundai config): `["EV", "PHEV", "HEV", "FCEV"]`
- **Mazda**: `["EV", "PHEV", "HEV"]`
- **Mitsubishi**: `["EV", "PHEV", "HEV", "FCEV"]`

**Fuel-Type Tokens Needing Migration** (`ENGINE_TYPE` → `POWERTRAIN_TYPE`):

| Classification File | Tokens to Migrate | Notes |
|---|---|---|
| `genesis_classification.json` | `electrified` | Genesis's EV branding (e.g., "Electrified GV70"). Keep `3.3t`, `3.5t`, `3.8`, `5.0`, `2.0t`, `2.5t`, `e-sc` as ENGINE_TYPE (real engine specs). |
| `honda_classification.json` | `hybrid` | |
| `mazda_classification.json` | `bev`, `ev`, `hybrid`, `mhev`, `phev` | |
| `mitsubishi_classification.json` | `phev` | |
| `kia_classification.json` | `ev`, `hev`, `hybrid`, `phev` | (Future readiness; not yet active pipeline) |
| `subaru_classification.json` | `hybrid` | (Future readiness; not yet active pipeline) |
| `toyota_classification.json` | `hybrid`, `phev` | (Future readiness; not yet active pipeline) |
| `volvo_classification.json` | `hybrid`, `phev` | (Future readiness; not yet active pipeline) |
| `hyundai_classification.json` | *(none)* | Already correct |
| `volkswagen_classification.json` | *(none)* | No fuel-type tokens present |

**Bonus Issue**: Genesis's `fuel_type_keywords` missing `ELECTRIFIED`
- Genesis real EVs are branded "Electrified" (e.g., "Electrified G80")
- This term is missing from Genesis's config, though `electrified` is correctly classified in the config file
- Should add for consistency and future-proofing before Genesis EV models hit the DB

---

## Proposed Solution

### Phase 1: Config-Driven EV Exclusion

**File**: `models/manufacture_module.py`  
**Function**: `search_models_by_description()` (~line 967)

**Changes**:
1. Add parameter: `oem_config: dict = None`
2. Replace hardcoded EV exclusion logic (lines 1026-1031) with:

```python
# Read fuel_type_keywords from OEM config, fall back to hardcoded list
oem_rules = (oem_config or {}).get("model_lookup_rules", {}).get(make, {})
fuel_type_keywords = oem_rules.get("fuel_type_keywords", EV_KEYWORDS)

if exclude_ev and not any(kw.upper() in [k.upper() for k in keywords] for kw in fuel_type_keywords):
    for fuel_keyword in fuel_type_keywords:
        pattern = build_word_boundary_pattern(fuel_keyword)
        df_filtered = df_filtered[
            ~df_filtered["Description"].str.contains(pattern, case=False, na=False, regex=True)
        ]
```

**Rationale**:
- `EV_KEYWORDS` stays as fallback for backward compatibility
- If `oem_config` is passed, reads OEM-specific `fuel_type_keywords` from config
- Excludes ALL fuel types defined by the OEM (HEV, PHEV, EV, FCEV, etc.)
- Only excludes if fuel keyword NOT explicitly in search keywords

---

**File**: `search_engine.py`  
**Function**: `VehicleSearchEngine.search()` (~line 129)

**Changes**:
Add `oem_config=self.oem_config` to the call:

```python
results = search_models_by_description(
    make=make,
    year=year,
    keywords=filtered_keywords,
    csv_path=self.csv_path,
    exclude_ev=exclude_ev,
    configs_dir=self.configs_dir,
    oem_config=self.oem_config,  # ← NEW
)
```

**Rationale**: The search engine already holds `self.oem_config` from `__init__`, just need to pass it through.

---

**File**: `accy_v2/oems/hyundai/config/hyundai_config.json`  
**Section**: `model_lookup_rules.Genesis.fuel_type_keywords` (line ~119)

**Change**: Add `"ELECTRIFIED"` to the list:

```json
"fuel_type_keywords": ["EV", "PHEV", "HEV", "FCEV", "ELECTRIFIED"]
```

**Rationale**: Genesis's "Electrified" models need to be excluded when searching for non-EV Genesis vehicles. Future-proofing before Genesis EV models enter the DB.

---

### Phase 2: Standardize POWERTRAIN_TYPE Category

**Why**: All fuel-type tokens should use the same category for consistent scoring and discriminator filtering.

**Changes**: For each file in the survey table above, change token classification from `"ENGINE_TYPE"` to `"POWERTRAIN_TYPE"`:

**Example** (from `genesis_classification.json`):
```json
// Before
"electrified": "ENGINE_TYPE"

// After
"electrified": "POWERTRAIN_TYPE"
```

**Files and tokens**:

1. **genesis_classification.json** (line ~30):
   - `"electrified": "POWERTRAIN_TYPE"`

2. **honda_classification.json**:
   - `"hybrid": "POWERTRAIN_TYPE"`

3. **mazda_classification.json**:
   - `"bev": "POWERTRAIN_TYPE"`
   - `"ev": "POWERTRAIN_TYPE"`
   - `"hybrid": "POWERTRAIN_TYPE"`
   - `"mhev": "POWERTRAIN_TYPE"`
   - `"phev": "POWERTRAIN_TYPE"`

4. **mitsubishi_classification.json**:
   - `"phev": "POWERTRAIN_TYPE"`

5. **kia_classification.json** (future):
   - `"ev": "POWERTRAIN_TYPE"`
   - `"hev": "POWERTRAIN_TYPE"`
   - `"hybrid": "POWERTRAIN_TYPE"`
   - `"phev": "POWERTRAIN_TYPE"`

6. **subaru_classification.json** (future):
   - `"hybrid": "POWERTRAIN_TYPE"`

7. **toyota_classification.json** (future):
   - `"hybrid": "POWERTRAIN_TYPE"`
   - `"phev": "POWERTRAIN_TYPE"`

8. **volvo_classification.json** (future):
   - `"hybrid": "POWERTRAIN_TYPE"`
   - `"phev": "POWERTRAIN_TYPE"`

**Rationale**:
- Unified category usage across OEMs
- Enables discriminator filtering for all OEMs (not just Hyundai)
- Consistent scoring weight (10 vs 8)
- No code changes needed—`_get_trim_discriminator_keywords()` and `compute_score()` already support POWERTRAIN_TYPE

---

## Verification Plan

### Test Scenarios

1. **Hyundai Elantra Luxury (no HEV keyword)** → Should exclude HEV variants
   - Query: `make="Hyundai", year=2024, keywords=["elantra", "luxury"]`
   - With `oem_config=hyundai_config`
   - Expected: 4 results (2 model codes × 2 interior variants, all non-Hybrid)
   - Current: May include Hybrid variants (bug we're fixing)

2. **Hyundai Elantra Hybrid (explicit HEV keyword)** → Should include HEV variants
   - Query: `make="Hyundai", year=2024, keywords=["elantra", "luxury", "hev"]`
   - Expected: 2-4 results including HEV variants
   - Current: Works (HEV keyword in search, so not excluded)

3. **Mazda CX-90 (no hybrid keyword, NEW FIX)** → Should exclude Hybrid/PHEV
   - Query: `make="Mazda", year=2026, keywords=["cx-90"]`
   - With `oem_config=mazda_config`
   - Expected: 1+ results (non-Hybrid CX-90 only)
   - Current: Likely includes Hybrid/PHEV (because Mazda's hybrid wasn't in hardcoded ["EV","PHEV"])

4. **Mitsubishi Outlander GT (no PHEV keyword)** → Should exclude PHEV
   - Query: `make="Mitsubishi", year=2026, keywords=["outlander", "gt"]`
   - With `oem_config=mitsubishi_config`
   - Expected: 1 result (non-PHEV Outlander GT)
   - Current: May include PHEV variants

5. **Backward Compatibility (no oem_config)** → Should still work
   - Query: `keywords=["outlander", "phev", "gt"]` WITHOUT passing `oem_config`
   - Expected: Falls back to hardcoded ["EV", "PHEV"]
   - Should return Outlander PHEV GT (explicit PHEV keyword)

### Test Code Provided
See `notebook_ev_exclusion_test.py` for runnable test suite.

---

## Trade-offs & Considerations

### Pro
- ✅ Eliminates hardcoded constant; OEMs own their fuel-type definitions
- ✅ Fixes bugs for Mazda, Mitsubishi, Honda, Subaru, Toyota, Volvo (inconsistent fuel-type exclusion)
- ✅ Consistent scoring across OEMs
- ✅ Enables discriminator filtering for all OEMs (not just Hyundai)
- ✅ Backward compatible (hardcoded fallback)
- ✅ No code changes to scorer or discriminator logic (already supports POWERTRAIN_TYPE)

### Con
- ⚠️ Requires updates to 8 classification JSON files (low risk, mechanical changes)
- ⚠️ Requires updates to 1 OEM config (Hyundai: add "ELECTRIFIED")
- ⚠️ Requires changes to 2 Python files (`manufacture_module.py`, `search_engine.py`)

---

## Implementation Checklist

- [ ] Phase 1 Code: Update `manufacture_module.py` with `oem_config` parameter
- [ ] Phase 1 Code: Update `search_engine.py` to pass `oem_config`
- [ ] Phase 1 Config: Add "ELECTRIFIED" to Genesis `fuel_type_keywords` in `hyundai_config.json`
- [ ] Phase 2 Config: Update all 8 classification JSONs (change fuel-type tokens to POWERTRAIN_TYPE)
- [ ] Test: Verify JSON validity on all modified files
- [ ] Test: Run regression suite (Elantra Lux, Elantra Hybrid from prior fix)
- [ ] Test: Run new test scenarios (Mazda CX-90, Mitsubishi Outlander, backward compat)
- [ ] Commit: Create single commit or separate Phase 1 + Phase 2 commits (TBD)

---

## Open Questions for Review

1. **Commit Strategy**: Should Phase 1 (code) and Phase 2 (config standardization) be one commit or separate?
   - Single commit: Atomicity, easier to revert if needed
   - Separate: Clearer history, can roll back phase independently

2. **Future OEMs**: Should we immediately update classification files for inactive OEMs (Kia, Subaru, Toyota, Volvo) for consistency, or only update active pipelines?
   - Proposed: Update all now (one-time mechanical task, avoids repeat work)

3. **Documentation**: Should we document this in `ARCHITECTURE.md` or a separate `VOCABULARY_FILTERING.md`?
   - Proposed: Yes, update relevant docs once implementation is approved

---

## Related Issues & Commits

- **Prior Fix**: Commit `2159045` (Duplicate-model-number feature) introduced POWERTRAIN_TYPE discriminator filtering for Hyundai
- **Prior Fix**: Commit `fee0e6d` (Reclassify 'black' token to enable Venue Black/Denim duplicate detection)
- **Root Cause**: Commit `33e69c2` (Database standardization) introduced description cleaning that exposed fuel-type filtering gaps

---

## References

- `ARCHITECTURE.md` (stale, but referenced)
- `semantic/scorer.py` (CATEGORY_WEIGHTS definitions)
- `accy_v2/oems/*/config/*_config.json` (OEM configurations)
- `configs/*_classification.json` (Token-to-category mappings)
- `README_VOCABULARY_FILTERING.md` (references desired Mitsubishi PHEV exclusion behavior)
