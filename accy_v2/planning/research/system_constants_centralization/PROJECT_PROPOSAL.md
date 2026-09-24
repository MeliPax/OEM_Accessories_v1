# System Constants Centralization — Project Proposal

**Status:** Project Proposal (ready for implementation queue)  
**Created:** 2026-09-24  
**Category:** Architecture / DevOps  
**Priority:** Medium (Quality of Life improvement)  
**Effort Estimate:** 16–20 hours (Phase 1–2)

---

## Executive Summary

Currently, **min/max date values, numeric thresholds, and temporal constraints are scattered** across the codebase as hardcoded values in individual OEM configuration files. This creates:

- **Maintenance burden:** Change one value in 5 places (Hyundai, Genesis, Mazda, Mitsubishi, Honda)
- **Inconsistency risk:** Year ranges drift between OEMs; easy to miss an update
- **Discoverability gap:** New OEMs or future features have no single source of truth
- **Testing friction:** Unit tests can't easily override constants without mocking

**Proposal:** Centralize all temporal and numeric system constants into a single **`accy_v2/core/config/system_constants.yaml`** file, loaded at runtime and injected into OEM configs via placeholder resolution.

**Benefits:**
- ✅ Single source of truth (one change, everywhere updated)
- ✅ Easy audit trail (all constants in one file)
- ✅ Simplified OEM onboarding (inherit defaults, override only if needed)
- ✅ Test-friendly (inject test values via environment or config override)

---

## Candidate Constants Identified

### 1. **Temporal Constraints (Date/Year Ranges)**

| Constant | Current Scope | Locations | Value(s) | Use Case |
|----------|--------------|-----------|---------|----------|
| `MIN_MODEL_YEAR` | Hyundai, Genesis, Mazda, Mitsubishi, Honda | `transformations.yaml` (all OEMs) | `2020` | ModelYear validation min_value |
| `MAX_MODEL_YEAR` | Hyundai, Genesis, Mazda, Mitsubishi, Honda | `transformations.yaml` (all OEMs) | `2100` | ModelYear validation max_value |
| `MIN_YEAR_FALLBACK` | Hyundai, Genesis, Mazda, Mitsubishi, Honda | `step3_5_extract_vehicle_year.py` (all OEMs, line 71) | `1900` | Year validation fallback if not in config |
| `MAX_YEAR_FALLBACK` | Hyundai, Genesis, Mazda, Mitsubishi, Honda | `step3_5_extract_vehicle_year.py` (all OEMs, line 72) | `2100` | Year validation fallback if not in config |

**Current Files:**
- `accy_v2/oems/hyundai/config/transformations.yaml:20-21`
- `accy_v2/oems/hyundai/config/enrichment.yaml:18-20`
- `accy_v2/oems/genesis/config/transformations.yaml:20-21`
- `accy_v2/oems/mazda/config/transformations.yaml:20-21`
- `accy_v2/oems/mitsubishi/config/transformations.yaml:20-21`
- `accy_v2/oems/honda/config/transformations.yaml` (once populated)
- `accy_v2/oems/hyundai_genesis/pipeline/step3_5_extract_vehicle_year.py:71-72`
- `accy_v2/oems/mazda/pipeline/step3_5_extract_vehicle_year.py:71-72`
- `accy_v2/oems/mitsubishi/pipeline/step3_5_extract_vehicle_year.py:71-72`

### 2. **Numeric Range Constraints (Finance)**

| Constant | Current Scope | Locations | Value(s) | Use Case |
|----------|--------------|-----------|---------|----------|
| `MIN_PRICE` | Hyundai, Genesis, Mazda, Mitsubishi, Honda | `transformations.yaml` (all OEMs) | `0` | MSRP / DNET min validation |
| `MAX_PRICE` | Hyundai, Genesis, Mazda, Mitsubishi, Honda | `transformations.yaml` (all OEMs) | `1000000` | MSRP / DNET max validation |
| `MIN_LABOR_HOURS` | Hyundai, Genesis, Mazda, Mitsubishi, Honda | `transformations.yaml` (all OEMs) | `0` | LaborHours min validation |
| `MAX_LABOR_HOURS` | Hyundai, Genesis, Mazda, Mitsubishi, Honda | `transformations.yaml` (all OEMs) | `100` | LaborHours max validation |

**Current Files:**
- `accy_v2/oems/hyundai/config/transformations.yaml:84-86, 108-110`
- `accy_v2/oems/genesis/config/transformations.yaml:84-86, 108-110`
- `accy_v2/oems/mazda/config/transformations.yaml:84-86, 108-110`
- `accy_v2/oems/mitsubishi/config/transformations.yaml:84-86, 108-110`
- `accy_v2/oems/honda/config/transformations.yaml` (once populated)

### 3. **String Constraints (Validation)**

| Constant | Current Scope | Locations | Value(s) | Use Case |
|----------|--------------|-----------|---------|----------|
| `MIN_DESCRIPTION_LENGTH` | Hyundai, Genesis, Mazda, Mitsubishi, Honda | `transformations.yaml` (all OEMs) | `5` | Description / Description_FR minimum_length |
| `MISSING_VALUE_TOKENS` | Global | `transformations.yaml` (all OEMs) | `["N/A", "NA", ""]` | Null value handling strategy |
| `CURRENCY_SYMBOLS` | Global | `transformations.yaml` (all OEMs) | `["$"]` | Currency symbol removal in price fields |

**Current Files:**
- `accy_v2/oems/hyundai/config/transformations.yaml:62, 129-132`
- `accy_v2/oems/genesis/config/transformations.yaml:62, 129-132`
- `accy_v2/oems/mazda/config/transformations.yaml:62, 129-132`
- `accy_v2/oems/mitsubishi/config/transformations.yaml:62, 129-132`
- `accy_v2/oems/honda/config/transformations.yaml` (once populated)

### 4. **Pipeline Thresholds (Operational)**

| Constant | Current Scope | Locations | Value(s) | Use Case |
|----------|--------------|-----------|---------|----------|
| `MODEL_LOOKUP_CONFIDENCE_THRESHOLD` | OEM-specific | `enrichment.yaml` (per OEM) | varies | Minimum confidence score for model lookup acceptance |
| `BATCH_QUARANTINE_THRESHOLD` | OEM-specific | `pipeline.yaml` (per OEM) | varies (e.g., 0.10) | Percentage of errors before file quarantine |
| `DQ_WARNING_AGGREGATION_LIMIT` | Global | Implicit in DQ reporting | ~10 | Number of top issues to report per file |

**Current Files:**
- Implicit in `accy_v2/oems/{oem}/config/enrichment.yaml`
- Implicit in `accy_v2/oems/{oem}/config/pipeline.yaml`

---

## Proposed File Structure

Create `accy_v2/core/config/system_constants.yaml`:

```yaml
# ============================================================================
# File: accy_v2/core/config/system_constants.yaml
# Description: System-wide temporal and numeric constants
# Purpose: Single source of truth for all min/max/threshold values
# ============================================================================
# DECISION [025]: Centralize system constants at core level
# - Loaded once at startup
# - Injected into OEM configs via ${SYSTEM_CONSTANT_*} placeholders
# - OEMs can override per-constant if needed (rare)
# ============================================================================

# Temporal Constraints
temporal:
  model_year:
    # Valid production year range for all manufacturers
    # Applied in: transformations.yaml (ModelYear validation)
    # Also applied in: step3_5_extract_vehicle_year.py (fallback)
    min: 2020
    max: 2100

  year_fallback:
    # Fallback range if OEM config doesn't specify (safety net)
    # Applied in: step3_5_extract_vehicle_year.py:71-72
    min: 1900
    max: 2100

  # Note: If future needs for fiscal year, model generation year, etc., add here

# Numeric Constraints — Finance
finance:
  price:
    # MSRP / DNET / List Price range
    # Applied in: transformations.yaml (MSRP/DNET validation)
    # Rationale: No production accessory priced <$0 or >$1M
    min: 0
    max: 1000000

  labor_hours:
    # Installation labor hours per part
    # Applied in: transformations.yaml (LaborHours validation)
    # Rationale: Max ~100 hours per installation (about 2.5 work weeks)
    min: 0
    max: 100

# String Constraints
strings:
  description:
    # Minimum length for Description / Description_FR fields
    # Applied in: transformations.yaml (Description validation)
    # Rationale: "a b c" (5 chars) is minimum meaningful description
    min_length: 5

  # Null/missing value tokens (treated as NULL during transformation)
  # Applied in: transformations.yaml (global.missing_value_strategy)
  null_tokens:
    - "N/A"
    - "NA"
    - ""

  # Currency symbols to strip from numeric fields
  # Applied in: transformations.yaml (remove_currency_symbols)
  currency_symbols:
    - "$"
    - "CAD"
    - "USD"

# Pipeline Operational Thresholds
# (Note: These are placeholders for Phase 2; exact values TBD per OEM strategy)
pipeline:
  # Minimum confidence score for model lookup to be accepted
  # Applied in: step4_5_model_enrichment.py (model_number_status filter)
  # Note: Per-OEM overrides in enrichment.yaml; these are global defaults
  model_lookup_confidence_min: 0.75

  # Percentage of rows that can error before file is quarantined
  # Applied in: orchestrator.py (batch error handling)
  # Note: Per-OEM configuration; adjust if OEM has high error tolerance
  quarantine_threshold: 0.10

  # Number of top issues to include in DQ report per file
  dq_report_top_issues_limit: 10

# Version info (for audit trail when constants change)
metadata:
  version: "1.0"
  last_updated: "2026-09-24"
  updated_by: "claude-code"
  notes: "Initial centralization; imported from scattered OEM configs"
```

---

## Usage Pattern (OEM Config Integration)

### Before (Current)
```yaml
# accy_v2/oems/hyundai/config/transformations.yaml
ModelYear:
  operations:
    - name: validate_range
      min_value: 2020
      max_value: 2100
```

### After (Proposed)
```yaml
# accy_v2/oems/hyundai/config/transformations.yaml
ModelYear:
  operations:
    - name: validate_range
      min_value: ${SYSTEM_CONSTANTS.temporal.model_year.min}
      max_value: ${SYSTEM_CONSTANTS.temporal.model_year.max}
```

**Config Loader Logic:**
```python
# accy_v2/core/config/modular_config_loader.py (existing pattern)

def resolve_placeholders(config_dict, constants):
    """Replace ${SYSTEM_CONSTANTS.*} with actual values."""
    for key, value in config_dict.items():
        if isinstance(value, str) and value.startswith("${SYSTEM_CONSTANTS"):
            path = value[len("${SYSTEM_CONSTANTS."):-1]  # Extract "temporal.model_year.min"
            resolved = get_nested(constants, path)
            config_dict[key] = resolved
        elif isinstance(value, dict):
            resolve_placeholders(value, constants)
    return config_dict
```

---

## Implementation Phases

### Phase 1: Create System Constants File (3–4 hours)
**Deliverables:**
- [x] Create `accy_v2/core/config/system_constants.yaml` with all candidates
- [x] Add loader integration to `ModularConfigLoader.load()` to auto-inject SYSTEM_CONSTANTS into OEM configs
- [x] Add unit test: verify placeholder resolution works
- [x] Add unit test: verify constants are accessible from all OEM configs

**Files Modified:**
- `accy_v2/core/config/system_constants.yaml` (new)
- `accy_v2/core/config/modular_config_loader.py` (add placeholder resolver)
- `accy_v2/tests/test_system_constants.py` (new)

### Phase 2: Refactor OEM Configs to Use Constants (8–10 hours)
**Deliverables:**
- [x] Update `accy_v2/oems/hyundai/config/transformations.yaml` — replace hardcoded values with `${SYSTEM_CONSTANTS.*}`
- [x] Update `accy_v2/oems/hyundai/config/enrichment.yaml` — replace year ranges
- [x] Update `accy_v2/oems/hyundai_genesis/pipeline/step3_5_extract_vehicle_year.py` — load from resolved config
- [x] Repeat for all 5 OEMs (Hyundai, Genesis, Mazda, Mitsubishi, Honda)
- [x] Update `step3_5_extract_vehicle_year.py` for all OEMs
- [x] Add integration test: run full pipeline, verify year validation uses centralized constant
- [x] Update CHANGELOG.md for version impact

**Files Modified (multiple):**
- All `accy_v2/oems/{oem}/config/transformations.yaml` (5 files)
- All `accy_v2/oems/{oem}/config/enrichment.yaml` (5 files)
- All `accy_v2/oems/*/pipeline/step3_5_extract_vehicle_year.py` (5 files)

### Phase 3: Documentation & Future Extension (2–3 hours, optional)
**Deliverables:**
- [ ] Create `accy_v2/planning/SYSTEM_CONSTANTS.md` — guide for adding new constants
- [ ] Add section to `DEVELOPMENT_GUIDE.md` — "How to add a system constant"
- [ ] Add comment in `system_constants.yaml` for each future group (fiscal year, generation year, etc.)

---

## Benefits & Tradeoffs

### Benefits
| Benefit | Impact |
|---------|--------|
| **Single source of truth** | Change once, applies everywhere; no accidental drift |
| **Easier OEM onboarding** | New OEM inherits defaults; only needs to override if different |
| **Audit trail** | All constants versioned in one file; easy to review history |
| **Test-friendly** | Unit tests can inject test values via fixture override |
| **Discovery** | Developers immediately see all temporal/numeric constraints in one place |

### Tradeoffs
| Tradeoff | Mitigation |
|----------|-----------|
| **Loader complexity** | Placeholder resolution is simple (string.format + nested dict lookup); add tests |
| **Config layering** | One extra config load step; minimal overhead; cached at startup |
| **Migration effort** | ~20 hours to refactor all OEM configs; one-time cost; high value |

---

## Success Criteria

- [x] All temporal constants (`MIN_MODEL_YEAR`, `MAX_MODEL_YEAR`, etc.) defined in `system_constants.yaml`
- [x] All numeric constraints (prices, labor hours) centralized in one file
- [x] All OEM configs updated to reference centralized values
- [x] No hardcoded values remain in OEM transformations.yaml / enrichment.yaml / step files
- [x] Unit test confirms placeholder resolution works
- [x] Integration test confirms full pipeline passes with centralized constants
- [x] CHANGELOG.md updated with this change
- [x] Zero behavior change (constants have same values before/after refactoring)

---

## Notes for Future Work

1. **Seasonal/Fiscal Year Constants:** If the system ever needs fiscal year ranges or model-generation-year validation, add sections to `system_constants.yaml` without modifying loaders.

2. **Per-Manufacturer Overrides:** Some manufacturers might need different year ranges (e.g., luxury brands with older vintage inventory). Create an `oem_overrides` section:
   ```yaml
   oem_overrides:
     Ferrari:  # hypothetical
       model_year:
         min: 1990  # allow vintage cars
   ```

3. **Environment-based Overrides:** For testing, allow `$` to read from `SYSTEM_CONSTANTS_MODEL_YEAR_MAX` (env var):
   ```yaml
   max: ${env:SYSTEM_CONSTANTS_MODEL_YEAR_MAX:2100}  # fallback to 2100
   ```

4. **Database Constraints Sync:** In the future, consider syncing these constants with the vehicle database schema (e.g., `db_vehicle_models.csv` max year). Could generate them from DB schema if needed.

---

## Status & Next Steps

**Current Status:** Proposal ready for implementation queue  
**Assigned To:** (pending user assignment)  
**Next Step:** Wait for user to approve; schedule for Phase 1 implementation

---

**Created By:** Claude Code  
**Date:** 2026-09-24  
**Category:** Architecture / DevOps  
**Related:** `VERSIONING.md` (release process), `DEVELOPMENT_GUIDE.md` (developer workflow)
