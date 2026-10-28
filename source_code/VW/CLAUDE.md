# VW Project — Working Rules

These rules apply to all work under `source_code/VW`. They are loaded automatically whenever this folder is opened or its files are read. The repository-root `CLAUDE.md` covers `accy_v2`; for VW work, these rules apply.

## Every task goes through four stages

```
1. Idea  ──(user approves the decisions)──►  2. Plan  ──(user approves the plan)──►  3. Build  ──(user signs off testing)──►  4. Completed
```

| Stage | Write | Then |
|---|---|---|
| **1. Idea** | `planning/ideas/NNN_short_name_design.md`: what was asked for, what the data shows, the options, a recommendation, and a **Decisions** table | **Stop.** The user approves or changes each decision |
| **2. Plan** | `planning/plans/NNN_short_name.md`: outcome, success criteria, phases with tasks, tests, decision log, risks. Link back to the idea | **Stop.** The user approves the plan |
| **3. Build** | Code, config and tests as planned. Tick tasks as they land, and record any deviation in the plan's **Decision log** | Full test suite and real runs pass. Status becomes `Built YYYY-MM-DD — in user testing` |
| **4. Completed** | After the user signs off: move the plan to `planning/completed/` and add **Completion notes** (what shipped, where it lives, test and run results, follow-ups). Set the idea's status to `Completed` | Update the docs (checklist below) |

Rules:
- **Never skip a stage.** "Go ahead" on an idea means: write the plan. Build only after the plan is approved, unless the user explicitly says to skip the plan.
- A **new task** is anything that changes pipeline code, config behaviour or outputs. Questions, investigations and doc-only fixes don't need an idea.
- `NNN` is one number shared by an idea, its plan and its completion record. Take the next free number from the index.
- A stage change and its index update happen in the same turn.

## Read the index first, not whole files

- **What has been worked on:** the *Index* table in [planning/README.md](planning/README.md). Read it before opening any idea or plan.
- **One doc's status:** its first lines (`**Status:**` ...). Read with a line limit, or `grep -m1 "^\*\*Status" planning/*/*.md`.
- **Data issues:** the summary table at the top of [planning/data_issues.md](planning/data_issues.md). For details, grep `### DI-NN` and read only that section.
- **Long files** (the ideas and plans run to 400 lines; `pipeline/*.py` too): grep the heading or function, then read with offset and limit.

## Keep updated at every stage change

| What | Where |
|---|---|
| Stage and status | The doc's `**Status:**` line and the README *Index* row |
| Decisions | The idea's *Decisions* table before the build; the plan's *Decision log* from then on |
| Data issues found or fixed | `planning/data_issues.md` (summary table and the `DI-NN` section) |
| Flag codes | `config/messages.yaml` (a test checks code ↔ catalogue both ways) |
| How to run, outputs, config | `README.md`, `db/README.md` |

## Standing rules

- **Part numbers are never padded.** The complete part number must be proven from `make&model` (idea 008).
- **Config, not code:** rules, words, units, thresholds and messages live in `config/`, validated at load with `CONFG_` codes.
- **Every change is logged:** before → after with the rule; every flag carries a code from `messages.yaml`. Nothing is deleted silently.
- **Tests:** `python -m pytest -q` from `source_code/VW`. Real runs: `python run_ingest.py` and `python run_accessories.py`.
- **Notebook:** don't edit `oem_access_data_analysis.ipynb` while it is open in the IDE.
- **Git:** work on a `feature/vw-*` branch. Commit work that is **approved and tested** without asking (user, 2026-10-28), for example at the end of each finished phase. **Push only when the user asks.** Don't commit files outside `source_code/VW`, the notebook (unless the user asks), or generated files that don't match a pipeline run.
