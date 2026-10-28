# 011 — Requirements Register and Documentation Standard: Design

**Status:** Idea — waiting for decisions (DOC-1 to DOC-10)
**Updated:** 2026-10-28
**Next:** user decides DOC-1 to DOC-10 (OI-13)
**Links:** extends idea / plan [010](010_work_process_and_tracking_design.md) · rules in [../../CLAUDE.md](../../CLAUDE.md)
**Summary:** A requirements register that captures every lasting rule when it is decided, a documentation set with one audience per doc, and a documentation step in the definition of done.

**Asked for:**
- a requirements document with the key project requirements, updated for every decision as we work;
- it is part of the documentation agents check and complete in the development process;
- after every plan is done and tested, the documentation states how it works and records the requirements;
- a documentation plan, done the way senior engineers do it.

## What exists today, and the gaps

| Today | Gap |
|---|---|
| About 95 decisions across ideas 001–010 (D1–D19, L1–L6, A1–A17, E1–E7, L1–L5, C1–C8, P1–P13, V1–V8, G1–G9, R1–R3) | Lasting rules ("never pad", "an accessory fits its whole set", "config, not code") are mixed in with one-off choices, spread over 10 files. Nothing lists **what the system must always do** |
| Some rules are restated in `CLAUDE.md`, the README and memory | Copies drift. There's no single home that the others link to |
| `README.md` (186 lines) mixes how to run, config, outputs and design | One file serves the manager, the engineer and the agent; hard to find things, and long to load |
| `db/README.md` (data dictionary), `data_issues.md` (issues and definitions) | Good. They stay, and get linked rather than copied |
| Ideas hold the *why*; plans hold the *what was built* | Nothing describes **how a feature works now**, after several plans have changed it (e.g. the accessory pipeline after 003, 006, 007, 008) |
| Tests prove behaviour | Nothing links a requirement to the test that proves it |

## How senior engineers do it, and what we take from each practice

| Practice | What it means here |
|---|---|
| **Requirements are numbered, stated once, and traceable** | Each has an ID, one "shall" sentence, the reason, the source decision, and the test that proves it |
| **Decisions are recorded where they're made** (ADRs) | Our ideas' *Decisions* tables and the plans' *Decision logs* already are the ADRs. The register links to them and doesn't copy them |
| **Docs as code** | Docs live in the repo and change in the same commit as the code. They're reviewed with the change, and checked by tests (links, IDs, coverage) |
| **One home per fact; link, don't copy** | Each fact has one owning file (table below); others link to it |
| **Each doc has one audience and one job** | Run it, operate it, change it, look things up. Split by reader, not by topic |
| **Definition of done includes docs** | A plan isn't complete until its doc tasks are ticked; a test checks the parts that can be checked |
| **Describe the system as it is now** | Feature docs are rewritten as the feature changes. History stays in the ideas, plans and changelog |
| **Real examples** | Docs use real values from the data (`000071200`, `25 min → 0.42 h`), not `foo` / `bar` |

## 1. The requirements register: `docs/REQUIREMENTS.md`

### One entry per requirement

```markdown
### REQ-PN-01 — Part numbers are never padded
- **Requirement:** The pipeline shall never add characters to a part number. A part number is changed only
  when `make&model` proves the complete number (leading zeros restored).
- **Why:** padding is a guess. Part numbers run from 9 to 14 characters, and a padded value is never checked.
- **Source:** user, 2026-10-27 · idea 008 P6
- **Verified by:** `tests/test_part_number_helpers.py::test_a_part_number_is_never_padded`
- **Status:** Implemented (plan 008)
```

| Field | Rule |
|---|---|
| **ID** | `REQ-<AREA>-NN`. Never reused, never renumbered |
| **Requirement** | One sentence with "shall": testable, about behaviour, not about code |
| **Why** | The reason, in a line. It's what stops someone "simplifying" the rule away |
| **Source** | Who decided and when, plus the decision ID (`idea 008 P6`). Several sources if it was refined |
| **Verified by** | A test (`file::test_name`), a check (`test_messages.py`), or `manual: <how>` when it can't be automated |
| **Status** | `Approved — planned (idea NNN)` → `Implemented (plan NNN)` → `Superseded by REQ-…` (kept, never deleted) |

### Areas (each a section, with an index table at the top)

| Area | Covers | Examples (from decisions already made) |
|---|---|---|
| `SCOPE` | Make, years, statuses in scope | VW only (D7); `min_model_year: 2020`, `max` optional (D9); Active parts only |
| `VEH` | Vehicle ingest and taxonomy | Key `(model_number, model_year)` (D19); option sets strict (D16); `Edition` never alone (D13) |
| `MATCH` | Accessory to vehicle matching | Fits the **whole** (model, submodel, year) set, never narrowed by descriptions (A1, A4); a unique key lookup, no saved merge table (A1) |
| `PN` | Part numbers | Never padded (P6); proven from `make&model` (P1, P7); exported as Excel text (P5) |
| `DATA` | Cleaning and units | Labour time in hours, 2 decimals, unit in the header (L1–L5); comments cleaned, raw text kept (C1–C6) |
| `CFG` | Configuration | Rules, words, units, thresholds and messages in config; validated at load with `CONFG_` codes (D1, D10) |
| `LOG` | Logging and traceability | Every change logged before → after with its rule; every excluded row has a reason (002 L1–L6) |
| `FLAG` | Flags and review | Every flag has a code with message, checked, found, causes, fix (E1–E7); option-set flags never stop the run (D17) |
| `VER` | Human-verified facts | Exact match only; contradictions are errors; nothing deleted (V1–V8) |
| `OUT` | Outputs | One sheet per accessory model name, matched rows only, Year column (A10, A13); the run report `<run_id>_report.xlsx` (R1–R3) |
| `PROC` | How we work | idea → plan → build → completed, with approvals (G1); commit approved and tested work, push only when asked (W-A) |
| `NFR` | Non-functional | Runs on Windows in OneDrive; a locked file gives a clear error, not a crash; full runs under a minute today |

The seed register is built from the ~95 decisions above. Only lasting rules become requirements, about 50 by a first count. One-off choices ("Performance is a package") stay in the ideas.

### When a requirement is written (the point of the request)

| Moment | What happens |
|---|---|
| **The user states a rule or makes a decision** that changes what the system must always do | The agent adds the requirement **in the same turn**: status `Approved — planned` with the source, or `Proposed` if the user hasn't confirmed it. Then it says so in its reply ("Added REQ-PN-01") |
| **Idea stage** | Each idea gets a `## Requirements` section: new REQs, changed REQs, REQs it must respect. Its decisions table marks which rows become requirements (`→ REQ-…`) |
| **Plan stage** | Each REQ the plan delivers gets a success criterion and a test |
| **Build** | `Verified by` filled with the real test name |
| **Completed** | Status `Implemented (plan NNN)`. A test checks every REQ's `Verified by` points to a test that exists |
| **A requirement changes** | Never edited in place. The old one becomes `Superseded by REQ-…`, and the new one has its own source decision |

## 2. The documentation set (each doc has one reader and one job)

```
source_code/VW/
├── README.md                 START HERE: what it is, run it in 3 commands, where everything is (short)
├── CHANGELOG.md              what shipped, when (plan 010)
├── CLAUDE.md                 agent rules (loaded automatically)
├── docs/
│   ├── REQUIREMENTS.md       what the system must always do, and why        → everyone
│   ├── ARCHITECTURE.md       how it works overall: pipelines, steps, data   → engineers, agents
│   │                         flow, files, why it's built this way
│   ├── features/             how each feature works now, one file each      → engineers, agents
│   │   ├── vehicle_ingest.md      accessory_matching.md     part_numbers.md
│   │   ├── logging_and_flags.md   labour_units.md           comment_cleaning.md   ...
│   ├── RUNBOOK.md            operate it: run, read the report, act on each  → platform manager
│   │                         flag, routine tasks, troubleshooting
│   └── CONFIG.md             every config file and key: meaning, default,   → whoever changes config
│                             valid values, the error when it's wrong
├── db/README.md              data dictionary: every file and column (stays next to the data)
└── planning/                 ideas, plans, completed, data issues, open items (history and decisions)
```

| Doc | Reader | Job | Updated when |
|---|---|---|---|
| `README.md` | anyone, first | Orient and run. Under about 80 lines; links to everything else | a new entry point or output |
| `docs/REQUIREMENTS.md` | everyone | The rules the system must keep | every lasting decision (same turn) |
| `docs/ARCHITECTURE.md` | engineers, agents | The big picture: both pipelines step by step, the data flow, the folders, the main design choices (with links to the ideas) | a step, file or flow changes |
| `docs/features/<name>.md` | engineers, agents | How one feature works **now** | each plan that changes the feature |
| `docs/RUNBOOK.md` | platform manager | What to do after a run, per action and flag. Routine tasks: add a keyword, a model year, a verified fact; take a new source file. Troubleshooting (file locked, config error) | new flags, actions or tasks |
| `docs/CONFIG.md` | config editors | The reference for every key | a config key is added or changed |
| `db/README.md` | analysts, engineers | Every output file and column | a file or column changes |

### The feature-doc template ("how it works")

```markdown
# Part numbers
**Covers:** REQ-PN-01 … REQ-PN-05 · **Built by:** plan 008 · **Updated:** 2026-10-27

## What it does            two or three sentences, for someone new
## How it works            the flow (diagram), step by step, with a real example (71200 -> 000071200)
## Config                  the keys it reads, with a link to CONFIG.md
## Inputs and outputs      the files and columns it reads and writes, with a link to db/README.md
## Flags                   each code: when it fires and what to do (link to RUNBOOK.md)
## Edge cases and limits   what it deliberately doesn't do (never pads; never uses the hint)
## Changing it safely      the tests that guard it, and what to rerun
## History                 the ideas and plans that shaped it
```

## 3. Documentation in the development process (definition of done)

Every plan ends with a mandatory **Documentation phase**, with these tasks. At *Completed*, each is ticked or marked "n/a: why".

| # | Task | Checked by |
|---|---|---|
| 1 | Requirements: new or changed REQs written; `Verified by` points to real tests; status set to `Implemented` | test |
| 2 | Feature doc: "how it works" written or updated for every feature the plan touched | test (a completed plan links a feature doc) + review |
| 3 | Architecture: steps, files and flow still accurate | review |
| 4 | Runbook: every new flag or action has a "what to do" entry | test (every `messages.yaml` code with severity warning or above appears in the runbook) |
| 5 | Config reference: every new key documented | test (every key in `config/*.yaml` appears in `CONFIG.md`) |
| 6 | Data dictionary: every new output file and column documented | review |
| 7 | Changelog entry; completion notes; index; open items | test (plan 010) |
| 8 | Links: every relative link in the docs resolves | test |

The agent does the review items as a written pass: it reads each doc the plan touched against the code, and records "docs checked" in the completion notes.

## 4. Building it (for the plan, once approved)

| Phase | Gives |
|---|---|
| **DOC-A** Skeleton and rules | The `docs/` folder and templates; the documentation phase added to `CLAUDE.md` and the plan template; the doc checks in `tests/test_planning_docs.py` (renamed `test_docs.py`) |
| **DOC-B** Requirements register | All lasting rules from ideas 001–010, with sources; `Verified by` mapped to existing tests; gaps listed as `manual:` or as a missing test (an open item) |
| **DOC-C** How it works (backfill) | `ARCHITECTURE.md`, feature docs for 001, 002, 003+004, 006, 007, 008; README shortened to a start page with links; config notes moved to `CONFIG.md` |
| **DOC-D** Runbook | For the platform manager: the after-run routine (today's files; the run report once idea 005 is built), one entry per flag code, routine tasks, troubleshooting |

Order:
1. Plan 010 first (headers, index, open items, changelog, checks).
2. Then 011, which extends those checks.
3. Then plan 009, the first feature built under the full standard.

## Decisions

| # | Question | Proposed |
|---|---|---|
| DOC-1 | One register, `docs/REQUIREMENTS.md`, with `REQ-<AREA>-NN` entries (requirement, why, source, verified by, status) and an index table at the top? | Yes |
| DOC-2 | Only **lasting rules** become requirements; one-off choices stay in the ideas? | Yes. About 50 from today's 95 decisions |
| DOC-3 | The agent writes a requirement **in the same turn** a rule is decided, and says so in its reply; `Proposed` until you confirm? | Yes |
| DOC-4 | Requirements are never edited in place or deleted: `Superseded by` with a new ID? | Yes |
| DOC-5 | The doc set above: README (start page), `docs/` REQUIREMENTS, ARCHITECTURE, features/, RUNBOOK, CONFIG; `db/README.md` stays as the data dictionary? | Yes |
| DOC-6 | One feature doc per feature, describing how it works **now**, using the template? | Yes |
| DOC-7 | Every plan ends with a Documentation phase (tasks 1–8); a plan can't be `Completed` until it's done? | Yes |
| DOC-8 | Tests check what can be checked: requirement tests exist, links resolve, every flag in the runbook, every config key in `CONFIG.md`, completed plans link a feature doc? | Yes |
| DOC-9 | The runbook is written for the platform manager, and becomes the "what to do" behind the run report's actions (idea 005)? | Yes |
| DOC-10 | Order: plan 010, then 011, then plan 009 built under the full standard? | Yes |
