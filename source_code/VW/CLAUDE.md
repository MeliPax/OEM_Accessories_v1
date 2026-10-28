# VW Project — Working Rules

These rules apply to all work under `source_code/VW`. They are loaded automatically whenever this folder is opened or its files are read. The repository-root `CLAUDE.md` covers `accy_v2`; for VW work, these rules apply.

## At session start

1. **Resume first.** If any plan in the [index](planning/README.md#index) is `Building`, read its `**Checkpoint:**` line and its first unticked task. Run `git status` and `python -m pytest -q` to confirm the state matches the checkpoint, then continue from there. Don't redo ticked tasks. If the state doesn't match, stop and report before changing anything.
2. Read the [index](planning/README.md#index) and [open_items.md](planning/open_items.md) for what's next.

## Every task goes through four stages

```
1. Idea  ──(user approves the decisions)──►  2. Plan  ──(user approves the plan)──►  3. Build  ──(user signs off testing)──►  4. Completed
```

| Stage | Write | Then |
|---|---|---|
| **1. Idea** | `planning/ideas/NNN_short_name_design.md`: what was asked for, what the data shows, the options, a recommendation, and a **Decisions** table | **Stop.** The user approves or changes each decision |
| **2. Plan** | `planning/plans/NNN_short_name.md`: outcome, success criteria, phases with tasks, tests, decision log, risks. Link back to the idea | **Stop.** The user approves the plan |
| **3. Build** | Status `Building`, plus a `**Checkpoint:**` line updated at each phase end and whenever work stops. Code, config and tests as planned. Tick tasks as they land, and record any deviation in the plan's **Decision log** | Full test suite and real runs pass → `Built — in user testing`. Commit each finished phase |
| **4. Completed** | After the user signs off: move the plan to `planning/completed/` and add `## Completion notes` (what shipped, where it lives, test and run results, follow-ups). Set the idea's status to `Completed` | Update the docs (checklist below) |

Rules:
- **Never skip a stage.** "Go ahead" on an idea means: write the plan. Build only after the plan is approved, unless the user explicitly says to skip the plan.
- A **new task** is anything that changes pipeline code, config behaviour or outputs. Questions, investigations and doc-only fixes don't need an idea.
- `NNN` is one number shared by an idea, its plan and its completion record. Take the next free number from the index.
- Every idea and plan starts with the five-field header (`Status`, `Updated`, `Next`, `Links`, `Summary`) and uses the fixed status words in [planning/README.md](planning/README.md#lifecycle-four-stages-three-approval-gates).
- A stage change and its index update happen in the same turn. `tests/test_planning_docs.py` fails when they drift.

## Read the index first, not whole files

- **What has been worked on, what's next:** the *Index* in [planning/README.md](planning/README.md) and [planning/open_items.md](planning/open_items.md). Read them before opening any idea or plan.
- **One doc's status:** its header (read with a 10-line limit), or `grep -m1 "^\*\*Status" planning/*/*.md`.
- **Data issues:** the summary table at the top of [planning/data_issues.md](planning/data_issues.md). For details, grep `### DI-NN` and read only that section.
- **Long files** (the ideas and plans run to 400 lines; `pipeline/*.py` too): grep the heading or function, then read with offset and limit.

## Keep updated at every stage change

| What | Where |
|---|---|
| Stage, next action, date | The doc's header and its README *Index* row (same words) |
| Decisions | The idea's *Decisions* table before the build; the plan's *Decision log* from then on |
| Follow-ups and open questions | `planning/open_items.md` (`OI-NN`, owner, status; closed rows kept) |
| What shipped | `CHANGELOG.md` (one entry per build or completion, with the commit) |
| Run numbers after a build | The *Baseline* table in `planning/README.md` |
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
