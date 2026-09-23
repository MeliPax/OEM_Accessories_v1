# Phase 6: Output & DQ Reporting

**Duration:** Weeks 7–8  
**Effort:** ~20 hours  
**Status:** Ready to start (after Phase 5)  
**Dependencies:** Phase 5 (enriched data)

---

## Deliverables

### Step 5: Output Generation (`step5_output.py`)

**Key Functions:**
1. Apply rate import column mapping (if applicable)
2. Filter to required columns
3. Format output (Description = title case, ModelNumber = uppercase, etc.)
4. Generate Excel workbook with 4 sheets:
   - **Main sheet:** Parts with model numbers, ready for downstream
   - **raw_data sheet:** Source audit trail (file, model, year, EN/FR columns, merge confidence)
   - **Confidence sheet:** Quality metrics (mapping confidence, cost variance, part availability)
   - **DQ Report sheet:** All warnings grouped by rule, sortable by severity

**Input:** Enriched dataframe from Step 4.5 + all DQ warnings logged during pipeline  
**Output:** `honda_MODEL_YEAR.xlsx` with all sheets

### Batch Aggregation (NEW)

Implement batch orchestrator logic:
- Scan directory for all Excel files
- Process each file through full pipeline
- Aggregate results:
  - Batch summary metrics (files processed, reconciliation rate, etc.)
  - Files with issues (recommended actions)
  - Create `batch_summary_dq.json` (per schema from Phase 2)

**Input:** Directory path (e.g., `landing_zone/honda/2026/2026-09/`)  
**Output:** 
- Excel files (one per model)
- `batch_summary_dq.json` (aggregated metrics)
- Pipeline logs

### DQ Logger Extensions

Add Honda-specific DQ rules to core DQ logger:
- Formalize rule names (from Phase 2 catalog)
- Implement rule firing logic
- Generate consistent message templates

---

## Code Changes

| File | Purpose |
|------|---------|
| `step5_output.py` | Output generation (main + raw_data + confidence + DQ sheets) |
| `batch_orchestrator.py` | Directory scanning, multi-file orchestration, batch aggregation |
| `accy_v2/core/helpers/dq_logger.py` | Add Honda DQ rules |
| `test_step5_*.py` | Unit tests |

---

## Critical Output Schemas

**raw_data sheet columns:**
```
source_file | model | year | part_number_en | part_number_fr | description_en | description_fr | 
cost_en | cost_fr | trims_en | trims_fr | merge_confidence | section | ...
```

**batch_summary_dq.json structure:** (See Phase 2 Design Doc)

---

## Testing

- Unit test: output formatting, sheet creation
- Integration test: full pipeline → Excel generation
- Verify all 3 sheets present & formatted correctly
- Verify DQ warnings populated in DQ sheet

---

## Validation Checklist

- [ ] Excel workbook generated with 4 sheets
- [ ] main sheet has model_number, model_status, all required columns
- [ ] raw_data sheet has EN/FR columns + merge_confidence
- [ ] confidence sheet has quality metrics
- [ ] DQ sheet has all warnings (grouped by rule, sortable)
- [ ] batch_summary_dq.json generated (valid JSON, matches schema)
- [ ] Unit test coverage >80%
- [ ] Commit: "Phase 6: Output & DQ — Step 5 implementation, batch aggregation, DQ schema"

---

**Estimated Completion:** ~18 hours  
**Actual Time:** (To be filled in after completion)
