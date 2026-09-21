# Orphaned Records Detection & Trim Hierarchy Config Rules — Architectural Design (2026-08-31)

**Date:** 2026-08-31  
**Status:** 🎯 DESIGN & PLANNING  
**Impact:** 15,800 orphaned records (across all OEMs); ~1,000+ fixable via config, ~300+ true data gaps

---

## Executive Summary

Pipeline analysis discovered 15,800 records reaching output with `Model=nan`, representing orphaned accessories with failed model enrichment. Investigation revealed **two distinct root causes**:

1. **Trim Hierarchy Gaps (Fixable - ~1,000+ records):** Source trim names don't match DB model+trim combinations
   - Example: "Elantra TCR" exists in DB only as "Elantra N TCR"
   - Affects: Elantra (TCR), IONIQ (N), Santa (XRT, Pref, Ult), Tucson (XRT)

2. **True Data Gaps (Database Issue - ~340+ records):** Trim variants don't exist in DB
   - Example: "Palisade Calligraphy" only exists as Hybrid in DB, not as ICE variant
   - Affects: Palisade (Calli ICE, Calli HEV)

**Solution Strategy:** Config-driven trim aliasing + proactive DQ flagging + architectural validation improvements.

---

## Problem Definition

### Current State: Orphaned Records in Output

**Finding:** 15,800 records with `Model=nan` in final output across Hyundai/Genesis

```
Elantra:     120 orphaned (TCR: 120)
Santa:       824 orphaned (XRT: 416, Pref: 204, Ult: 204)
Palisade:    338 orphaned (Calli ICE: 172, Calli HEV: 166)
Tucson:      200 orphaned (XRT: 200)
IONIQ:       98  orphaned (N: 98)
... and 40+ other combinations across all models/OEMs
```

### Root Cause Analysis

#### Issue #1: Trim Hierarchy Mismatch (Fixable via Config)

**Example: Elantra TCR**

| Layer | Data | Issue |
|-------|------|-------|
| Source | Trim = "TCR" | Generic trim designation |
| DB Query | Model="Elantra" + Trim="TCR" | Returns 0 records |
| DB Actual | Model="Elantra N" + Trim="TCR" | 2 records exist |
| **Result** | Model=nan | **ORPHANED** |

**Why this happens:**
- Source data provides abbreviated trim names (TCR, XRT, N)
- DB stores full hierarchies (Elantra N TCR, Santa Fe XRT, IONIQ 5 N)
- Search logic doesn't account for this multi-level hierarchy
- Record passes validation → reaches output with nan Model

**Affected trims (confirmed DB exists):**
- Elantra TCR → "Elantra N" has TCR
- IONIQ N → IONIQ 5/IONIQ Hybrid/IONIQ 9 have N
- Santa XRT → Santa Fe/Santa Cruz have XRT
- Santa Pref/Ult → exists under multiple Santa variants + hybrids
- Tucson XRT → exists in DB

#### Issue #2: True Data Gaps (Requires DB/ADS Update)

**Example: Palisade Calligraphy**

| Model | 2026 Variants in DB |
|-------|------|
| Palisade Hybrid | Calligraphy, Luxury, Ultimate, etc. |
| Palisade ICE | Preferred, Luxury (NO Calligraphy) |

Source requests "Palisade Calligraphy ICE" → DB has no such row → Model=nan

**Affected cases:**
- Palisade Calli ICE (172 records) — NO ICE variant in DB
- Palisade Calli HEV (166 records) — Database gap (should exist)

---

## Proposed Solution: Three-Layer Approach

### Layer 1: Config-Driven Trim Aliasing Rules

**New config section:** `model_lookup.brands.<OEM>.trim_hierarchy_aliases`

**Purpose:** Map abbreviated trims to their full model+trim combinations in DB.

**Schema:**

```yaml
model_lookup:
  brands:
    Hyundai:
      # ... existing config ...
      
      # Trim hierarchy aliases: when source trim doesn't match any DB records,
      # try alternative model+trim combinations (cross-model search)
      trim_hierarchy_aliases:
        # Format: source_trim -> [list of (model_override, alternate_trim_search)]
        
        - source_trim: TCR
          # TCR only exists under Elantra N in DB
          candidates:
            - model_base: Elantra
              model_override: Elantra N
              trim_search: TCR
              years: [2024, 2025, 2026]
        
        - source_trim: N
          # "N" trim exists across multiple IONIQ models
          candidates:
            - model_base: IONIQ 5
              model_override: null  # Already correct
              trim_search: N
            - model_base: IONIQ 6
              model_override: IONIQ Hybrid  # N only under Hybrid variant
              trim_search: N
            - model_base: IONIQ 9
              model_override: null
              trim_search: N
        
        - source_trim: XRT
          # XRT available in Santa Fe/Santa Cruz variants
          candidates:
            - model_base: Santa
              model_override: Santa Fe
              trim_search: XRT
            - model_base: Santa
              model_override: Santa Cruz
              trim_search: XRT
        
        - source_trim: Pref
          # Preferred only in certain Santa variants
          candidates:
            - model_base: Santa
              model_override: Santa Fe
              trim_search: Pref
            - model_base: Santa
              model_override: Santa Cruz
              trim_search: Pref
```

**Implementation Location:** `search_engine.py`, step 4 (after primary search fails, before returning None)

**Logic:**
1. Primary search: `model + trim` → finds N records
2. If N=0 and trim is in `trim_hierarchy_aliases`:
   - For each candidate alias:
     - Search with `model_override + trim_search`
     - If found: return result with confidence marker `trim_hierarchy_matched: true`
3. If still 0: return None (true data gap)

**Safety:**
- Only fires after primary search fails (no false matches)
- Marked in SearchResult for DQ logging
- Exact trim matching (not substring)
- Year-scoped (can disable for certain years if needed)

---

### Layer 2: DQ Rule for Orphaned Records

**New DQ rule:** `orphaned_record_without_model`

**Purpose:** Flag any record that reaches output with `Model=nan` for visibility and triage.

**Implementation location:** `step4_5_model_enrichment.py`, at output generation

**Rule trigger:**
```python
if result.model_number is None and result.is_null_fallback is False:
    # Record made it through pipeline without model enrichment (not intentional null)
    dq_logger.log_warning(
        sheet_name=model_name,
        model_name=model_name,
        rule_violated="orphaned_record_without_model",
        issue_description=(
            f"[ORPHANED] {make} {year} {trim}: Accessory record has no model number. "
            f"Possible causes: (1) Trim not in database, (2) Trim hierarchy mismatch, "
            f"(3) Source trim name incorrect. Verify source trim name or update trim_hierarchy_aliases config."
        ),
        record_snapshot={"trim": trim, "accessory": accessory, "part": part_number},
        severity: "warning"
    )
```

**DQ Report Output:**
- Sheet name: model name (e.g., "elantra_EN")
- Issue count per model
- Breakdown by trim causing orphans
- Suggested config rules to fix

**Example Report Entry:**
```
Orphaned Records Report:
  Elantra: 120 orphaned (100% TCR)
    Recommended Fix: Add trim_hierarchy_aliases rule for TCR→ElantraN

  Santa Fe: 824 orphaned (50% XRT, 25% Pref, 25% Ult)
    Recommended Fix: Add trim_hierarchy_aliases for XRT, Pref, Ult (multi-model)

  Palisade: 338 orphaned (51% Calli ICE, 49% Calli HEV)
    Status: TRUE DATA GAP - Request ADS/DB update for Palisade Calli ICE
```

---

### Layer 3: Validation Architecture Improvements

**Goal:** Catch data issues earlier in pipeline, not at output stage.

#### 3A: Pre-Search Validation (Step 3.5 - New)

**New step:** Validate that classified tokens will match SOMETHING in DB before expensive search.

```python
def validate_search_feasibility(make, year, model, trim, classified_tokens):
    """
    Pre-flight check: Does this model+trim combination exist in DB?
    Runs before expensive search operation.
    
    Returns: (is_valid: bool, issue: str, suggested_fix: str)
    """
    # Query: count distinct (Model, Trim) for this (Make, Year)
    db_combinations = db.query(
        f"SELECT COUNT(DISTINCT (ModelName, TrimName)) 
         WHERE Manufacturer=? AND ModelYear=?",
        (make, year)
    )
    
    source_model_trim = f"{model}+{trim}"
    
    # If combination doesn't exist in DB
    if not exists_in_db(make, year, model, trim):
        return False, f"No {source_model_trim} in DB", "Check trim_hierarchy_aliases"
    
    return True, None, None
```

**Benefits:**
- Identifies data issues before search (faster)
- Enables early DQ logging with context
- Opportunity to suggest fixes before enrichment attempt

#### 3B: DQ Categorization at Failure Point (Step 4.5 - Enhanced)

**Current:** Generic `MODEL_LINE_NOT_FOUND` for all failures

**Proposed:** Categorize by root cause

```python
def categorize_search_failure(make, year, model, trim, search_result):
    """
    Classify why search failed into actionable categories.
    """
    
    # Check 1: Is this trim+model combination in DB at all?
    if not exists_in_db(make, year, model, trim):
        # Check if alternative models have this trim
        alternatives = find_trim_in_other_models(make, year, trim)
        if alternatives:
            return "TRIM_HIERARCHY_MISMATCH", {
                "missing_combination": f"{model}+{trim}",
                "found_in_models": alternatives,
                "suggested_rule": f"trim_hierarchy_aliases: {trim} -> {alternatives[0]}"
            }
        else:
            return "TRUE_DATA_GAP", {"model_trim": f"{model}+{trim}"}
    
    # Check 2: Model exists but trim doesn't
    if exists_in_db(make, year, model, None) and not exists_in_db(make, year, model, trim):
        available_trims = get_available_trims(make, year, model)
        return "TRIM_UNAVAILABLE_FOR_MODEL", {
            "model": model,
            "requested_trim": trim,
            "available_trims": available_trims
        }
    
    # ... other categories ...
```

#### 3C: Cross-OEM Validation Rule (New Generic Rule)

**Purpose:** Ensure consistency across OEMs; catch same issue in Mitsubishi/Mazda/Honda before reaching output.

**Rule:** Before output, check all records and flag any with `model_number is None` unless intentionally flagged.

```python
class RecordValidator:
    def validate_before_output(self, df):
        """
        Final validation: no record should reach output with null model unless marked.
        """
        orphans = df[df['model_number'].isna() & df['is_intentional_null'] != True]
        
        if len(orphans) > 0:
            self.logger.critical(
                f"HALT: {len(orphans)} orphaned records detected before output. "
                f"Trim distribution: {orphans['trim'].value_counts().to_dict()}. "
                f"Review trim_hierarchy_aliases config or data source."
            )
            # Option: Block output until resolved
            raise DataQualityException("Orphaned records in output")
```

---

## Implementation Roadmap

### Phase 1: Immediate (This Sprint)

**1.1 Add DQ Rule for Orphaned Detection**
- File: `accy_v2/oems/hyundai_genesis/pipeline/step4_5_model_enrichment.py`
- Add: `orphaned_record_without_model` rule
- Output: Breakdown by model/trim in DQ report
- Time: 1-2 hours

**1.2 Create Trim Hierarchy Aliases Config Template**
- Files: `accy_v2/oems/hyundai/config/enrichment.yaml` + Genesis + others
- Add: Empty `trim_hierarchy_aliases: []` section with documentation
- Documentation: Pattern explanation, how to identify candidates, current rules
- Time: 30 min

**1.3 Implement Alias Logic in Search Engine**
- File: `accy_v2/model_lookup/search_engine.py`
- Add: `_search_with_trim_aliases()` fallback (after primary search fails)
- Add: SearchResult field `trim_hierarchy_matched: bool`
- Time: 2-3 hours

### Phase 2: Config Population (Next Sprint)

**2.1 Populate Hyundai Rules**
- TCR → Elantra N
- N → IONIQ variants
- XRT → Santa variants
- Pref/Ult → Santa variants
- Years: 2024-2026

**2.2 Genesis Rules**
- Similar pattern (if Genesis has same issues)

**2.3 Mitsubishi/Mazda/Honda Review**
- Check for similar trim hierarchy issues
- Add rules for any found

**2.4 True Data Gap Triage**
- Flag Palisade Calli ICE/HEV for data team
- Create ADS/DB update request

### Phase 3: Validation Architecture (Future Sprint)

**3.1 Pre-search validation layer**
**3.2 Failure categorization logic**
**3.3 Cross-OEM orphan detection rule**

---

## Files to Modify/Create

| File | Change | Sprint |
|------|--------|--------|
| `accy_v2/model_lookup/search_engine.py` | Add alias fallback logic + SearchResult field | Phase 1 |
| `accy_v2/oems/hyundai/config/enrichment.yaml` | Add `trim_hierarchy_aliases` section + rules | Phase 1-2 |
| `accy_v2/oems/genesis/config/enrichment.yaml` | Add template | Phase 1 |
| `accy_v2/oems/mitsubishi/config/enrichment.yaml` | Add template + review | Phase 2 |
| `accy_v2/oems/mazda/config/enrichment.yaml` | Add template + review | Phase 2 |
| `accy_v2/oems/honda/config/enrichment.yaml` | Add template + review | Phase 2 |
| `accy_v2/oems/hyundai_genesis/pipeline/step4_5_model_enrichment.py` | Add orphaned record DQ rule | Phase 1 |
| `accy_v2/docs/2026-08-31_orphan_records_detection.md` | This document | Phase 1 |

---

## Risk Analysis

### Low Risk
- DQ rule addition (read-only, non-blocking)
- Config addition (no code change, fallback only)
- Alias logic (runs only after primary search fails)

### Mitigation
- All new logic in fallback paths (primary search unchanged)
- SearchResult field optional (backwards compatible)
- Alias rules require exact trim+model match (no false matches)
- Comprehensive regression testing on primary search paths

---

## Expected Outcomes

### After Phase 1
- ✅ All orphaned records flagged in DQ report with root cause
- ✅ Config-driven approach ready for population
- ✅ Foundation for future alias rules

### After Phase 2
- ✅ 1,000+ records recovered (TCR, N, XRT, Pref, Ult variants)
- ✅ All OEMs configured with templates
- ✅ True data gaps (Palisade, Santa variants) clearly identified

### After Phase 3
- ✅ Orphaned records caught earlier in pipeline
- ✅ Consistent categorization across all pipelines
- ✅ Architectural safeguards prevent similar issues in future OEMs

---

## Cross-OEM Architectural Design

**Key principle:** Trim hierarchy complexity is per-OEM. Some OEMs have flat trim structures (Mazda), others have deep hierarchies (Hyundai: Model → Sub-model → Trim). 

**Solution:** Config-driven, not code-driven.

```
OEM Config Structure:
├── Hyundai: trim_hierarchy_aliases populated (complex hierarchy)
├── Genesis: trim_hierarchy_aliases populated
├── Mitsubishi: trim_hierarchy_aliases empty initially (review needed)
├── Mazda: trim_hierarchy_aliases empty (flat structure)
└── Honda: trim_hierarchy_aliases empty initially (review needed)
```

Future OEM additions inherit template automatically; no code changes needed.

---

## References

- Related: `2026-08-31_search_gaps_fixes/` (earlier search corrections)
- Database: `accy_v2/model_lookup/db/db_vehicle_models.csv`
- Output analysis: Orphaned records detected in Aug 28 pipeline run
