# 013 — Labour Time Units to Hours: Design

**Status:** Idea — approved (H1–H7, 2026-11-02)
**Updated:** 2026-11-02
**Next:** completed with plan 013 once testing is signed off (013-T)
**Links:** plan [013](../plans/013_labour_time_units_to_hours.md) · corrects idea [006](006_labor_time_units_design.md) / plan [006](../plans/006_labor_time_units.md) · data issue [DI-07](../data_issues.md#di-07) · data-source question DI07-S1 · export names plan [012](../plans/012_final_export_columns.md)
**Summary:** `laborTime` arrives in time units (100 time units = 1 hour; 300 = 3 h), not minutes; a new `labor_hours` column carries the converted value downstream and the ingest value is demoted to lineage.
**Applies to:** the accessory pipeline (plan 003): `stage` (column names), `clean` (conversion), DQ rules, dict, export
**Asked for:** the labour value comes in time units (100 time units = 1 hour). At transformation, create a new labour column = ingest value / 100 (300 / 100 = 3) and push it to the output file. The ingest labour column is demoted; the new column is promoted for everything downstream.

## What changes from idea 006

Idea 006 assumed the file holds **minutes** (÷ 60). The source unit is **time units**, 100 to the hour (÷ 100). Every non-zero labour value in the export changes:

| `laborTime` (as read) | Rows | Today (as minutes ÷ 60) | New (time units ÷ 100) |
|---|---|---|---|
| 0 | 793 | 0.00 | 0.00 |
| 10 | 111 | 0.17 | **0.10** |
| 25 | 149 | 0.42 | **0.25** |
| 30 / 40 / 50 | 63 / 95 / 72 | 0.50 / 0.67 / 0.83 | **0.30 / 0.40 / 0.50** |
| 100 | 32 | 1.67 | **1.00** |
| 250 | 5 | 4.17 | **2.50** |
| 0.4 (`3QF601025KAX1`) | 2 | 0.01, flagged | **0.004 → rounds to 0.00**, flagged (see H5) |

Row counts are from idea 006 (1,357 unique part / model rows, 2026-10-20 file); the build re-counts them on the latest file.

## The idea: one ingest column, one promoted column

```
laborTime ──stage──► labor_time_source  (time units, as read)   ── demoted: lineage only (dict), never exported
                          │
                       clean: ÷ 100 (units config), 2 decimals
                          ▼
                     labor_hours        (hours)                  ── promoted: DQ rules, dict, export "Hours"
```

**1. The conversion stays config, not code.** Add the unit to the existing definitions table and point the column at it. The factor (1/100) is worked out and logged as today:

```yaml
units:
  definitions:                      # how many of each unit make one hour
    hours: 1
    minutes: 60                     # kept: may serve another column later
    time_units: 100                 # the labour unit in the accessory file: 100 time units = 1 hour (300 = 3 h)
  columns:
    labor_time_source:              # the column as read (H2)
      source_unit: time_units
      target_unit: hours
      target_column: labor_hours    # NEW key: the promoted column (H2)
      decimals: 2                   # whole time units -> exact at 2 decimals (H4)
      suspect_if:
        not_whole: true             # a fraction of a time unit (0.4) can't be right
        above: 1000                 # 10 hours, the same real limit as before (H6)
```

**2. Column routing (the "demote / promote" part).**

| Column | Holds | Used by | Exported |
|---|---|---|---|
| `labor_time_source` | the ingest value, time units (`300`) | lineage in the dict, change log, review rows | No |
| `labor_hours` | the converted value, hours (`3.00`) | `dq_rules` (`not_null`, `numeric_non_negative`), dict, export | Yes, header `Hours` |
| `labor_time` | — | removed everywhere, so nothing downstream can pick up the wrong unit | — |

`stage` maps `laborTime` straight to `labor_time_source`, so the ingest value is never under a name that looks final. `clean` creates `labor_hours`. Config validation fails the run (`CONFG_UNKNOWN_REFERENCE`) if `dq_rules` or `export.columns` still name `labor_time`, so a half-done rename can't ship.

**3. Code changes (small; the engine exists).**

| Where | Change |
|---|---|
| `config/accessories.yaml` | `columns: laborTime → labor_time_source`; `units` block above; `dq_rules` and `export.columns` use `labor_hours` |
| `pipeline/config_helpers.py` | `_units_spec` accepts `target_column` (must not clash with a read column); lineage set includes the units source column itself |
| `pipeline/accessory_helpers.py` | `convert_units` writes `rule['target_column']` instead of overwriting the column and no longer adds `<col>_source` when the column already is the source; `DICT_COLUMNS`: `labor_time` → `labor_time_source`, `labor_hours` |
| Tests | `test_text_helpers.py` units cases (÷ 100: `25 → 0.25`, `250 → 2.5`, `0.4` flagged); config cases (`target_column` checks, stale `labor_time` reference fails); end-to-end `test_labour_time_is_exported_in_hours` on the real file (pairs `300 → 3`, header `Hours`) |
| Docs | idea/plan 006 marked corrected by 013; DI-07 rewritten (unit is time units, 100 per hour, not minutes); OI-06 reworded; `ARCHITECTURE.md` examples (`10 min → 0.17 h` → `10 → 0.10 h`); `README.md`, `db/README.md`, `CHANGELOG.md` |

**4. Governance kept from 006:** the multiplier is logged on every run (`time_units -> hours x 0.01, 2 decimals`), one change-log row per distinct value (`25 -> 0.25`, rule `unit_convert`), suspect values flagged `ACCESS_CLEAN_UNIT_SUSPECT` and listed in `accessory_review.csv`.

## Decisions

> **IDs (idea 015):** H1–H7 are 013-D1 – 013-D7.

| # | Question | Proposed |
|---|---|---|
| H1 | Confirm the unit: the file holds **time units** (100 = 1 hour), and the output is **hours** (300 → 3, 25 → 0.25 = 15 min). Not "percent of an hour" as the output unit? | ✅ 2026-11-02: Yes |
| H2 | Column routing: ingest → `labor_time_source` (demoted, dict only), new promoted column `labor_hours`; `labor_time` removed. Or keep today's names (`labor_time` = hours, `labor_time_source` = raw) and only change the unit? | ✅ 2026-11-02: New `labor_hours` column, as asked: the name states the unit and nothing downstream can read the raw value by mistake |
| H3 | Define the unit in `units.definitions` (factor 1/100 worked out), rather than a literal `divide_by: 100`? | ✅ 2026-11-02: Yes, named **`time_units: 100`** (user: clearer and more accurate than `hundredths_of_hour`) |
| H4 | Keep 2 decimals? Whole time units convert exactly (25 → 0.25), so nothing is lost | ✅ 2026-11-02: Yes |
| H5 | The 0.4 value (`3QF601025KAX1`, 2 rows) becomes 0.004 h and rounds to **0.00**, which reads as "no labour". Flag and export 0.00, flag and leave **empty**, or flag and keep 3 decimals for it? | ✅ 2026-11-02: Flag `ACCESS_CLEAN_UNIT_SUSPECT` and leave `labor_hours` **empty** for suspect values, so the export never shows a made-up 0; the review row carries the source value. The `not_null` DQ rule skips values already flagged suspect, so the part gets one flag, not two. Ask the source (OI-06) |
| H6 | Suspect "too high" limit: 1000 time units (10 h, the same real limit as today's 600 minutes)? | ✅ 2026-11-02: Yes |
| H7 | Scope: VW accessory pipeline only (the vehicle ingest has no labour column; `accy_v2` OEM pipelines are not touched)? | ✅ 2026-11-02: Yes |
