# Hyundai/Genesis Full Pipeline Separation + Compound-Model Merge Fix

**Status:** Planning complete, expanded scope approved, branch created, awaiting implementation approval  
**Branch:** `feature/hyundai-genesis-lookup-fix`  
**Date Created:** 2026-08-28  
**Updated:** 2026-08-28 (scope expanded to include full separation + config-driven sheet names)

## Context

The initial investigation identified two bugs causing false-positive `[DATABASE_NO_MATCH]` warnings
in the Hyundai pipeline (128 total; ~110 false positives, ~18 genuine gaps). Rather than a
targeted bug fix alone, the user requested a broader architectural refactor to **prevent the same
bugs from recurring** by redesigning the pipeline to eliminate the entanglement between Hyundai
and Genesis data, and by moving hardcoded sheet names into configuration.

This document covers three interconnected changes:

1. **Full Hyundai/Genesis pipeline separation** — genesis becomes a standalone sibling OEM
   pipeline (like Mitsubishi/Mazda), reading its own dedicated sheet, producing its own separate
   output.
2. **Config-driven sheet-name resolution** — each OEM's source sheet name lives in YAML, not
   Python, and is validated to exist before use.
3. **Compound-model-name merge fix** — correct the dead code that prevents "Santa Fe" and
   "Santa Cruz" from matching their classification config entries.

Together, these eliminate the original false positives, prevent future routing bugs, and simplify
both pipelines by removing manufacturer-detection logic that becomes unnecessary once each sheet
contains only one brand.

---

## Problem: Original False-Positive Investigation

The latest Hyundai pipeline run (`run_id 74912dd6`, 2026-08-27) produced 128 `[DATABASE_NO_MATCH]`
DQ warnings. Deep investigation found:

### Root Cause 1: Genesis Models Silently Routed as "Hyundai"

**File:** `accy_v2/oems/hyundai/pipeline/orchestrator.py:72-99` (`load_file()` method)

```python
genesis_models = list(enrichment_config.get("model_lookup", {}).get("brands", {}).keys())
if "Hyundai" in genesis_models:
    genesis_models.remove("Hyundai")
...
manufacturer = "Genesis" if str(model).strip() in genesis_models else "Hyundai"
```

The code confuses **brand keys** with **model names**: `enrichment_config["model_lookup"]["brands"]`
contains `{"Hyundai": {...}, "Genesis": {...}}`. After removing "Hyundai", `genesis_models ==
["Genesis"]` — just the literal brand string. So `"G70" in genesis_models` is always False, and
every Master sheet row is routed as `manufacturer="Hyundai"`. Downstream, the DB search filters on
`Manufacturer == "HYUNDAI"`, silently excluding all real `GENESIS` rows in the CSV.

**Impact:** All Genesis models (G70, G80, G90, GV60, GV70, GV80) fail across all trims/years —
~90+ of the 128 warnings. Confirmed via output inspection: `g70_EN`, `g80_EN`, etc. are 100% blank.

### Root Cause 2: Compound-Model-Name Merge is Dead Code

**File:** `accy_v2/oems/hyundai/pipeline/step4_5_model_enrichment.py:191-222`
(`_merge_compound_model_names()` function)

```python
classification_path_str = oem_config.get("classification_config_path", "").strip()
if classification_path_str:
    classification_path = Path(classification_path_str)
else:
    classification_path = (.../ "configs" / f"{make}_classification.json")
if not classification_path.exists():
    return tokens  # UNMERGED
```

No config key named `classification_config_path` exists anywhere (always returns `""`). Fallback
constructs path to `configs/hyundai_classification.json` which doesn't exist (real file is
`configs/hyundai/classification.yaml`). Result: tokens stay unmerged as `["santa", "fe"]` instead
of `["santa fe"]`.

Hyundai's `classification.yaml` has only compound MODEL entries (`santa fe: MODEL`, `santa cruz:
MODEL`) with no single-word fallback. Unmerged tokens never classify as MODEL, search validation
fails *before* the DB is queried, and the generic `DATABASE_NO_MATCH` masks the true cause.

**Impact:** Santa Fe and Santa Cruz trims fail across all years — ~20+ more of the 128 warnings.
Confirmed: output columns for `santa_fe_EN` (1827 rows, 100% blank) and `santa_cruz_EN` (907 rows,
100% blank).

---

## Solution: Full Separation + Config Consolidation

### Item 1: Genesis Becomes a Standalone OEM Pipeline

**Architecture decision:** Genesis is promoted to a sibling OEM (`OEM_NAME = "genesis"`), mirroring
the existing Mitsubishi/Mazda/Honda pattern. Step modules are shared (not duplicated) to avoid
maintenance burden, while orchestrators and configs remain fully separate.

**Implementation details:**

1. **Shared step module extraction:**
   - Create `accy_v2/oems/hyundai_genesis/pipeline/` directory.
   - Move step modules here: `step1_validation.py`, `step2_header_normalization.py`,
     `step3_standardization.py`, `step3_5_extract_vehicle_year.py`, `step4_transformation.py`,
     `step4_5_model_enrichment.py`, `step5_output.py` (moved from `oems/hyundai/pipeline/`).
   - Apply compound-merge fix + diagnostics wiring once, both pipelines benefit.
   - Update import statements in both Hyundai's and Genesis's `orchestrator.py` to use
     `oems.hyundai_genesis.pipeline`.

2. **New Genesis pipeline orchestrator:**
   - `accy_v2/oems/genesis/pipeline/orchestrator.py` — `GenesisPipeline(BasePipeline)`, reads
     `source_sheet: "Genesis"` from config, imports steps from shared `oems.hyundai_genesis.pipeline`.
   - `accy_v2/oems/genesis/config/` — new config directory with `pipeline.yaml` (`source_sheet:
     "Genesis"`), `enrichment.yaml` (Genesis brand config extracted from Hyundai's version),
     `transformations.yaml`, `schemas/upstream.yaml|intermediate.yaml|downstream.yaml` (copied,
     as sheets share identical 33-column layout).
   - `accy_v2/run_genesis.py` — new entry script, mirrors `run_hyundai.py` pattern.

2. **New Genesis output locations (automatic, no code needed):**
   - Output workbook: `accy_v2/output/ready_to_upload/genesis/genesis_*.xlsx`
   - DQ reports: `accy_v2/output/dq_reports/genesis/dq_report_*.json`
   - Pipeline logs: `accy_v2/output/pipeline_logs/genesis/pipeline_*.log`

3. **Simplified Hyundai orchestrator:**
   - Drop all `genesis_models` lookup/derivation logic (lines 72-99 of current file).
   - Read `source_sheet: "Hyundai"` from config (Item 2 below).
   - Set `manufacturer="Hyundai"` as a fixed constant (no per-row routing needed).
   - Import step modules from its own `oems.hyundai.pipeline` package (unchanged).

**Outcome:** Running `python accy_v2/run_hyundai.py` touches **only Hyundai** data (Hyundai sheet
rows) and produces output in `genesis/` → no Genesis rows leaked into Hyundai output, and no
Hyundai rows leaked into Genesis output.

### Item 2: Config-Driven Sheet Names

**Principle:** Hardcoded sheet names (`"Master"`, `"Hyundai"`, `"Genesis"`) in Python are
hard to change and error-prone. Sheet names belong in config YAML.

**Implementation:**

Add `source_sheet` key to each OEM's `pipeline.yaml`:

```yaml
# accy_v2/oems/hyundai/config/pipeline.yaml
source_sheet: "Hyundai"

# accy_v2/oems/genesis/config/pipeline.yaml
source_sheet: "Genesis"
```

Modify each orchestrator's `load_file()` to read this config:

```python
def load_file(self, file_path: str) -> Dict[str, pd.DataFrame]:
    excel = pd.ExcelFile(file_path)
    config_root = Path(__file__).parent.parent / "config"
    loader = ModularConfigLoader(self.OEM_NAME, config_root)
    pipeline_config = loader.load_pipeline_config()
    
    # Resolve sheet name with validation
    sheet_name = self._resolve_sheet(excel, pipeline_config["source_sheet"])
    
    raw = excel.parse(sheet_name=sheet_name, header=None)
    # ... rest of grouping/metadata logic
```

Add a helper:

```python
def _resolve_sheet(self, excel: pd.ExcelFile, wanted: str) -> str:
    match = next(
        (s for s in excel.sheet_names if s.strip().lower() == wanted.strip().lower()),
        None
    )
    if match is None:
        raise ValueError(
            f"Required sheet '{wanted}' not found in workbook. Found sheets: {excel.sheet_names}."
        )
    return match
```

**Outcome:** Incorrect or missing sheet names fail fast with a clear error listing available
sheets, instead of silent `pd.ExcelFile` KeyError. Sheet names are now configurable and easy to
change.

### Item 3: Fix Compound-Model-Name Merge

**File:** Both `accy_v2/oems/hyundai/pipeline/step4_5_model_enrichment.py` AND
`accy_v2/oems/genesis/pipeline/step4_5_model_enrichment.py` (apply to both standalone copies)

Replace the entire `_merge_compound_model_names()` function to use the correct config key and YAML
loader:

```python
classification_path = oem_config.get("classifier_config")
if not classification_path:
    return tokens

classification_path = Path(classification_path)
if not classification_path.exists():
    return tokens

with open(classification_path, "r") as f:
    classification = yaml.safe_load(f)  # changed from json.load

token_map = classification.get("token_map", {})
# ... rest of merge logic unchanged
```

**Why:** The config loader (`core/config_loader_v2.py:263-278`) already resolves `classifier_config`
to an absolute Path. No new path construction needed — just use the value directly. Files are YAML,
not JSON.

**Genesis impact:** None — Genesis's `classification.yaml` has zero multi-word MODEL entries. The
merge function returns tokens unchanged. Only Hyundai's Santa Fe/Santa Cruz benefit.

### Item 4: Wire Up Precise Failure Diagnostics (Companion, Recommended)

**File:** Both step4_5 copies, `_categorize_search_failure()` (~line 455-489)

Currently, both pipelines always log generic `[DATABASE_NO_MATCH]` regardless of failure cause.
Mitsubishi's pipeline instead calls `diagnose_search_failure()` (`search_engine.py:438-580`) to
return precise reasons.

**Recommendation:** Port this pattern into both Hyundai's and Genesis's step4_5 modules, mirroring
Mitsubishi's pattern (`oems/mitsubishi/pipeline/step4_5_model_enrichment.py:259-288`). This would
have caught both original bugs immediately and turns remaining genuine gaps into clearly labeled
categories. Low risk — straight port of existing working code.

---

## Files Touched

| File | Change |
|---|---|
| `accy_v2/oems/hyundai_genesis/pipeline/` (new) | Shared step modules (moved from hyundai/pipeline): step1_validation.py, step2_header_normalization.py, step3_standardization.py, step3_5_extract_vehicle_year.py, step4_transformation.py, step4_5_model_enrichment.py, step5_output.py. Apply compound-merge fix + diagnostics wiring once here. |
| `accy_v2/oems/hyundai/pipeline/orchestrator.py` | Simplified `load_file()`: read `source_sheet` from config, drop `genesis_models` logic, set manufacturer constant; update imports to use `oems.hyundai_genesis.pipeline` |
| `accy_v2/oems/hyundai/config/pipeline.yaml` | Add `source_sheet: "Hyundai"` |
| `accy_v2/oems/hyundai/config/enrichment.yaml` | Remove `brands.Genesis` block (moves to Genesis's own config) |
| `accy_v2/oems/genesis/pipeline/orchestrator.py` (new) | `GenesisPipeline`, trimmed `load_file()`; imports from `oems.hyundai_genesis.pipeline` |
| `accy_v2/oems/genesis/config/pipeline.yaml` (new) | `source_sheet: "Genesis"` |
| `accy_v2/oems/genesis/config/enrichment.yaml` (new) | Genesis brand config (extracted from Hyundai's) |
| `accy_v2/oems/genesis/config/transformations.yaml` (new) | Copy of Hyundai's |
| `accy_v2/oems/genesis/config/schemas/*.yaml` (new) | Copies of Hyundai's (upstream, intermediate, downstream) |
| `accy_v2/run_genesis.py` (new) | Entry script |

**No changes to:** `base_pipeline.py`, `config_loader_v2.py`, Mazda, Mitsubishi, Honda, shared
`model_lookup` search engine, or `classification.yaml` files (existing `santa fe`/`santa cruz`
entries are correct; the merge fix in shared code makes them match).

---

## Verification Plan (Once Implementation Approved)

1. **Hyundai pipeline produces Hyundai-only output:**
   - `python accy_v2/run_hyundai.py` against `2026-8-1 HACC MAF DIST - 08102026.xlsx`
   - Output workbook should contain only Hyundai models (Elantra, Ioniq, Kona, Santa Fe, etc.)
   - Zero Genesis rows in Hyundai output

2. **Genesis pipeline produces Genesis-only output:**
   - `python accy_v2/run_genesis.py` against the same file
   - New output workbook created under `output/ready_to_upload/genesis/`
   - Contains only Genesis models (G70, G80, G90, GV60, GV70, GV80)
   - Zero Hyundai rows in Genesis output

3. **DQ warning counts drop to expected levels:**
   - Hyundai baseline (broken code): 128 warnings
   - Hyundai after fix: expect ~11-18 (genuine gaps: G70 "2.0T", 2026 Tucson "XRT", etc.)
   - Genesis: expect low count (no Hyundai routing bugs for this brand)

4. **Spot-check Genesis models now resolve:**
   - Genesis output columns for `g70_EN`, `g80_EN`, `g90_EN`, `gv60_EN`, `gv70_EN`, `gv80_EN` are no longer blank
   - Confirm a sample (e.g., 2024 G70 "2.5T Advanced") has a model number

5. **Spot-check Santa Fe / Santa Cruz now resolve:**
   - Hyundai output columns for `santa_fe_EN` and `santa_cruz_EN` are no longer blank
   - Confirm samples (e.g., 2025 Santa Fe "XRT", 2024 Santa Cruz "Preferred") have model numbers

6. **Confirm genuine gaps still fail:**
   - G70 "2.0T" trim (doesn't exist in CSV) should still produce a warning
   - 2026 Tucson "XRT" (not yet loaded) should still produce a warning
   - Verifies the fix didn't over-correct into false negatives

7. **Check sheet-name validation:**
   - Manually edit a `pipeline.yaml` to have an invalid `source_sheet: "NonExistent"` and re-run
   - Pipeline should fail fast with a clear error listing available sheets, not a cryptic KeyError

8. **EV model naming mismatch (side issue, report as follow-up if unresolved):**
   - Genesis sheet has `G80 EV` and `GV70 EV`
   - CSV has `Electrified G80` and `Electrified GV70`
   - Do not attempt fix within this change; flag as a separate naming-alignment gap if unresolved

9. **Regression checks:**
   - Run Mitsubishi and Mazda pipelines (unchanged code) — should execute identically to before
   - No shared code was touched, so this should be a no-op confirmation

10. **If diagnostics wiring is included:**
    - Verify remaining ~11-18 warnings show specific reasons (`MODEL_YEAR_NOT_IN_DB`,
      `TRIM_VARIANT_NOT_FOUND`, etc.) instead of generic `[DATABASE_NO_MATCH]`

---

## Future Item (Separate Plan): Classification Completeness + ADS Auto-Population

This change does NOT touch the broader "predefine every model across every OEM" initiative. That
is a separate future plan (see `08_CLASSIFICATION_COMPLETENESS_FUTURE.md` in the same planning
folder) that will:

- Cross-reference every distinct `ModelName` in `db_vehicle_models.csv` per manufacturer against
  each OEM's `classification.yaml` `token_map`, and fill any gaps found (confirming all model
  names are added as complete, defined entries like `"santa fe": MODEL` — never decomposed into
  single-word fallback tokens).
- Fix the broken `build_classification_config()` / `_heuristic_model_tokens()` in
  `model_lookup/semantic/classifier.py` and the broken hook in
  `manufacture_module.py::save_vehicle_models_to_csv()` so that every ADS pull automatically
  regenerates classification configs from fresh DB data, keeping model coverage self-maintaining.
- Flag the already-discovered `plug-in hybrid` ENGINE_TYPE zero-coverage pattern in Mitsubishi's
  `classification.yaml` for that pass (not addressed here).

---

## Implementation Steps (After Approval)

1. Extract shared step modules to `accy_v2/oems/hyundai_genesis/pipeline/` (move from Hyundai).
2. Apply compound-merge fix + diagnostics wiring in the shared step4_5_model_enrichment.py.
3. Update Hyundai orchestrator (drop genesis_models logic, read source_sheet from config, update imports).
4. Update Hyundai config (add source_sheet, remove Genesis brand block from enrichment.yaml).
5. Create Genesis orchestrator importing shared steps.
6. Create Genesis config by extracting Genesis brand block and copying Hyundai's transformations/schemas.
7. Create run_genesis.py entry script.
8. Run verification steps (both pipelines against the test workbook).
9. Commit all changes on this branch.
10. Report verification results.

No merge/PR until user confirms verification results and reviews the changes.
