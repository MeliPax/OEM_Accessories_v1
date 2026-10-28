# 005 — Pipeline Run Report: Design

**Status:** Idea — waiting for decisions (R1–R3 decided 2026-10-28; R4–R12 open)
**Updated:** 2026-10-28
**Next:** user decides R4–R12 (OI-11)
**Links:** uses plans [002](../plans/002_pipeline_logging.md), [003](../plans/003_accessory_model_matching.md) · `VERIFIED` status from plan [009](../plans/009_human_verified_vehicle_facts.md)
**Summary:** One Excel run report per run (`<run_id>_report.xlsx`), one worksheet per category, built for the platform manager.
**Applies to:** both pipelines (vehicle ingest and accessories); one report per run
**Asked for:**
- a structured way to read a pipeline run that is easy for the **platform manager**;
- one main report with the high-level picture and stats, which then points to where the data-quality issues are reviewed;
- less chaotic, and hard to miss anything;
- (from the seed, 2026-10-27) a report card that covers the pipeline from start to finish for management and governance: which vehicles got updates, which have no data, which miss model numbers.

## Reading it as the platform manager

After a run, the manager wants answers to four questions, in this order:

1. **Can I use the output?** Did both pipelines finish, and on which data?
2. **What do I need to do?** Who has to do what, and what is new since last time?
3. **What changed?** New, removed and changed vehicles and parts.
4. **Where's the proof?** The detail behind any number, when someone asks.

### What happens today (latest run, 2026-10-28)

| What the manager meets | Why it's hard |
|---|---|
| **15+ files in 5 folders** (`db/dq`, `db/review`, `db/logs/...`, `output/`) and a terminal printout | No "start here". You have to know which file answers which question |
| **Two review files**, one per pipeline, in different shapes | Two places to check, and it's easy to look at one and forget the other |
| **467 review rows** for the accessories | They come down to **9 actions** (below). The manager has to do that grouping in their head every run |
| **32 flags**, 18 of them info | The noise sits next to the things that matter |
| **Every run overwrites the review files** | There's no telling what is new, what is still open from last week, or what was fixed |
| **No record of what was decided** ("asked VW on the 28th", "accepted") | The same items get checked again every run |
| **Silence means nothing:** a check that passed doesn't appear anywhere | "No warning" could mean "fine" or "never checked" |
| **The same source file run twice looks like a fresh refresh** | The manager may believe new data was processed when it wasn't |
| **The review file can be changed after the run, unnoticed** | Found while writing this: `db/review/accessory_review.csv` was overwritten at 09:04 today, an hour after the 08:04 run. It now holds 13 bare match keys instead of 467 review rows. Nothing in the pipeline writes that shape, and nothing would warn the manager |

### The 467 rows, as the 9 actions a manager would act on

| # | Owner | Action | Size | Severity |
|---|---|---|---|---|
| 1 | You decide | Atlas 2020: parts listed, but the vehicle export has no 2020 Atlas | 132 parts | error |
| 2 | You decide | ID.4 2026: parts listed, no 2026 ID.4 in the vehicle export | 92 parts | error |
| 3 | You decide | ID. Buzz 2026: same | 1 part | error |
| 4 | You decide | Golf R 2020–2021: parts listed, Golf R starts 2022 (never offered → verify, idea 009) | 54 parts, 108 part-years | error |
| 5 | You decide | Arteon 2022–2023: parts listed, Arteon ends 2021 (never offered → verify, idea 009) | 60 parts, 118 part-years | error |
| 6 | VW data | No parts yet for model year 2027: Atlas, Jetta, Jetta GLI, Taos, Tiguan | 14 vehicles | warning |
| 7 | VW data | Part `000071200` stored as a number (lost its zeros; restored from `make&model`) | 12 rows | warning |
| 8 | VW data | Labour time 0.4 on `3QF601025KAX1` looks like the wrong unit | 2 rows | warning |
| 9 | You (config) | 10 vehicle files still `drafted`, not `reviewed` | 10 files | check |

## The idea: one report per run, read top-down, built from the logs

**User direction (2026-10-28):**
- the report is an Excel file created by each run, named with the pipeline run id and timestamp;
- every report category is its own worksheet, so everything is in one place and reviewable at a glance;
- the logs are only for investigating, when more detail is needed;
- the goal is to go through it quickly without checking lots of other files.

What that means for the design:

| Rule | How |
|---|---|
| **One file per run, named by the run** | `output/reports/<run_id>_report.xlsx`, e.g. `vw_accessories_20261028_080428_report.xlsx`. The run id already carries the date and time, so the report sorts by time and matches the run's logs by name |
| **Each sheet stands on its own** | Rows 1–3 of every sheet show the run id, the run time, and the sheet's one-line takeaway (e.g. "Actions: 9 open, 0 new"). The data table starts on row 5, with filters and frozen headers |
| **Glance first, detail below** | The Summary fits on one screen. Every other sheet opens on its own totals, then the rows |
| **The report is enough to review** | Nothing in `db/` or `logs/` needs to be opened to decide what to do |
| **The logs are for investigating** | Each action and detail row has a `look in the logs` column: the log file, and the `record` / `code` to filter on, e.g. `logs/flags/vw_accessories_20261028_080428.csv`, code `ACCESS_COVER_VEHICLE_NO_PARTS`. *Run info* lists every log file of the run |

```
pipeline run ends
   └─► output/reports/<run_id>_report.xlsx               ◄── the only file the manager opens
         1 Summary     verdict · data used · headline numbers · the action list · every check
         2 Actions     one row per action: owner, what to do, size, new / open / resolved, since when
         3 Details     every review row behind each action (filter by action #)
         4 Changes     vehicles and parts added / removed / changed since the last run
         5 Coverage    model × submodel × year: vehicles, parts, status
         6 Funnel      each step's rows in → out, both pipelines
         7 Trend       the last 10 runs
         8 Run info    run ids, files and hashes, config versions, log file paths (for engineers)
```

Principles (what makes it easy, and hard to miss things):

| # | Principle | How |
|---|---|---|
| 1 | **One entry point** | One workbook covers both pipelines. The terminal prints its path and the verdict. The `db/` files stay for engineers and the pipeline |
| 2 | **Verdict first** | One word on the first line: **RED** (don't use the output), **AMBER** (usable, there are actions), **GREEN** (nothing to do). The rules are in config (R4) |
| 3 | **Actions, not rows** | Flags are grouped into actions with one owner and one fix sentence each. 467 rows become 9 actions. The rows stay in *Details*, tagged with their action number |
| 4 | **New first** | Every action is `NEW`, `OPEN` (seen before, with its age), `RESOLVED` (gone since the last run) or `VERIFIED` / `ACCEPTED` (decided). New items sit at the top |
| 5 | **Every check is listed, pass or fail** | A fixed checklist (below) with ✔ / ✘, so silence is never ambiguous |
| 6 | **Nothing falls through** | A code with no owner shows up as `Unassigned` at the top of the list. The report reconciles itself: details rows = action sizes = flag counts |
| 7 | **A snapshot, not a pointer** | The report copies the review rows into its *Details* sheet when it's written. Editing a `db/` file later can't change what the report says. The next run warns when a review file changed outside the pipeline (today's case) |
| 8 | **Decisions are remembered** | A decision such as "asked VW 2026-10-28" or "accepted" is recorded once. Later runs show the item with that status instead of asking again (R8) |
| 9 | **Same words as the pipeline** | Owner, fix and causes come from `messages.yaml`, so the report and the logs never disagree |
| 10 | **Built from the logs** | Every number comes from `steps.csv`, the flags, changes and review files. The report never recounts the data |

### Sheet 1, Summary (mock-up on today's numbers)

```
VW DATA REFRESH — RUN REPORT                                         2026-10-28 08:04
AMBER  ·  output usable  ·  9 actions (0 new, 8 open, 1 config)  ·  0 resolved since last run

DATA USED
  Accessory file   2026-10-20_VW Canada Accessories Data EN.xlsx   24,396 rows   ⚠ same file as the last run
  Vehicle export   vw_models_data.csv                              323 rows      vehicle DB built 2026-10-27 (1 day)

HEADLINE
  Vehicles 269  ·  Parts × models 1,357  ·  Vehicle keys matched 64 of 71 (90%)
  Exported rows 25,345 in 14 sheets  ·  Vehicles with parts 255 of 269 (95%)

WHAT YOU NEED TO DO                                                      → sheet 2
  #  Status  Owner         Action                                              Size
  1  OPEN    You decide    Atlas 2020: parts listed, no 2020 Atlas              132 parts
  ...
  9  OPEN    You (config)  10 vehicle files still drafted                       10 files

CHECKS                                                                   → sheet 8
  ✔ Vehicle ingest finished (ok)            ✔ Accessories finished (ok_with_errors)
  ✔ Rows reconcile in every step            ✔ Vehicle DB is newer than 7 days
  ✔ Accessories ran on the current DB       ✔ Export written: 14 sheets
  ✔ Part numbers proven: 0 unproven         ✔ Review rows = action sizes = flags
  ⚠ Same accessory file as the last run     ✘ 10 of 10 vehicle files still drafted
```

### Sheet 2, Actions (one row per action)

| Column | Example |
|---|---|
| `#`, `status` | 6, `OPEN` |
| `owner` | VW data |
| `action` | No parts yet for model year 2027 |
| `scope` | Atlas, Jetta, Jetta GLI, Taos, Tiguan; 2027 |
| `size` | 14 vehicles |
| `severity`, `code` | warning, `ACCESS_COVER_VEHICLE_NO_PARTS` |
| `what to do` | the fix from `messages.yaml` ("ask VW for the 2027 accessory list") |
| `first seen`, `runs open` | 2026-10-27, 4 |
| `decision`, `decided by`, `on` | `asked source`, (name), 2026-10-28 (R8) |
| `details` | sheet 3, filter `action = 6` |
| `look in the logs` | `logs/flags/<run_id>.csv`, code `ACCESS_COVER_VEHICLE_NO_PARTS` |

**How flags become actions:** each code in `messages.yaml` gets two new fields:
- `owner`: `you_decide`, `data_source`, `config` or `platform`;
- `group_by`: for example `[model, submodel]` for the lookup codes, or `[year]` for the 2027 coverage gap, which then becomes one action instead of five.

An action's key (code + group) stays the same across runs, so its status and age can be tracked.

### The checklist (every run, every item shown)

| Check | ✘ / ⚠ when |
|---|---|
| Each pipeline finished | a fatal, or a pipeline didn't run → RED |
| Accessories ran on the current vehicle DB | the DB is newer than the accessory run → RED ("rerun the accessories") |
| Vehicle DB age | older than `max_db_age_days` → ⚠ |
| Source files are new | same hash as the last run → ⚠ "same file as last run" |
| Rows reconcile in every step | in ≠ out + excluded + removed → RED |
| Export written, with the expected sheets | missing or locked → RED |
| Review rows = action sizes = flag counts | any difference → RED (the report can't be trusted) |
| Review files unchanged since the last run | changed outside the pipeline → ⚠ |
| Part numbers proven | any unproven → ✘ |
| Vehicle files reviewed | any `drafted` → ⚠ (becomes action 9) |
| Verified facts (idea 009) still hold | any contradiction → ✘ |

### Where the decisions live (R8)

`db/review/decisions.csv` is tracked in git, with one row per decided action:

```
action_key, decision, decided_by, decided_on, note, until
```

- `decision` is one of `asked_source`, `accepted` or `will_fix_config`. The report reads it and shows the item with that status.
- An `until` date makes a decision expire, so a forgotten "asked VW" comes back as `OPEN`.
- "Never offered" vehicle facts stay in the vehicle YAMLs (idea 009). This file covers the other decisions.

## What it gives on today's run

| Today | With the report |
|---|---|
| Open about 15 files, read 467 + 1 review rows and 32 flags | Open 1 file, read 1 verdict and 9 actions |
| New, still open, fixed: unknown | Shown per action, with its age |
| The review file changed after the run: unnoticed | ⚠ on the next run; the report keeps its own copy |
| Same input file reprocessed: unnoticed | ⚠ "same file as the last run" |
| "Asked VW about 2027": remembered by a person | `decisions.csv`: shown as `ASKED SOURCE`, expires on a date |

## Build in three phases (for the plan, once approved)

| Phase | Gives | Needs |
|---|---|---|
| **R-1** Report core | Summary, Actions, Details, Funnel and Run info sheets; verdict; checklist; terminal line; `owner` / `group_by` in `messages.yaml` | only the logs and files there today |
| **R-2** Across runs | `NEW` / `OPEN` / `RESOLVED` and age; `decisions.csv`; review-file tamper check; same-file check | an action history (`db/review/action_history.csv`) |
| **R-3** Changes and coverage | Changes sheet (vehicles and parts added, removed, price / labour changes), Coverage grid, Trend | an accessory snapshot of the last run to compare against |

## Decisions

| # | Question | Proposed |
|---|---|---|
| R1 | One report covering **both** pipelines, written at the end of each run, plus `python run_report.py` to rebuild it for the latest runs? | ✅ 2026-10-28: Yes. Each run creates its own report |
| R2 | Format: an **Excel workbook** in `output/reports/`, plus a short summary printed in the terminal? | ✅ 2026-10-28: Yes, named `<run_id>_report.xlsx` (run id + timestamp). The logs are only for investigating |
| R3 | Sheet order Summary → Actions → Details → Changes → Coverage → Funnel → Trend → Run info, read top-down? | ✅ 2026-10-28: Yes: every report category is its own worksheet, each with a run-id / time / takeaway banner |
| R4 | Verdict RED / AMBER / GREEN, with the rules and thresholds (`max_db_age_days: 7`, ...) in a new `config/report.yaml`? | Yes |
| R5 | Group flags into **actions** with `owner` and `group_by` per code in `messages.yaml`; info flags are counted but not listed as actions? | Yes |
| R6 | Owners: `you_decide` (lookup gaps), `data_source` (VW data), `config` (YAML / keywords), `platform` (pipeline faults)? | Yes. Rename them to match your team |
| R7 | Track actions across runs: `NEW` / `OPEN` (with age) / `RESOLVED`, new items on top? | Yes (phase R-2) |
| R8 | Record decisions in `db/review/decisions.csv` (in git), with an optional `until` date that makes a decision expire? | Yes (phase R-2). "Never offered" stays in idea 009 |
| R9 | The report copies the review rows (a snapshot); the next run warns when a review file was changed outside the pipeline? | Yes |
| R10 | The checklist above, every item shown pass or fail? | Yes |
| R11 | Build in phases R-1 → R-2 → R-3, each usable on its own? | Yes |
| R12 | Who reads it first, and what's their name for the owner groups (for example "VW data" or "Data source")? | Your answer |
