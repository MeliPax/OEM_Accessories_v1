# 014 — Labour Values Below One Corrected (× 100): Design

**Status:** Idea — approved (B1–B7, 2026-11-03)
**Updated:** 2026-11-03
**Next:** completed with plan 014 once testing is signed off (014-T)
**Links:** plan [014](../plans/014_labour_below_one_correction.md) · builds on idea [013](013_labour_time_units_to_hours_design.md) / plan [013](../plans/013_labour_time_units_to_hours.md) · data issue [DI-07](../data_issues.md#di-07) · data-source question DI07-S1
**Summary:** A labour value above 0 and below 1 is treated as an entry error (hours typed into a time-units column) and multiplied by 100 in the `clean` step, before the hours conversion and before the dict expands the rows.
**Applies to:** the accessory pipeline, `clean` step (runs on the 1,028 deduplicated rows, not the ~9,400 dict rows)
**Asked for:** in the first round of transformation, take the ingested labour values below 1 and multiply them by 100 (0.4 → 40). Any value below 1 is treated as an error and corrected this way. Do it before the data is expanded, so it runs on fewer rows.

## What the data shows (accessory file 2026-10-20, all 24,396 rows)

| `laborTime` | Source rows | Reads as |
|---|---|---|
| 0 | 14,774 | no install time; **must not be touched** (0 × 100 = 0, but it isn't an error) |
| **0.4** | 16 (`3QF601025KAX1`, Atlas and Atlas Cross Sport, Active) → 2 after dedupe | below 1: hours typed into a time-units column; 0.4 h = **40 time units** |
| 10 – 250 | the rest | time units (idea 013) |

Today, plan 013 flags 0.4 `ACCESS_CLEAN_UNIT_SUSPECT` and leaves `Hours` empty on its 22 export rows. With this rule it becomes 40 → **0.40 h**, still flagged so the source gets fixed.

## Where it runs

```
ingest ─► staging ─► year_window ─► part_numbers ─► clean_text ─► dedupe ─► clean ─────────────────────────► … ─► build_dict ─► export
24,396     20,399      9,675                                        1,028    │                                       ~9,400 rows
                                                                             ├─ 1. correct: 0 < value < 1 → × 100   (NEW, this idea)
                                                                             ├─ 2. suspect check (not whole, above 1000)
                                                                             └─ 3. convert ÷ 100 → labor_hours       (idea 013)
```

It runs first inside `clean`, on 1,028 rows: after `dedupe` (the 16 source rows are already 2) and before `build_dict` expands each part to one row per year and vehicle. It must run **before** the suspect check, or 0.4 would still be flagged "not a whole number" and left empty.

## The rule, in config

Part of the existing units entry, so the column, the units and the correction sit together and the factor comes from the definitions table, not a typed number:

```yaml
units:
  definitions:
    hours: 1
    minutes: 60
    time_units: 100
  columns:
    labor_time_source:
      source_unit: time_units
      target_unit: hours
      target_column: labor_hours
      decimals: 2
      correct_if:                   # NEW (idea 014): entry errors fixed before converting
        between: [0, 1]             # above 0 and below 1 (0 itself is a real value and is left alone)
        entered_as: hours           # the value was typed in hours: x definitions[time_units] / definitions[hours] = x 100
      suspect_if:
        not_whole: true
        above: 1000
```

## Governance

| Practice | How |
|---|---|
| Lineage | `labor_time_source` keeps the value **as read** (0.4). A new column `labor_time_corrected` holds the value the conversion used (40), so the dict shows both (B4) |
| Traceability | Change log: one row per distinct value, `0.4 -> 40`, rule `unit_correct`, detail `between 0 and 1: entered as hours x 100; 2 rows`. Then `40 -> 0.4` (rule `unit_convert`) as for any value |
| Flag | New code `ACCESS_CLEAN_UNIT_CORRECTED` (warning) once per part and value: "Part 3QF601025KAX1: labor_time_source 0.4 is below 1, read as hours and corrected to 40 time_units (0.4 h) (2 rows)"; fix: ask the source to correct the file. A `type = value` row in `accessory_review.csv` |
| No double flag | A corrected value is not also flagged `ACCESS_CLEAN_UNIT_SUSPECT` (it is whole after × 100) |
| Validated config | `between` must be two numbers, low < high; `entered_as` must be in `units.definitions` (`CONFG_` errors) |

## What it gives on today's data

| Part | As read | Corrected | `Hours` (export) | Flag |
|---|---|---|---|---|
| `3QF601025KAX1` (2 deduped rows, 22 export rows) | 0.4 | 40 | **0.40** (was empty) | `ACCESS_CLEAN_UNIT_CORRECTED` (replaces `ACCESS_CLEAN_UNIT_SUSPECT`) |
| every other part | unchanged | — | unchanged | — |

## Decisions

> **IDs (idea 015):** B1–B7 are 014-D1 – 014-D7.

| # | Question | Proposed |
|---|---|---|
| B1 | Range: correct values **above 0 and below 1** only? 0 is real "no install time" (14,774 rows) and negatives are left to the `numeric_non_negative` DQ rule | ✅ 2026-11-03: Yes |
| B2 | Run it in `clean`, after `dedupe` and before the suspect check and the ÷ 100 conversion (1,028 rows, not ~9,400) | ✅ 2026-11-03: Yes |
| B3 | Define it in config as `correct_if: { between: [0, 1], entered_as: hours }` on the units entry, the × 100 worked out from `units.definitions` rather than typed as `multiply_by: 100` | ✅ 2026-11-03: Yes: same pattern as 006 / 013; the rule states *why* (entered in hours) |
| B4 | Lineage: keep `labor_time_source` exactly as read (0.4) and add `labor_time_corrected` (40) to the dict, or correct `labor_time_source` in place? | ✅ 2026-11-03: Keep as read + `labor_time_corrected`; the dict always shows what the file said |
| B5 | Flag each correction as a **warning** (`ACCESS_CLEAN_UNIT_CORRECTED`) with a review row, so the source can fix the file? | ✅ 2026-11-03: Yes |
| B6 | Values that are still suspect after correcting (e.g. 0.405 → 40.5, not whole) stay flagged `ACCESS_CLEAN_UNIT_SUSPECT` and are left empty | ✅ 2026-11-03: Yes |
| B7 | Close OI-06 / update DI-07: the 0.4 is handled by this rule (read as 0.4 h); still ask the source to correct the file | ✅ 2026-11-03: Yes |
