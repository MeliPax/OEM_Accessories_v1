# VW Planning

Planning workspace for the VW data work (model ingest, taxonomy, accessory matching).

```
planning/
├── ideas/       Design options, trade-offs, open questions. Nothing here is committed to yet.
├── plans/       Approved work, broken into phases with tasks and acceptance criteria.
└── completed/   Plans (or phases) that are done, moved here with a short completion note.
```

## Lifecycle

1. **Idea** — write it in `ideas/NNN_short_name.md`. Capture the problem, options, a recommendation and open questions.
2. **Plan** — once the idea's decisions are made, create `plans/NNN_short_name.md` with phases. Link back to the idea.
3. **Execute** — tick off tasks in the plan as they land. Note deviations in the plan's *Decision log*.
4. **Complete** — when a plan (or a self-contained phase) is done, move it to `completed/`, and add a *Completion notes* section: what shipped, where it lives, test/verification results, follow-ups.

## Naming

- `NNN_` is a 3-digit sequence shared across all three folders, so an idea, its plan and its completion record keep the same number (e.g. `001_vw_model_ingest_design.md` → `001_vw_model_ingest_mvp.md`).
- Use lowercase `snake_case` after the number.

## Index

| # | Title | Stage |
|---|---|---|
| 001 | [VW model ingest — design ideas](ideas/001_vw_model_ingest_design.md) | Idea (decisions pending) |
| 001 | [VW model ingest — MVP plan](plans/001_vw_model_ingest_mvp.md) | Plan (draft, pending idea decisions) |
