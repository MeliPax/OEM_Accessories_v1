# 009 — Human-Verified Vehicle Facts: Plan

**Status:** Plan — approved (2026-10-28)
**Updated:** 2026-10-28
**Next:** build Phases V1–V3; V4 needs the name to record as `verified_by` for the first two entries
**Links:** idea [009](../ideas/009_human_verified_vehicle_facts_design.md) (V1–V8) · depends on plans [001](001_vw_model_ingest_mvp.md), [002](002_pipeline_logging.md), [003](003_accessory_model_matching.md) · feeds idea [005](../ideas/005_pipeline_report_card_design.md) (the `VERIFIED` action status)
**Summary:** A `verified:` section per vehicle YAML records facts a person confirmed; a final `verify` step in both pipelines downgrades the flags those facts explain, and turns contradictions into errors.

## Outcome

A person can record, in `config/vehicles/<model>.yaml`, that a vehicle was **never offered** in certain years, or never offered with certain options. Each entry carries a reason, who confirmed it and when. Both pipelines finish with a `verify` step that checks every verifiable flag against these facts:
- **covered:** the flag drops to info. It stays in the flag log with the entry that covered it, and leaves the review files, the run status and the exit code;
- **contradicted by the data:** a new error;
- **unused entries:** reported.

Vehicles with no parts yet can be marked `no_parts_expected` until a date (V6).

**Success criteria (today's data, after the first two entries)**

- [ ] Golf R `never_offered.years [2020, 2021]` and Arteon `never_offered.years [2022, 2023]` are in the YAMLs, with reason, `verified_by` and `verified_on`.
- [ ] Accessories: 7 lookup errors → 3 (Atlas 2020, ID.4 2026, ID. Buzz 2026). The 4 verified flags are info, with `verified_entry` filled in.
- [ ] `accessory_review.csv` loses the Golf R and Arteon rows: 467 → 241 (108 + 118 part-year rows removed). Those rows stay in the dict, with `match_status = never_offered`.
- [ ] `db/dq/verified_flags.csv` lists the 4 verified flags, each with its entry, reason, `verified_by` and `verified_on`.
- [ ] The run log has one `VERIFIED` line per entry used, and `accessory_runs.csv` / `ingest_runs.csv` gain `flags_verified` and `verified_contradicted`.
- [ ] Vehicle ingest: 0 flags change today (review queue already 0), and the 269 vehicles are unchanged.
- [ ] A test fixture with a 2021 Golf R vehicle in the DB gives `ACCESS_VERIFY_CONTRADICTED` (error) and leaves the original flag as it was.
- [ ] A broken entry (unknown submodel, category or value; missing `reason`; `never_offered.years` overlapping an option set's years) stops the run with a `CONFG_` error naming the file and the entry number.
- [ ] Fatals and codes without `verifiable: true` are never downgraded (test).
- [ ] All existing tests still pass.

---

## Phase V1 — Config: the `verified:` section

- [ ] Schema per entry:
  - `submodel` (optional);
  - `years` (needed with a category fact);
  - `never_offered` (`years`, or `<category>: [values]`);
  - `no_parts_expected` (`years`, `until`) (V6);
  - `reason`, `verified_by` and `verified_on` (required, V1).
- [ ] `pipeline/config_helpers.py`: `_verified_spec(file, data, taxonomy, option_sets)` validates each entry when the vehicle files load:
  - an unknown submodel, category or value → `CONFG_UNKNOWN_REFERENCE`;
  - a missing required field, or a bad date or year → `CONFG_VALUE_INVALID`;
  - `never_offered.years` overlapping an option set, or a `never_offered` value that the option set offers in those years → `CONFG_VALUE_INVALID` ("the file says both");
  - each problem names `<file> verified #N`.
- [ ] `load_option_sets` returns the verified entries with the option sets. `status: reviewed` is kept separate (V7).
- [ ] `dim_verified.csv` in `db/definitions/` lists each entry, like the other definition tables.

**Done when:** the real config loads, and each broken case in `test_config_helpers.py` fails with its message.

## Phase V2 — Messages and flag fields

- [ ] `config/messages.yaml`:
  - `verifiable: true` on the availability codes: `ACCESS_LOOKUP_YEAR_AFTER_LAST_KNOWN`, `_BEFORE_FIRST_KNOWN`, `_IN_GAP`, `_IN_CONFIG_NOT_IN_DB`, `ACCESS_COVER_VEHICLE_NO_PARTS`, `ACCESS_COVER_MODEL_NO_PARTS`, `VEH_VALID_OPTION_NOT_OFFERED`, `VEH_VALID_NOT_IN_CONFIG` (V4);
  - new codes `VEH_VERIFY_CONTRADICTED` and `ACCESS_VERIFY_CONTRADICTED` (error, V5), `VEH_VERIFY_ENTRY_UNUSED` and `ACCESS_VERIFY_ENTRY_UNUSED` (info), and `ACCESS_VERIFY_EXPIRED` (warning: a `no_parts_expected` past its `until` date, so the coverage flag comes back).
- [ ] `tests/test_messages.py`: `verifiable` must be true or false, is never set on a fatal, and is set only on the stages `LOOKUP`, `COVER` and `VALID`.
- [ ] `pipeline/logging_helpers.py`:
  - `FLAG_COLUMNS` gains `model`, `submodel`, `original_severity` and `verified_entry`;
  - `_key_fields` fills `model` and `submodel` from the row, so lookup and coverage flags carry the key as fields, not only in `subject`.

**Done when:** the message tests pass, and the existing flag logs still load (new columns empty).

## Phase V3 — The `verify` step

- [ ] New `pipeline/verify_helpers.py`:
  - `match_flag(flag, entries)` → the entry or None. Exact match on model, submodel, year and category / value (V2); no wildcards;
  - `contradictions(entries, vehicles, lookup_index)` → facts the data now breaks;
  - `verify_flags(flags, entries, ctx, pipeline)` → downgrades matched flags (severity `info`, keeps `original_severity`, sets `verified_entry`), logs `VERIFIED` per entry, raises the contradiction and unused-entry flags, and returns the verified rows.
- [ ] **Accessories** (`accessory_helpers.run_pipeline`):
  - add the `verify` step after `validate`;
  - move writing `accessory_review.csv` out of `coverage` into `verify`, so the file is written once, after verification;
  - drop review rows whose (code, match key) was verified;
  - set `match_status = never_offered` on those dict rows;
  - write `db/dq/verified_flags.csv`.
- [ ] **Vehicle ingest** (`run_ingest.py`):
  - add the `verify` step after `validate`, before `write`;
  - build `review_queue.csv` after `verify`;
  - check contradictions against the vehicles being written.
- [ ] `run_summary` and the ingest summary gain `flags_verified` and `verified_contradicted`. The run status comes from the flags after verification (unchanged `run_status`).

**Done when:** the unit tests (match, downgrade, contradiction, unused, expired, fatal never touched) pass on hand-made flags.

## Phase V4 — First entries, real runs, docs

- [ ] Add the Golf R and Arteon entries (V8), with the name you give for `verified_by`.
- [ ] Real runs: `run_ingest.py`, then `run_accessories.py`. Check the success-criteria numbers.
- [ ] Docs:
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
| 2026-10-28 | **Plan.** Writing `accessory_review.csv` moves from `coverage` to the new `verify` step | The review file must be written after verification, once |
| 2026-10-28 | **Plan.** Flags gain `model` / `submodel` fields | Today those values are only inside `subject` text; exact matching needs fields |
| 2026-10-28 | **Plan.** Verified accessory rows stay in the dict with `match_status = never_offered` | Nothing is deleted; the export (matched rows only) is unchanged |
| 2026-10-28 | **Plan.** A config entry that contradicts its own option sets is a config error | The file would say both "offered" and "never offered" |

## Risks

| Risk | Mitigation |
|---|---|
| A fact hides a real change in the data | Contradictions are errors; exact match only; nothing deleted (`verified_flags.csv`) |
| An entry silences more than intended | No wildcards; codes need `verifiable: true`; validated at load |
| A forgotten `no_parts_expected` hides a gap for ever | It needs an `until` date, and `ACCESS_VERIFY_EXPIRED` brings the flag back |
| Moving the review write changes the review file for the report (idea 005) | Same columns. Verified rows are listed in `verified_flags.csv` instead |
