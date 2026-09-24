# System Constants Centralization — Implementation Notes

**Purpose:** Quick reference for implementing the system constants centralization project  
**Created:** 2026-09-24  
**Status:** Ready for Phase 1

---

## Quick Summary

**Goal:** Move hardcoded min/max values from scattered OEM config files into a single core-level `system_constants.yaml`, referenced via `${SYSTEM_CONSTANTS.*}` placeholders.

**Why:** 
- Currently 2020, 2100, 1000000, 100 are repeated in 5+ files (Hyundai, Genesis, Mazda, Mitsubishi, Honda)
- Changing one value requires editing every OEM config
- New OEMs have no template; no clear "what are the system defaults?"

**Outcome:** All constants in one place, easy to change, easy to audit.

---

## Phase 1 Checklist — Create System Constants File (3–4h)

### Step 1: Create `accy_v2/core/config/system_constants.yaml`

Copy template from PROJECT_PROPOSAL.md and populate:
- Temporal: `model_year.min: 2020`, `model_year.max: 2100`, `year_fallback.min: 1900`, `year_fallback.max: 2100`
- Finance: `price.min: 0`, `price.max: 1000000`, `labor_hours.min: 0`, `labor_hours.max: 100`
- Strings: `description.min_length: 5`, `null_tokens: [N/A, NA, ""]`, `currency_symbols: [$]`
- Pipeline: `model_lookup_confidence_min: 0.75`, `quarantine_threshold: 0.10`, `dq_report_top_issues_limit: 10`

**File:** See PROJECT_PROPOSAL.md for full template.

### Step 2: Update `accy_v2/core/config/modular_config_loader.py`

Add placeholder resolver to `load()` method:

```python
def load(self, config_path: str, **override_vars) -> Dict:
    """Load and parse config file, resolving all placeholders."""
    config = self._load_yaml(config_path)
    
    # Load system constants
    constants_path = os.path.join(self.base_path, "config", "system_constants.yaml")
    system_constants = self._load_yaml(constants_path) if os.path.exists(constants_path) else {}
    
    # Resolve ${SYSTEM_CONSTANTS.*} placeholders
    config = self._resolve_placeholders(config, system_constants)
    
    return config

def _resolve_placeholders(self, obj: Any, constants: Dict) -> Any:
    """Recursively replace ${SYSTEM_CONSTANTS.path.to.value} with actual values."""
    if isinstance(obj, str) and obj.startswith("${SYSTEM_CONSTANTS."):
        path = obj[len("${SYSTEM_CONSTANTS."):-1]  # Extract "temporal.model_year.min"
        try:
            resolved = self._get_nested_value(constants, path)
            return resolved
        except KeyError:
            raise ValueError(f"System constant '{path}' not found in system_constants.yaml")
    elif isinstance(obj, dict):
        return {k: self._resolve_placeholders(v, constants) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [self._resolve_placeholders(item, constants) for item in obj]
    return obj

def _get_nested_value(self, d: Dict, path: str) -> Any:
    """Get nested dict value using dot notation (e.g., 'temporal.model_year.min')."""
    keys = path.split(".")
    for key in keys:
        d = d[key]  # Raises KeyError if not found
    return d
```

**Effort:** 1–2 hours (straightforward implementation; add docstring + tests)

### Step 3: Create Unit Tests

File: `accy_v2/tests/test_system_constants.py`

```python
import pytest
from core.config.modular_config_loader import ModularConfigLoader

class TestSystemConstantResolution:
    
    def test_resolve_temporal_constants(self):
        """Placeholder ${SYSTEM_CONSTANTS.temporal.model_year.min} resolves to 2020."""
        loader = ModularConfigLoader(base_path="accy_v2")
        config = {
            "columns": {
                "ModelYear": {
                    "operations": [
                        {
                            "name": "validate_range",
                            "min_value": "${SYSTEM_CONSTANTS.temporal.model_year.min}",
                            "max_value": "${SYSTEM_CONSTANTS.temporal.model_year.max}"
                        }
                    ]
                }
            }
        }
        constants = {"temporal": {"model_year": {"min": 2020, "max": 2100}}}
        result = loader._resolve_placeholders(config, constants)
        
        assert result["columns"]["ModelYear"]["operations"][0]["min_value"] == 2020
        assert result["columns"]["ModelYear"]["operations"][0]["max_value"] == 2100
    
    def test_resolve_finance_constants(self):
        """Finance constants (price, labor) resolve correctly."""
        # Similar test for price.min, price.max, labor_hours.min, labor_hours.max
        pass
    
    def test_missing_constant_raises_error(self):
        """Unresolvable placeholder raises ValueError with helpful message."""
        loader = ModularConfigLoader(base_path="accy_v2")
        config = {"value": "${SYSTEM_CONSTANTS.missing.path}"}
        constants = {"temporal": {"model_year": {"min": 2020}}}
        
        with pytest.raises(ValueError, match="System constant 'missing.path' not found"):
            loader._resolve_placeholders(config, constants)
    
    def test_resolve_nested_lists(self):
        """Placeholders in lists are resolved."""
        # Test for currency_symbols list, null_tokens list
        pass
```

**Effort:** 1–2 hours (4–6 test cases covering main paths + edge cases)

### Step 4: Verify Integration

- [ ] Run unit tests: `pytest accy_v2/tests/test_system_constants.py -v`
- [ ] No test should fail
- [ ] All test cases should pass

**Effort:** 30 min (run tests, debug if needed)

---

## Phase 2 Checklist — Refactor OEM Configs (8–10h)

**Files to Update (in order):**

### Hyundai (`accy_v2/oems/hyundai/config/`)

1. **transformations.yaml** — Replace:
   - Line 20: `min_value: 2020` → `min_value: ${SYSTEM_CONSTANTS.temporal.model_year.min}`
   - Line 21: `max_value: 2100` → `max_value: ${SYSTEM_CONSTANTS.temporal.model_year.max}`
   - Line 85: `min_value: 0` → `min_value: ${SYSTEM_CONSTANTS.finance.price.min}`
   - Line 86: `max_value: 1000000` → `max_value: ${SYSTEM_CONSTANTS.finance.price.max}`
   - Line 109: `min_value: 0` → `min_value: ${SYSTEM_CONSTANTS.finance.labor_hours.min}`
   - Line 110: `max_value: 100` → `max_value: ${SYSTEM_CONSTANTS.finance.labor_hours.max}`
   - Line 62: `minimum_length: 5` → `minimum_length: ${SYSTEM_CONSTANTS.strings.description.min_length}`
   - Line 129-132: Replace hardcoded null tokens with reference to `SYSTEM_CONSTANTS`

2. **enrichment.yaml** — Replace:
   - Line 19: `min: 2020` → `min: ${SYSTEM_CONSTANTS.temporal.model_year.min}`
   - Line 20: `max: 2100` → `max: ${SYSTEM_CONSTANTS.temporal.model_year.max}`

**Effort per OEM:** ~1–1.5 hours (6–8 value replacements)

### Genesis (`accy_v2/oems/genesis/config/`)
- Same pattern as Hyundai (identical files)

### Mazda (`accy_v2/oems/mazda/config/`)
- Same pattern as Hyundai (identical files)

### Mitsubishi (`accy_v2/oems/mitsubishi/config/`)
- Same pattern as Hyundai (identical files)

### Honda (`accy_v2/oems/honda/config/`)
- Same pattern (once Honda transformations.yaml is fully populated)

### Step Files Update (`accy_v2/oems/*/pipeline/step3_5_extract_vehicle_year.py`)

**Current Pattern (lines 71–72):**
```python
min_year = year_range.get("min", 1900)
max_year = year_range.get("max", 2100)
```

**Change to:**
```python
# Fallback to system constants if not in OEM config
min_year = year_range.get("min", config.get("system_constants", {}).get("temporal", {}).get("year_fallback", {}).get("min", 1900))
max_year = year_range.get("max", config.get("system_constants", {}).get("temporal", {}).get("year_fallback", {}).get("max", 2100))
```

OR (cleaner, with helper function):
```python
def _get_system_constant(config, path: str, fallback):
    """Get system constant with fallback."""
    keys = path.split(".")
    value = config.get("system_constants", {})
    for key in keys:
        value = value.get(key, {})
    return value if isinstance(value, (int, float)) else fallback

min_year = year_range.get("min", _get_system_constant(config, "temporal.year_fallback.min", 1900))
max_year = year_range.get("max", _get_system_constant(config, "temporal.year_fallback.max", 2100))
```

**Effort:** ~1–1.5 hours (5 step files × 15 min each)

---

## Phase 2 Verification Checklist

- [ ] All hardcoded 2020, 2100, 1900, 1000000, 100, 5 values replaced in OEM configs
- [ ] All enrichment.yaml year ranges point to constants
- [ ] All step3_5_extract_vehicle_year.py files use fallback pattern
- [ ] Run full Hyundai pipeline test: `python run_hyundai.py` (should produce same output as before)
- [ ] Run full Genesis pipeline test: `python run_genesis.py` (should produce same output)
- [ ] Run Mazda, Mitsubishi tests
- [ ] All DQ reports, output Excel files identical to baseline (constants have same values)
- [ ] CHANGELOG.md updated: `PATCH: Centralize system constants to core/config/system_constants.yaml`

---

## Phase 3 Optional — Documentation (2–3h)

### Create `accy_v2/planning/SYSTEM_CONSTANTS.md`

Guide for developers on how to:
- Add a new system constant
- Override a constant for a specific OEM
- Use constants in Python code vs. YAML config

### Update `accy_v2/planning/DEVELOPMENT_GUIDE.md`

Add section:
```markdown
## System Constants

All temporal, numeric, and operational thresholds are centralized in `accy_v2/core/config/system_constants.yaml`.

### Using Constants in Config
In any OEM config file (transformations.yaml, enrichment.yaml, etc.):
```yaml
max_value: ${SYSTEM_CONSTANTS.temporal.model_year.max}
```

### Using Constants in Python
```python
constants = config.get("system_constants", {})
min_year = constants.get("temporal", {}).get("model_year", {}).get("min", 2020)
```

### Adding a New Constant
1. Add to `system_constants.yaml` under appropriate section
2. Document the use case and affected files
3. Update any OEM configs that currently hardcode the value
4. Add unit test if applies to all OEMs
```

---

## Effort Breakdown

| Phase | Task | Hours |
|-------|------|-------|
| 1 | Create `system_constants.yaml` | 1 |
| 1 | Update `modular_config_loader.py` | 1.5 |
| 1 | Create unit tests | 1.5 |
| 1 | **Phase 1 Total** | **4** |
| 2 | Update OEM configs (5 OEMs × 1h) | 5 |
| 2 | Update step3_5 files (5 files × 1h) | 1.5 |
| 2 | Integration testing + CHANGELOG | 1.5 |
| 2 | **Phase 2 Total** | **8** |
| 3 | Documentation + guides | 2.5 |
| | **Grand Total** | **14.5–16 hours** |

---

## Success Criteria (Before "Done")

- [x] `system_constants.yaml` created with all constants defined
- [x] Placeholder resolution logic added to `ModularConfigLoader`
- [x] Unit tests pass (4+ test cases)
- [x] All OEM transformations.yaml / enrichment.yaml updated
- [x] All step3_5 files use fallback pattern
- [x] Integration tests pass (full pipeline run, identical output to baseline)
- [x] CHANGELOG.md updated with PATCH version bump
- [x] No hardcoded 2020/2100/1000000/100/5 values remain in OEM code
- [x] PR review + merge to `dev`

---

## Common Pitfalls to Avoid

1. **Forgetting OEM overrides:** Some OEMs might need different values (e.g., luxury brand with vintage inventory). Add `oem_overrides` section to `system_constants.yaml` if needed (Phase 3+).

2. **Typo in placeholder path:** `${SYSTEM_CONSTANTS.temporal.model_year.min}` is case-sensitive. Test resolution early.

3. **Circular references:** Don't reference a constant that itself contains a placeholder. Not expected, but worth noting.

4. **Lazy loading:** Load `system_constants.yaml` once at startup, not per-config-load (cache it).

5. **Version mismatch:** After refactoring, verify baseline tests still pass. Constants have same values, so output must be identical.

---

## Questions for User Before Starting

1. **OEM Overrides:** Should some OEMs (Genesis, Honda luxury) have different year ranges? (E.g., allow 2015–2130 for Genesis?)

2. **Test Strategy:** Should centralized constants be tested with integration tests only, or unit tests + integration?

3. **Rollout Plan:** Refactor all 5 OEMs at once, or one at a time (lower risk but more overhead)?

4. **Documentation Priority:** Is Phase 3 (docs) required before merge, or can it be deferred to a follow-up task?

---

**Next Step:** Approval to begin Phase 1 implementation.
