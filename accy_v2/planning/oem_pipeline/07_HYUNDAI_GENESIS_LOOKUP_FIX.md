# Fix: False-Positive DATABASE_NO_MATCH Warnings (Hyundai/Genesis Model Lookup)

**Status:** Planning complete, branch created, awaiting implementation approval  
**Branch:** `fix/hyundai-genesis-model-lookup`  
**Date Created:** 2026-08-28

## Problem

The latest Hyundai pipeline run (`run_id 74912dd6`, 2026-08-27) produced 128 `[DATABASE_NO_MATCH]` DQ warnings. Deep investigation confirmed the large majority (~110 of 128) are **false positives** — the flagged vehicles actually exist in `db_vehicle_models.csv` but are not being found due to two distinct bugs in the Hyundai pipeline code (not present in Mitsubishi). The remaining ~11-18 warnings are genuine data gaps (trims/years that don't yet exist in the database).

## Root Cause 1: Genesis Models Routed as Hyundai

**File/Location:** `accy_v2/oems/hyundai/pipeline/orchestrator.py:72-99` (`load_file()` method)

The Genesis model detection is broken:

```python
genesis_models = list(enrichment_config.get("model_lookup", {}).get("brands", {}).keys())
if "Hyundai" in genesis_models:
    genesis_models.remove("Hyundai")
...
manufacturer = "Genesis" if str(model).strip() in genesis_models else "Hyundai"
```

`enrichment_config["model_lookup"]["brands"]` is keyed by **brand name** (`Hyundai`, `Genesis`), not model names. After removing `"Hyundai"`, `genesis_models == ["Genesis"]` — just the literal string. So `"G70" in genesis_models` is always `False`, and every Genesis sheet gets `manufacturer="Hyundai"`. Downstream, the DB search filters `Manufacturer == "HYUNDAI"`, silently excluding all real `GENESIS` rows in the CSV.

**Impact:** Genesis models (G70, G80, G90, GV60, GV70, GV80, GV80_coupe) fail 100% of the time across all years/trims — approximately 90+ of the 128 warnings.

**Evidence:** Output workbook columns for `g70_EN`, `g80_EN`, `g90_EN`, etc. are 100% blank (no model numbers found).

## Root Cause 2: Compound Model-Name Merge is Dead Code

**File/Location:** `accy_v2/oems/hyundai/pipeline/step4_5_model_enrichment.py:191-222` (`_merge_compound_model_names()` function)

The function tries to load a non-existent configuration file:

```python
classification_path_str = oem_config.get("classification_config_path", "").strip()
if classification_path_str:
    classification_path = Path(classification_path_str)
else:
    make = oem_config.get("make", "hyundai").lower()
    classification_path = (Path(__file__).parent.parent.parent.parent
        / "model_lookup" / "configs" / f"{make}_classification.json")
if not classification_path.exists():
    return tokens  # UNMERGED
```

Problems:
- No config anywhere uses the key `classification_config_path` — always returns `""`.
- Fallback constructs path to `configs/hyundai_classification.json` which doesn't exist (real file is `configs/hyundai/classification.yaml`).
- Function returns tokens unmerged: `["santa","fe"]` instead of `["santa fe"]`.

Since Hyundai's `classification.yaml` has only compound MODEL entries (`santa fe: MODEL`, `santa cruz: MODEL`) with no single-word fallback, unmerged tokens never classify as MODEL. Search validation fails with "No MODEL token in search" *before* the DB is queried, logged as `DATABASE_NO_MATCH` — masking the real cause.

**Impact:** Every Santa Fe and Santa Cruz trim fails 100% of the time — approximately 20+ more of the 128 warnings. Confirmed: output columns for `santa_fe_EN` (1827 rows, 100% blank) and `santa_cruz_EN` (907 rows, 100% blank).

## Solution

### Fix 1: Read Genesis Models from the Workbook's Own Sheet

Replace the broken `enrichment_config` derivation with a direct read of the `Genesis` sheet that ships with every source file:

```python
genesis_sheet_name = next(
    (s for s in excel.sheet_names if s.strip().lower() == "genesis"), None
)
if genesis_sheet_name is None:
    raise ValueError(
        f"Required 'Genesis' reference sheet not found in workbook. "
        f"Found sheets: {excel.sheet_names}."
    )

genesis_raw = excel.parse(sheet_name=genesis_sheet_name, header=None)
genesis_working = promote_header_row(genesis_raw)
genesis_working.columns = [clean_column_name(str(c)) for c in genesis_working.columns]
genesis_col_lower = {c.lower(): c for c in genesis_working.columns}
genesis_model_col = next((c for c in genesis_col_lower if c == "model"), None)
if not genesis_model_col:
    raise ValueError(f"'Model' column not found in Genesis sheet. Found: {genesis_working.columns.tolist()}")

genesis_models = {
    str(m).strip().lower()
    for m in genesis_working[genesis_col_lower[genesis_model_col]].dropna().unique()
}
```

Update the routing comparison: `manufacturer = "Genesis" if str(model).strip().lower() in genesis_models else "Hyundai"`.

**Advantage:** Self-maintaining (no hand-kept list in config to drift out of sync as Genesis models change). The data is already present in every source file and authoritatively maintained by the data provider.

### Fix 2: Use the Correct Config Key and YAML Loader

Replace the entire logic in `_merge_compound_model_names()` to use the already-resolved `classifier_config` path from the config loader:

```python
classification_path = oem_config.get("classifier_config")
if not classification_path:
    if pipeline_logger:
        pipeline_logger.debug("[MERGE] No classifier_config configured for this brand")
    return tokens

classification_path = Path(classification_path)
if not classification_path.exists():
    if pipeline_logger:
        pipeline_logger.debug(f"[MERGE] Classification file not found: {classification_path}")
    return tokens

with open(classification_path, "r") as f:
    classification = yaml.safe_load(f)  # changed from json.load

token_map = classification.get("token_map", {})
```

Add `import yaml` to the imports. Check whether `import json` becomes unused elsewhere and remove if so.

**Why:** The config loader (`core/config_loader_v2.py:263-278`) already resolves `classifier_config` to an absolute Path (e.g., `.../model_lookup/configs/hyundai/classification.yaml`). No new path construction needed — just use the value directly. Files are YAML, not JSON.

**Genesis impact:** None — Genesis's `classification.yaml` has zero multi-word MODEL entries, so the merge function returns tokens unchanged. Only Hyundai's Santa Fe/Santa Cruz benefit.

### Companion Change (Recommended): Wire Up Precise Failure Diagnostics

**File:** `accy_v2/oems/hyundai/pipeline/step4_5_model_enrichment.py`, `_categorize_search_failure()` (~line 455-489)

Currently, Hyundai always logs the generic `[DATABASE_NO_MATCH]` message regardless of failure cause — which is exactly what let both bugs above hide in plain sight. Mitsubishi's pipeline instead calls `diagnose_search_failure()` (`accy_v2/model_lookup/search_engine.py:438-580`) on a failed search to return a precise reason.

**Recommendation:** Port this pattern into Hyundai, mirroring `accy_v2/oems/mitsubishi/pipeline/step4_5_model_enrichment.py:259-288`. This would have caught both bugs immediately (Model not found; No MODEL token in search) instead of masking them, and turns remaining genuine gaps into clearly labeled categories. Low risk — straight port of Mitsubishi's existing working code.

**Explicitly out of scope:** The separately-broken `ignore_keyword_categories` wiring (`step4_5_model_enrichment.py:299-311`) is a real latent bug but not confirmed to cause the false positives investigated here. Defer to separate investigation.

## Mitsubishi: No Changes Required

Mitsubishi's pipeline has neither bug pattern:
- No Genesis-style brand-routing logic (single manufacturer).
- No `_merge_compound_model_names`-equivalent function.
- Already uses the correct `classifier_config` key and calls `diagnose_search_failure()`.

Mitsubishi is in fact the reference implementation for the patterns both fixes adopt.

## Files Modified

| File | Change |
|---|---|
| `accy_v2/oems/hyundai/pipeline/orchestrator.py` | Read Genesis model list from workbook's `Genesis` sheet instead of broken `enrichment_config` derivation (lines 72-99) |
| `accy_v2/oems/hyundai/pipeline/step4_5_model_enrichment.py` | Fix `_merge_compound_model_names()` to use correct `classifier_config` key and YAML loader (lines 191-222); (recommended) wire `diagnose_search_failure()` into failure-logging call site |

No changes to: Mitsubishi pipeline, shared model-lookup engine, `db_vehicle_models.csv`.

## Verification Plan

1. **Re-run the Hyundai pipeline** against the same landing-zone file used for run `74912dd6` (`2026-8-1 HACC MAF DIST - 08102026.xlsx`).

2. **Compare DQ warning counts:**
   - Baseline (broken code): 128 `[DATABASE_NO_MATCH]` warnings
   - Expected after fix: ~11-18 warnings (genuine gaps only)

3. **Spot-check Genesis models** now resolve:
   - Verify `g70_EN`, `g80_EN`, `g90_EN`, `gv60_EN`, `gv70_EN`, `gv80_EN` output columns are no longer 100% blank
   - Confirm a sample Genesis record (e.g., 2024 G70 "2.5T Advanced") now has a model number in the output
   - Verify `meta_data["manufacturer"] == "Genesis"` for these rows (can log/inspect)

4. **Spot-check Santa Fe / Santa Cruz** now resolve:
   - Verify `santa_fe_EN` and `santa_cruz_EN` output columns are no longer 100% blank
   - Confirm a sample record (e.g., 2025 Santa Fe "XRT", 2024 Santa Cruz "Preferred") now resolves

5. **Confirm genuine gaps still fail:**
   - G70 "2.0T" trim (doesn't exist in CSV) should still produce a warning
   - 2026 Tucson "XRT" (not yet loaded) should still produce a warning
   - This verifies the fix didn't over-correct into false negatives

6. **Check EV model naming alignment** (side issue):
   - Genesis sheet has `G80 EV` and `GV70 EV`
   - CSV has `Electrified G80` and `Electrified GV70`
   - Report whether these resolve or remain a separate gap (do not attempt fix; separate follow-up if needed)

7. **Regression check on Mitsubishi:**
   - Run Mitsubishi pipeline once (unchanged code)
   - Should execute identically to before

8. **If `diagnose_search_failure` wiring is included:**
   - Verify remaining ~11-18 warnings now show specific reasons (`MODEL_YEAR_NOT_IN_DB`, `TRIM_VARIANT_NOT_FOUND`)
   - Instead of generic `[DATABASE_NO_MATCH]`

## Implementation Steps (After Approval)

1. Fix Bug 1 in `orchestrator.py`
2. Fix Bug 2 in `step4_5_model_enrichment.py`
3. (Recommended) Wire diagnostics
4. Run verification steps
5. Commit on this branch
6. Report results

No merge/PR until user confirms verification results.
