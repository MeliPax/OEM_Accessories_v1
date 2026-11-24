# Mitsubishi Translator-Classifier Alignment Initiative

**Scope:** Mitsubishi OEM only  
**Status:** Proposal  
**Date:** 2026-08-27  

---

## Quick Summary

Mitsubishi's keyword translation system has a structural gap where translated outputs (e.g., "plug-in hybrid", "gt premium") aren't always recognized by the classifier, causing silent search failures or wrong results. This folder contains a detailed proposal and implementation plan to fix it in three phases.

---

## Documents in This Folder

### [PROPOSAL.md](PROPOSAL.md)
**Audience:** Decision makers, architects, reviewers  
**Content:**
- Executive summary
- Problem statement with examples
- Proposed 3-phase solution
- Risk analysis (low risk due to OEM isolation)
- Success criteria
- Timeline

**Read this for:** Understanding what needs to be fixed and why.

### [IMPLEMENTATION.md](IMPLEMENTATION.md)
**Audience:** Engineers implementing the fix  
**Content:**
- Exact config file changes (5 lines)
- Contract test code to prevent regression (50 lines)
- E2E validation steps
- Rollback plan
- Troubleshooting guide

**Read this for:** Step-by-step instructions on what to change and how to validate.

---

## Quick Reference

### The Problem

Translator produces: `gt-p → gt premium`, `phev → plug-in hybrid`  
Classifier expects: `gt premium: TRIM`, but only has `GT Premium: TRIM`, `gt-premium: TRIM`  
Result: Multi-word outputs aren't recognized → silent failures

### The Fix (3 Phases)

| Phase | What | Time | Risk |
|-------|------|------|------|
| 1 | Update classification.yaml to add missing translator outputs | 5 min | None |
| 2 | Add contract test to prevent regression | 30 min | None |
| 3 | Validate on real Mitsubishi data | 1 hour | Low (isolated) |

### Files to Change

- `accy_v2/model_lookup/configs/mitsubishi/classification.yaml` — Add 1 line, remove 2 lines
- `accy_v2/model_lookup/tests/test_search_engine.py` — Add 50-line test

### Why This Is Safe

- **OEM isolated:** Changes only to Mitsubishi's config, not shared code
- **No code changes:** Only YAML + test additions
- **No backward compat issues:** Existing data/queries work unchanged
- **Regression protection:** Contract test prevents this bug from recurring

---

## Decision Flow

**Approve Phase 1-2?**
→ Yes: Proceed with config change + test (15 min total)  
→ No: Escalate for architectural review

**Phase 3 validation passes?**
→ Yes: Merge and close  
→ No: Investigate and rollback if needed

---

## Next Steps

1. **Review** PROPOSAL.md (decision)
2. **Approve** Phase 1-2 scope
3. **Implement** via IMPLEMENTATION.md (engineer)
4. **Validate** Phase 3 end-to-end
5. **Merge** when all checks pass

---

## Related Context

- **Phase 7 (Mitsubishi Model Lookup):** This fix enables Phase 7's enrichment columns to work correctly
- **Shared code:** `search_engine.py` used by Hyundai + Genesis, but no changes needed (OEM isolation)
- **Extensibility:** Same fix pattern can be applied to Hyundai/Genesis independently if they have the same gap

---

## Questions?

See **Troubleshooting** section in IMPLEMENTATION.md for common issues and solutions.