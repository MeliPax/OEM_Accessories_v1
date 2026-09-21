# Plan: Package Column as Vehicle Differentiator + Related Search-Correctness Fixes

**Status:** Approved and documented for implementation.  
**Date Documented:** 2026-08-28  
**Scope:** 4 interconnected fixes to search engine and duplicate-code detection.

---

## Context

Pipeline DQ analysis of Hyundai's 2026 run surfaced a search failure: "Palisade Calligraphy HEV"
found zero results even though two matching DB rows exist (`PAHW7G2DULCH`, base and "NHL Special
Edition"). Root cause: both rows share the same `ModelNumber` but differ in `Package` (480299 vs
481523) and in description wording ("NHL Special Edition"); the search engine's duplicate-code
merge logic couldn't reconcile them and returned `None`.

A prior quick fix added `PACKAGE` to `ignore_keyword_categories` so the two rows would normalize
to the same key and merge — but this was flagged as risky (verified: 121 model numbers in the
Hyundai DB legitimately repeat across multiple package variants) and replaced with a better
approach: **use the actual `Package` DB column as an explicit differentiator** instead of hiding
it, and **surface `Package` in the final output** (following the pattern Mitsubishi already uses)
so downstream users can tell package variants apart.

While designing this, two more issues surfaced in the same functions (confirmed against live DB
data, not hypothetical):

1. **TRIM narrowing regression** (self-inflicted, from an earlier fix this session): changing
   exact TRIM-set matching to subset matching (to let "Calligraphy" match "Ultimate Calligraphy")
   also makes bare `"GT"` match `"GT"` + `"GT Premium"` + `"GT NOIR"` together (Mitsubishi
   Outlander), and bare `"Preferred"` match `"Preferred"` + `"Preferred +"` (Hyundai IONIQ 9), and
   bare `"N-Line"` match `"N-Line"` + `"N-Line Ultimate"` (Hyundai Kona) — confirmed live in the
   DB. The fix needs both behaviors: exact match when a bare-trim row exists, subset match only as
   a fallback when it doesn't.

2. **`exclude_ev` default filter only checks `TrimName`/`Description`**, not `ModelName` or
   `engine_type`. For Hyundai, fuel type is usually signaled only in `ModelName` ("Santa Fe
   **Hybrid**") and `engine_type` ("hybrid") — not repeated in `TrimName`/`Description`. Confirmed
   live: searching `Hyundai 2026 "Santa Fe" "Luxury"` (no fuel keyword) silently returns the
   **Hybrid** variant, because Santa Fe 2026 has no gas "Luxury" trim and the filter never sees
   "hybrid" in the columns it checks. This is the same gap the `'ice'` keyword handling added
   earlier this session already had to work around with its own ad hoc multi-column check.

All four fixes touch the same two functions (`search_engine.py`'s `search()`,
`manufacture_module.py`'s `search_models_by_description()`) that are already being modified for
the Package work, so they're addressed together rather than left as known regressions in code
being actively rewritten.

---

## Fix 1 — Package as an explicit differentiator (the core ask)

**File:** `accy_v2/model_lookup/search_engine.py`

Replace the two separate branches that currently handle `candidate_count > 1` — "duplicate code
merge" (lines ~224-258, matches on normalized description only) and "unique-model-number variant
handling" (lines ~260-287, matches on `ModelNumber` uniqueness only) — with **one unified
grouping pass** keyed on `(normalized_description, Package value)`:

- Rows sharing both the same normalized description *and* the same `Package` value are true
  duplicate DB rows (e.g., legacy/current part-number pairs for the identical config) → collapsed
  to one entry. **Every time this collapse happens, it must be flagged in the DQ report** (see
  "DQ logging" below) so data stewards can see which raw `ModelNumber`s were treated as duplicates
  of each other and confirm that's correct rather than a data-entry mistake in the source DB.
- Rows sharing the same normalized description but **different** `Package` values (the Palisade
  Calligraphy case) are genuine package variants → **all returned**, each tagged with its own
  `ModelNumber` and `Package`.
- Rows with different normalized descriptions (transmission variants like TCR Manual/DCT, fuel
  variants like HEV/PHEV) already form separate groups naturally, same as today.

`SearchResult` gets a new `packages: List[Optional[str]]` field parallel to `model_numbers` (index
`i` of `packages` is the package for `model_numbers[i]`). The existing scalar `package` field is
kept for backward compatibility, set to `packages[0]`.

`SearchResult` also gets a new `collapsed_duplicates: List[Dict]` field — one entry per group that
had more than one raw DB row collapse into it (true duplicate: same normalized description *and*
same `Package`), each entry recording `{"model_numbers": [...], "package": ..., "description": ...}`.
Empty list when no collapsing occurred. This is what powers the DQ logging below.

**Which DB column is the differentiator — config-driven, not hardcoded:** the grouping key reads
the column name from OEM config rather than a literal `"Package"` string in Python:
`oem_rules.get("package_differentiator_column", "Package")`. Add
`package_differentiator_column: Package` under `model_lookup.brands.<Brand>` in
`accy_v2/oems/hyundai/config/enrichment.yaml` and `accy_v2/oems/genesis/config/enrichment.yaml` —
same pattern already used for `trim_column_name`, `fuel_type_keywords`, etc. in these files. The
Python-level default (`"Package"`) only applies to OEMs that don't set the key, preserving current
behavior for Mitsubishi/Mazda/Honda (out of scope for this pass).

**Verified against real data this won't regress current behavior:**
- Elantra N TCR (Manual/DCT): different `ModelNumber` *and* different `Package` (480295/480296) →
  still 2 separate variants.
- Venue Essential (base / "W/two-Tone"): different `ModelNumber` *and* different `Package`
  (480300/480301) → still 2 variants returned — and as a side benefit, each now carries its own
  correct `Package` instead of both being mislabeled with row-0's package as today.
- All 121 Hyundai model numbers that legitimately repeat across package variants: same
  `ModelName`/`Drivetrain`/`engine_type` in every case (confirmed via DB scan) — package is purely
  an additional trim option, never a different vehicle, so grouping by it is safe.

**Downstream:** `accy_v2/oems/hyundai/config/enrichment.yaml` and
`accy_v2/oems/genesis/config/enrichment.yaml` — remove `PACKAGE` from `ignore_keyword_categories`
(revert the earlier quick fix; back to `INTERIOR`, `EXTERIOR_COLOR`, `ENGINE_SPEC` only, matching
Honda/Mitsubishi's existing pattern). Package differentiation now happens via the raw `Package`
column value, not by hiding PACKAGE-category description tokens.

---

## Fix 2 — Carry `package` through enrichment and into the final output (config-driven, no hardcoding)

**File:** `accy_v2/oems/hyundai_genesis/pipeline/step4_5_model_enrichment.py`

- `_batch_lookup_model_numbers()`: alongside the existing `model_mapping[trim] = result.model_numbers`,
  add `package_mapping[trim] = result.packages`, returned as a third dict.
- `_add_model_number_columns()`: map `df["package"] = df[trim_col].map(package_mapping)`, then
  explode `model_number` and `package` together — `df.explode(["model_number", "package"], ignore_index=True)`
  (pandas 2.3, installed here, supports multi-column explode; keeps each model number paired with
  its correct package instead of the two lists desyncing).

**DQ logging for collapsed duplicates:** in `_batch_lookup_model_numbers()`, immediately after
`result = engine.search(...)`, if `result.collapsed_duplicates` is non-empty, log one DQ entry per
collapsed group (new rule name, following the existing `*_rule` naming convention used throughout
this file — `model_number_lookup_rule`, `csv_uniqueness_rule`, etc.):
```python
for dup in result.collapsed_duplicates:
    dq_logger.log_warning(
        sheet_name=group_key,
        model_name=model_name,
        record_index=None,
        record_snapshot={"trim": trim, "package": dup["package"], "description": dup["description"]},
        rule_violated="duplicate_model_code_rule",
        issue_description=(
            f"[DUPLICATE_MODEL_CODE] {vehicle_make} {year} {trim}: Multiple DB rows "
            f"({dup['model_numbers']}) share identical description and Package ({dup['package']}) "
            f"and were collapsed into one entry — verify this is a legitimate old/new part-number "
            f"pair, not a data-entry duplicate in the source DB."
        ),
    )
```
This surfaces every collapse in the `_Data_Issues` output sheet (already rendered from `dq_logger`
records via `downstream.yaml`'s `_Data_Issues` sheet definition — no output-schema change needed,
`IssueCategory`/`IssueDescription` columns already exist there) so data stewards can review and
confirm each one rather than have it silently disappear into a merged row.

**Output column — config-driven, following the exact pattern Mitsubishi already uses (per your
instruction to check that first, and to keep this fully config-driven with no hardcoded
columns):** `accy_v2/core/helpers/output_column_mapper.py` already renames/filters output columns
purely from `downstream.yaml`'s `columns:` list (`source_column` → `output_column`) — confirmed no
code changes needed there. Mitsubishi's `downstream.yaml` already has:
```yaml
- output_column: Package
  source_column: package
  data_type: string
  width: 12
  description: "ADS numeric style ID from vehicle database"
```
Add the identical entry (both `Accessories_EN` and `Accessories_FR` sheets, positioned after the
`Model` column entry, same as Mitsubishi) to:
- `accy_v2/oems/hyundai/config/schemas/downstream.yaml`
- `accy_v2/oems/genesis/config/schemas/downstream.yaml`

This is the only change needed to make `Package` appear in the final Excel output — no Python
code touches column lists.

---

## Fix 3 — TRIM narrowing: exact match first, subset match as fallback

**File:** `accy_v2/model_lookup/search_engine.py`, step 5.5 (TRIM token-set narrowing)

Change the narrowing loop to try exact-set matches first; only fall back to subset matches when no
candidate is an exact match:
```python
exact_matches = [row for ... if candidate_trim_set == searched_trim_set]
narrowed = exact_matches if exact_matches else [row for ... if searched_trim_set.issubset(candidate_trim_set)]
```
This restores correct narrowing for bare trims that have their own DB row (`"GT"` excludes `"GT
Premium"`/`"GT NOIR"`; `"Preferred"` excludes `"Preferred +"`; `"N-Line"` excludes `"N-Line
Ultimate"`), while preserving the subset fallback needed for trims like `"Calligraphy"` that have
no bare row of their own (always `"Ultimate Calligraphy"` in the DB).

---

## Fix 4 — `exclude_ev` default filter must check `ModelName` and `engine_type`, not just `TrimName`/`Description`

**File:** `accy_v2/model_lookup/models/manufacture_module.py`, `search_models_by_description()`

Introduce one shared helper and use it in both places that need "does this row indicate a
non-default fuel type" logic. **The columns it scans are config-driven, not hardcoded** — read
from `oem_rules` the same way `fuel_type_keywords` already is, with the current four columns kept
only as the Python-level fallback default:
```python
DEFAULT_FUEL_CHECK_COLUMNS = ["ModelName", "engine_type", "Description", "TrimName"]

def _matches_any_fuel_keyword(df: pd.DataFrame, fuel_keywords: list[str], columns: list[str]) -> pd.Series:
    mask = pd.Series(False, index=df.index)
    for kw in fuel_keywords:
        pattern = build_word_boundary_pattern(kw)
        for col in columns:
            if col in df.columns:
                mask |= df[col].fillna("").str.contains(pattern, case=False, na=False, regex=True)
    return mask
```
Call sites pass `oem_rules.get("fuel_type_check_columns", DEFAULT_FUEL_CHECK_COLUMNS)`.

Add `fuel_type_check_columns` under `model_lookup.brands.<Brand>` in
`accy_v2/oems/hyundai/config/enrichment.yaml` and `accy_v2/oems/genesis/config/enrichment.yaml`,
alongside the existing `fuel_type_keywords` key:
```yaml
fuel_type_check_columns:
  - ModelName
  - engine_type
  - Description
  - TrimName
```
(Same DB-schema columns as the fallback default — writing them out explicitly in YAML for the OEMs
actually being fixed here, rather than relying on the Python default, so the behavior is visible
and editable without a code change if a future OEM's schema differs.)

- Move the existing `fuel_type_keywords` resolution (OEM-configured, translated) earlier in the
  function, before the per-keyword search loop, so both consumers below can share it.
- Replace the current `'ice'` special-case block (added earlier this session) to call
  `~_matches_any_fuel_keyword(df_filtered, fuel_type_keywords, fuel_check_columns)` instead of its
  own separate hardcoded column/keyword scan — removes duplicated logic.
- Replace the default `exclude_ev` block's `TrimName`/`Description`-only check with
  `_matches_any_fuel_keyword(df_filtered, fuel_type_keywords, fuel_check_columns)`.

**Verified this fixes a real, silent correctness bug:** `search_models_by_description("Hyundai",
2026, ['santa fe', 'luxury'])` currently returns the Santa Fe **Hybrid** Luxury row with no
indication it's not a gas trim (Santa Fe 2026 has no gas Luxury trim, and neither `Description`
nor `TrimName` say "hybrid" — only `ModelName` and `engine_type` do). After the fix, this case
correctly returns empty (no gas Luxury Santa Fe exists) instead of silently substituting the
hybrid. It also fixes the Mitsubishi Outlander PHEV leak: `engine_type` says `"plug-in hybrid"` but
`TrimName`/`Description` don't, so the PHEV `"GT"` row was leaking into bare `"GT"` searches.

---

## Files Touched

| File | Change |
|---|---|
| `accy_v2/model_lookup/search_engine.py` | Unified Package-aware duplicate/variant grouping (Fix 1); `packages` field on `SearchResult`; `collapsed_duplicates` tracking (Fix 1); exact-first/subset-fallback TRIM narrowing (Fix 3) |
| `accy_v2/model_lookup/models/manufacture_module.py` | Shared `_matches_any_fuel_keyword()` helper; reordered `fuel_type_keywords` resolution; `'ice'` block and default `exclude_ev` block both use the helper (Fix 4) |
| `accy_v2/oems/hyundai_genesis/pipeline/step4_5_model_enrichment.py` | `package_mapping` parallel to `model_mapping`; explode `["model_number", "package"]` together; DQ-log every `collapsed_duplicates` entry (Fix 2) |
| `accy_v2/oems/hyundai/config/enrichment.yaml` | Remove `PACKAGE` from `ignore_keyword_categories` (revert earlier quick fix); add `package_differentiator_column: Package` and `fuel_type_check_columns: [...]` |
| `accy_v2/oems/genesis/config/enrichment.yaml` | Same revert + same two new keys |
| `accy_v2/oems/hyundai/config/schemas/downstream.yaml` | Add `Package` output column (EN + FR sheets), mirroring Mitsubishi's existing entry |
| `accy_v2/oems/genesis/config/schemas/downstream.yaml` | Same addition |

**No schema changes needed** — `duplicate_model_code_rule` entries render through the existing
generic `_Data_Issues` sheet definition (`IssueCategory`/`IssueDescription` columns already handle
arbitrary `rule_violated` values, same as `model_number_lookup_rule` does today).

**No changes to:** `output_column_mapper.py` (already fully YAML-driven), `base_pipeline.py`,
Mitsubishi/Mazda/Honda config or code.

---

## Verification

1. **Unit-level, isolated `VehicleSearchEngine.search()` calls** (no pipeline run needed):
   - Palisade Calli HEV → 2 results, `model_numbers=['PAHW7G2DULCH','PAHW7G2DULCH']`,
     `packages=[480299, 481523]` (previously: `None`).
   - IONIQ 9 bare "Preferred" → only the bare `Preferred` row, not `Preferred +`.
   - Kona bare "N-Line" → only bare `N-Line`, not `N-Line Ultimate`.
   - Mitsubishi Outlander bare "GT" → resolves to exactly the gas `GT` row (PHEV `GT` excluded by
     Fix 4, `GT Premium`/`GT NOIR` excluded by Fix 3).
   - Hyundai Santa Fe "Luxury" (no fuel keyword) → empty (no gas Luxury trim exists), not the
     Hybrid row.
   - Elantra N TCR, Venue Essential: unchanged result sets, now with correct per-row `Package`.

2. **Full pipeline run:** `python accy_v2/run_hyundai.py`, then `python accy_v2/run_genesis.py`.
   - Confirm the `2026_palisade` DQ warning for "Calli HEV" is gone.
   - Open the output `.xlsx`, confirm a `Package` column is present and populated on both
     `Accessories_EN`/`Accessories_FR` sheets, and that Palisade Calligraphy rows show two
     distinct package values.
   - Re-check total DQ warning count vs. the current baseline (was 10 model-lookup warnings before
     this pass) — expect it to drop further; remaining ones should all be genuine data gaps
     (confirmed absent from the DB, e.g. Elantra XRT 2026, IONIQ 5 N 2026).

3. **Regression check:** run Mitsubishi's pipeline once — no code paths specific to Mitsubishi
   change, but it shares `search_models_by_description()`/`search_engine.py`, so a clean run with
   no new DQ warnings confirms no regression.

---

## Rollback Plan

If issues are discovered after implementation:
1. Revert `PACKAGE` back to `ignore_keyword_categories` — restores old behavior (strict duplicate
   merging, Package column still in output).
2. Revert `search_engine.py` changes — back to old duplicate detection and TRIM matching.
3. Remove `Package` from `downstream.yaml` if end users don't need it in output.
4. Revert `manufacture_module.py` to pre-fix state.

All changes are **isolated** to their respective files and reversible.
