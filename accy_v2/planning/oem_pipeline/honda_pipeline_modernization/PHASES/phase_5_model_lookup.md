# Phase 5: Model Lookup & Enrichment

**Duration:** Weeks 6–7  
**Effort:** ~16 hours  
**Status:** Ready to start (after Phase 4)  
**Dependencies:** Phase 4 (Step 4 output), Phase 2 (trim_helpers utility)

---

## Deliverables

### Step 3.5: Extract Vehicle Year (`step3_5_extract_vehicle_year.py`)

- Extract year from metadata (already populated in Step 1)
- Validate year range (2020–2030)
- Store in metadata

**Input:** Metadata  
**Output:** Metadata with vehicle_year confirmed

### Step 4.5: Model Enrichment (`step4_5_model_enrichment.py`)

**Key Functions:**
1. For each unique trim: extract keywords using existing `keyword_extractor()`
2. Normalize trim keywords (translate abbreviations, classify, score)
3. Call `VehicleSearchEngine.search(make="Honda", year, keywords)`
4. Handle multiple candidates (packages, drivetrain variants)
5. Add `model_number` and `model_status` to each row
6. Explode multi-package variants (if applicable)

**DQ Rules:**
- `model_lookup_not_found_rule` — VehicleSearchEngine returned 0 candidates
- `model_lookup_low_confidence_rule` — Confidence < 0.7
- `trim_normalization_rule` — Trim normalized during processing

**Input:** Long-format dataframe from Step 4 + metadata  
**Output:** Dataframe with model_number + model_status for each row

---

## Critical Integration

**VehicleSearchEngine Reuse:**
- No code changes to search engine (proven robust across 4 OEMs)
- Honda config (translator.yaml, classification.yaml) drives behavior
- Handles fuel type inference, package differentiation, compound keywords

**Trim Tokenization:**
- Split on space/hyphen (preserve compound keywords: "EX-L", "Sport-L")
- Follow Honda trim_config.yaml rules
- Normalize before search (lowercase, deduplicate)

---

## Code Changes

| File | Purpose |
|------|---------|
| `step3_5_extract_vehicle_year.py` | Simple year extraction & validation |
| `step4_5_model_enrichment.py` | Trim tokenization, VehicleSearchEngine integration |
| `test_step3_5_*.py`, `test_step4_5_*.py` | Unit tests |

---

## Testing

- Unit tests: trim tokenization, keyword extraction
- Integration test: Step 4 output → Step 4.5 → verify model_number added
- Regression test: existing OEMs unaffected

---

## Validation Checklist

- [ ] Year extraction works (from metadata)
- [ ] Trim tokenization preserves compound keywords
- [ ] VehicleSearchEngine integration working (returns model_number)
- [ ] Multi-package handling correct (explode rows per package)
- [ ] DQ rules fire correctly (NOT_FOUND, LOW_CONFIDENCE)
- [ ] Unit test coverage >80%
- [ ] Commit: "Phase 5: Model Enrichment — trim tokenization, VehicleSearchEngine integration"

---

**Estimated Completion:** ~14 hours  
**Actual Time:** (To be filled in after completion)
