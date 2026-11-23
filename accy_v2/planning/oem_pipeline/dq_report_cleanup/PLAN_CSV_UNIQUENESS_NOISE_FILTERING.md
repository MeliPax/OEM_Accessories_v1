# Plan: Filter csv_uniqueness_rule Noise from DQ Export Documents

**Date:** 2026-09-08  
**Status:** PLANNING (not yet approved for implementation)  
**Audience:** Backend/Pipeline Engineering

---

## Problem

### Current Behavior
DQ reports generated after each pipeline run include **all** DQ warnings, including `csv_uniqueness_rule` violations. These are currently counted and summarized at the top level of the DQ report JSON.

**Example from Genesis 2026-09-08 run:**
```
Total warnings: 39
  - csv_uniqueness_rule: 30 (noise)
  - model_number_lookup_rule: 5 (actionable)
  - ... other rules
```

### Why This is Noise

`csv_uniqueness_rule` detects **duplicate rows within the source data file** — the same exact record appearing multiple times in the CSV input. This is expected behavior when:
- ADS refresh scripts re-run and re-detect rows already in the database
- Source files are processed multiple times
- The database row already exists in the target system

**This is not an error or a problem** — the duplicate detection is working correctly. It's simply logging that the row has been seen before.

### Why It Clutters Reports

1. **For Business Stakeholders:** The DQ report is supposed to highlight actionable issues (missing trim names, model lookup failures, incorrect classifications). Seeing 30 "uniqueness violations" when there are only 5 real lookup problems obscures the actual issues.

2. **For Data Stewards:** They need to focus on warnings that require intervention (model_number_lookup_rule, missing trim data) vs. those that are expected operational noise.

3. **For Prioritization:** A report showing 39 warnings looks worse than showing 9 warnings, even though the actual issue count is the same. Noise inflates severity perception.

---

## Proposed Solution

### 1. Keep csv_uniqueness_rule in Pipeline Logs (KEEP)
- Pipeline logs (`pipeline_*.log`) should continue logging csv_uniqueness_rule at DEBUG/INFO level
- Engineers debugging duplicate detection still have full visibility
- **No change to logging infrastructure**

### 2. Filter csv_uniqueness_rule from DQ Export Documents (REMOVE)

Two approach options — choose one:

#### **Option A: Filter at Report Generation (Recommended)**
**Advantage:** Minimal code change, DQ Logger stays simple  
**Implementation:**
1. Modify `DQLogger._build_summary()` to exclude `csv_uniqueness_rule` records from summary counts
2. Add `"records": [...]` to DQ report filtered to exclude csv_uniqueness_rule entries
3. Add a metadata field `"filtered_rules": ["csv_uniqueness_rule"]` to indicate noise was removed
4. Update report schema documentation to note that csv_uniqueness_rule is excluded

**File:** `accy_v2/core/helpers/dq_logger.py` (lines ~70-85)

**Pseudocode:**
```python
def write_dq_report(self, output_path: str, exclude_rules=None) -> None:
    """
    exclude_rules: list of rule names to exclude from report (e.g., ["csv_uniqueness_rule"])
    These are still logged to pipeline logs, just not included in stakeholder-facing DQ report.
    """
    if exclude_rules is None:
        exclude_rules = ["csv_uniqueness_rule"]  # Default: always exclude noise rules
    
    filtered_records = [
        r for r in self._records 
        if r["rule_violated"] not in exclude_rules
    ]
    
    payload = {
        "run_id": self.run_id,
        "source_file": self.source_file,
        "generated_at": timestamp,
        "total_warnings": len(filtered_records),  # Count only non-filtered
        "filtered_rules": exclude_rules,  # Document what was removed
        "summary": self._build_summary(filtered_records),
        "records": filtered_records,
    }
```

#### **Option B: Tag Records at Log Time (Alternative)**
**Advantage:** More explicit control, easier to vary per rule  
**Implementation:**
1. Add `"is_noise": bool` field to each warning logged
2. Set `is_noise=True` for csv_uniqueness_rule when logging
3. Filter `is_noise=False` records when building report
4. **Downside:** More invasive change, requires updating all log_warning calls

---

## Affected Files

### Code Changes Required
- **Primary:** `accy_v2/core/helpers/dq_logger.py`
  - Modify `write_dq_report()` method
  - Update `_build_summary()` to filter out excluded rules
  - Add `"filtered_rules"` metadata field

### Documentation Updates Required
- **`accy_v2/docs/dq_report_guide.md`**
  - Document the new `"filtered_rules"` metadata field
  - Explain why csv_uniqueness_rule is excluded
  - Clarify that these warnings still appear in pipeline logs
  
- **`accy_v2/docs/CHANGELOG.md`**
  - Note in next release: DQ reports now exclude csv_uniqueness_rule noise for clarity

### No Changes Needed
- Pipeline log infrastructure (keep as-is)
- Pipeline scripts (no caller-side changes)
- DQ report downstream consumers (report structure is backward compatible — fewer warnings but same format)

---

## Verification Plan

After implementation:

1. **Run all 4 OEM pipelines** and verify DQ reports:
   - Genesis: warnings should drop from 39 → 9 (remove 30 csv_uniqueness_rule entries)
   - Hyundai: warnings should drop from 145 → ~115 (check actual count)
   - Mazda: should remain 0 (no csv_uniqueness_rule in clean run)
   - Mitsubishi: warnings should drop from 124 → ~94 (check actual count)

2. **Spot-check reports:**
   - Verify `"filtered_rules": ["csv_uniqueness_rule"]` is present
   - Confirm all model_number_lookup_rule, missing_trim_name, etc. are still present
   - Confirm DQ summary counts match filtered record count

3. **Check pipeline logs:**
   - Grep pipeline logs for `csv_uniqueness_rule` — should still appear
   - Verify they're logged at the right level (DEBUG or INFO)
   - Sample log lines should match old format

4. **No regression testing:**
   - Run full pipeline on all OEMs
   - Verify no new errors introduced
   - Confirm "real" DQ issues still detected and reported

---

## Questions for Review

1. **Noise Rule Definition:** Are there other rules beyond `csv_uniqueness_rule` that should be filtered?
   - Currently only csv_uniqueness_rule is confirmed as noise
   - Suggest: Keep it simple, filter only this rule for now, revisit if others emerge

2. **Report Consumers:** Are there any downstream processes (dashboards, alerting, data pipelines) that currently parse DQ report counts and need to be updated?
   - If so, they should be notified that csv_uniqueness_rule is excluded
   - Suggest: Check deployment docs / team comms

3. **Audit Trail:** Should there be a separate "detailed" DQ report with csv_uniqueness_rule included for compliance/audit purposes?
   - Current proposal: pipeline logs serve as audit trail (not in stakeholder-facing export)
   - Suggest: Keep proposal as-is, audit can query pipeline logs if needed

4. **Backward Compatibility:** Should the filtered report keep an old format for downstream consumers?
   - Adding `"filtered_rules"` field is non-breaking (new field, same structure)
   - Suggest: Safe to implement as-is

---

## Timeline Estimate

- **Implementation:** 1-2 hours (small code change + testing)
- **Testing:** 1-2 hours (run all pipelines, verify counts)
- **Documentation:** 30 minutes
- **Total:** ~3-4 hours for full implementation + verification

---

## Decision

⏳ **Awaiting approval to proceed with Option A (Filter at Report Generation)**

Once approved:
1. Implement DQLogger filtering (Option A)
2. Update documentation
3. Run full pipeline verification
4. Merge to dev/main when all pipelines pass

