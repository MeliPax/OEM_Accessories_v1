# Documentation Index

Quick navigation to all accy_v2 documentation.

## Latest (2026-08-31)

### Three Critical Search Gaps Fixes
**Location:** [`2026-08-31_search_gaps_fixes/`](./2026-08-31_search_gaps_fixes/)
- **README:** Overview & quick reference
- **FIXES_DETAILED.md:** Comprehensive technical documentation
- **QUICK_REFERENCE.md:** High-level summary by audience  
- **VERIFICATION_RESULTS.md:** Test results & metrics

**Quick Summary:** Fixed 3 code bugs (Palisade Calli HEV grouping, Night Edt.HEV tokenization, Tucson fuel-locked trims). NOT_FOUND reduced 14 → 10 (40% reduction).

---

## System Architecture & Planning

- **[SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md)** — Full pipeline architecture (5 layers, dataflow, dependencies)
- **[SYSTEM_ARCHITECTURE_DIAGRAM.txt](SYSTEM_ARCHITECTURE_DIAGRAM.txt)** — ASCII diagram of pipeline flow

---

## Reference Guides

- **[config_schema.md](config_schema.md)** — OEM configuration structure and options
- **[dq_report_guide.md](dq_report_guide.md)** — Data quality report format and interpretation
- **[MODELNAME_QUICK_REFERENCE.txt](MODELNAME_QUICK_REFERENCE.txt)** — Model names across OEMs
- **[MODELNAME_INGESTION_PLAN.md](MODELNAME_INGESTION_PLAN.md)** — How model names are ingested

---

## Implementation Plans & Proposals

### Completed

- **[PHASE5_STATUS.md](PHASE5_STATUS.md)** — Phase 5 completion report
- **[IMPLEMENTATION_QUICK_START.md](IMPLEMENTATION_QUICK_START.md)** — Quick start guide
- **[DOWNSTREAM_RESTRUCTURING_PLAN.md](DOWNSTREAM_RESTRUCTURING_PLAN.md)** — Output schema restructuring
- **[IMPLEMENTATION_PLAN_DOWNSTREAM_SCHEMA.md](IMPLEMENTATION_PLAN_DOWNSTREAM_SCHEMA.md)** — Downstream schema implementation

### Proposals & Analysis

- **[proposals/2026-08-25_model_search_fallback_hierarchy.md](proposals/2026-08-25_model_search_fallback_hierarchy.md)** — Search fallback strategy proposal
- **[PIPELINE_ANALYSIS_AND_FIX_PLAN.md](PIPELINE_ANALYSIS_AND_FIX_PLAN.md)** — Comprehensive pipeline analysis
- **[2026-07-28_PIPELINE_REVIEW_AND_EXECUTION_PLAN.md](2026-07-28_PIPELINE_REVIEW_AND_EXECUTION_PLAN.md)** — Pipeline review & execution

---

## Issue Tracking

### 2026-08-07: Translator/Classifier Ordering
**Location:** [`ISSUE_20260807_001_translator_classifier_ordering/`](./ISSUE_20260807_001_translator_classifier_ordering/)
- issue.md, plan.md, summary.md

### 2026-08-06: Trim Column Detection
**Location:** [`ISSUE_20260806_001_trim_column_detection/`](./ISSUE_20260806_001_trim_column_detection/)
- issue.md, plan_a_config_driven_detection.md, plan_b_vocabulary_bootstrap.md, summary.md

### 2026-07-21: Model Lookup Failures
**Location:** [`2026-07-21_model_lookup_failures/`](./2026-07-21_model_lookup_failures/)
- Executive summary, data issues report, implementation plan, exact fixes required, testing guide

---

## Changelog

- **[CHANGELOG.md](CHANGELOG.md)** — Complete version history with all changes, organized by release

---

## How to Use This Index

1. **For current work:** Start with latest section → 2026-08-31_search_gaps_fixes
2. **For architecture:** → SYSTEM_ARCHITECTURE.md
3. **For configuration:** → config_schema.md
4. **For past issues/context:** → Issue Tracking section
5. **For version history:** → CHANGELOG.md

---

**Last Updated:** 2026-08-31  
**Current Version:** 2.5.0
