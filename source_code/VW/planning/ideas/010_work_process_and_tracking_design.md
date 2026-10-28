# 010 — Work Process, Tracking and Indexing: Design

**Status:** Idea — approved (G1–G9, 2026-10-28)
**Updated:** 2026-10-28
**Next:** build plan 010
**Links:** plan [010](../plans/010_work_process_and_tracking.md) · rules in [../../CLAUDE.md](../../CLAUDE.md)
**Summary:** The idea → plan → build → completed process, what we track and where, and indexing so status is read without loading whole files.
**Applies to:** all VW work: the planning folder, the docs, and how an agent finds what was done
**Asked for:**
- every new task goes idea → planning → implementation → moved to completed and documented;
- the instructions load by default whenever the VW project is worked on;
- a plan for what we track and keep updated;
- indexing, so checking what has been worked on doesn't mean loading whole files.

## What exists today, and the gaps

| Already there | Gap |
|---|---|
| `planning/README.md`: lifecycle and an *Index* table | The index has no **next action** or **last updated** columns, so it says what exists, not what to do next |
| A `**Status:**` line at the top of each doc | Each status is worded differently, so a grep can't sort them (see below) |
| `ideas/`, `plans/`, `completed/` folders | `completed/` is empty. Nothing defines when something counts as done, so six plans sit at "Built, in user testing" |
| Decisions tables, decision logs, build notes | Ideas 006–008 were built without a plan (now written up as as-built plans) |
| `data_issues.md` with a summary table and `### DI-NN` sections | Works well as an index. It is updated by hand, and one heading is stale ("Units and text (planned, ideas 006 and 007)") |
| — | Follow-ups are scattered across plans and the conversation: notebook cells, questions for the data source, open questions, the YAML review |
| — | No dated record of what shipped, so the work log only exists in git |

The status lines today, all different:

```
ideas/001  **Status:** Idea — all decisions made (see [Decisions](#decisions))
ideas/006  **Status:** Built 2026-10-28 — all decisions (L1–L5) approved; see *Build notes* at the end
plans/001  **Status:** Built 2026-10-26 — 74 tests passing; in user testing. Open: review of ...
plans/003  **Status:** Built 2026-10-27, in user testing. 152 tests pass. Open: notebook cell ...
```

**Done already, from this request (2026-10-28):**
- `source_code/VW/CLAUDE.md` holds the four-stage process, "read the index first", the update checklist and the standing rules. It loads automatically for any work in this folder.
- Plans 006, 007 and 008 are written up as as-built plans.

The rest below waits for approval.

## 1. The process: four stages, three approval gates

```
Idea ──G1──► Plan ──G2──► Build ──G3──► Completed
     approve       approve        user signs off testing
     decisions     the plan
```

| Stage | Status value (fixed words) | Lives in | Leaves the stage when |
|---|---|---|---|
| Idea | `Idea — waiting for decisions` / `Idea — approved` | `ideas/NNN_*_design.md` | the user approves every decision |
| Plan | `Plan — waiting for approval` / `Plan — approved` | `plans/NNN_*.md` | the user approves the plan |
| Build | `Building` / `Built — in user testing` | `plans/NNN_*.md` (tasks ticked) | tests and real runs pass, then the user signs off |
| Completed | `Completed` | `completed/NNN_*.md` (the plan moved there) | — |
| Others | `Seed` (an idea to discuss later), `Dropped` (with the reason) | where they are | — |

What "documented" means at completion, as a checklist in the completion notes:
1. the plan's *Completion notes*: what shipped, where it lives, tests, real-run numbers, follow-ups;
2. `README.md` / `db/README.md` updated for any new run option, output, config block or flag;
3. `data_issues.md` statuses updated;
4. a `CHANGELOG.md` entry (section 2);
5. follow-ups moved to `open_items.md` (section 2);
6. the index row set to `Completed`.

## 2. What we track: one home for each kind of fact

| What | Single home | Updated when | New? |
|---|---|---|---|
| Stage, status and next action of every work item | `planning/README.md` *Index* (columns: #, title, stage, next, updated) | every stage change | add 2 columns |
| Decisions before the build | the idea's *Decisions* table | when the user decides | — |
| Tasks, progress, deviations | the plan's checkboxes and *Decision log* | during the build | — |
| What shipped, and when | `source_code/VW/CHANGELOG.md`: one dated entry per completed or built item, with the plan number and commit | at build and at completion | **new** |
| Follow-ups and questions | `planning/open_items.md`: `OI-NN`, item, owner (user / data source / agent), linked doc, status | when one appears or closes | **new** |
| Data issues | `planning/data_issues.md` (`DI-NN`, `DV-NN`) | when found or fixed | — |
| Today's baseline numbers (vehicles, rows, keys, errors, tests) | a short *Baseline* table in `planning/README.md` | after each build's real run | **new section** |
| Flag codes and messages | `config/messages.yaml` (test-enforced) | with the code | — |
| How to run, outputs, config | `README.md`, `db/README.md` | at build | — |
| Standing rules for agents | `source_code/VW/CLAUDE.md` | when a rule changes | done |

Rule: a fact is written in its home, and other docs **link** to it rather than copying it. Copies are what go stale.

`open_items.md` would start with what is open today:

| OI | Item | Owner | Linked |
|---|---|---|---|
| OI-01 | Sign off testing of plans 001, 002, 003, 006, 007, 008 | user | plans |
| OI-02 | Notebook cells for plans 001, 002, 003 (when the notebook is closed) | agent | plans 001–003 |
| OI-03 | Review `config/vehicles/*.yaml` (status `drafted` → `reviewed`) | user | plan 001 |
| OI-04 | Atlas 2020, ID.4 2026, ID. Buzz 2026: missing vehicles or wrong year ranges? | data source | DI-05 |
| OI-05 | No parts for model year 2027 | data source | DI-06 |
| OI-06 | Labour time 0.4 for `3QF601025KAX1` | data source | DI-07 |
| OI-07 | Export `stockCode` as text | data source | DI-03, plan 008 |
| OI-08 | "ReferAlways": what the "Refer..." sentence should say (optional) | data source | DI-16 |
| OI-09 | Should accessory lookup misses be warnings instead of errors? | user | plan 003 |
| OI-10 | Decisions V1–V8 | user | idea 009 |
| OI-11 | Report card and DQ sheet | user | idea 005 (seed) |

## 3. Indexing: find things without loading whole files

Four layers, cheapest first:

| Layer | What | How an agent uses it |
|---|---|---|
| **1. The index** | `planning/README.md` *Index* + `open_items.md`: one line per item, under 60 lines each | Read these two files first. That answers "what has been worked on, what's next" |
| **2. A fixed header** | The first 6 lines of every idea and plan, with fixed field names (below) | `grep -m1 "^\*\*Status:" planning/*/*.md` gives a status board; or read a doc with a 10-line limit |
| **3. Stable IDs and headings** | `NNN`, `DI-NN`, `OI-NN`, decision IDs (`L1`, `C3`, `P6`), fixed headings (`## Decisions`, `## Decision log`, `## Completion notes`) | `grep -n "^## Decision log" plans/003*.md`, then read from that line with a limit |
| **4. A check** | `tests/test_planning_docs.py` (G7) | Fails when the index and the docs disagree, so the index can be trusted without opening the docs |

The fixed header for every idea and plan:

```markdown
# 006 — Labour Time Units (minutes → hours): Plan

**Status:** Built — in user testing
**Updated:** 2026-10-28
**Next:** user signs off testing (OI-01); confirm the 0.4 value (OI-06)
**Links:** idea [006](../ideas/006_labor_time_units_design.md) · depends on plan [003](003_accessory_model_matching.md)
**Summary:** Labour time converted from minutes to hours, with the multiplier from unit definitions in config.
```

- `Status` uses only the fixed words from section 1. Detail goes in `Next` or the body.
- `Summary` is one sentence, so the header alone says what the item is.

What the check verifies (it runs with the normal test suite):
- each idea and plan has the five header fields, with a status from the fixed list;
- every file in `ideas/`, `plans/` and `completed/` has an index row, and each row's stage matches the file's `Status`;
- every plan links to an idea with the same number; every `Built` or `Completed` plan has a matching idea with all decisions made;
- every file in `completed/` has a `## Completion notes` section;
- every `OI-NN` mentioned in the docs exists in `open_items.md`.

## 4. Applying it to what exists (once approved)

1. Rewrite the header of the 9 ideas and 6 plans into the fixed form. Only the first lines change; the bodies stay.
2. Add *Next* and *Updated* columns and a *Baseline* table to `planning/README.md`.
3. Create `open_items.md` (the list above) and `CHANGELOG.md`, seeded from the commits so far (`7b42c88`, `b068917`, `f0e0ffa`) and today's uncommitted work.
4. Add `tests/test_planning_docs.py`.
5. Fix the stale data-issues heading. Add a *Last updated* line check.
6. Nothing moves to `completed/` until the user signs off (OI-01).

## Decisions

| # | Question | Proposed |
|---|---|---|
| G1 | Four stages with three approval gates: idea (decisions approved) → plan (plan approved) → build → completed (user signs off testing)? | ✅ 2026-10-28: Yes |
| G2 | A "new task" is anything that changes pipeline code, config behaviour or outputs; questions, investigations and doc-only fixes skip the process? | ✅ 2026-10-28: Yes |
| G3 | At completion, the **plan** moves to `completed/`; the idea stays in `ideas/` with status `Completed` and a link? | ✅ 2026-10-28: Yes. Ideas keep their links stable, and the completed folder holds the record of what shipped |
| G4 | Fixed status words and a five-field header (`Status`, `Updated`, `Next`, `Links`, `Summary`) on every idea and plan? | ✅ 2026-10-28: Yes |
| G5 | New `planning/open_items.md` (`OI-NN`) as the single list of follow-ups and questions? | ✅ 2026-10-28: Yes |
| G6 | New `source_code/VW/CHANGELOG.md`, one dated entry per build and completion? | ✅ 2026-10-28: Yes. The repo root's `accy_v2` changelog stays separate |
| G7 | `tests/test_planning_docs.py` checks the index against the docs, so drift fails the test suite? | ✅ 2026-10-28: Yes. The alternative, a script that generates the index, rewrites a file people also edit by hand |
| G8 | A *Baseline* table (today's run numbers and test count) in `planning/README.md`? | ✅ 2026-10-28: Yes. Updated after each build's real run |
| G9 | `source_code/VW/CLAUDE.md` (done) is the always-loaded rulebook: short, linking to the planning docs rather than copying them? | ✅ 2026-10-28: Yes. It stays under about 80 lines so it costs little context every session |

After approval: plan 010 (the steps in section 4), then the build.
