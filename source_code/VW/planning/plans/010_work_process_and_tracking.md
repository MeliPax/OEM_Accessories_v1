# 010 — Work Process, Tracking and Indexing: Plan

**Status:** Plan — approved (2026-10-28)
**Updated:** 2026-10-28
**Next:** build; idea 011 (requirements and documentation) extends Phases W2–W4 once approved
**Links:** idea [010](../ideas/010_work_process_and_tracking_design.md) (G1–G9) · rules in [../../CLAUDE.md](../../CLAUDE.md)
**Summary:** Fixed headers and status words on every planning doc, an index with next actions, `open_items.md`, `CHANGELOG.md`, a baseline table, and a test that keeps the index and the docs in step.

## Outcome

- Anyone, or any agent, can see what has been worked on and what comes next by reading **two short files**: the *Index* in `planning/README.md` and `planning/open_items.md`. One grep gives the status of every doc.
- Every planning doc opens with the same five fields.
- A test fails when the index and the docs disagree.

**Success criteria**

- [ ] All ideas and plans (10 ideas, 8 plans today) open with `Status` / `Updated` / `Next` / `Links` / `Summary`, using only the fixed status words (G4).
- [ ] `grep -m1 "^\*\*Status:" planning/*/*.md` prints one fixed-word status per file.
- [ ] The README *Index* has `Next` and `Updated` columns, one row per idea and plan, and a *Baseline* table (G8).
- [ ] `planning/open_items.md` exists with OI-01 to OI-11 from the idea (G5), each with an owner and a linked doc.
- [ ] `source_code/VW/CHANGELOG.md` exists, seeded from commits `7b42c88`, `b068917`, `f0e0ffa` and today's uncommitted work (G6).
- [ ] `tests/test_planning_docs.py` passes, and fails on each broken case (missing field, unknown status, file not indexed, index stage ≠ file status, plan without idea, completed plan without *Completion notes*, unknown `OI-NN`) (G7).
- [ ] `CLAUDE.md` names the new files and stays under 80 lines (G9).
- [ ] Nothing is moved to `completed/` (that waits for the user's sign-off, OI-01).
- [ ] **Resume, not redo:** build work interrupted at any point (a session ends, context runs out, the machine restarts) carries on from its last checkpoint. Ticked tasks are checked, not redone (Phase W5).

---

## Phase W1 — Headers and status words

- [ ] Rewrite the first lines of each idea and plan into the five-field header. Old detail moves to `Next` or the body; the bodies stay as they are.
- [ ] Fixed status words:
  - `Seed`;
  - `Idea — waiting for decisions` / `Idea — approved` / `Completed`;
  - `Plan — waiting for approval` / `Plan — approved` / `Building` / `Built — in user testing`;
  - `Dropped`.
  - A date or extra detail may follow after ` (`, e.g. `Idea — approved (2026-10-28)`.
- [ ] Update the *Lifecycle* section of `planning/README.md` to the four stages and three gates (G1, G3).

**Done when:** the grep above prints only fixed-word statuses.

## Phase W2 — Tracking files

- [ ] README *Index*: columns `#`, `doc`, `stage`, `next`, `updated`.
- [ ] README *Baseline*: vehicles 269 · accessory rows unique 1,357 · keys 71 (64 found / 7 missed) · exported rows 25,345 · review rows 467 · tests 221. Update it after each build's real run.
- [ ] `planning/open_items.md`: the table from the idea, plus a short "how to add / close an item" note. A closed item keeps its row, with status `Closed` and the date.
- [ ] `CHANGELOG.md`: newest first, one entry per build or completion: date, plan numbers, what changed, commit.
- [ ] `planning/data_issues.md`: fix the stale heading "Units and text (planned, ideas 006 and 007)", and update *Last updated*.

**Done when:** each file exists, and the index has every doc.

## Phase W3 — The check (`tests/test_planning_docs.py`)

- [ ] Parse the header of every `ideas/*.md`, `plans/*.md` and `completed/*.md`.
- [ ] Check:
  - the fields are present and the status is a fixed word;
  - every file has an index row with a matching stage;
  - every plan has an idea with the same number;
  - every completed plan has `## Completion notes`;
  - every `OI-NN` mentioned exists in `open_items.md`.
- [ ] One failing case per check, using a copy of the planning folder in `tmp_path`.

**Done when:** the test passes on the real folder, and every broken case fails with a readable message.

## Phase W4 — Rules file

- [ ] `CLAUDE.md`: name `open_items.md`, `CHANGELOG.md` and the baseline in the *Keep updated* table; point to the header format; keep it under 80 lines.

**Done when:** the rules file names the new files and stays under 80 lines.

## Phase W5 — Resume after an interruption

The goal: never redo work that already landed.

| What can stop the work | What is lost today | With W5 |
|---|---|---|
| The session ends, or context runs out mid-build | Where it stopped lives only in the conversation | The plan's checkpoint says where, and what is half done |
| The machine restarts, or OneDrive syncs mid-edit | Uncommitted files may be half edited, with no record of which | The checkpoint lists the files in progress; tests show whether they're whole |
| A long gap between sessions | Someone has to re-read the conversation | Read the checkpoint, check, continue |

- [ ] **Small tasks, ticked as they land.** Each plan task fits in one sitting. It is ticked the moment it's done, with its evidence: the test that passes, or the file and function.
- [ ] **A checkpoint line in the header**, for plans with status `Building`:

  ```markdown
  **Checkpoint:** 2026-10-28 14:10 · Phase V3, task 2 of 4 · done: verify_helpers.py + 6 tests passing
                  · in progress: wiring into run_ingest.py (not run yet) · files: pipeline/verify_helpers.py, run_ingest.py
  ```

  It's updated at the end of every phase, before any long step, and whenever work stops.
- [ ] **Phases end in a safe state.** Each phase's *Done when* leaves the full test suite passing. A phase boundary is always a clean place to stop.
- [ ] **Resume procedure** in `CLAUDE.md`. At the start of a session:
  1. look for any plan with status `Building`;
  2. read its checkpoint and its first unticked task;
  3. run `git status` and the test suite to confirm the state matches the checkpoint;
  4. continue from there.

  Ticked tasks are checked, not redone. If the state doesn't match the checkpoint, stop and report before changing anything.
- [ ] **A commit per phase** (decision W-A below): with the user's standing approval, each finished phase is committed on the feature branch. A restart then loses at most the phase in progress.
- [ ] `tests/test_planning_docs.py`: a `Building` plan must have a `Checkpoint` line.

**Done when:** a test session can be stopped mid-phase and resumed from the checkpoint, with no ticked task redone.

**Not included: anything for interrupted pipeline runs** (user decision, 2026-10-28). A full vehicle ingest takes 1 second and a full accessory run takes 12 seconds, so an interrupted run is simply rerun. Revisit if runs grow past a few minutes (more OEMs, bigger files).

## Open decision

| # | Question | Proposed |
|---|---|---|
| W-A | Standing approval to commit each finished phase on the feature branch (no push), so an interruption loses at most one phase? | ✅ 2026-10-28: Yes. User: "you can commit what is approved and tested without needing my confirmation". Pushing still needs the user |

---

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-10-28 | G1–G9 approved as proposed | User: "I like the ideas in 9 and 10" |
| 2026-10-28 | `CLAUDE.md` and the as-built plans 006–008 already done, before this plan | Asked for directly in the same request |
| 2026-10-28 | **Plan.** Plans 009 and 010 already use the five-field header | The format was approved (G4); no rewrite needed later |
| 2026-10-28 | **Plan.** Phase W5 added: checkpoints and a resume procedure for interrupted build work | User: "prevent redoing the whole thing when the process is interrupted" |
| 2026-10-28 | Plan approved; W-A approved | User: "I like plan in 9 and 10"; "commit what is approved and tested" |
| 2026-10-28 | No retry or resume work for pipeline runs for now, and no idea for it | User: the pipelines are small and quick to run (1 s and 12 s); revisit if runs get long |

## Risks

| Risk | Mitigation |
|---|---|
| The index drifts from the docs again | `test_planning_docs.py` runs with every test run |
| The header rewrite loses information | Old status detail moves to `Next` or the body; reviewed in the diff before committing |
| The check is too strict for quick notes | It only reads the five header fields and the index; the bodies are free |
