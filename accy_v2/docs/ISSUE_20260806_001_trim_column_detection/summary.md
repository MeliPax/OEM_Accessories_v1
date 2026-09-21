# Summary: Trim Column Detection Implementation Plan

**Issue:** Trim column identification should be data-driven, robust, and config-driven—not position-dependent.

**Solution:** Multi-signal scoring with vocabulary validation and filtering to data rows.

---

## Quick Reference

### Problem in 30 Seconds

Current pipeline uses **position-based heuristics** to find trim columns:

- ❌ Brittle: breaks silently when landing file format changes
- ❌ Non-generalizable: custom logic per OEM
- ❌ No data validation: doesn't verify column actually contains trim values
- ❌ No filtering: processes entire worksheet, including empty/meta rows

### Solution in 30 Seconds

**Multi-signal scoring:**

1. Does header match "trim" keywords? (0.3 weight)
2. Do values overlap with known trim vocabulary? (0.4 weight)
3. Is column mostly populated? (0.2 weight)
4. Are values concise strings? (0.1 weight)

Pick column with highest score (> 0.5 confidence). Filter to rows with actual trim data.

---

## Three-Phase Implementation

| Phase       | Deliverable                                                                  | Effort | Dependencies | Status |
| ----------- | ---------------------------------------------------------------------------- | ------ | ------------ | ------ |
| **A** | Config structure + TrimColumnDetector class + filtering + Step 1 integration | ~6 hrs | None         | Ready  |
| **B** | Database vocabulary fetching + config fallback                               | ~3 hrs | Phase A done | Ready  |
| **C** | Bootstrap script + vocabulary extraction                                     | ~1 hr  | Phase B done | Ready  |

**Recommendation:** Implement A → D (integration) first. Then B → C (vocabulary). Phase A alone is valuable and works even without database.

---

## Phase A: Config-Driven Detection + Filtering

### What Gets Built

1. **New config section** in `accy_v2/oems/mitsubishi/config/enrichment.yaml`:

   ```yaml
   trim_detection:
     enabled: true
     confidence_threshold: 0.5
     scoring_rules:
       header_keywords: {weight: 0.3, keywords: [trim, level, variant, ...]}
       vocabulary_overlap: {weight: 0.4, source: hybrid, min_overlap_ratio: 0.1}
       data_density: {weight: 0.2, min_populated_ratio: 0.5}
       data_shape: {weight: 0.1, max_value_length: 30}
     filtering:
       enabled: true
       strategy: "data_only"  # Keep only rows with populated trim column
   ```
2. **TrimColumnDetector class** (`accy_v2/core/helpers/trim_column_detection.py`):

   - `find_trim_column(ws)` → returns (column_name, confidence_score)
   - `filter_to_data_rows(ws, trim_column)` → returns list of row indices to keep
   - Four scoring rules, all config-driven
3. **Integration into Step 1** (`accy_v2/oems/mitsubishi/pipeline/step1_validation.py`):

   ```python
   detector = TrimColumnDetector(config, oem_name="Mitsubishi")
   trim_col, score = detector.find_trim_column(ws)
   data_rows = detector.filter_to_data_rows(ws, trim_col)
   # Continue processing only data_rows
   ```

### Key Features

- ✅ **Robust:** Works across layout variations (position changes → doesn't matter)
- ✅ **Diagnostic:** Returns confidence score; logs why it picked a column
- ✅ **Generalizable:** Same code works for all OEMs (config-driven per OEM)
- ✅ **Filters empty rows:** Only processes rows with actual trim data
- ✅ **Fallback:** Disabled scoring rules = neutral scores (not fatal)

### Config for Other OEMs

Once Phase A works for Mitsubishi, copy + customize for Hyundai, Mazda, etc.:

```yaml
# accy_v2/oems/hyundai/config/enrichment.yaml
trim_detection:
  enabled: true
  confidence_threshold: 0.5
  scoring_rules:
    header_keywords:
      weight: 0.3
      keywords: [trim, level, series, grade, package]  # OEM-specific keywords
    # ... rest as above ...
```

### Testing

Test cases in `accy_v2/tests/test_trim_column_detection.py`:

- Column scoring (header keywords, data density, shape)
- Filtering (keep data rows, skip empty)
- Ambiguity detection (warn if multiple columns tie)

---

## Phase B: Vocabulary from Database

### What Gets Built

1. **Database fetching** in TrimColumnDetector:

   ```python
   def _fetch_from_database(self) -> set:
       """Query db_vehicle_models.csv for known trims of this OEM."""
       df = load_existing_csv(db_path)
       df_oem = df[df["Manufacturer"] == "MITSUBISHI"]
       trims = set(df_oem["ModelNumber"].dropna().str.upper())
       return trims
   ```
2. **Config fallback**:

   ```python
   def _fetch_from_config(self) -> set:
       """Load hardcoded fallback_trims from enrichment.yaml."""
       return set(self.scoring_rules["vocabulary_overlap"]["fallback_trims"])
   ```
3. **Hybrid strategy** in TrimColumnDetector:

   ```python
   def _fetch_vocabulary(self, source: str) -> set:
       """Try DB first, fall back to config."""
       vocab = set()
       if source in ["database", "hybrid"]:
           vocab = self._fetch_from_database()  # Try DB
       if not vocab and source in ["config", "hybrid"]:
           vocab = self._fetch_from_config()  # Fall back to config
       return vocab
   ```

### Benefits

- **Live data:** When ADS data is added, vocabulary grows automatically
- **Resilience:** If DB is missing, config fallback ensures pipeline doesn't break
- **Gap detection:** Can compare DB vs config to spot missing trims

### Prerequisite

- Phase A complete and integrated
- `db_vehicle_models.csv` has at least some OEM data (e.g., Hyundai from prior runs)

---

## Phase C: Vocabulary Bootstrap (One-Time Setup)

### What Gets Built

1. **Bootstrap script** (`scripts/bootstrap_trim_vocabulary.py`):

   ```bash
   python scripts/bootstrap_trim_vocabulary.py --oem mitsubishi
   ```

   Scans all Mitsubishi landing files → extracts unique trim values → outputs YAML snippet:

   ```yaml
   fallback_trims:
     - ES
     - LS
     - XLS
     - PHEV
     - ECLIPSE_CROSS
     # ...
   ```
2. **Manual step:** Copy output into `accy_v2/oems/mitsubishi/config/enrichment.yaml` under `trim_detection.scoring_rules.vocabulary_overlap.fallback_trims`

### Effort

- ~5 min: run bootstrap script
- ~2 min: copy-paste output into YAML

### Do This For

- Mitsubishi (current landing files)
- Hyundai (if moving to new data structure)
- Mazda, Honda, Kia, Volkswagen (when they land)

---

## Implementation Order

### Week 1: Phase A

1. Create `accy_v2/core/helpers/trim_column_detection.py` (TrimColumnDetector class)
2. Add config section to `accy_v2/oems/mitsubishi/config/enrichment.yaml`
3. Update `accy_v2/oems/mitsubishi/pipeline/step1_validation.py` to use detector
4. Write test cases
5. Test with sample Mitsubishi sheets
6. Verify no regressions in Hyundai/Mazda pipelines

### Week 2: Phase B (if database is available)

1. Implement `_fetch_from_database()` and `_fetch_from_config()`
2. Test hybrid strategy
3. Verify DB query works with Hyundai data
4. Confirm fallback works when DB is empty

### Week 3: Phase C (bootstrap + finalize)

1. Create `scripts/bootstrap_trim_vocabulary.py`
2. Run: `python scripts/bootstrap_trim_vocabulary.py --oem mitsubishi`
3. Copy `fallback_trims` into enrichment.yaml
4. Repeat for other OEMs
5. End-to-end test

---

## Risk Mitigation

| Risk                                                         | Mitigation                                                                          |
| ------------------------------------------------------------ | ----------------------------------------------------------------------------------- |
| **Database missing/empty**                             | Phase A works even without DB; Phase B adds fallback config                         |
| **Vocabulary too strict** (high `min_overlap_ratio`) | Config-driven threshold; tune per OEM if needed                                     |
| **Ambiguous columns tie**                              | Detector logs warning; includes DQ category for investigation                       |
| **Position-based code elsewhere**                      | Find all uses of`trim_level` / trim column indices; update to use detector output |

---

## Files to Read for Details

| File                                  | Content                                                                                      |
| ------------------------------------- | -------------------------------------------------------------------------------------------- |
| `issue.md`                          | Full problem statement + benefits overview                                                   |
| `plan_a_config_driven_detection.md` | Detailed Phase A: config structure, full TrimColumnDetector code, integration steps, testing |
| `plan_b_vocabulary_bootstrap.md`    | Detailed Phase B: DB fetching, hybrid strategy, bootstrap script                             |
| `summary.md`                        | This file (quick reference + implementation order)                                           |

---

## Next Steps

### If Approved:

1. Create Phase A branch: `feature/trim_detection_phase_a`
2. Implement TrimColumnDetector class
3. Add config to Mitsubishi enrichment.yaml
4. Integrate into step1_validation.py
5. Test and merge
6. Plan Phase B once Phase A is live

### If Questions:

- Confidence thresholds too high/low? → Configurable in YAML
- Other OEMs need different keywords? → Add to their enrichment.yaml `header_keywords`
- Vocabulary too sparse? → Run bootstrap script to extract from landing files
- Data rows filtering too aggressive? → Change `strategy` from "data_only" to "full_sheet" in config

---

## Success Criteria

✅ Phase A complete:

- [ ] Trim column detected correctly for Mitsubishi sheets
- [ ] Filters to data rows (skips empty/meta rows)
- [ ] No regressions in Hyundai/Mazda output
- [ ] Confidence score logged and visible

✅ Phase B complete (optional):

- [ ] Vocabulary loaded from `db_vehicle_models.csv`
- [ ] Config fallback works when DB is empty
- [ ] Hybrid strategy tested

✅ Phase C complete (optional):

- [ ] Bootstrap script runs and generates YAML
- [ ] fallback_trims populated in enrichment.yaml

---

## Related Issues / Decisions

- **DECISION [019]:** Programmable column mapping (downstream.yaml). Phase A uses same pattern for trim detection config.
- **DECISION [015]:** Modular config architecture per OEM. Phase A extends this pattern.
- **Prior issue:** Hyundai model lookup + ADS fallback gate. Phase B follows same hybrid DB + fallback pattern.
