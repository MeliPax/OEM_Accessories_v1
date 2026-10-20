# Honda Pipeline Steps 2-3 Refactoring — Design Proposal

**Date:** 2026-10-15  
**Status:** Design Phase — Ready for Review & Approval  
**Scope:** Align Honda Steps 2-3 with standard OEM pattern (Hyundai/Genesis/Mazda/Mitsubishi)

---

## Overview

This folder contains the complete design proposal for refactoring Honda pipeline Steps 2 and 3 to align with standard OEM architecture while preserving Honda-specific parent/child and section-based data handling.

**Problem:** Honda's current design diverges from standard OEM pattern  
**Solution:** Three-phase refactoring with clear design documents for each phase

---

## Documents in This Folder

### 1. **STEPS_2_3_ARCHITECTURE.md** (START HERE)
**Purpose:** High-level architecture overview and design decisions

- Problem statement and desired state
- Solution strategy
- Key design decisions (table format)
- Implementation phases overview
- Related documents and references

**Read this first** to understand the overall approach and rationale.

---

### 2. **PHASE_1_STEP2_METADATA.md**
**Purpose:** Detailed design for Step 2 refactoring (Header Normalization)

**Objective:** Step 2 should return metadata dict (col_mapping, valid_trim_cols) matching OEM pattern

**Contains:**
- Current state analysis
- Desired state specification
- col_mapping design (how to build, why numeric indices)
- valid_trim_cols design (trim column extraction)
- Parent/child metadata (what to update in meta_data)
- Implementation steps (3 steps, code structure)
- Testing strategy (5 scenarios)
- Acceptance criteria (checklist)

**Duration:** Phase 1 implementation ~4-6 hours

---

### 3. **PHASE_2_STEP3_STANDARDIZATION.md**
**Purpose:** Detailed design for Step 3 refactoring (Standardization)

**Objective:** Step 3 applies col_mapping, forward-fills parent/child, enforces types, normalizes trims

**Contains:**
- Current state and desired state
- Design for each transformation:
  - Apply col_mapping (rename/drop columns)
  - Forward-fill parent/child pricing (algorithm, example)
  - Enforce data types (prices to float)
  - Normalize trim values (whitespace, markers)
  - Validate trim applicability (≥1 trim per record)
- EN/FR handling (separate calls to Step 3)
- Implementation steps (code structure)
- Testing strategy (5 scenarios)
- Acceptance criteria (checklist)

**Duration:** Phase 2 implementation ~4-6 hours

---

### 4. **PHASE_3_STEP4_INTEGRATION.md**
**Purpose:** Design for Step 4 integration and verification

**Objective:** Verify Step 4 correctly receives EN/FR from Step 3, melts, and merges

**Contains:**
- Input/output specifications (data flow diagrams)
- Orchestration changes (how EN/FR flow through pipeline)
- Step 4 melting logic (wide to long format)
- EN+FR merging algorithm
- Verification strategy (6 checks)
- Testing scenarios (3 examples)
- Potential issues & solutions (troubleshooting table)
- Integration checklist

**Duration:** Phase 3 verification ~2-3 hours

---

## How to Use These Documents

### For Planning:
1. Read **STEPS_2_3_ARCHITECTURE.md** first (10 min)
2. Review each phase document (15 min each)
3. Understand the overall flow and dependencies

### For Implementation:
1. Start with **Phase 1** (Step 2)
   - Follow "Implementation Steps" section
   - Use "Testing Strategy" to verify completion
   - Check off "Acceptance Criteria"

2. Then **Phase 2** (Step 3)
   - Same structure as Phase 1
   - Build on Phase 1 completion

3. Finally **Phase 3** (Step 4)
   - Verification phase (shorter)
   - Ensure integration works end-to-end

### For Code Review:
- Each document has "Implementation Steps" showing code structure
- "Testing Strategy" shows what to verify
- "Acceptance Criteria" is the checklist for PR approval

---

## Key Design Decisions

| Decision | Reasoning |
|----------|-----------|
| Step 2 returns metadata dict | Matches Hyundai/Genesis pattern; base pipeline contract |
| Step 3 called separately for EN/FR | Allows independent processing; Step 4 merges |
| Parent/child forward-filled in Step 3 | Children inherit pricing before output; ready for melting |
| Sections hidden (flattened) | Output is one DataFrame, not section-based |
| Melting in Step 4 (not Step 3) | Standard OEM pattern; Step 3 focused on standardization |

---

## Implementation Timeline

| Phase | Scope | Duration | Blocker |
|-------|-------|----------|---------|
| **Phase 1** | Step 2 refactoring | 4-6 hours | None (can start immediately) |
| **Phase 2** | Step 3 refactoring | 4-6 hours | Phase 1 completion |
| **Phase 3** | Step 4 integration | 2-3 hours | Phase 2 completion |
| **End-to-end test** | Full pipeline test | 1-2 hours | Phase 3 completion |

**Total:** ~12-18 hours

---

## Document Structure

Each phase document follows this structure:
1. **Current State** — What exists now
2. **Desired State** — What we want
3. **Design** — Algorithms and detailed steps
4. **Implementation Steps** — How to code it
5. **Testing Strategy** — How to verify it works
6. **Acceptance Criteria** — Checklist for done

---

## Next Steps

1. **Review this folder** (5 min) — Understand the structure
2. **Read STEPS_2_3_ARCHITECTURE.md** (10 min) — Grasp overall approach
3. **Review each phase document** (15 min each) — Understand detailed designs
4. **Approve or request changes** — Get alignment on design before implementation
5. **Begin Phase 1 implementation** — Start with Step 2 refactoring

---

## References

- `accy_v2/oems/hyundai/pipeline/step2_header_normalization.py` — Reference implementation (Step 2 pattern)
- `accy_v2/oems/hyundai/pipeline/step3_standardization.py` — Reference implementation (Step 3 pattern)
- `accy_v2/core/base_pipeline.py` — Pipeline contract and flow
- `accy_v2/planning/VERSIONING.md` — Versioning strategy
- `accy_v2/docs/SYSTEM_ARCHITECTURE.md` — Pipeline architecture overview

---

**Status:** Ready for design review and approval before implementation begins.
