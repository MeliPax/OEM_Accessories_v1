# Issue: Trim Column Detection — Data-Driven, Robust, Config-Driven

**Created:** 2026-08-06  
**Priority:** Medium  
**Status:** Suggested, Not Yet Implemented  
**Scope:** Mitsubishi (generalizes to all OEMs)

---

## Problem Statement

Current trim column identification in Mitsubishi's pipeline relies on **position-based detection**: assuming the trim column is at a fixed location (between Remarks and DNP, or similar structural assumptions). This approach has critical weaknesses:

1. **Fragile to format changes:** When a landing file changes column order or source system, detection breaks silently—no error, just wrong/missing data.
2. **No data validation:** Can't verify the column actually contains trim values; only checks position.
3. **Not generalizable:** Each OEM requires custom position logic; no pattern scales across Hyundai, Honda, Kia, etc.
4. **No filtering logic:** After identifying the trim column, the entire worksheet (including empty/meta rows) is processed; no way to isolate "data rows" from structural/header rows.

## Proposed Solution

Replace position-based detection with **multi-signal scoring**, where a column's identity comes from **what it contains**, not **where it sits**:

### Multi-Signal Scoring (4 rules, weighted 0.0–1.0)

1. **Header Keywords** (weight 0.3)  
   Does the column name contain trim-related keywords (trim, level, variant, code, grade, spec)?

2. **Vocabulary Overlap** (weight 0.4)  
   What % of column values match known trim codes from the vehicle database?

3. **Data Density** (weight 0.2)  
   Is the column mostly populated (≥ 50% non-empty)?

4. **Data Shape** (weight 0.1)  
   Are values concise strings (< 30 chars), not long descriptions?

### Filtering Logic

After identifying the trim column, filter the worksheet to **data rows only**:
- **Strategy 1:** Keep rows where the trim column has data (simplest).
- **Strategy 2:** Keep rows where ≥ 50% of "data columns" are populated (more flexible).

All thresholds and strategies are **config-driven** in `enrichment.yaml`.

### Vocabulary Source (Hybrid Model)

The trim vocabulary (what counts as a "known trim"?) comes from:
1. **Primary:** Query `db_vehicle_models.csv` for trims of this OEM (live, auto-updated).
2. **Fallback:** Hardcoded list in `enrichment.yaml` (resilience if DB is empty/unavailable).

## Benefits

| Aspect | Before | After |
|--------|--------|-------|
| **Robustness** | Breaks on format change | Works across layout variations |
| **Diagnostics** | Silent failure | Scores show *why* a column was picked; ambiguity warnings |
| **Generalization** | Per-OEM hardcoding | One function + config per OEM |
| **Data Quality** | No validation | Filters to actual data rows, skips meta/empty rows |
| **Maintenance** | Brittle updates per file | Config-driven rules apply to all future files |

## Implementation Phases

| Phase | What | Effort | Blocker? |
|-------|------|--------|----------|
| **A** | Config structure + TrimColumnDetector class + filtering | ~4 hrs | None |
| **B** | DB vocabulary fetching + config fallback | ~2 hrs | Phase A |
| **C** | Bootstrap vocabulary from landing files (one-time) | ~1 hr | Phase B |
| **D** | Integration into step1_validation.py | ~1 hr | Phase A |

**Recommendation:** Implement Phases A+D first (trim detection + filtering work even without DB vocabulary). Then add Phase B (makes vocabulary overlap signal work). Phase C is one-time setup.

## Next Steps

1. Review the detailed plans in `plan_a_config_driven_detection.md` and `plan_b_vocabulary_bootstrap.md`.
2. Approve implementation order + scope.
3. Begin Phase A.

---

## Related Files

- `plan_a_config_driven_detection.md` — Detailed config structure and TrimColumnDetector implementation
- `plan_b_vocabulary_bootstrap.md` — Database vocabulary fetching and fallback strategy
- `summary.md` — Quick reference and implementation checklist
