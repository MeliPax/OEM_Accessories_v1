# Future Plan: Classification Completeness + ADS Auto-Population

**Status:** Plan only — **NOT to be implemented in the current cycle**  
**Date Created:** 2026-08-28  
**Related to:** [07_HYUNDAI_GENESIS_LOOKUP_FIX.md](../hyundai_genesis_lookup_fix/07_HYUNDAI_GENESIS_LOOKUP_FIX.md) — depends on compound-model-name merge fix being complete first

---

## Context

The current work fixes two specific bugs that cause false-positive `[DATABASE_NO_MATCH]` warnings
in Hyundai (Genesis routing bug, compound-model-name merge bug). That work establishes the
foundation for this future initiative: **ensuring all models are permanently pre-defined in
classification configs, and automating the maintenance of that completeness via ADS pulls.**

This document outlines that broader initiative **for future work** — it is a plan to build, not
a plan to build now.

---

## Problem Statement

### Current State: Manual, Brittle Classification Coverage

1. **No automated completeness check.** Classification config `token_map` entries are manually
   maintained. If a new model is added to `db_vehicle_models.csv` via an ADS pull, the
   `classification.yaml` is **not** automatically updated. The new model might silently fail to
   match if its name isn't already in the token map.

2. **No inventory of gaps.** There's no systematic way to know which models in the database are
   not yet in the classification config. Discovery happens only when a pipeline run fails and
   someone investigates.

3. **Compound-model-name anti-pattern.** Multi-word model names (e.g., `santa fe`, `santa cruz`,
   `plug-in hybrid`) can be entered as compound entries *without* single-word fallbacks, and if
   the compound-merge code breaks (as it did), the entire model fails silently. No guard against
   this pattern.

4. **Inconsistent entry types.** Some entries are single-word (`g70: MODEL`), some compound
   (`santa fe: MODEL`), some are category keywords (`ev: ENGINE_TYPE`). No consistent rule for
   what constitutes a valid entry.

### Known Deficiencies Already Discovered

- **Hyundai:** `santa fe` and `santa cruz` — compound MODEL entries with no single-word fallback.
  Fixed in current work via the compound-merge bug fix, but no prevention against regression.
- **Mitsubishi:** `plug-in hybrid: ENGINE_TYPE` — compound ENGINE_TYPE entry, zero-coverage pattern.
  Deferred to this future initiative.
- **Genesis:** No known gaps (fully covered), but no automated verification process.

---

## Proposed Solution

### Phase 1: Immediate Completeness Verification

**For each OEM** (`accy_v2/model_lookup/configs/{hyundai,genesis,mitsubishi}/classification.yaml`):

1. **Extract all distinct model names** from `db_vehicle_models.csv` filtered by Manufacturer
   (e.g., all rows where `Manufacturer == "Hyundai"`).
2. **Compare against the `token_map`** in `classification.yaml`:
   - For each model name, check if it (or a variant) appears as a key in the token map.
   - Flag any model that has zero coverage (no matching token_map entry at any granularity).
3. **Generate a completeness report** for each OEM listing:
   - ✓ Covered models (already in token_map)
   - ✗ Missing models (found in DB but not in config)
   - ⚠ Partial/risky models (compound entries with no single-word fallback)

**Outcome:** A clear inventory of what needs to be added before production use.

### Phase 2: Standardize Entry Format

Establish and document a **single, consistent rule for classification entries:**

**Rule:** All model names must be added as **complete, multi-word entries** to the `token_map`.
Never use single-word fallback tokens.

**Rationale:**
- A small, explicit list of exact model names (e.g., `"Santa Fe": MODEL`, `"Santa Cruz": MODEL`)
  is more maintainable and less error-prone than a fragmented system mixing compound entries with
  single-word fallbacks.
- Hyundai and Genesis don't have hundreds of models — the list is small enough to maintain
  manually if needed.
- The compound-model-name merge fix (implemented in current work) ensures multi-word entries
  always work.

**Entry format example:**
```yaml
token_map:
  # Hyundai models (complete, multi-word where applicable)
  elantra: MODEL
  ioniq: MODEL
  ioniq 5: MODEL
  ioniq 6: MODEL
  ioniq 9: MODEL
  kona: MODEL
  kona ev: MODEL
  palisade: MODEL
  santa cruz: MODEL
  santa fe: MODEL
  sonata: MODEL
  tucson: MODEL
  venue: MODEL

  # Genesis models (same pattern)
  g70: MODEL
  g80: MODEL
  g80 ev: MODEL
  g90: MODEL
  gv60: MODEL
  gv70: MODEL
  gv70 ev: MODEL
  gv80: MODEL
  gv80 coupe: MODEL
```

### Phase 3: Automate via ADS Refresh

**Current broken machinery:**

The codebase *already has* an auto-generation function, but it's broken in 3 ways:

1. **`build_classification_config()`** (`model_lookup/semantic/classifier.py:147-259`):
   - Missing `import json` (line 182, 243).
   - Wrong output path/filename/format (constructs JSON instead of YAML).
   - Uses `_heuristic_model_tokens()` to extract single-word MODEL candidates only — insufficient
     for multi-word model names like "Santa Fe".

2. **`_heuristic_model_tokens()`** (`model_lookup/semantic/classifier.py:108-144`):
   - Only generates single-word tokens, never compounds.
   - Insufficient to cover multi-word model names.

3. **Call site** in `save_vehicle_models_to_csv()` (`model_lookup/models/manufacture_module.py:337-365`):
   - Tries to call `build_classification_config()` after every ADS refresh (line 362).
   - Uses wrong import path: `from model_lookup.classifier import ...` (should be
     `model_lookup.semantic.classifier`).
   - Wrapped in bare `except Exception: pass` (line 364) — fails silently, no rebuild ever
     happens. Confirmed via log inspection: no rebuild activity recorded in any pipeline runs.

**Future fix:**

1. **Repair `build_classification_config()`:**
   - Fix imports.
   - Change output format to YAML (match the files it's meant to regenerate).
   - Take the complete list of distinct model names from the CSV and add them to token_map as
     complete entries (not decomposed keywords).
   - Output should match the structure of the existing `.yaml` files in
     `model_lookup/configs/{make}/`.

2. **Repair the call site in `save_vehicle_models_to_csv()`:**
   - Fix the import path.
   - Remove the silent exception handler (or at least log warnings so failures are visible).
   - Ensure it's called **after** the CSV is written and contains the new models.

3. **Update maintenance documentation:**
   - Record the rule: all new/missing models are added as complete entries, never decomposed.
   - Log every ADS refresh operation so failures are discoverable.

**Outcome:** Every time `refresh_db_ads.py` is run, it automatically updates each OEM's
`classification.yaml` to include all models now in the database. Maintenance becomes
self-maintaining (the data provider's source of truth, the database, drives the config).

### Phase 4: Integrate Completeness into Pipeline Startup

**Optional enhancement (for future consideration):**

Add an optional pre-pipeline validation step that warns (or fails fast) if the database contains
models that aren't in the classification config. This catches configuration drift early:

```python
def validate_classification_completeness(oem_name: str, db_path: str, classification_yaml_path: str):
    """Warn if DB contains models not in classification config."""
    db = pd.read_csv(db_path)
    db_models = db[db["Manufacturer"] == oem_name.capitalize()]["ModelName"].unique()
    
    with open(classification_yaml_path) as f:
        config = yaml.safe_load(f)
    
    config_models = set(config.get("token_map", {}).keys())
    
    missing = set(db_models) - config_models
    if missing:
        print(f"WARNING: Models in {oem_name} DB but not in classification.yaml: {missing}")
```

This is *not* blocking (the pipeline still runs), but makes drift visible. Could be added to
`pipeline_logger` or `DQLogger` output.

---

## Files Touched (When Implemented)

| File | Change |
|---|---|
| `accy_v2/model_lookup/semantic/classifier.py` | Fix `build_classification_config()` and `_heuristic_model_tokens()` to generate complete multi-word model entries in YAML format |
| `accy_v2/model_lookup/models/manufacture_module.py` | Fix import path and error handling in `save_vehicle_models_to_csv()` call to `build_classification_config()` |
| `accy_v2/model_lookup/configs/hyundai/classification.yaml` | Add any missing models discovered in Phase 1; standardize to all-complete-entries format per rule |
| `accy_v2/model_lookup/configs/genesis/classification.yaml` | Verify completeness; standardize format if needed |
| `accy_v2/model_lookup/configs/mitsubishi/classification.yaml` | Add missing models (including `plug-in hybrid` fix); standardize format |
| Documentation (TBD) | Add maintenance guide: "How to maintain classification configs"; record the single-entry-type rule |

---

## Verification (When Implemented)

1. **Phase 1 completeness report** shows all OEMs with 100% coverage (no missing models).
2. **All classification.yaml files** follow the single-entry-type rule (no single-word fallback
   tokens, all complete entries).
3. **Run an ADS refresh** (`refresh_db_ads.py --brands Hyundai Genesis Mitsubishi --years 2026
   2027`) and verify:
   - New models in the pulled data are automatically added to the respective `classification.yaml`
     files.
   - No errors logged (previously-silent failures are now visible).
4. **Run each OEM pipeline** (Hyundai, Genesis, Mitsubishi) against sample data and verify:
   - Models that were previously classified as DATABASE_NO_MATCH due to missing config entries
     now resolve.
   - No regression in existing behavior.
5. **Optional: validate completeness check** (Phase 4) warns if DB/config drift occurs.

---

## Dependencies

This future plan **depends on:**
- ✓ [07_HYUNDAI_GENESIS_LOOKUP_FIX.md](../hyundai_genesis_lookup_fix/07_HYUNDAI_GENESIS_LOOKUP_FIX.md)
  completed and verified (compound-model-name merge fix must be working).

This future plan **enables:**
- Permanent reduction in classification-related false positives.
- Self-maintaining classification configs (driven by ADS data).
- Clear, documented maintenance rule for future model additions.

---

## Timeline and Effort Estimate

**When:** After [07_HYUNDAI_GENESIS_LOOKUP_FIX.md](../hyundai_genesis_lookup_fix/07_HYUNDAI_GENESIS_LOOKUP_FIX.md) is verified and merged.

**Effort estimate:**
- Phase 1 (completeness verification): 1-2 hours (script to compare DB vs. config, generate report)
- Phase 2 (standardization): 30 min (document rule, audit existing entries)
- Phase 3 (fix auto-generation): 2-3 hours (repair classifier.py, manufacture_module.py, test)
- Phase 4 (optional validation): 1 hour (add pre-pipeline check)
- Testing & verification: 1-2 hours

**Total: ~6-9 hours**

---

## Future Considerations

### Scaling Beyond Three OEMs

If more OEMs are added (Honda, Suzuki, etc.), the same pattern scales:
1. Ensure each has a dedicated `model_lookup/configs/{make}/classification.yaml`.
2. Add to the ADS refresh automation scope.
3. The single-entry-type rule and completeness check apply universally.

### Integration with CI/CD

Consider adding a pre-commit or pre-PR hook that validates:
- No single-word fallback entries exist (enforces the rule).
- `classification.yaml` is valid YAML and contains required top-level keys.

### Machine Learning Enhancement (Far Future)

If in-house data grows (e.g., customer-provided trim names), could train a fuzzy-match classifier
to auto-map custom trim names to standard database entries. Out of scope for this initiative.

---

## Summary

This plan systematizes and automates the currently-manual, error-prone process of maintaining
classification configs. It **does not change pipeline behavior** (the pipelines work fine once
configs are correct) — it ensures configs stay complete and correct without manual intervention,
via automated ADS-driven regeneration and a clear, enforced rule for what constitutes a valid
entry.

No implementation now; build after [07_HYUNDAI_GENESIS_LOOKUP_FIX.md](../hyundai_genesis_lookup_fix/07_HYUNDAI_GENESIS_LOOKUP_FIX.md) is verified.

