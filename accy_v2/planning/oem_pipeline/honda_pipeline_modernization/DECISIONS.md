# Honda Pipeline: Critical Decisions Log

Record of all major architectural decisions made during planning. Each decision includes the choice, rationale, alternatives considered, and tradeoffs.

---

## D1: Architecture Extension vs. Monolithic Rewrite

**Decision:** Extend accy_v2's 5-layer pipeline architecture (create Honda as a domain-specific specialization)

**Alternative Considered:** Rewrite from scratch as standalone module

**Rationale:**
- accy_v2 architecture already proven (Hyundai, Genesis, Mazda, Mitsubishi ship with it)
- Honda's unique aspects (sections, EN/FR reconciliation, rollup) fit into existing layers without core changes
- Enables code reuse: VehicleSearchEngine, DQ logger, pipeline logger, translators
- Reduces maintenance burden (bug fixes benefit all OEMs)

**Tradeoff:** Less flexibility to deviate from pattern, but gain consistency

**Impact:** Reduces Honda implementation from ~200h to ~156h (22% savings)

---

## D2: Configuration Format

**Decision:** YAML (vs. JSON used by other OEMs)

**Rationale:**
- Honda config is nested and complex: sections, subsections, patterns, rules
- YAML is more readable than JSON for nested structures
- YAML supports inline comments (useful for documenting section patterns)
- accy_v2 has Hyundai using YAML already (enrichment.yaml, translator.yaml)
- No code impact (config loader treats YAML/JSON identically)

**Tradeoff:** Slight inconsistency with Mazda/Mitsubishi (who use JSON), but Honda's complexity justifies it

**Files Affected:**
- `section_patterns.yaml` (section detection rules)
- `reconciliation.yaml` (EN/FR matching strategy)
- `trim_config.yaml` (applicability markers, tokenization)
- `pipeline.yaml` (error handling, batch settings)

---

## D3: EN/FR Data Handling

**Decision:** Load EN and FR sheets independently, then reconcile via mapping (vs. naive column pairing)

**Rationale:**
- EN and FR often diverge: part numbers, costs, part counts, trim lists
- Naive pairing (left-join on row order) silently breaks on misalignments
- Explicit reconciliation map makes divergences visible to DQ reporting
- User spec: "track all divergences as DQ warnings, flag to partners for confirmation"
- Enables independent validation of each sheet before reconciliation

**Tradeoff:** More complex logic (reconciliation engine), but better data quality & transparency

**Impact:** Adds Step 1.5 (Reconciliation Engine) + enhanced Step 4 (reconciliation-aware transformation)

---

## D4: Packages/Kits Rollup Logic

**Decision:** Parent-driven aggregation (keep parent row, aggregate child descriptions into comments)

**Rationale:**
- User spec: "roll up to one row per package, aggregate child parts into comment section"
- Parent-driven aligns with data structure: parent row = package header, children = contents
- Numeric values (price, labor, install time): use parent (child values are often blank)
- Trim applicability: keep parent; flag if any child diverges (data quality check)
- Descriptions: concatenate children into comment section (preserves info)

**Tradeoff:** Requires detecting parent-child structure (not always obvious); adds DQ complexity

**DQ Rules Added:**
- `rollup_verification_rule` — child count vs. aggregated count
- `parent_child_trim_mismatch_rule` — flag when child trim applicability diverges from parent
- `parent_missing_numeric_rule` — flag when parent numeric value is empty

---

## D5: Model Lookup Integration

**Decision:** Reuse VehicleSearchEngine (existing shared implementation)

**Rationale:**
- VehicleSearchEngine already proven across 4 OEMs
- Includes: keyword extraction, translation, classification, scoring, database search
- Honda's trim tokenization rules (compound keywords like "EX-L") fit existing patterns
- No need to reinvent search logic

**Tradeoff:** Inherited assumptions may not fit all Honda cases, but existing mechanism flexible enough (precedent: Mitsubishi also fits via config)

**Impact:** Reduces Honda implementation effort significantly; no search engine coding needed

---

## D6: Batch Processing Strategy

**Decision:** Multi-file orchestrator wrapper around main pipeline (handle directory scanning, aggregation)

**Rationale:**
- Honda unique: single-model-per-file (vs. Hyundai/Genesis single-master-file)
- Directory structure: `landing_zone/honda/2026/2026-09/` contains 10–13 files
- Batch orchestrator scans all files, processes each via main pipeline, aggregates results
- Batch-level DQ report summarizes: files processed, reconciliation metrics, files with issues
- Per-file error quarantine (errors don't fail whole batch, record isolation)

**Tradeoff:** Adds orchestration layer, but keeps per-file pipeline logic clean & testable

**Files Created:**
- `accy_v2/oems/honda/batch_orchestrator.py` (directory scanning, aggregation)
- Batch-level DQ schema (batch_summary_dq.json)

---

## D7: Section Detection Strategy

**Decision:** Config-driven pattern matching (exact text + header structure validation)

**Rationale:**
- Honda files have consistent section structure (6 sections per file)
- Sections identified by exact text: "1.0 Packages and Kits", "2.0 Wheels and Wheel Accessories", etc.
- EN/FR versions have same numbering but different text
- Config approach: define patterns in YAML, validate against actual file
- Enables DQ validation: flag if section count/order diverges

**Tradeoff:** Requires precise config; brittle if section text varies, but robustness via DQ logging

**Config Structure:**
```yaml
sections:
  packages:
    en: "1.0 Packages and Kits"
    fr: "1.0 Groupes et ensembles"
  wheels:
    en: "2.0 Wheels and Wheel Accessories"
    fr: "2.0 Jantes et accessoires de jantes"
  # ... 6 total
```

---

## D8: Trim Applicability Markers

**Decision:** Config-driven marker sets (["•", "T", "E"] = applies; [" ", "", "N/A"] = not applies)

**Rationale:**
- Honda uses marks in trim columns: "•" (bullet), "T", "E" (applies); blank or "N/A" (not applies)
- Config approach: define markers, validate each cell against marker sets
- Enables DQ validation: flag cells with unexpected values
- Future-proof: if markers change, only update config (no code change)

**Tradeoff:** Assumes consistent marker convention; adds DQ rules to flag ambiguous values

**DQ Rules Added:**
- `trim_applicability_invalid_marker_rule` — cell has unexpected marker
- `trim_applicability_missing_rule` — part has no trims marked (orphan record)

---

## D9: Composite Part Number Handling

**Decision:** Prioritize left side of "or"/"ou" separator; normalize to single part number

**Rationale:**
- EN file: "50977-565-45BH or 50977-565-45SH" (can be used interchangeably)
- FR file: "50977-565-45BH ou 50977-565-45SH" (same, different language)
- Specification: "keep first part number, slice and strip, check for empty, otherwise pick other half"
- Strategy: left-priority (first is preferred), fallback to right if left empty
- Ensures EN/FR produce same part number for same item

**Tradeoff:** Loses information (doesn't track both part numbers), but simplifies data model & ensures EN/FR alignment

**Utility Function:** `normalize_composite_part_number(part_num, language: "EN"|"FR")`
- Input: raw part number (may have "or"/"ou")
- Output: normalized part number (single value)

---

## D10: Output Schema Design

**Decision:** Include raw_data sheet (EN/FR merged) + confidence/metadata columns + DQ sheet

**Rationale:**
- User spec: "complete trace back" — audit trail for reviewing transformations
- Raw data sheet: source file, manufacture date, model, year, EN/FR columns with merge confidence
- Confidence columns: mapping_confidence, cost_variance_pct, part_availability_pct
- DQ sheet: all warnings by rule, sortable by severity
- Enables partners to review data quality & confirm/correct issues

**Tradeoff:** Excel workbook larger (3–4 sheets instead of 1), but transparency justifies it

**Output Structure:**
```
output.xlsx
├── Main (processed parts with model numbers, ready for downstream)
├── raw_data (source audit trail)
├── Confidence (quality scores, divergences)
└── DQ Report (all warnings, grouped by rule)
```

---

## D11: State Management Across Steps

**Decision:** Explicit metadata propagation (group_key, model_name, reconciliation_map, section_structure, etc.)

**Rationale:**
- Each step receives: (transformed_data, metadata, config)
- Metadata contains state that downstream steps need: reconciliation map, trim candidates, section info
- Explicit schema (vs. implicit dict keys) makes dependencies clear
- DQ traceability: each row knows its origin (source file, section, model, year)

**Metadata Schema:**
```python
metadata = {
  "group_key": "accord_2027",
  "model_name": "accord",
  "vehicle_year": 2027,
  "manufacturer": "Honda",
  "source_file": "landing_zone/honda/2026/2026-09/Accord_2027.xlsx",
  "publication_date": "2026-09-01",
  "section_structure": {...},
  "trim_columns": [...],
  "trim_candidates": ["SE", "EX", "LX"],
  "reconciliation_map": {...},  # From EN/FR reconciliation
  "fr_sheet_data": {...},  # FR dataframe for Step 4 join
  "validation_warnings": [...],
  "batch_id": "2026-09",
}
```

---

## D12: Error Handling Strategy

**Decision:** Config-driven per-error-type handling (FATAL vs. WARNING vs. QUARANTINE)

**Rationale:**
- Some errors are unrecoverable (missing_section → skip file)
- Some errors are per-record (trim_parsing_error → exclude row, continue file)
- Some errors warrant file quarantine (error rate > threshold → mark file as quarantined)
- Config approach: define error type → action mapping
- Enables flexibility: can tune behavior per OEM without code change

**Config Example:**
```yaml
error_handling:
  FATAL:
    - "missing_section"          # Stop processing this file
    - "encoding_error"
  WARNING:
    - "trim_parsing_error"       # Log, exclude row, continue
    - "cost_mismatch"
    - "part_count_mismatch"
  QUARANTINE_THRESHOLD: 0.10    # Quarantine file if >10% errors
```

**DQ Rules:** Each error type gets a DQ rule (e.g., `section_missing_rule`, `encoding_error_rule`)

---

## D13: Testing Strategy

**Decision:** Regression tests for all 4 existing OEMs + unit/integration for Honda

**Rationale:**
- Must not break existing pipelines: Hyundai, Genesis, Mazda, Mitsubishi
- Regression tests use minimal synthetic data (fast feedback)
- Honda gets comprehensive unit + integration tests (real data from landing_zone/)
- Phase 7 includes end-to-end testing with actual Honda files

**Test Approach:**
- Unit tests: step functions in isolation (mock inputs/outputs)
- Integration tests: full pipeline on real data
- Regression tests: existing OEMs with reduced dataset (unchanged output)

---

## D14: Documentation Strategy

**Decision:** Structured project folder with phase files + design docs + navigation

**Rationale:**
- Planning is extensive (10 challenge areas, 7 phases); need organized reference
- Phase files are self-contained (read 1 file to understand 1 phase)
- Design docs separate (linked but not duplicated in every phase file)
- Navigation guides readers ("what to read when")
- Reduces cognitive load during implementation

**Folder Structure:**
```
honda_pipeline_modernization/
├── PROJECT.md (overview)
├── NAVIGATION.md (how to use this folder)
├── DECISIONS.md (this file)
├── PHASES/
│   ├── phase_1_foundation.md
│   ├── phase_2_design.md
│   ├── ...
│   └── phase_7_testing.md
├── DESIGN_DOCS/
│   ├── composite_part_number_normalization.md
│   ├── trim_generalization_algorithm.md
│   ├── dq_rule_specifications.md
│   └── batch_reporting_schema.md
└── DELIVERABLES/
    └── (populated during implementation)
```

---

## Open Decisions (Awaiting User Input)

None — all critical decisions made. Minor clarifications needed during implementation:

1. Real Honda Excel files for encoding verification (Phase 3)
2. Exact section identifier text in EN/FR (Phase 3)
3. Composite part number examples (Phase 2)
4. Trim generalization examples (Phase 2)

---

## Decision Timeline

| Decision | Date | Status |
|----------|------|--------|
| D1–D14 | 2026-09-23 | ✅ Approved |
| Encoding confirm | TBD Phase 3 | ⏳ Pending (non-blocking) |
| Section text verify | TBD Phase 3 | ⏳ Pending (non-blocking) |

---

**Last Updated:** 2026-09-23  
**Decision Authority:** User (makeville00@gmail.com)  
**Review Status:** ✅ Approved for implementation
