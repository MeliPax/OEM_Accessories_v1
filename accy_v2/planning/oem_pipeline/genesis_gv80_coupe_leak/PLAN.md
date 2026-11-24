# Fix plan: GV80 rows get GV80 Coupe model numbers

**Status:** 📋 FOR REVIEW. No code changed yet.
**Branch:** `fix/genesis-gv80-coupe-leak` (from `dev` at `c93f806`)
**Scope:** PATCH (bug fix in shared lookup code; only Genesis is configured to use it)
**Date:** 2026-11-24

---

## 1. The problem

On the Genesis **GV80** sheet, the Prestige trims are given the **GV80 Coupe** model number as well as their own:

| Year | Source trim | Gets today | Should get |
|---|---|---|---|
| 2026, 2027 | 3.5T Prestige | `V8CW7K3BGP00`, `V8CW7K3BGPBL`, **`V8CC7K3BGPBL`** | `V8CW7K3BGP00`, `V8CW7K3BGPBL` |
| 2026, 2027 | 3.5T Prestige Black | `V8CW7K3BGPBL`, **`V8CC7K3BGPBL`** | `V8CW7K3BGPBL` |

`V8CC…` codes are GV80 Coupe; `V8CW…` codes are GV80. So every GV80 Prestige accessory row is also exported against the Coupe. The **GV80 Coupe sheet is correct**, and the vehicle DB is correct (separate `ModelName` values: `GV80` and `GV80 Coupe`).

## 2. Root cause

`search_models_by_description()` in [manufacture_module.py](../../../model_lookup/models/manufacture_module.py) (lines ~1324–1352):

1. The keyword `gv80` is matched against `ModelName` as a whole word, so it matches both `GV80` and `GV80 Coupe`. This is expected; a later filter is meant to drop the Coupe.
2. That later filter (`_has_extra_discriminator_keywords`) does two checks in one:
   - **Trim check:** drop rows whose description has trim words that weren't searched (e.g. searching "Advanced" drops "Advanced Plus").
   - **Model check:** drop rows whose model name has a sub-variant word that wasn't searched. Genesis config sets `model_sub_variant_tokens: [coupe]`, whose comment says it's there to stop "gv80" matching "GV80 Coupe".
3. The whole filter is skipped when the search includes a trim word (`prestige` is one) or a fuel word. Skipping the trim check there is deliberate (searching "Prestige" should return every Prestige variant), but the model check is skipped with it, so the Coupe gets through.

Reproduced directly against the current DB:

| Keywords | Result |
|---|---|
| `gv80 3.5t prestige` | GV80 `V8CW7K3BGP00`, GV80 `V8CW7K3BGPBL`, **GV80 Coupe `V8CC7K3BGPBL`** |
| `gv80 3.5t prestige black-package` | GV80 `V8CW7K3BGPBL`, **GV80 Coupe `V8CC7K3BGPBL`** |
| `gv80 coupe 3.5t prestige black-package` | GV80 Coupe `V8CC7K3BGPBL` (correct) |

## 3. Proposed change

One function, one file: `accy_v2/model_lookup/models/manufacture_module.py`, the post-filter inside `search_models_by_description()`.

**Rule after the change:**
- **Model check: always on.** A row whose model name has a sub-variant word (`coupe`) is dropped unless that word was searched.
- **Trim check: unchanged.** Still skipped when a trim, sub-variant or fuel word was searched, exactly as today.

Sketch (final code may differ in naming only):

```python
skip_trim_check = user_requested_fuel_type or bool(search_kw_set & all_discriminators)

def _has_extra_discriminator_keywords(row) -> bool:
    # Model check: always. "gv80" must not return "GV80 Coupe" unless "coupe" was searched.
    model_name = row.get("ModelName", "")
    model_tokens = set(_extract_description_tokens(model_name)) if model_name else set()
    if (model_tokens & model_sub_variant_tokens) - search_kw_set:
        return True
    # Trim check: only when no trim / fuel word was searched (unchanged behaviour)
    if skip_trim_check:
        return False
    desc_tokens = set(_extract_description_tokens(row["Description"]))
    return bool((desc_tokens & trim_discriminators) - search_kw_set)

if not df_filtered.empty and (model_sub_variant_tokens or not skip_trim_check):
    df_filtered = df_filtered[~df_filtered.apply(_has_extra_discriminator_keywords, axis=1)]
```

The `not df_filtered.empty` guard also fixes a latent issue: `DataFrame.apply(axis=1)` on an empty frame returns a DataFrame, not a boolean Series.

**Not changed:** the trim check logic, config files, the search engine's scoring and narrowing, other OEMs' configs.

## 4. Who is affected

| OEM | `model_sub_variant_tokens` set? | Expected change |
|---|---|---|
| Genesis | yes (`coupe`) | GV80 Prestige / Prestige Black rows lose `V8CC7K3BGPBL` (2026, 2027) |
| Hyundai | no | none |
| Mazda | no (doesn't use model lookup) | none |
| Mitsubishi | no | none |
| VW (`source_code/VW`) | doesn't call this function | none |

Expected Genesis numbers: the GV80 sheet loses one exploded row per affected source row (2026 and 2027, Prestige and Prestige Black, EN and FR). Nothing else in Genesis should move, the GV80 Coupe sheet included.

## 4a. Review: how vehicle configuration feeds this filter (2026-11-24)

**Config inputs to the filter:**

| Input | Defined in | Set for |
|---|---|---|
| Sub-variant words (`coupe`) | `model_sub_variant_tokens`, `oems/<oem>/config/enrichment.yaml` | Genesis only |
| Trim words (`prestige`, `advanced`, …) | TRIM / TRIM_VARIANT entries, `model_lookup/configs/<make>/classification.yaml` | every make |
| Fuel words (`electric`, `hybrid`, …) | `fuel_type_keywords` in enrichment.yaml (or built-in list) | every make |
| Filter runs at all | keyword vocabulary `model_lookup/configs/<make>_keywords.json` (rewritten on ADS refresh) | every make |

**Findings:**
- **Only one model line in the vehicle DB has a sub-variant word:** `GV80 Coupe` (2025–2027). No Hyundai, Mazda, Mitsubishi or Honda model name contains `coupe`.
- **Hyundai and Mitsubishi** pass their config to the same function but have no `model_sub_variant_tokens`. With an empty set, the new code runs the filter under exactly the old condition, so their results can't change.
- **Mazda** doesn't use the model lookup (0 searches).
- **`model_lookup/core/search.py`** has its own, older copy of the trim filter with no sub-variant concept. No pipeline uses it, so it's unaffected.
- **VW** (`source_code/VW`) has `coupe` in its own classification config but doesn't call this function.
- **The GV80 Coupe sheet** searches include `coupe` (and `electric`, from `e-sc`), so the always-on guard keeps the Coupe rows there.
- **Future data:** a source sheet for a Coupe trim that doesn't say "coupe" would now return nothing instead of a wrong GV80 match, and gets reported as NOT_FOUND. That's the intended direction.
- **Config caution for later:** whatever goes in `model_sub_variant_tokens` now always removes model lines containing that word unless it's searched. Words that are also fuel types (`hybrid`, `electric`) or single letters (`n`) shouldn't be added without a test. For example, `hybrid` would remove `Tucson Hybrid` from any search that doesn't literally contain "hybrid", including ones where the hybrid fuel type is implied by a config rule.

**Replay check:** every real search from the latest inputs was run through both the current and the proposed filter (Genesis 87, Hyundai 156, Mitsubishi 62, Mazda 0). **4 results differ, all intended:**

| Year | Keywords | Current | Proposed |
|---|---|---|---|
| 2026 | gv80 3.5t prestige | GV80 `…GP00`, GV80 `…GPBL`, Coupe `V8CC7K3BGPBL` | GV80 `…GP00`, GV80 `…GPBL` |
| 2026 | gv80 3.5t prestige black-package | GV80 `…GPBL`, Coupe `V8CC7K3BGPBL` | GV80 `…GPBL` |
| 2027 | gv80 3.5t prestige | same pattern as 2026 | GV80 codes only |
| 2027 | gv80 3.5t prestige black-package | same pattern as 2026 | GV80 code only |

## 5. Tests

1. **Unit test** (new, `accy_v2/model_lookup/tests/test_model_sub_variant_guard.py`), using a small temporary CSV, so it doesn't depend on the live DB:
   - `gv80 prestige` → GV80 rows only (the case fixed here).
   - `gv80 coupe prestige` → Coupe row only.
   - `gv80` with no trim word → Coupe still excluded, trim check still applied (unchanged).
   - No `model_sub_variant_tokens` configured → same result as today.
   - Search that filters everything out → empty result, no crash.
   - Run directly by path: the existing `model_lookup/tests` files fail to import on `dev` (known, separate issue).
2. **Pipeline test:** all four OEMs on `dev` and on the branch with the same inputs; output compared cell by cell and DQ compared by rule. Pass = only the Genesis GV80 rows in section 4 change.

## 6. Steps

1. ✅ Create branch `fix/genesis-gv80-coupe-leak` from `dev`.
2. ✅ Write this plan.
3. ⏳ **Your review of this plan.**
4. Make the change and the unit test; commit on the branch.
5. Run the four-OEM comparison; report results.
6. On your approval: CHANGELOG entry, merge `--no-ff` into `dev`, push, delete the branch.

## 7. Out of scope (noted, not fixed here)

- Hyundai has similar model-line pairs (e.g. Elantra / Elantra N, Santa Fe / Santa Fe Hybrid) but doesn't use `model_sub_variant_tokens`. Whether any of them leak the same way hasn't been checked; worth a separate look.
- Genesis DB rows label the 3.5T e-SC (a combustion engine with an electric supercharger) as `engine_type: electric`. That's how the ADS data comes; the search relies on it for the G90 / GV80 Coupe e-SC lookups, so it stays as is.
