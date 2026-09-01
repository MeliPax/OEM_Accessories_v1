# Cross-OEM Package Differentiator — Already Generalized, One Live Bug Found

**Date:** 2026-08-31  
**Status:** Research findings (architecture confirmed, one bug isolated)  
**Impact:** Mitsubishi silently drops multi-package variants before output; no code change needed for search/grouping layers

---

## Executive Summary

The user asked: "Use Package as a differentiator for every OEM, and make sure it reaches the output workbook."

**Finding:** The architecture is **already generalized**:
- Search-engine differentiator (`search_engine.py:335-366`) is fully OEM-agnostic
- Package output columns (`downstream.yaml`) already exist for 4/5 OEMs
- Package data is 100% populated and unique per row in the DB for all OEMs

**However, one confirmed live bug was found:** Mitsubishi's enrichment step silently drops multi-package variants before output — it reads only the *first* package and never explodes, while Hyundai/Genesis explode correctly.

No search/grouping code changes needed. One Mitsubishi enrichment fix + confirmation that architecture is already complete for other OEMs.

---

## Finding 1: The Package Differentiator Logic is Already OEM-Agnostic

### Code Location

`search_engine.py:335-366` (inline in the `candidate_count > 1` block):

```python
# 3rd branch: if all packages are distinct, accept as variants
pkgs = [r.get(package_col) if pd.notna(r.get(package_col)) else None for r in group_representatives]
if len(set(pkgs)) == len(pkgs) and all(p is not None for p in pkgs):
    # All Package values are unique and non-null → these are distinct package variants
    model_nums = [r["ModelNumber"] for r in group_representatives]
    return SearchResult(
        ..., packages=pkgs, ...
    )
```

`package_col` is resolved config-first with OEM-agnostic default (line 274):
```python
package_col = oem_rules.get("package_differentiator_column", "Package")
```

**Zero OEM-specific branching in the matching/grouping logic itself.** Add a new OEM config, override `package_differentiator_column` if needed, and it works.

---

## Finding 2: Package is 100% Populated and Unique for All Manufacturers

### DB Data (confirmed via direct query)

```
Manufacturer     Total Rows  Package Non-Null  Unique Values
HYUNDAI          400         400               400
GENESIS          162         162               162
MAZDA            250         250               250
MITSUBISHI       139         139               139
HONDA            217         217               217
```

Every single row in `db_vehicle_models.csv` has a Package value, and those values are **globally unique per row** (no duplicates within a manufacturer). This means the differentiator condition (`len(set(pkgs)) == len(pkgs)`) will essentially always fire whenever it's reached (any multi-candidate group will have distinct packages).

**Implication:** No additional search/grouping logic needed for any OEM — the mechanism is inherently complete.

---

## Finding 3: Package Already Reaches Output for 4 of 5 OEMs

### Configuration Check

Checked each OEM's `downstream.yaml` (sheet-output column mappings):

| OEM | Has Package Output Column | Source Column | Commit |
|-----|---------------------------|---------------|--------|
| Hyundai | Yes | `package` | e4d2ace |
| Genesis | Yes | `package` | e4d2ace |
| Mitsubishi | Yes | `package` | e4d2ace |
| Mazda | Yes | `Package` | e4d2ace |
| Honda | No | — | — |

**Sample from `hyundai/config/schemas/downstream.yaml:82-83`:**
```yaml
- output_column: Package
  source_column: package
```

(Duplicate blocks exist for each OEM's `_EN`/`_FR` language variants.)

**Honda caveat:** Honda has no pipeline code yet (config-only scaffold), so its stale `downstream.yaml` config is irrelevant until a pipeline is built.

---

## Finding 4: The Live Bug — Mitsubishi Silently Drops Multi-Package Variants

### The Gap

**Hyundai/Genesis pipeline** (`accy_v2/oems/hyundai_genesis/pipeline/step4_5_model_enrichment.py:350,456,462`):
```python
# Store BOTH singular and plural fields
package_mapping[trim] = result.packages if result.packages else [result.package] * len(result.model_numbers)

# Explode to one row per (model_number, package) pair
df.explode(["model_number", "package"], ...)  # ← creates separate rows for each package
```

**Mitsubishi pipeline** (`accy_v2/oems/mitsubishi/pipeline/step4_5_model_enrichment.py:247,335`):
```python
# Store ONLY the singular field (first package)
model_mapping[trim]["package"] = result.package  # ← NOT result.packages

# No explode call
df["package"] = df[trim_col].apply(lambda trim: extract_field(trim, "package"))
```

Mitsubishi never reads `result.packages` (plural) and never explodes on package. If `search()` returns a multi-variant `SearchResult` (which it does — the Fix A differentiator branch correctly identifies distinct packages), Mitsubishi's enrichment keeps only the **first** variant and **silently drops the rest**.

### Real Impact — Confirmed Data Example

Mitsubishi DB has 9 real duplicate `(Year, ModelName, ModelNumber)` groups with distinct Package values:

**Example: 2022 Mirage ES**
```
Package 423372: "Es Manual" (TrimName: ES)
Package 423373: "Es Cvt" (TrimName: ES CVT)
ModelNumber: CG44-A (same for both)
```

Both rows exist in the DB and would be returned by `search()` as variants via the Fix A branch. Mitsubishi's enrichment would:
1. Store only `package = 423372` (first one)
2. Create one output row with Package=423372
3. Silently drop the other row with Package=423373

The second variant never reaches the output workbook.

---

## Finding 5: Mazda's Package is Different Data (Unrelated to DB Differentiator)

### What Mazda's "Package" Actually Is

`accy_v2/oems/mazda/pipeline/step3_standardization.py:41`:
```python
df["package"] = df["model_number"].astype(str).str[-4:]  # last 4 chars of TrimLevel
```

Mazda's `Package` is **not** the DB's ADS-style Package/StyleID column — it's a derived **trim-code slice**. Mazda's source data includes model numbers (TrimLevel) directly, not generic trim names like "Advanced" or "Prestige". Mazda never calls `search_engine.py` to do DB lookups:

`mazda/config/enrichment.yaml:12`:
```yaml
model_lookup:
  enabled: false
```

Mazda's model enrichment step is a no-op — model numbers are pre-populated. So Mazda's `Package` column in the output is artifact-data (the last 4 chars of the trim code), not a genuine differentiator.

### Generalization Implication

Generalizing the **DB-driven** Package differentiator to Mazda (if ever desired) would require:
1. Enabling `model_lookup` for Mazda (enabling search_engine.py)
2. Removing the pre-embedded model numbers from source data
3. Re-architecting Mazda's source data ingestion

**This is a separate, materially larger architecture decision**, not a mechanical extension of Fix A. Out of scope for this pass.

---

## Finding 6: Dead-Code Trap (Pre-Existing Bug)

`accy_v2/oems/hyundai/pipeline/step4_5_model_enrichment.py` is a stale, **never-imported** duplicate file that sits next to the real shared `hyundai_genesis` version. It lacks the `df["package"] = ...` and `explode()` logic entirely.

Import trace:
- `HyundaiPipeline.__init__` (`accy_v2/oems/hyundai/pipeline/orchestrator.py`) imports `from oems.hyundai_genesis.pipeline import step4_5_model_enrichment`
- The dead file (`oems/hyundai/pipeline/step4_5_model_enrichment.py`) is **never imported by any orchestrator**
- Confirmed via grep: `oems.hyundai.pipeline.step4_5_model_enrichment` has zero importers

**Guardrail:** Do not edit the wrong file during any future Package-related work. The real file is in `hyundai_genesis/pipeline/`.

---

## Mitigation: Fix Mitsubishi's Silent Package Drop

### Change Required

Modify `accy_v2/oems/mitsubishi/pipeline/step4_5_model_enrichment.py` to store and explode on `result.packages` (plural), same pattern as Hyundai/Genesis:

**Current (incorrect) — line 247:**
```python
model_mapping[trim]["package"] = result.package  # ← singular only
```

**Fixed:**
```python
model_mapping[trim]["package"] = result.packages if result.packages else [result.package]
```

**Current (missing) — after model_mapping is populated, before output:**
```python
# Add explode call (place it after the enrichment dataframe is built, before `frames[sheet_key] = df`):
df.explode(["model_number", "package"], ignore_index=True)
```

(Exact line numbers depend on the full file structure; details to be finalized during implementation.)

**Time to fix:** 5-10 minutes. **Risk:** Very low (reuses proven pattern from Hyundai/Genesis).

---

## No Changes Needed

- **search_engine.py:** Already OEM-agnostic, no change needed
- **Hyundai/Genesis:** Already correct
- **Mazda:** Package means different data; generalization out of scope
- **Honda:** No pipeline exists yet

---

## Open Questions

1. **Is Mitsubishi's silent drop an acceptable behavior, or a bug?** This research treats it as a bug (data loss), but if the user has a different intent (e.g., "we only want the first package variant in output"), then the current Mitsubishi behavior is working as designed. Clarification needed before implementing the fix.

2. **Mazda's DB-driven Package:** Should making Mazda's Package output DB-driven become its own research topic for a future pass, or is Mazda's current trim-code-slice approach considered sufficient long-term?

3. **Honda:** When Honda's pipeline is built, should it automatically include the `explode` logic, or keep it optional pending first pipeline run?

---

## References

- **Code:**
  - `search_engine.py:335-366` (Fix A differentiator branch, OEM-agnostic)
  - `hyundai_genesis/pipeline/step4_5_model_enrichment.py:350,456,462` (correct explode pattern)
  - `mitsubishi/pipeline/step4_5_model_enrichment.py:247,335` (missing explode, silent drop)
  - `mazda/pipeline/step3_standardization.py:41` (unrelated trim-code-slice logic)
- **Config:**
  - `downstream.yaml` for all OEMs (Package output column definitions)
  - `mazda/config/enrichment.yaml:12` (model_lookup.enabled: false)
- **Data:** db_vehicle_models.csv (Package unique values per OEM)
