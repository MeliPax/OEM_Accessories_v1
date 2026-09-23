# Honda Pipeline Project Navigation

Quick reference for finding what you need in this project folder.

---

## 📋 Start Here

1. **[PROJECT.md](PROJECT.md)** — Overview, timeline, success criteria
   - What is this project?
   - When will it be done?
   - What's the status?

2. **[DECISIONS.md](DECISIONS.md)** — All architectural decisions made
   - Why did we choose X over Y?
   - What tradeoffs were considered?
   - What's still open?

---

## 🏗️ Implementation Phases

For each phase, read the detailed phase file:

| Phase | Duration | Read This | Then Do This |
|-------|----------|-----------|--------------|
| 1 | Weeks 1–2 | [PHASES/phase_1_foundation.md](PHASES/phase_1_foundation.md) | Create directories, scaffolds, run script |
| 2 | Weeks 2–3 | [PHASES/phase_2_design.md](PHASES/phase_2_design.md) | Write design docs, core utilities |
| 3 | Weeks 3–4 | [PHASES/phase_3_configuration.md](PHASES/phase_3_configuration.md) | Populate configs, implement Step 1 |
| 4 | Weeks 4–6 | [PHASES/phase_4_core_steps.md](PHASES/phase_4_core_steps.md) | Implement Steps 2–4 (transformation pipeline) |
| 5 | Weeks 6–7 | [PHASES/phase_5_model_lookup.md](PHASES/phase_5_model_lookup.md) | Implement Steps 3.5–4.5 (model enrichment) |
| 6 | Weeks 7–8 | [PHASES/phase_6_output_dq.md](PHASES/phase_6_output_dq.md) | Implement Step 5 (output generation) |
| 7 | Weeks 8–12 | [PHASES/phase_7_testing.md](PHASES/phase_7_testing.md) | Unit/integration/regression tests, docs |

**How to use:**
- Each phase file contains: objectives, deliverables, dependencies, effort estimate, code changes needed
- Read the phase file before starting that phase
- Check dependencies (what must be done first)
- Use the file as a checklist during implementation

---

## 📚 Design Documents

For deep dives on complex logic:

- **[DESIGN_DOCS/composite_part_number_normalization.md](DESIGN_DOCS/composite_part_number_normalization.md)**
  - How EN/FR part numbers with "or"/"ou" are normalized
  - Algorithm, edge cases, examples

- **[DESIGN_DOCS/trim_generalization_algorithm.md](DESIGN_DOCS/trim_generalization_algorithm.md)**
  - How "Sport" maps to ["Sport AWD", "Sport FWD", "Sport Hybrid"]
  - Integration with VehicleSearchEngine

- **[DESIGN_DOCS/dq_rule_specifications.md](DESIGN_DOCS/dq_rule_specifications.md)**
  - All DQ rule names and message templates
  - When each rule fires; what it means; how to fix

- **[DESIGN_DOCS/batch_reporting_schema.md](DESIGN_DOCS/batch_reporting_schema.md)**
  - Structure of batch_summary_dq.json
  - Aggregation metrics, pass/fail per file

**When to read:**
- Before Phase 2 (to understand what needs to be designed)
- Before implementing related phases (e.g., read trim_generalization before Phase 5)
- During code review (as reference documentation)

---

## 📦 Deliverables Folder

As phases complete, deliverables are collected here:
- [DELIVERABLES/](DELIVERABLES/)
  - Phase 1 completion checklist
  - Phase 2 design docs (once created)
  - Phase 3 config files (once populated)
  - etc.

This folder helps track progress and ensures nothing is lost.

---

## 🔍 Cross-References

**Original Architecture Notes:**
- See `accy_v2/planning/research/Notes/Honda_pipeline_modenization` for user's detailed requirements

**System Architecture (Reference):**
- See `accy_v2/docs/SYSTEM_ARCHITECTURE.md` for 5-layer pipeline overview
- See `accy_v2/docs/config_schema.md` for config file format

**Existing OEM Implementation (Template):**
- See `accy_v2/oems/hyundai_genesis/pipeline/` for orchestrator pattern
- See `accy_v2/oems/mazda/config/` for config structure

---

## ❓ FAQ

**Q: I'm new to this project. Where do I start?**
A: Read PROJECT.md, then the current phase file (e.g., phase_1_foundation.md if Phase 1 is active).

**Q: I need to understand why we made decision X.**
A: See DECISIONS.md → find the decision → read the rationale.

**Q: I'm implementing Phase 4. What do I need to know about reconciliation?**
A: Read phase_4_core_steps.md (high-level), then DESIGN_DOCS/composite_part_number_normalization.md (deep dive).

**Q: What's the status of the project?**
A: Check PROJECT.md → Timeline & Phases section. Or check DELIVERABLES folder for completed work.

**Q: Where do I document my findings during implementation?**
A: Add to DELIVERABLES/ folder with a new markdown file. Use naming: `phase_N_completion.md`.

---

## 📝 How to Update This Navigation

When you:
- ✅ Add a new design doc → Add it to the "Design Documents" table above
- ✅ Complete a phase → Add completion notes to DELIVERABLES/
- ✅ Change dependencies → Update phase files + this navigation
- ✅ Add new decisions → Add to DECISIONS.md + link from PROJECT.md

---

**Last Updated:** 2026-09-23  
**Current Active Phase:** Phase 1 (Foundation & Setup) — Ready to start
