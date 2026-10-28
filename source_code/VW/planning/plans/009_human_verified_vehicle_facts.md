# 009 — Human-Verified Vehicle Facts: Plan

**Status:** Built — in user testing (2026-10-28)
**Updated:** 2026-10-28
**Next:** user signs off testing (OI-01)
**Links:** idea [009](../ideas/009_human_verified_vehicle_facts_design.md) · depends on plans [001](001_vw_model_ingest_mvp.md), [002](002_pipeline_logging.md), [003](003_accessory_model_matching.md) · feeds idea [005](../ideas/005_pipeline_report_card_design.md)
**Summary:** A verified: section per vehicle YAML and a final verify step in both pipelines: matched flags drop to info, contradictions become errors.

## Outcome

A person can record, in `config/vehicles/<model>.yaml`, that a vehicle was **never offered** in certain years, or never offered with certain options. Each entry carries a reason, who confirmed it and when. Both pipelines finish with a `verify` step that checks every verifiable flag against these facts:
- **covered:** the flag drops to info. It stays in the flag log with the entry that covered it, and leaves the review files, the run status and the exit code;
- **contradicted by the data:** a new error;
- **unused entries:** reported.

Vehicles with no parts yet can be marked `no_parts_expected` until a date (V6).

**Success criteria (today's data, after the first two entries)**

- [x] Golf R `never_offered.years [2020, 2021]` and Arteon `never_offered.years [2022, 2023]` are in the YAMLs, with reason, `verified_by` and `verified_on`.
- [x] Accessories: 7 lookup errors → 3 (Atlas 2020, ID.4 2026, ID. Buzz 2026). The 4 verified flags are info, with `verified_entry` filled in.
- [x] `accessory_review.csv` loses the Golf R and Arteon rows: 467 → 241 (108 + 118 part-year rows removed). Those rows stay in the dict, with `match_status = never_offered`.
- [x] `db/dq/verified_flags.csv` lists the 4 verified flags, each with its entry, reason, `verified_by` and `verified_on`.
- [x] The run log has one `VERIFIED` line per entry used, and `accessory_runs.csv` / `ingest_runs.csv` gain `flags_verified` and `verified_contradicted`.
- [x] Vehicle ingest: 0 flags change today (review queue already 0), and the 269 vehicles are unchanged.
- [x] A test fixture with a 2021 Golf R vehicle in the DB gives `ACCESS_VERIFY_CONTRADICTED` (error) and leaves the original flag as it was.
- [x] A broken entry (unknown submodel, category or value; missing `reason`; `never_offered.years` overlapping an option set's years) stops the run with a `CONFG_` error naming the file and the entry number.
- [x] Fatals and codes without `verifiable: true` are never downgraded (test).
- [x] All existing tests still pass.

---

## Phase V1 — Config: the `verified:` section

- [x] Schema per entry:
  - `submodel` (optional);
  - `years` (needed with a category fact);
  - `never_offered` (`years`, or `<category>: [values]`);
  - `no_parts_expected` (`years`, `until`) (V6);
  - `reason`, `verified_by` and `verified_on` (required, V1).
- [x] `pipeline/config_helpers.py`: `_verified_spec(file, data, taxonomy, option_sets)` validates each entry when the vehicle files load:
  - an unknown submodel, category or value → `CONFG_UNKNOWN_REFERENCE`;
  - a missing required field, or a bad date or year → `CONFG_VALUE_INVALID`;
  - `never_offered.years` overlapping an option set, or a `never_offered` value that the option set offers in those years → `CONFG_VALUE_INVALID` ("the file says both");
  - each problem names `<file> verified #N`.
- [x] `load_option_sets` returns the verified entries with the option sets. `status: reviewed` is kept separate (V7).
- [x] `dim_verified.csv` in `db/definitions/` lists each entry, like the other definition tables.

**Done when:** the real config loads, and each broken case in `test_config_helpers.py` fails with its message.

## Phase V2 — Messages and flag fields

- [x] `config/messages.yaml`:
  - `verifiable: true` on the availability codes: `ACCESS_LOOKUP_YEAR_AFTER_LAST_KNOWN`, `_BEFORE_FIRST_KNOWN`, `_IN_GAP`, `_IN_CONFIG_NOT_IN_DB`, `ACCESS_COVER_VEHICLE_NO_PARTS`, `ACCESS_COVER_MODEL_NO_PARTS`, `VEH_VALID_OPTION_NOT_OFFERED`, `VEH_VALID_NOT_IN_CONFIG` (V4);
  - new codes `VEH_VERIFY_CONTRADICTED` and `ACCESS_VERIFY_CONTRADICTED` (error, V5), `VEH_VERIFY_ENTRY_UNUSED` and `ACCESS_VERIFY_ENTRY_UNUSED` (info), and `ACCESS_VERIFY_EXPIRED` (warning: a `no_parts_expected` past its `until` date, so the coverage flag comes back).
- [x] `tests/test_messages.py`: `verifiable` must be true or false, is never set on a fatal, and is set only on the stages `LOOKUP`, `COVER` and `VALID`.
- [x] `pipeline/logging_helpers.py`:
  - `FLAG_COLUMNS` gains `model`, `submodel`, `original_severity` and `verified_entry`;
  - `_key_fields` fills `model` and `submodel` from the row, so lookup and coverage flags carry the key as fields, not only in `subject`.

**Done when:** the message tests pass, and the existing flag logs still load (new columns empty).

## Phase V3 — The `verify` step

- [x] New `pipeline/verify_helpers.py`:
  - `match_flag(flag, entries)` → the entry or None. Exact match on model, submodel, year and category / value (V2); no wildcards;
  - `contradictions(entries, vehicles, lookup_index)` → facts the data now breaks;
  - `verify_flags(flags, entries, ctx, pipeline)` → downgrades matched flags (severity `info`, keeps `original_severity`, sets `verified_entry`), logs `VERIFIED` per entry, raises the contradiction and unused-entry flags, and returns the verified rows.
- [x] **Accessories** (`accessory_helpers.run_pipeline`):
  - add the `verify` step after `validate`;
  - move writing `accessory_review.csv` out of `coverage` into `verify`, so the file is written once, after verification;
  - drop review rows whose (code, match key) was verified;
  - set `match_status = never_offered` on those dict rows;
  - write `db/dq/verified_flags.csv`.
- [x] **Vehicle ingest** (`run_ingest.py`):
  - add the `verify` step after `validate`, before `write`;
  - build `review_queue.csv` after `verify`;
  - check contradictions against the vehicles being written.
- [x] `run_summary` and the ingest summary gain `flags_verified` and `verified_contradicted`. The run status comes from the flags after verification (unchanged `run_status`).

**Done when:** the unit tests (match, downgrade, contradiction, unused, expired, fatal never touched) pass on hand-made flags.

## Phase V4 — First entries, real runs, docs

- [x] Add the Golf R and Arteon entries (V8), with the name you give for `verified_by`.
- [x] Real runs: `run_ingest.py`, then `run_accessories.py`. Check the success-criteria numbers.
- [x] Docs:
  - `README.md` (how to add a verified fact);
  - `db/README.md` (`verified_flags.csv`, the new flag columns and codes);
  - `planning/data_issues.md` (DI-05: Golf R and Arteon verified; Atlas 2020, ID.4 2026 and ID. Buzz 2026 still Open).

**Done when:** every success criterion is ticked.

---

## Tests

| File | Covers |
|---|---|
| `tests/test_verify_helpers.py` (new) | Exact match only (a different submodel or year doesn't match); never-offered years and options; `no_parts_expected` before and after `until`; contradictions; unused entries; fatals and non-verifiable codes untouched; severity restored in `original_severity` |
| `tests/test_config_helpers.py` | Each broken `verified:` case, with the file and entry number in the message |
| `tests/test_messages.py` | The `verifiable` field rules; the new codes used and filled |
| `tests/test_accessories_end_to_end.py` | Real file with the two entries: 3 lookup errors, review rows 241, `verified_flags.csv`, dict `never_offered` rows, the export unchanged |
| `tests/test_end_to_end.py` | Vehicle ingest unchanged (269 vehicles, review queue 0) with the `verify` step; a contradiction fixture |

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-10-28 | V1–V8 approved as proposed | User: "I like the ideas in 9 and 10" |
| 2026-10-28 | Plan approved | User: "I like plan in 9 and 10" |
| 2026-10-28 | `verified_by: P.M` for the first two entries (OI-12) | User: "verified by P.M" |
| 2026-10-28 | Built before plan 011, not after it as idea 011 DOC-10 proposed | DOC-10 isn't decided yet; plan 009 is approved and unblocked, and the docs it needs are written to the 011 standard once that is approved |
| 2026-10-28 | **Plan.** Writing `accessory_review.csv` moves from `coverage` to the new `verify` step | The review file must be written after verification, once |
| 2026-10-28 | **Plan.** Flags gain `model` / `submodel` fields | Today those values are only inside `subject` text; exact matching needs fields |
| 2026-10-28 | **Plan.** Verified accessory rows stay in the dict with `match_status = never_offered` | Nothing is deleted; the export (matched rows only) is unchanged |
| 2026-10-28 | **Plan.** A config entry that contradicts its own option sets is a config error | The file would say both "offered" and "never offered" |
| 2026-10-28 | **Build.** A separate `load_verified()` reads the `verified:` sections; `load_option_sets` is unchanged | Its flat list is used by many callers; a second return value would touch all of them |
| 2026-10-28 | **Build.** Every `years` in `verified:` is a list of single years, never a `[start, end]` range | A fact covers exactly what is written (exact match only); `[2024, 2026]` can't silently mean 2025 too |
| 2026-10-28 | **Build.** Verifiable codes: `ACCESS_LOOKUP_YEAR_AFTER_LAST_KNOWN`, `_BEFORE_FIRST_KNOWN`, `_IN_GAP`, `_MODEL_NOT_IN_DB`, `ACCESS_COVER_VEHICLE_NO_PARTS`. Not `_IN_CONFIG_NOT_IN_DB` (a never-offered year can't be declared in config, so it can never match), not `ACCESS_COVER_MODEL_NO_PARTS` (no year to match), not the `VEH_VALID_` codes | Only codes a fact can match exactly |
| 2026-10-28 | **Build.** The vehicle ingest's `verify` step checks contradictions only; no vehicle flag is ever downgraded, and there is no `VEH_VERIFY_ENTRY_UNUSED` | A flagged vehicle exists in the export, so a never-offered fact can only be contradicted by it (idea: "none to silence"). `ingest_runs.csv` gains `verified_contradicted` only |
| 2026-10-28 | **Build.** The ingest's review queue didn't need moving: `verify` runs before `write`, which builds it | Contradictions reach the queue as they are |
| 2026-10-28 | **Build.** The contradiction cases are unit tests on hand-made vehicles and index (`test_verify_helpers.py`), not a modified copy of the real data | Same coverage, no test fixture of fake vehicles in the real files |
| 2026-10-28 | **Build.** `accessory_runs.csv` also gains `review_rows` (241); the terminal summary shows `verified` and `review rows` | The review count is what the manager acts on |
| 2026-10-28 | **Build.** Real runs: ingest 269 vehicles, 0 changes, 0 contradictions; accessories 7 → 3 lookup errors, 4 flags verified, review rows 467 → 241, export unchanged (25,345 rows); 253 tests pass | Success criteria met |

## Risks

| Risk | Mitigation |
|---|---|
| A fact hides a real change in the data | Contradictions are errors; exact match only; nothing deleted (`verified_flags.csv`) |
| An entry silences more than intended | No wildcards; codes need `verifiable: true`; validated at load |
| A forgotten `no_parts_expected` hides a gap for ever | It needs an `until` date, and `ACCESS_VERIFY_EXPIRED` brings the flag back |
| Moving the review write changes the review file for the report (idea 005) | Same columns. Verified rows are listed in `verified_flags.csv` instead |
