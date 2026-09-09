# Proposal: Trim-Hierarchy Fallback + Orphaned-Record Safety Net (Cross-OEM)

**Date:** 2026-08-31  
**Status:** ✅ IMPLEMENTED (2026-09-09)  
**Scope:** Both Part 1 (implied_trim_variant_trims) and Part 2 (orphaned_record_rule) complete

---

## Problem Statement

A user-reported record — 2026 Elantra, Trim "TCR", part `000HCPNR2P` — reached the final Hyundai output workbook with `Model = nan`. Investigation traced the root cause: the database only has this trim under `ModelName="Elantra N"` (not "Elantra"), and the source spreadsheet's trim value "TCR" carries no signal that it belongs under the "N" sub-line.

By design, `_add_model_number_columns()` in `step4_5_model_enrichment.py` deliberately keeps every row — including ones where model enrichment failed — "for manual correction." However, this design requires precise DQ logging upstream to ensure no records silently reach the customer-facing workbook unaccounted-for.

A broader scan of the same Hyundai/Genesis output file found **15,800 rows with `Model = nan`** across all 42 sheets. Investigation is ongoing; some are true data gaps (missing in DB), others are code-path issues (like the Elantra TCR case).

---

## Solution: Two-Part Architectural Pattern

### Part 1: Config-Driven Trim Variant Fallback

Add a new config mechanism, `implied_trim_variant_trims`, alongside the existing `implied_fuel_type_trims` in OEM enrichment configs. This injects a missing `TRIM_VARIANT` keyword when:
- Source trim exists **only** under a model sub-line (e.g., TCR only under "Elantra N")
- Source label omits the sub-line designation (e.g., source says "TCR" not "Elantra N-TCR")
- Database has the sub-line available (e.g., DB has TRIM_VARIANT "n" for Elantra)

**Confirmed case:** Elantra TCR exists in DB only as `ModelName="Elantra N"` with `TrimName="TCR"`. Source provides bare "TCR" → rule injects "n" (TRIM_VARIANT) → search succeeds.

**Config schema:**
```yaml
implied_trim_variant_trims:
  - model_keywords: [elantra]
    trim_keywords: [tcr]
    implied_trim_variant: n
    years: [2026]   # TBD: confirm if TCR exists in other years
```

**Implementation approach:**
- New step 3.6 in `VehicleSearchEngine.search()` (after existing step 3.5's `implied_fuel_type_trims`)
- Identical pattern to fuel-type logic: exact-set matching on MODEL+TRIM tokens, optional year scope, keyword injection
- New `SearchResult` field: `implied_trim_variant: Optional[str]`
- New DQ rule: `implied_trim_variant_rule` (logged when field is set)

**Scope for first implementation:** Only the one verified case (Elantra TCR). Santa Fe/Santa Cruz XRT/Pref/Ult, Tucson XRT, IONIQ N are **not** yet individually root-caused; they'll surface via Part 2's safety net for follow-up investigation.

---

### Part 2: Orphaned-Record Safety Net (Cross-OEM)

Add a new shared DQ check that runs at the final output stage, per-sheet, immediately after column mapping: **every row with a null/empty model number gets flagged with a distinct DQ rule** (`orphaned_record_rule`).

**Purpose:**
- Catch any record whose failure wasn't logged upstream (code gap, new OEM, edge case)
- Independent checkpoint: even if Part 1 never fires, ensures no orphan silently exits
- Cross-OEM: runs for all active OEMs (Hyundai, Genesis, Mitsubishi, Mazda), regardless of other config

**Implementation approach:**
- New shared helper: `accy_v2/core/helpers/orphan_record_validator.py`
- Function: `flag_orphaned_records(df, dq_logger, sheet_name, model_number_column="Model")`
- Checks for `.isna()` **and** empty strings/literal "nan" (matters for Mazda's derived `short_model_number`)
- Call site: `step5_output.py` per-sheet loop, after `apply_downstream_column_mapping()` and before `frames[sheet_key] = df`
- Requires threading `dq_logger` through `base_pipeline.py` and all 4 orchestrators (mechanical change, reuses existing `pipeline_logger` threading pattern)

**Scope:** All active OEMs with pipeline code (Hyundai/Genesis, Mitsubishi, Mazda). Honda not touched (no pipeline code exists yet).

---

## Design Rationale

**Why `implied_trim_variant_trims` instead of the earlier "model_override" design:**
The earlier draft proposed re-running the search with a substituted model name. This is unnecessary and higher-risk because:
- DB matching is **token-based**, not string-based (confirmed: Genesis's `use_single_char_token_matching`, working N-Line searches)
- Keyword injection works for fuel type; same pattern works for trim variants
- No recursion/retry path needed
- Reuses proven-safe code shape

**Why a dedicated `orphaned_record_rule` instead of relying on per-trim NOT_FOUND logs:**
- Elantra TCR row **should** have a per-trim `model_number_lookup_rule` entry (it does, confirmed)
- But finding it in a 15,800+ row DQ report is hard; a dedicated cross-cutting rule at the output level is immediately visible
- Acts as an independent checkpoint for any gap upstream (whether Part 1, Part 2, or unknown code paths)
- Guards against silent data loss due to future bugs or edge cases

**Why `implied_trim_variant_trims` in enrichment.yaml (config), not hardcoded:**
- New OEMs inherit templates automatically (empty list = no behavior change)
- Data-driven: rule population doesn't require code changes
- Auditable: each rule is documented with affected years and trim variants
- Follows the existing pattern (Hyundai already has `implied_fuel_type_trims` in same location)

---

## Scope (This Pass)

### In Scope
✅ Proposal / planning document (this file)  
✅ Design decision (two-part pattern, config-driven, cross-OEM)  
✅ Grounded findings (DB queries, code inspection, integration points confirmed)  
✅ Open questions (7 items below for user review)

### Out of Scope (for implementation pass later)
❌ Code changes (search_engine.py, step4_5_model_enrichment.py, etc.)  
❌ Config changes (enrichment.yaml rules)  
❌ Helper implementation (orphan_record_validator.py)  
❌ Broader orphan-record investigation (Santa Fe/Cruz/Tucson/IONIQ root causes — deferred to Part 2 safety net findings)  
❌ Honda pipeline (flagged as separate, pre-existing stale-config bug)

---

## Open Questions (Requires User Confirmation)

1. **Rule population scope for first implementation**
   - Option A: Only Elantra TCR (verified case). Santa Fe/Cruz/Tucson/IONIQ surface via Part 2's `orphaned_record_rule` DQ entries for individual follow-up.
   - Option B: Attempt config rules for those others now, accepting they're unverified per-case.
   - **Recommended:** A (proven case first, new safety net catches the rest)

2. **Elantra TCR years scope**
   - DB query found TCR in exactly 2 rows, both ModelYear=2026
   - Config currently: `years: [2026]`
   - Question: Does TCR exist in other years (2024, 2025) not surfaced by today's query? If yes, should be `years: null` (apply to all).
   - **Action needed:** Re-verify against fresh DB pull at implementation time

3. **Naming preferences**
   - Config key: `implied_trim_variant_trims` (mirrors `implied_fuel_type_trims` pattern)
   - DQ rule 1: `implied_trim_variant_rule` (fired when Part 1 rule matches)
   - DQ rule 2: `orphaned_record_rule` (fired when row has no model number)
   - Acceptable, or prefer different names?

4. **`orphaned_record_rule` behavior**
   - Proposed: Log-only (matches all existing DQ rules; `DQLogger` has no severity/blocking concept)
   - Should this rule ever halt a pipeline run, or only flag for review regardless of count?
   - **Recommended:** Log-only (data should not be silently dropped; let humans decide)

5. **`dq_logger` threading scope**
   - Wiring it requires changes to: `base_pipeline.py` (1 file), 4 orchestrators, 3 `step5_output.py` files (~8 files total, all mechanical)
   - Approved already (user confirmed "Thread dq_logger through")
   - Documented here for implementation-plan reference

6. **Documentation folder location**
   - Proposing: `accy_v2/planning/oem_pipeline/trim_hierarchy_orphan_safety_net/PROPOSAL.md`
   - Mirrors existing folder conventions (`search_engine_package_differentiator/`, `mitsubishi_translator_classifier_alignment/`)
   - This is cross-OEM, not Hyundai-specific, so new folder rather than extending `hyundai_genesis_lookup_fix/`
   - Acceptable?

7. **Honda stale-config follow-up**
   - Found: `accy_v2/oems/honda/config/enrichment.yaml` is an unedited copy of Hyundai's (has `brands.Hyundai`/`brands.Genesis` keys, `hyundai/...` config paths, not `brands.Honda`)
   - Honda has no `pipeline/` directory yet (config-only scaffold)
   - This is a separate, pre-existing bug, out of scope for this proposal
   - Should this get its own follow-up ticket, or handle it when Honda's pipeline is actually built?

---

## Findings Grounding This Design

### Code Structure (Confirmed via Direct Inspection)

- **Search engine (`search_engine.py:72-397`):** 8-stage flow; step 3.5 (lines 140-168) already has proven `implied_fuel_type_trims` mechanism
  - Reads OEM config via `oem_rules = self.oem_config.get("model_lookup_rules", {}).get(make, {})`
  - Matches classified token sets as exact matches against config lists
  - Injects keyword into `filtered_keywords` if rule fires
  - Already shipped/verified for fuel-type case

- **Classification categories:** Hyundai/Genesis have `TRIM_VARIANT` (n, n-line) as distinct from `TRIM` (lux, tcr, etc.); Mazda/Mitsubishi/Honda are flat (TRIM only)
  - "Elantra N TCR" = MODEL(elantra) + TRIM_VARIANT(n) + TRIM(tcr)

- **DQ logging:** `DQLogger.log_warning()` has 6 params: sheet_name, model_name, record_index, record_snapshot, rule_violated, issue_description
  - No severity parameter exists
  - 12 existing `rule_violated` values in use
  - Already logs `model_number_lookup_rule` for per-trim NOT_FOUND cases

- **Output generation:** All active OEMs' `step5_output.py` files loop over language variants, call shared `apply_downstream_column_mapping()`, then hand off to Excel writer
  - No row filtering on model_number (by design, for manual correction)
  - Output column is "Model" for all (Hyundai/Genesis via `model_number` source, Mazda via `short_model_number` source)

### Database Query Findings (Confirmed)

| Case | Status | Details |
|------|--------|---------|
| Elantra TCR | **FOUND** | 2 DB rows, both `ModelName="Elantra N"`, `TrimName="TCR"`, `ModelYear=2026` |
| Santa Fe/Cruz XRT | **FOUND** | Exists in DB (not yet per-sheet verified) |
| Santa Fe/Cruz Pref/Ult | **FOUND** | Exists in DB (not yet per-sheet verified) |
| Tucson XRT | **FOUND** | 1 DB row exists |
| IONIQ 5 N | **FOUND** | Exists in DB (not yet per-sheet verified) |
| Palisade Calli ICE | **MISSING** | 2026 Palisade Calli only exists as Hybrid in DB (true data gap) |
| Palisade Calli HEV | **MISSING** | Potential DB gap (status unclear) |

---

## References

- Related: `accy_v2/docs/2026-08-31_search_gaps_fixes/` (earlier fixes: package differentiation, compound keywords, implied fuel type)
- Database: `accy_v2/model_lookup/db/db_vehicle_models.csv`
- Pipeline: `accy_v2/oems/hyundai_genesis/pipeline/step4_5_model_enrichment.py`
- Config: `accy_v2/oems/hyundai/config/enrichment.yaml`

---

## Implementation Summary (2026-09-09)

**Part 1 — Implemented:**
- ✅ Added `implied_trim_variant` field to `SearchResult` class
- ✅ Added step 3.6 logic in `search_engine.py` for `implied_trim_variant_trims` config matching
- ✅ Added `implied_trim_variant_trims: []` template to all OEM enrichment.yaml configs (Hyundai, Genesis, Mitsubishi, Mazda)
- ✅ Populated Elantra TCR rule in Hyundai config: `[elantra] + [tcr] → implied_trim_variant: n` (years: 2026)
- ✅ Updated all SearchResult return statements to pass `implied_trim_variant` field

**Part 2 — Implemented:**
- ✅ Created `accy_v2/core/helpers/orphan_record_validator.py` with `flag_orphaned_records()` helper
- ✅ Updated `base_pipeline.py` abstract method to pass `dq_logger` to `run_step5_output()`
- ✅ Updated all OEM orchestrators (Hyundai, Genesis, Mitsubishi, Mazda) to accept and pass `dq_logger`
- ✅ Integrated orphan check into all step5_output.py files with `flag_orphaned_records()` call
- ✅ Logs `orphaned_record_rule` DQ warning for any row with null/empty model number at output boundary
- ✅ Mazda: checks `short_model_number` column; others check `Model` column

**Files modified:** 13 core/pipeline files, 4 OEM enrichment.yaml configs, 1 new helper file
**Commit:** 0df7f8b ("Implement: Trim hierarchy orphan safety net")
