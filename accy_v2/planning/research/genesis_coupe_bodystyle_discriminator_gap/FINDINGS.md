# Genesis: Coupe Body-Style — Discriminator Filter Gap (ModelName-Blind)

**Date:** 2026-08-31  
**Status:** Research findings (extension to existing mechanism identified)  
**Impact:** Bare "gv80" search not defensively separated from "GV80 Coupe" rows; potential ambiguity in accessory matching

---

## Executive Summary

`"coupe"` is correctly classified as a MODEL category and found in the DB when explicitly searched. However, the trim-discriminator exclusion filter (`_get_trim_discriminator_keywords`) only checks TRIM/TRIM_VARIANT tokens against Description — not MODEL tokens against ModelName. Result: a bare `"gv80"` search (no "coupe" keyword) is not defensively kept away from `GV80 Coupe` rows.

**Mitigation:** Extend the existing discriminator mechanism to also cover MODEL-category sub-variant tokens (e.g., `coupe`) checked against `ModelName`, not just Description.

---

## Finding 1: "Coupe" is Classified as MODEL, Not TRIM

### Configuration

`genesis/classification.yaml:12`:
```yaml
coupe: MODEL
```

This is **hand-authored**, not auto-derived — confirmed absent from `genesis_keywords.json` (the auto-vocab). The classifier's vocabulary-building (`build_manufacturer_keyword_vocab`, `manufacture_module.py:796-799`) only tokenizes the `Description` column:

```python
for desc in df_make["Description"].dropna():
    tokens = _extract_description_tokens(desc)  # ← only Description, never ModelName
```

So `"coupe"` could never appear in the auto-vocab because it doesn't exist in any Description — it lives **only in ModelName** ("GV80 Coupe").

### Data Evidence

All Genesis `ModelName` values (confirmed via db query):
```
Electrified G80, Electrified GV70, G70, G80, G90, GV60, GV70, GV80, GV80 Coupe
```

For 2026 `GV80 Coupe`:
```
ModelName: "GV80 Coupe"
Description (2 rows): "3.5t Electric Awd", "3.5t Electric Prestige Black-Package Awd"
TrimName: "3.5T e-SC", "3.5T e-SC Prestige Black"
```

**"coupe" never appears in Description or TrimName; only in ModelName.**

---

## Finding 2: DB-Side Matching Correctly Checks ModelName

When `"coupe"` **is** in a search, the DB-side matcher (`manufacture_module.py:1229-1246`) correctly finds it:

```python
pattern = build_word_boundary_pattern("coupe")  # → r"\bcoupe\b"
model_matches = df_filtered["ModelName"].str.contains(pattern, case=False)  # ✓ checks ModelName
```

Confirmed: searching `["gv80", "coupe", "3.5t", "..."]` **does** find `GV80 Coupe` rows (pending the unresolved "e-sc" tokenization question in Cluster 4).

---

## Finding 3: Trim-Discriminator Filter is TRIM/TRIM_VARIANT-Only + Description-Only

The trim-discriminator logic prevents "extra unwanted variant" matches by checking whether a Description contains trim keywords the search didn't explicitly request:

`manufacture_module.py:1030-1068` (`_get_trim_discriminator_keywords`):
```python
trim_tokens = {
    token for token, category in config.get("token_map", {}).items()
    if category in ("TRIM", "TRIM_VARIANT")  # ← only TRIM/TRIM_VARIANT, not MODEL
}
```

`manufacture_module.py:1256-1279` (the filter):
```python
def _has_extra_discriminator_keywords(desc: str) -> bool:  # ← checks Description, not ModelName
    tokens = set(_extract_description_tokens(desc))
    discriminator_tokens = tokens & trim_discriminators
    extra_discriminators = discriminator_tokens - search_kw_set
    return bool(extra_discriminators)

df_filtered = df_filtered[~df_filtered["Description"].apply(_has_extra_discriminator_keywords)]
```

**Two constraints:**
1. Only TRIM/TRIM_VARIANT tokens collected → `coupe` (MODEL) is exempt
2. Only `Description` checked → `coupe` (in ModelName) is invisible

### Impact

A bare `"gv80"` search (no "coupe" token):
- Classifies as MODEL={"gv80"}, TRIM={}
- Matches both `"GV80"` and `"GV80 Coupe"` rows (substring match on raw ModelName string)
- Trim-discriminator filter would normally exclude rows with "extra" trim tokens (e.g., if "prestige" appeared in one row's Description but not the search) — but it can't protect against "coupe" because:
  - `coupe` is MODEL, not TRIM
  - `coupe` is in ModelName, not Description

**Result:** ambiguous candidate set, both gas and Coupe variants returned. Downstream logic (duplicate/variant grouping, `search_engine.py:264-397`) is not designed to resolve body-style ambiguity.

---

## Mitigation

### Extend Discriminator to Cover MODEL Sub-Variants

Modify `_get_trim_discriminator_keywords` to also collect MODEL-category tokens **if they are classified as sub-variants** (determined by a new config block):

```python
# genesis/config/enrichment.yaml (new section):
model_sub_variant_tokens:
  - coupe

# manufacture_module.py:1030-1068, modify collection:
trim_tokens = {
    token for token, category in config.get("token_map", {}).items()
    if category in ("TRIM", "TRIM_VARIANT")
}
model_variant_tokens = set(config.get("model_sub_variant_tokens", []))
all_discriminators = trim_tokens | model_variant_tokens
```

Then extend the filter to check both Description and ModelName:

```python
def _has_extra_discriminator_keywords(desc: str, model_name: str) -> bool:
    desc_tokens = set(_extract_description_tokens(desc))
    model_tokens = set(_extract_description_tokens(model_name))  # or manual split
    
    discriminator_tokens = (desc_tokens | model_tokens) & all_discriminators
    extra_discriminators = discriminator_tokens - search_kw_set
    return bool(extra_discriminators)

df_filtered = df_filtered[~df_filtered.apply(
    lambda row: _has_extra_discriminator_keywords(row["Description"], row["ModelName"]),
    axis=1
)]
```

**Benefits:**
- Additive to existing mechanism (no risky changes to TRIM logic)
- Config-driven (new `model_sub_variant_tokens` list per OEM, defaults to empty)
- Safe for other OEMs: no entry in their configs = no change in behavior
- Correctly defends against bare `"gv80"` matching `GV80 Coupe`

---

### Alternative: MODEL-Only Matching (Narrower Scope)

If the user prefers a narrower, Genesis-only fix:

```python
# In manufacture_module.py, add special case after main discriminator logic:
if make.lower() == "genesis" and "coupe" in [t.lower() for t in model_tokens if t in classified.get("MODEL", [])]:
    # If search didn't request "coupe", exclude GV80 Coupe rows
    if "coupe" not in search_kw_set:
        df_filtered = df_filtered[~df_filtered["ModelName"].str.contains(r"\bcoupe\b", case=False)]
```

**Pros:** Minimal code, immediate effect  
**Cons:** Hardcoded for Genesis, not a reusable pattern, higher maintenance burden if similar issues arise for other OEMs

**Recommendation:** Use the config-driven extension (first option) for consistency with the existing architecture-over-code philosophy.

---

## Open Questions

1. **MODEL sub-variant scope:** Should this be Genesis-only (narrowest, matches proven need) or a cross-OEM config mechanism now (broader, but consistent with other config-driven capabilities)?

2. **Other MODEL sub-variants:** Are there other Genesis (or other OEM) MODEL tokens beyond `coupe` that should be classified as sub-variants? E.g., does Mitsubishi have model-line variants (body-style, market-specific) that should be treated similarly?

---

## References

- **Code:** `manufacture_module.py:1030-1068` (discriminator collection), `manufacture_module.py:1256-1279` (discriminator filter)
- **Config:** `genesis/classification.yaml:12` (coupe: MODEL), `genesis/config/enrichment.yaml` (no model_sub_variant_tokens entry yet)
- **Data:** db_vehicle_models.csv (GV80 vs. GV80 Coupe ModelName distinction)
