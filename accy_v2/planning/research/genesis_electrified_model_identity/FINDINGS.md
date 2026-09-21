# Genesis: Electrified Model Identity — Inconsistent Encoding Across Model Lines

**Date:** 2026-08-31  
**Status:** Research findings (design assessment pending)  
**Impact:** Silent vehicle mismatch on queries for Electrified GV70; potential future mismatch risk for GV80 Coupe

---

## Executive Summary

Genesis encodes "electric" variants inconsistently across model lines, causing keyword-matching misses and silent wrong-vehicle returns:

- **Electrified GV70**: separate `ModelName` (not a trim flag), never searched correctly without explicit "electrified" keyword; default fuel filter silently returns wrong (gas) vehicle when electric-exclusive trimlines exist
- **GV60**: always-electric model (no ICE variant) with blank `engine_type`, no "Electrified" prefix — inverse of GV70 naming
- **GV80 Coupe**: separately-named line (not "Electrified GV80"), non-BEV powertrain (`engine_type: 3.5t`), yet Description contains literal word "Electric" (from e-SC trim, not BEV designation) — sets a fragility trap for future config changes

---

## Finding 1: Electrified GV70 is a Separate `ModelName`, Not a Trim Flag

### Data Evidence (confirmed via db_vehicle_models.csv)

| Year | ModelName | TrimName | Description | ModelNumber | engine_type |
|------|-----------|----------|-------------|-------------|------------|
| 2024 | Electrified GV70 | Prestige | Prestige Awd | V7EW5ZE1GP00 | electric |
| 2024 | GV70 | 2.5T Select | 2.5t Select Awd | V71SAA25KX53 | 2.5t |
| 2026 | Electrified GV70 | Advanced | Advanced Awd | V7EW5ZE1GA00 | electric |
| 2026 | GV70 | 2.5T Select | 2.5t Select Awd | V71SAA25DX53 | 2.5t |

**Key observation:** "Electrified"/"electric" appears **only in `ModelName` and `engine_type`**, never in `Description` or `TrimName`. Description is just trim level ("Prestige Awd", "Advanced Awd") with no electric designation.

### Search Engine Behavior

`manufacture_module.py:1229-1246` does **substring/regex matching on raw `ModelName` string**, not tokenized comparison:

```python
pattern = build_word_boundary_pattern("gv70")  # → r"\bgv70\b"
model_matches = df_filtered["ModelName"].str.contains(pattern, case=False)
```

This matches **both** `"Electrified GV70"` and `"GV70"` equally. At the classification stage (`search_engine.py`, steps 1-3), only Description/TrimName tokens are classified — ModelName is never tokenized. So searching `["gv70", "prestige"]` (tokens from source data) classifies as MODEL={"gv70"}, TRIM={"prestige"}, ENGINE_TYPE={}. Neither "electrified" nor "electric" is in the classified set.

### Silent Wrong-Vehicle Return

When the default `exclude_ev` filter runs (`manufacture_module.py:1248-1254`):

```python
has_fuel_type = _matches_any_fuel_keyword(df_filtered, ["electric", "phev", "hev", "fcev"], ...)
if exclude_ev and not any(kw in search_kw_lower for kw in ["electric", ...]):
    df_filtered = df_filtered[~has_fuel_type]  # drop electric rows
```

Because no fuel keyword is in the classified set, and `Electrified GV70` has `engine_type=electric`, the electric row is dropped. But a plain `GV70` row exists for every year 2022-2027, so **the search does not fail — it returns the gas GV70** instead of the intended Electrified variant.

**This is worse than NOT_FOUND:** a wrong vehicle, not a missing one. Accessory compatibility checks downstream will silently bind accessories meant for Electrified to a gas model.

### Root Cause

The source data (ADS trimline names) never carries the "Electrified" prefix — it only provides the trim level ("Prestige", "Advanced"). The pipeline has no signal to disambiguate which variant is intended. The `exclude_ev` filter's assumption — "no fuel keyword = assume user doesn't want electric" — is valid when the *same trim* exists on both variants, but breaks when the trim is exclusive to one line.

---

## Finding 2: GV60 is EV-by-Default (No ICE Variant) with Blank engine_type

### Data Evidence

All 2026 GV60 rows (`ModelName = "GV60"`):

| TrimName | engine_type | Description |
|----------|------------|-------------|
| Advanced | (blank/NaN) | Advanced Awd |
| (blank) | (blank/NaN) | Awd *Ltd Avail* |
| \+ | (blank/NaN) | \+ Awd |
| Sport | (blank/NaN) | Sport Awd |

**Key observation:** No "Electrified GV60" ModelName exists; GV60 is inherently electric. Yet `engine_type` is **blank for every row**, never `"electric"` — unlike Electrified GV70/G80 which do get `engine_type=electric`.

### Search Engine Behavior

Since `engine_type` is blank, the fuel-check logic (`manufacture_module.py:1248-1254`) finds no fuel-type keywords in ModelName or engine_type and does not exclude GV60 rows. A bare `"gv60"` search should work correctly.

### Assessment

**This case does not appear to be a live code bug** — the pipeline logic is actually correct for this edge case. The user's test of GV60 "Performance" trim not appearing is more likely a **missing-data issue** (GV60 Performance may not exist in the 2026 DB, only certain trims are populated, etc.) rather than a search-engine architectural gap. This case belongs in the "validate data gaps" category, not "code-fix" category.

### Guardrail

Document that GV60's EV-by-default status with blank `engine_type` works today because `fuel_type_check_columns` doesn't include Description. A future config change to broaden fuel-type matching might inadvertently treat GV60 as "fuel-type-flagged" and drop it from searches — worth documenting as a known-good edge case.

---

## Finding 3: GV80 Coupe is a Non-BEV with "Electric" in Description (Fragility Trap)

### Data Evidence

All 2026 `GV80 Coupe` rows (`ModelName = "GV80 Coupe"`):

| TrimName | engine_type | Description | ModelNumber |
|----------|------------|-------------|------------|
| 3.5T e-SC | 3.5t | 3.5t Electric Awd | V8CC7K3BGP00 |
| 3.5T e-SC Prestige Black | 3.5t | 3.5t Electric Prestige Black-Package Awd | V8CC7K3BGPBL |

"Coupe" appears **only in `ModelName`**, never in Description or TrimName. The word "Electric" in Description refers to the "e-SC" (electric supercharger) trim designation, **not a BEV powertrain** — `engine_type` is still `3.5t`. Plain GV80 includes gas trims (2.5T, 3.5T); GV80 Coupe does not — Coupe variants are e-SC only, not electric-only.

### Current Behavior

Genesis's `fuel_type_check_columns` (from `genesis/config/enrichment.yaml`) includes only `ModelName` and `engine_type`, **not `Description`**. So the literal word "Electric" in Description does not trigger the fuel-type exclusion today.

**This is currently not a live bug** — the config-scoped behavior is correct.

### Fragility & Guardrail

If `fuel_type_check_columns` is ever extended to include `Description` (e.g., for some future OEM or to fix a different gap), GV80 Coupe rows would start being **wrongly excluded** by any fuel-less search, because Description contains the word "Electric" even though the powertrain is not a BEV.

**Recommendation:** Add a config-level comment/documentation note at `genesis/config/enrichment.yaml`'s `fuel_type_check_columns` key, explicitly calling out that Description is deliberately excluded for Genesis because GV80 Coupe Description contains "Electric" (e-SC, not BEV designation), and including it would break GV80 Coupe matching.

---

## Mitigation Ideas (Assessed Against Architecture)

### Cluster 1A: Electrified GV70 Wrong-Vehicle Return

**Problem:** Trim exclusive to Electrified line returns gas variant silently.

**Mitigation 1A.1: DB-Exclusive Rule via `implied_fuel_type_trims` (Config-Driven)**

Reuse the already-proven mechanism from Hyundai's Tucson fix. Confirm via DB query whether 2026 GV70 "Advanced" exists **only** under Electrified GV70 (not as a standalone gas trim). If yes:

```yaml
# genesis/config/enrichment.yaml
implied_fuel_type_trims:
  - model_keywords: [gv70]
    trim_keywords: [advanced]
    fuel_type: electric
    years: [2026]  # or null if exclusive across all years
```

When source provides `["gv70", "advanced"]` (tokens from ADS) with no fuel keyword, the engine injects `"electric"` into `filtered_keywords` before the DB-side match runs, flipping the exclude_ev filter to keep the EV row and exclude the gas row. DQ rule `implied_fuel_type_rule` logs the injection for auditability.

**Requirement:** DB confirmation of exclusivity **per model+trim+year** before writing the rule — don't guess. This is the same discipline applied to the Elantra TCR proposal.

**Scope:** Genesis template already exists; needs population only.

---

**Mitigation 1A.2: Flag Ambiguous Cases (DQ Safety Net)**

For trims that exist on *both* lines in the same year (e.g., if GV70 "Prestige" turns out to exist as both gas and Electrified in 2026):

The `implied_fuel_type_trims` mechanism cannot disambiguate — there's no single keyword to inject. Instead: add a new DQ rule (`fuel_type_ambiguous_rule`) to the exclude_ev step in `manufacture_module.py`. When the filter is about to drop EV rows that would leave a non-empty, non-EV result, log it:

```python
# manufacture_module.py, modify exclude_ev block:
if exclude_ev and (EV rows exist and non-EV rows exist after filtering):
    dq_logger.log_warning(
        rule_violated="fuel_type_ambiguous_rule",
        issue_description=(
            f"Fuel-type ambiguity: search returned both EV and non-EV candidates; "
            f"no fuel keyword in source to disambiguate. Returning {selection}; "
            f"verify correctness."
        )
    )
    # Still return the filter's choice (non-EV), but flag it for review
```

This is **log-only, additive**, follows the same "don't silently guess" philosophy as the orphaned-record safety net.

---

### Cluster 2 & 3: GV60 / GV80 Coupe (No Code Fix)

- **GV60:** Appears to be missing-data issue, not a code bug. No code fix proposed; add to data-validation pass.
- **GV80 Coupe:** Fragility is documented; add config-level guardrail comment. No code change needed.

---

## Open Questions (For User)

1. **Electrified GV70 DB-exclusivity:** which specific (model, trim, year) combinations are confirmed DB-exclusive to Electrified line? Needs per-year/trim audit before config rules are written. Sample check:
   - Does 2026 GV70 "Advanced" exist as a standalone gas trim, or only under Electrified GV70?
   - Does 2026 GV70 "Prestige" exist in both?
   - Are there any 2025/2024 trims that differ from 2026?

2. **Ambiguous-fuel-type DQ rule (1A.2):** is flagging ambiguous cases (log-only, return best-guess) the right behavior, or should ambiguous cases hard-fail (return NOT_FOUND)? This is a real behavior change with customer-facing consequences — needs explicit user direction before implementation.

3. **Related to sibling proposal:** should `fuel_type_ambiguous_rule` live in the same rule family as `orphaned_record_rule`, both being "don't silently guess" safety nets?

---

## References

- **Code:** `manufacture_module.py:1229-1254` (exclude_ev logic), `search_engine.py:140-168` (implied_fuel_type_trims)
- **Config:** `genesis/config/enrichment.yaml:47-51` (fuel_type_check_columns), `genesis/config/enrichment.yaml:61` (implied_fuel_type_trims template)
- **Data:** db_vehicle_models.csv (Genesis rows)
- **Related:** Sibling proposal `accy_v2/planning/oem_pipeline/trim_hierarchy_orphan_safety_net/PROPOSAL.md` (implies_fuel_type_trims pattern)
