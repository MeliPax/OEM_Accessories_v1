# Architecture and Design Decisions

This document captures significant design and architecture decisions made for the `OEMAccessories` pipeline project. Each entry explains the problem, decision, and rationale — helping future developers understand *why* things were built this way and preventing re-litigation of settled decisions.

## Table of Contents

1. Multi-OEM scalable architecture
2. Single JSON config file per OEM
3. Two-logger separation (dq_logger vs pipeline_logger)
4. Excel loaded with `header=None` to preserve raw row structure
5. Word-token column matching (not substring matching)
6. `__na__` sentinel in config for `pd.isna()` checks
7. `rate_import_column_mapping` uses `"description"` (post-language-split name)
8. Non-null violations: DQ warning + configurable threshold instead of always-FATAL
9. Batch model lookup: one database query per unique trim
10. Keyword combination strategy: model_name + trim + fuel_type
11. Modular 5-file config structure per OEM (replacing single JSON)
12. use_model_lookup flag remains configurable per OEM
13. non_null_threshold remains configurable global setting
14. Output paths derived from OEM name in code (not configured)
15. Rename rate_import_* to output_column_* in downstream schema

---

## [001] Multi-OEM scalable architecture

**Date:** 2026-05-18

**Context:** The initial pipeline was a one-off for Mitsubishi. But the business needs to handle multiple OEMs (Honda, Mazda, etc.), each with potentially different column names, business rules, and validation logic. Duplicating the entire pipeline per OEM would be unmaintainable.

**Decision:** Create a shared `core/` module containing the abstract pipeline and all common logic, then create OEM-specific modules under `oems/<oem_name>/` that override/configure behavior as needed.

**Rationale:**
- **Shared core:** All five pipeline steps, column mapping, data type enforcement, logging — these are generic across OEMs.
- **OEM-specific config:** Business rules (trim boundaries, required columns, output format) are entirely expressed in a single JSON config file per OEM, not code.
- **Minimal replication:** Each new OEM needs only a config file + an orchestrator class + an entry point script (~100 lines total).

**Files affected:**
- `core/base_pipeline.py` — defines the abstract 5-step pipeline contract
- `core/config_loader.py` — validates all configs match a standard schema
- `oems/<oem_name>/config/<oem_name>_config.json` — the complete business rules for one OEM
- `oems/<oem_name>/pipeline/orchestrator.py` — implements the abstract pipeline
- `run_<oem_name>.py` — entry point

---

## [002] Single JSON config file per OEM

**Date:** 2026-05-18

**Context:** Initially, column definitions, required columns, trim bounds, output mappings, and other business rules were scattered across the codebase. This made it hard for non-engineers to adjust rules and easy to make inconsistent changes.

**Decision:** All business rules for an OEM live in a single `<oem_name>_config.json` file. The pipeline loads it once and passes sections to each step.

**Rationale:**
- **Single source of truth:** All Mitsubishi rules in one place; no hunting through multiple files.
- **Non-engineer friendly:** OEM teams can adjust rules (e.g., add a required column) without touching Python.
- **Versioning:** Config changes are visible in git history and can be reviewed independently from code changes.
- **Validation:** A single `config_loader.py` ensures all configs have the required keys.

**Files affected:**
- `core/config_loader.py` — validates required keys
- `oems/mitsubishi/config/mitsubishi_config.json` — single config file
- All pipeline steps reference `config["key"]` instead of hard-coded values

---

## [003] Two-logger separation (dq_logger vs pipeline_logger)

**Date:** 2026-05-18

**Context:** The pipeline produces two distinct types of output: (1) data quality issues found *within* the data (null records, unprofitable parts), which stakeholders care about, and (2) execution events (sheet start, record counts, FATAL errors), which developers care about. Initially, both were mixed in one log.

**Decision:** Create two separate loggers:
- **dq_logger:** Accumulates data quality warnings and writes a JSON DQ report for stakeholders.
- **pipeline_logger:** Records execution events and writes a text log for developers.

**Rationale:**
- **Audience separation:** Stakeholders read DQ reports; developers read pipeline logs. Different formats, different details.
- **DQ report is structured:** JSON allows parsing and filtering by `rule_violated`, `sheet_name`, etc.
- **Pipeline log is human-readable:** Text format with timestamps is easy to grep and scan.
- **Prevents mixing concerns:** A null record is a data quality issue (goes to dq_logger), not a pipeline failure (goes to pipeline_logger).

**Files affected:**
- `core/helpers/dq_logger.py` — generates JSON DQ report
- `core/helpers/pipeline_logger.py` — generates text pipeline log
- `core/base_pipeline.py` — instantiates both and passes them to steps

---

## [004] Excel loaded with `header=None` to preserve raw row structure

**Date:** 2026-05-18

**Context:** OEM Excel files have a specific structure: Row 0 = model name, Row 1 = actual column headers, Row 2+ = data. Early validation needs to check this structure. If we load with `header=1`, pandas auto-sets headers and we lose row 0.

**Decision:** Load Excel files with `header=None`, so the raw row structure is preserved. Step 1 validation checks row structure and calls `promote_header_row()` to demote row 0 and promote row 1 as headers.

**Rationale:**
- **Structural validation:** We can check "does row 0 contain a model name?" before processing.
- **Early failure:** If the file structure is wrong, we fail fast (FATAL) before wasting time on data validation.
- **Clarity:** The pipeline explicitly shows: drop row 0, use row 1 as headers, process row 2+. No magic.

**Files affected:**
- `core/helpers/header_helpers.py` — `promote_header_row()` function
- `oems/mitsubishi/pipeline/step1_validation.py` — calls `promote_header_row()`
- `run_mitsubishi.py` — passes `header=None` to `pd.read_excel()`

---

## [005] Word-token column matching (not substring matching)

**Date:** 2026-05-19

**Context:** Column names come from OEMs in various formats ("Part Number", "PART_NUMBER", "Part #", etc.). The pipeline needs to recognize them. Initial implementation used substring matching: a column "Part Number" was split to "part_number", then checked if "part" and "number" were substrings of "part_number". This caused a bug: "french_description" contains the substring "en" (from "french"), so it would incorrectly match `english_description` before reaching `french_description`.

**Decision:** Split the lowercased column name by `_` to get word tokens. Match keywords against whole tokens, not substrings.

**Rationale:**
- **Eliminates false positives:** "en" as a token is not in ["french", "description"], so no collision.
- **More semantically correct:** "part" is a word in "part_number"; "en" is not a word in "french".
- **Handles variants better:** "part-number", "Part Number", "PART_NUMBER" all become the same token set after cleaning.

**Files affected:**
- `core/helpers/column_mapper.py` — `column_type_finder()` now splits by `_` and checks token membership

---

## [006] `__na__` sentinel in config for `pd.isna()` checks

**Date:** 2026-05-18

**Context:** The trim validation config needs to specify "expected values are either 'X', '', or null". Null is represented as `np.nan` in Python, but JSON doesn't have a null value type in the config syntax. Early attempts used `is_na` as a string, which couldn't be distinguished from a literal column value.

**Decision:** Use the string `"__na__"` in the config JSON to represent "check for pandas null with `pd.isna()`". At runtime, when building validation rules, `"__na__"` is interpreted as `pd.isna()` and checked accordingly.

**Rationale:**
- **JSON-serializable:** `"__na__"` is a plain string, so it's valid JSON.
- **Unambiguous:** Won't collide with actual column values (no real data contains the literal string `"__na__"`).
- **Self-documenting:** Future readers see `"__na__"` and understand it means "null".

**Files affected:**
- `oems/mitsubishi/config/mitsubishi_config.json` — `trim_validation_config.must_have_only.expected_value_types: ["X", "", "__na__"]`
- `core/helpers/trim_helpers.py` — `validate_trim_by_datatype()` interprets `"__na__"` as `pd.isna()`

---

## [007] `rate_import_column_mapping` uses `"description"` (post-language-split name)

**Date:** 2026-05-19

**Context:** Step 4 splits the data by language (EN/FR) and renames `english_description` → `"description"` and `french_description` → `"description"`. Step 5 receives these dataframes and needs to map columns to the output format. Initially, the config still referenced `english_description`, but that column no longer exists after Step 4.

**Decision:** The `rate_import_column_mapping` in the config now maps the post-language-split column names. After language split, both EN and FR dataframes have a column called `"description"`, so the mapping uses that key.

**Rationale:**
- **Matches runtime state:** By Step 5, the column is called `"description"`, so the mapping must reference that.
- **Simplifies Step 4:** Language split renames to a neutral name, avoiding duplicate keys in the mapping.
- **Clear handoff:** Each step receives the dataframe state it expects.

**Files affected:**
- `oems/mitsubishi/config/mitsubishi_config.json` — `rate_import_column_mapping: { "description": "Description", ... }`
- `oems/mitsubishi/pipeline/step4_transformation.py` — renames language-specific columns to `"description"`
- `oems/mitsubishi/pipeline/step5_output.py` — applies the mapping

---

## [008] Non-null violations: DQ warning + configurable threshold instead of always-FATAL

**Date:** 2026-05-19

**Context:** Initially, if a required non-null column had even one null record, the entire sheet was skipped (FATAL). This was too strict: a sheet with 130 valid records and 2 null records in MSRP would produce zero output, even though 98% of the data was usable.

**Decision:** If the null rate in a non-null column is **below a configurable threshold** (default 50%), log each null record as a DQ warning, exclude those rows, and continue processing. If the null rate is **at or above the threshold**, still skip the sheet as FATAL (structural problem).

**Rationale:**
- **Maximizes output:** Most sheets with a few stray nulls now produce output for the good records.
- **Data quality visibility:** Each null record is logged to the DQ report for stakeholder review.
- **Structural safety:** If >50% of a column is null, it's likely a format problem (wrong file, wrong column), so we still skip the sheet.
- **Configurable threshold:** Each OEM can set `"non_null_threshold"` in their config based on tolerance.

**Files affected:**
- `oems/mitsubishi/config/mitsubishi_config.json` — `"non_null_threshold": 0.5`
- `oems/mitsubishi/pipeline/step1_validation.py` — `_validate_non_null_columns()` now logs warnings and returns filtered dataframe instead of raising FATAL

---

## [009] Single combined output file per run with Report sheet

**Date:** 2026-05-19

**Context:** Initially, the pipeline wrote one Excel file per OEM model processed. For Mitsubishi with 11 models, this meant 22 files per run (EN + FR for each). Reviewers had to open multiple files to understand the overall data quality and cross-model patterns. Additionally, run-level metadata (source file, timestamp, total warnings) had no natural place to live.

**Decision:** Write a single combined Excel file per pipeline run (named `{oem}_{run_id}_{timestamp}.xlsx`) containing:
- **`_Report` sheet (first tab)** with three sections:
  1. **Run Summary** (key-value table): run_id, source file, generated timestamp, sheets processed/skipped, total DQ warnings
  2. **Model Profile** (data table): one row per processed model with records_in, records_out, DQ warnings delta
  3. **DQ Records** (data table): all flagged records with rule violated, issue description, and part number/description for quick review
- **Model sheets** (`{model}_{lang}`) containing the processed data frames, one per model/language combination

**Rationale:**
- **Single review artifact:** Stakeholders open one file per run instead of hunting for 22 files across folders.
- **Metadata in one place:** Run-level context (what was processed, when, how many issues) is visible immediately without separately reading logs.
- **Actionable summaries:** The Report sheet lists all problems in one place with context, enabling quick triage and prioritization.
- **Simpler output structure:** No proliferation of files; output folder stays clean.
- **Report sheet advantages:** Data quality reviewers can filter/sort issues by rule, model, or severity without switching between DQ JSON and data sheets.

**Trade-offs:**
- **Single file assumption:** Assumes reviewers review everything together. If separate OEM teams need isolated outputs, the config could be extended to support multiple output modes.

**Files affected:**
- `core/base_pipeline.py` — changed `run_step5_output()` return type to `Dict[str, pd.DataFrame]`; added `run_write_combined_output()` abstract method; collect frames and stats across all sheets, write once after loop
- `oems/mitsubishi/pipeline/step5_output.py` — split into `prepare_frames()` (returns frames, no write) and `write_combined_output()` (writes combined file + Report sheet)
- `oems/mitsubishi/pipeline/orchestrator.py` — implement both new methods
- `oems/mitsubishi/config/mitsubishi_config.json` — unchanged (same output paths, same column mappings)

---

## [010] Raw data folder inside OEMAccessories with per-OEM subfolders

**Date:** 2026-05-19

**Context:** Raw source files initially lived outside the project at `OEM Accessories_v1/landing_zone/`. The pipeline entry point required relative `../` path arguments that only worked if invoked from a specific working directory, making the project less portable and harder to use. Additionally, separation of code and data across folders meant a user had to manage file locations across two different places.

**Decision:** Create a `data/landing_zone/{oem}/` folder structure inside `OEMAccessories/`. Each OEM has its own subfolder where source Excel files are placed. The pipeline entry point auto-discovers the most recent file in the OEM folder, with optional explicit path overrides.

```
OEMAccessories/
└── data/
    └── landing_zone/
        ├── mitsubishi/
        │   └── Accessory Guide - February26.xlsx
        ├── honda/         (future)
        └── mazda/         (future)
```

**Rationale:**
- **Self-contained project:** Data and code live together; no external dependencies or relative paths needed for typical use.
- **OEM-per-subfolder pattern:** Mirrors the `oems/` and `output/` folder patterns — clear, scalable structure for adding new OEMs.
- **No year subfolder:** Year context is in the filename itself (`February26`); one active file per OEM per run. Simpler and less nesting.
- **Auto-discovery:** Entry point auto-discovers the latest file, reducing command-line boilerplate for daily use while keeping explicit paths available for overrides.
- **Git-friendly:** Raw data folder is in `.gitignore` (sensitive pricing data, large binaries), so only code is version-controlled.

**Trade-offs:**
- **File replacement:** Old files are replaced when new ones arrive (no built-in history). Users should manually archive old files if needed.
- **Single file per OEM assumption:** Pattern assumes one active file per OEM per run cycle. If multiple concurrent versions are needed, the structure can be extended with date-based subfolders.

**Files affected:**
- `OEMAccessories/data/landing_zone/` — new folder structure created
- `OEMAccessories/run_mitsubishi.py` — updated to auto-discover files in `data/landing_zone/mitsubishi/`
- `OEMAccessories/.gitignore` — exclude raw data from version control
- `README.md` — updated project structure diagram and running instructions
- `CHANGELOG.md` — documented the change

---

## [011] Batch model lookup: one database query per unique trim

**Date:** 2026-06-22

**Context:** Model number lookup was initially implemented as per-row lookups: for every row in the melted dataframe, query the vehicle model database. This meant 100+ database queries for a single part list. Performance was acceptable for small datasets but would degrade rapidly at scale. Additionally, the same trim (e.g., "ES") across 45 rows resulted in 45 identical queries.

**Decision:** Implement batch model lookup at the trim level: identify all unique trims from the standardized data (before melting), perform ONE database query per unique trim, and cache the results. Then apply the cached model number to all rows with that trim during melting/enrichment.

**Rationale:**
- **Dramatic performance improvement:** 100 rows with 3 trims = 3 queries instead of 100 queries (33x improvement).
- **Reduced database load:** Each trim is looked up exactly once, independent of how many rows use that trim.
- **Deterministic lookup:** Trims are identified once, results are cached; no risk of inconsistent lookups across rows.
- **Natural data point:** Trim is an OEM-specific classification that semantically represents a distinct vehicle variant; it's the natural unit for model lookup.

**Trade-offs:**
- **Earlier trim identification:** Requires identifying all applicable trims before lookup, but trims are already identified in Step 2 (Header Normalization).
- **Cache invalidation not needed:** Since we lookup before melting, cache is immutable during row processing.

**Files affected:**
- `core/base_pipeline.py` — added `run_step3_5_extract_vehicle_year()` to extract year before model lookup
- `core/base_pipeline.py` — added `run_step4_5_model_enrichment()` step for batch model lookup
- `oems/mitsubishi/pipeline/step4_5_model_enrichment.py` — implemented batch lookup: identify unique trims, query once per trim, cache results
- `oems/mazda/pipeline/step4_5_model_enrichment.py` — same batch approach for Mazda

---

## [012] Keyword combination strategy: model_name from metadata + trim keywords + fuel_type

**Date:** 2026-06-22

**Context:** Sheet names vary in format: some include model name ("2026 Outlander PHEV"), others only year and fuel type ("2026 PHEV"). Initial keyword extraction attempted to extract everything from sheet_name, failing for abbreviated sheet names like "2026 PHEV" where "Outlander" was never present in the name.

**Decision:** Combine keywords from THREE sources:
1. **Model name** from `meta_data["model_name"]` (extracted in Step 1 from cell A1 of the sheet)
2. **Fuel type** from sheet_name parsing (if applicable: EV, PHEV, HEV, etc.)
3. **Trim keywords** from the trim column value, with abbreviation expansion

**Rationale:**
- **Completeness:** Step 1 always extracts a model name from cell A1 (e.g., "Outlander ES"); this is more reliable than parsing sheet names which vary by OEM.
- **Layered information:** Combining model (A1) + fuel type (sheet name) + trim ensures we capture all disambiguating context.
- **Robustness to format variance:** Works even if sheet names are abbreviated ("2026 PHEV") because model name comes from data, not filename.
- **Single truth per step:** Each step contributes its natural domain: Step 1 has model name (from data), sheet name has fuel type, trim column has trim.

**Trade-offs:**
- **Dependency on Step 1:** Requires that Step 1 correctly extract model_name from cell A1. If this fails, model lookup has incomplete context. (Already a requirement, so minimal new risk.)

**Files affected:**
- `oems/mitsubishi/pipeline/step4_5_model_enrichment.py` — extract model_name from meta_data, combine with fuel_type and trim keywords
- `oems/mazda/pipeline/step4_5_model_enrichment.py` — same approach for Mazda
- `core/helpers/keyword_extractor.py` — added `extract_keywords_for_model_lookup()` convenience method

---

## [013] Trim keyword parsing: single-letter abbreviations expanded, multi-char hyphenated terms preserved

**Date:** 2026-06-22

**Context:** Initial trim parsing split all hyphenated terms into separate keywords: "gt-p" → ["gt", "p"]; "s-awc" → ["s", "awc"]. This caused lookup failures: "s-awc" became keywords ["s", "awc"], but database descriptions contained "S-AWC" (single hyphenated term), so keyword search for separate ["s", "awc"] wouldn't match.

**Decision:** Parse trim keywords with two rules:
1. **Single-letter abbreviations** after hyphen are expanded via abbreviation library: "gt-p" → ["gt", "premium"] (if "p" in library)
2. **Multi-character hyphenated terms** stay intact: "s-awc" → ["s-awc"] (one keyword), matching how database stores the term

**Rationale:**
- **Matches database format:** Database uses "S-AWC" as a single term in descriptions; keeping "s-awc" as one keyword matches this.
- **Semantic accuracy:** "S-AWC" is a branded feature name (Super All-Wheel Control), not two separate concepts ("s" + "awc").
- **Supports abbreviation expansion:** Single-letter abbreviations (p→premium, n→noir) are common OEM shorthand; expanding them improves match rates.
- **Keeps logic simple:** Clear rule: if it's single-letter AFTER a dash, expand it; otherwise, keep as-is.

**Trade-offs:**
- **Abbreviation library dependency:** Expansion only works if abbreviation is in the config library. Unknown abbreviations are logged and kept as-is (safe fallback).

**Files affected:**
- `core/helpers/keyword_extractor.py` — rewrote `_process_component()` to distinguish single-letter vs. multi-char hyphenated terms
- `oems/mitsubishi/config/mitsubishi_config.json` — trim_abbreviation_library defines which single letters expand

---

## [014] Config-driven EV/hybrid exclusion with translator-aware keyword matching

**Date:** 2026-07-20

**Context:** Initial model lookup implementation used a hardcoded `EV_KEYWORDS = ["EV", "PHEV"]` constant to exclude electric and plug-in hybrid vehicles when no fuel-type keyword was in the user's search (e.g., searching "Elantra Luxury" without "HEV" should exclude Hybrid variants). This approach had two problems:

1. **Non-adaptive to OEMs:** Each OEM defines its own `fuel_type_keywords` in config (Hyundai: `["EV", "PHEV", "HEV", "FCEV"]`; Mazda: `["EV", "PHEV", "HEV"]`), but the exclusion logic ignored this, using only the hardcoded `["EV", "PHEV"]`.
2. **Silent failure on translator mismatch:** When OEM translators map abbreviations (e.g., Hyundai's `hev`→`hybrid`, `phev`→`plug-in`), the config-level keywords (`["HEV", "PHEV"]`) no longer matched the already-translated search keywords or ingested DB text. Result: exclusion would silently fail — no HEV variants would be excluded even when intended.

**Decision:** Make EV/hybrid exclusion config-driven AND translator-aware:

1. Read `fuel_type_keywords` from each OEM's `oem_config.model_lookup_rules[make].fuel_type_keywords`
2. Translate the fuel keywords through the same OEM translator used for search keywords (ensuring vocab consistency)
3. Check if the translated keywords match any in the search; if not, exclude those fuel types from results
4. When a fuel-type keyword IS explicitly requested (e.g., user searches `['elantra', 'hev']`), skip the exclusion entirely

This ensures the exclusion logic works in the same vocabulary as the database ingestion pipeline.

**Rationale:**
- **OEM-specific rules:** Each OEM controls its own fuel-type definitions; no hard-coded constant.
- **Translator consistency:** Both search keywords and fuel keywords go through the same translator, eliminating vocab mismatches.
- **Intentional inclusion:** When user explicitly requests a fuel type, we return those variants even if there are multiple trim levels.
- **Discriminator intelligence:** Trim discriminator filtering (which rejects results with extra trim keywords not in the search) now skips POWERTRAIN_TYPE tokens when a fuel-type keyword is present, allowing "elantra hev" to return all trim levels of hybrid.

**Trade-offs:**
- **Requires config compliance:** Each OEM config must define `fuel_type_keywords`. Fallback to hardcoded `["EV", "PHEV"]` for missing configs (backward compatible).
- **Translation dependency:** Correctness depends on the OEM's translator being accurate. Genesis EV exclusion is deferred pending real data verification.

**Bug Discovered & Fixed:**
- During implementation, a critical bug was found in `VehicleSearchEngine.search()` line 178: it checked `oem_config.get("allow_duplicate_model_numbers")` at the top level, but this key is nested under `model_lookup_rules[make]`. Result: multi-candidate searches (like Elantra Hybrid with 4 model codes) never collapsed to a single SearchResult, returning `None` instead. Fixed by navigating the correct path: `oem_config.get("model_lookup_rules", {}).get(make, {}).get("allow_duplicate_model_numbers", False)`.

**Files affected:**
- `model_lookup/models/manufacture_module.py` — added `oem_config` parameter to `search_models_by_description()`, replaced hardcoded fuel-keyword loop with config-driven translated version, updated discriminator logic to skip POWERTRAIN_TYPE and to respect fuel-type keywords
- `model_lookup/search_engine.py` — pass `oem_config` to `search_models_by_description()`; fixed nested config path for duplicate group resolution
- `oems/hyundai/config/hyundai_config.json` — fuel_type_keywords already present (used by this implementation)
- `oems/mitsubishi/config/mitsubishi_config.json` — fuel_type_keywords already present; benefits from the same fix
- `model_lookup/configs/*_classification.json` — existing POWERTRAIN_TYPE tokens already correct for Hyundai; other OEMs can be standardized in a future decision

---

## [015] Modular 5-file config structure per OEM (replacing single JSON)

**Date:** 2026-08-03

**Context:** Previously, all business rules for an OEM lived in a single JSON file (`{oem}_config.json`). This file mixed concerns: data schemas (what columns exist), transformation rules (how to clean data), enrichment logic (how to find model numbers), orchestration settings (where to write output), and output structure (which columns in which sheet). This made the file hard to navigate (200+ lines) and difficult to modify without affecting unrelated concerns.

**Decision:** Replace single config file with modular 5-file YAML structure per OEM:
1. **pipeline.yaml** — Orchestration settings (output paths, feature flags, runtime behavior)
2. **transformations.yaml** — Data cleaning rules (per-column operations, standardization)
3. **enrichment.yaml** — Model lookup and optional enrichment rules
4. **schemas/upstream.yaml** — Input validation (expected columns, types, languages)
5. **schemas/intermediate.yaml** — Post-transformation quality gate (guaranteed columns/types)
6. **schemas/downstream.yaml** — Output sheet structure (which columns in which sheet)

**Rationale:**
- **Single responsibility:** Each file has one semantic concern (schema, transformation, enrichment, output, orchestration)
- **Discoverability:** New team members know where to look for each type of rule
- **Loose coupling:** Independent concerns can be modified without touching unrelated files
- **Maintainability:** Smaller files are easier to review and change
- **Extensibility:** Future settings (dry_run, retry_count, timeouts) have a natural place to live in pipeline.yaml
- **Precedent:** Docker (Dockerfile + docker-compose.yml), Kubernetes (Deployment + ConfigMap), Django (models.py + settings.py) all separate concerns this way

**Files affected:**
- `accy_v2/oems/{oem}/config/` — new 6-file structure (replacing single JSON)
- `accy_v2/core/config_loader_v2.py` — new ModularConfigLoader class to load all 6 files
- All pipeline steps updated to use modular loader (phased: Phase 2a, Phase 2b)

**Migration path:**
- Phase 1: Create new 6-file skeleton, keep old JSON working in parallel
- Phase 2a-2b: Migrate pipeline steps to use new loader (non-breaking)
- Phase 3: Delete old JSON config (breaking point)
- Phase 4: Roll out to all OEMs (Mazda, Mitsubishi, Honda)

---

## [016] use_model_lookup flag remains configurable per OEM

**Date:** 2026-08-03

**Context:** Initially, after Phase 2b (ADS fallback + mandatory enrichment), it seemed model lookup should always be enabled. However, some OEMs like Mazda come with pre-populated model numbers in their source files, making local lookup unnecessary. Other OEMs like Hyundai need lookup because trims must be translated to model numbers.

**Decision:** Keep `use_model_lookup: true/false` in pipeline.yaml as a configurable OEM setting.
- **If true:** Run model lookup + ADS fallback (normal flow)
- **If false:** Skip model lookup entirely; trust that source file has model numbers already

**Rationale:**
- **OEM flexibility:** Some OEMs have complete data (Mazda), others need enrichment (Hyundai). One size doesn't fit all.
- **Cost optimization:** Skipping lookups for OEMs that don't need them saves database queries
- **Future-proof:** If an OEM later switches to providing model numbers, just flip the flag
- **Backward compatible:** Hyundai (use_model_lookup: true) continues to work; Mazda (use_model_lookup: false) uses existing model numbers

**Implementation:**
- In orchestrator, check flag before calling `step4_5_model_enrichment()`
- If false, skip enrichment and go directly to output

**Files affected:**
- `pipeline.yaml` — retains `use_model_lookup` flag
- `accy_v2/oems/{oem}/pipeline/orchestrator.py` — conditional step4.5 call based on flag

---

## [017] non_null_threshold remains configurable global setting

**Date:** 2026-08-03

**Context:** `non_null_threshold` was initially questioned as unnecessary (all OEMs should be uniform). However, different OEMs have different data quality expectations:
- Hyundai: Strict (50% threshold — fail sheet if >50% nulls in required column)
- Future OEMs: May tolerate higher null rates if other compensations exist

**Decision:** Keep `non_null_threshold: 0.5` in pipeline.yaml as configurable per OEM.

**Rationale:**
- **OEM autonomy:** Each OEM defines acceptable data quality thresholds for their supply chain
- **Business rules:** Some OEMs may accept 60% completeness for a column; others 30%. Let config drive this.
- **Low cost:** Single config line; no code changes needed

**Files affected:**
- `pipeline.yaml` — retains `non_null_threshold` (default 0.5)
- `accy_v2/core/base_pipeline.py` — reads from pipeline config

---

## [018] Output paths derived from OEM name in code (not configured)

**Date:** 2026-08-03

**Context:** Output paths follow a predictable pattern:
- `accy_v2/output/ready_to_upload/{oem}/`
- `accy_v2/output/dq_reports/{oem}/`
- `accy_v2/output/pipeline_logs/{oem}/`

Initially, these were configured in pipeline.yaml. This added configuration overhead with no flexibility: no OEM deviates from this pattern, and if they did, a code change would be needed anyway.

**Decision:** Derive output paths from OEM name in code. Remove path configuration from pipeline.yaml.

```python
def get_output_paths(oem: str) -> Dict[str, Path]:
    base = Path("accy_v2/output")
    return {
        "ready_to_upload": base / "ready_to_upload" / oem.lower(),
        "dq_reports": base / "dq_reports" / oem.lower(),
        "pipeline_logs": base / "pipeline_logs" / oem.lower(),
    }
```

**Rationale:**
- **Eliminates configuration boilerplate:** Every OEM config had the same 3 lines of paths
- **Automatic consistency:** New OEMs automatically follow the same folder structure
- **Reduces configuration surface:** Fewer things to configure = fewer things to get wrong
- **Explicit in code:** Behavior is transparent (not hidden in config) and easy to audit

**Trade-offs:**
- **Loses flexibility:** If an OEM needs custom paths (e.g., cloud storage), path derivation needs updating. But this is rare and would require code changes anyway.

**Implementation:**
- Call `get_output_paths(oem)` in orchestrator during setup
- Pass paths to pipeline steps (or store in a context object)

**Files affected:**
- `accy_v2/oems/{oem}/pipeline/orchestrator.py` — derive paths from OEM name
- `pipeline.yaml` — REMOVED `output_paths` section

---

## [019] Rename rate_import_* to output_column_* in downstream schema

**Date:** 2026-08-03

**Context:** The configuration keys `rate_import_column_mapping` and `rate_import_required_columns` were historically named around a "rate import" feature that doesn't exist. What they actually do is format the output for export:
1. `rate_import_column_mapping` renames columns (`part_number` → `Part`, `msrp` → `Price`)
2. `rate_import_required_columns` selects which columns to include in the output

These are core output formatting operations used in every pipeline run, not optional imports.

**Decision:** Rename for clarity and move to downstream schema:
- `rate_import_column_mapping` → `output_column_mapping`
- `rate_import_required_columns` → `output_required_columns`
- Move from pipeline.yaml to `schemas/downstream.yaml` (where they logically belong)

**Rationale:**
- **Accurate naming:** "output_column" describes what the config does (format output columns)
- **Semantic placement:** These settings define output structure, so they belong in downstream schema
- **Clarity for future developers:** New team members won't confuse this with "rate imports from ADS"
- **Consistency:** Downstream schema now defines both output sheets AND output column formatting

**Implementation:**
- In `schemas/downstream.yaml`, add columns with `output_column_mapping` and `output_required_columns`
- Update `step5_output.py` to read from downstream schema instead of pipeline config
- Update all OEM configs (Hyundai, Mazda, Mitsubishi, Honda) to use new names/locations

**Files affected:**
- `schemas/downstream.yaml` — add `output_column_mapping` and `output_required_columns`
- `accy_v2/oems/{oem}/pipeline/step5_output.py` — read from downstream schema
- `accy_v2/core/config_loader_v2.py` — ModularConfigLoader loads from downstream

---

## Adding a New Decision

When a significant design or architecture decision is made, add a new entry to this document:

1. Increment the decision number
2. Include: Date, Context, Decision, Rationale, Files affected
3. Keep entries concise but complete — future readers should understand the decision without asking

Examples of decisions worth documenting:
- Architectural choices (what to abstract, how to structure)
- Trade-offs between approaches (why this solution over that)
- Constraints or assumptions (why we can't do X)
- Bug fixes that inform future design (what we learned)

Non-examples (don't document):
- Routine code changes
- Bug fixes that are obvious from the commit message
- Temporary debugging or exploration
