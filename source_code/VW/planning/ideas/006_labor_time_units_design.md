# 006 — Labour Time Units (minutes → hours): Design

**Status:** Built 2026-10-28 — all decisions (L1–L5) approved; see *Build notes* at the end. Plan (as built): [plans/006](../plans/006_labor_time_units.md)
**Applies to:** the accessory pipeline (plan 003), `clean` step
**Asked for:** labour time arrives in minutes; the export should show hours. The units and the multiplier are config, not code, with good governance.

## What the data shows (2026-10-27, 1,357 unique part / model rows)

| Labour value (`laborTime`) | Rows | Reads as |
|---|---|---|
| 0 | 793 | no install time |
| 10, 15, 20, 25, 30, 35, 40, 50, 75, 80, 100, 150, 200, 250 | 562 | whole minutes (250 min = 4.17 h) |
| **0.4** | 2 | not a whole minute; most likely already in hours (0.4 h = 24 min) |

## The idea: units are definitions, the conversion is a rule

```
source value (minutes) ──► multiplier from config ──► rounded ──► labor_time (hours)
        │                                                              │
        └── kept as labor_time_source (lineage) ──────────── change log: 25 min -> 0.42 h (rule unit_convert)
```

**1. Units are defined once, in config.** A new `units:` block in `accessories.yaml` defines each unit by how many of it make one hour. The multiplier is then exact (1 / 60), with no repeating decimal typed by hand:

```yaml
units:
  definitions:                 # how many of each unit make one hour
    hours: 1
    minutes: 60
  columns:
    labor_time:
      source_unit: minutes     # what the accessory file holds
      target_unit: hours       # what the dict and the export hold
      decimals: 2              # rounding of the converted value (25 min -> 0.42 h)
      suspect_if:              # values that look like the wrong unit: flagged, still converted
        not_whole: true        # a fraction of a minute (0.4) probably means the value is already in hours
        above: 600             # more than 10 hours of labour is unlikely for an accessory
```

The multiplier is `definitions[target] / definitions[source]` = 1 / 60. The run log records it (`unit_convert labor_time minutes -> hours x 0.016667, 2 decimals`), so every run states the rule it used.

> **Alternative (A1):** a literal multiplier, `multiplier: 0.0166667`. It's simpler to read, but the value is typed by hand and rounded. The definitions table avoids that and also serves future columns (e.g. a weight in grams).

**2. The conversion runs in the `clean` step,** right after the numbers are typed and before data-quality checks. The DQ rules (non-negative, ...) then check hours, the unit the export shows.

**3. Governance:**

| Practice | How |
|---|---|
| No hard-coded units or factors | Units, multiplier source, rounding and suspect rules are all in `accessories.yaml` |
| Validated config | Unknown unit, missing definition, or a column not in `columns:` stops the run (`CONFG_UNKNOWN_REFERENCE` / `CONFG_VALUE_INVALID`) |
| Lineage | The dict keeps `labor_time_source` (the raw minutes) next to `labor_time` (hours); the export shows hours only |
| Traceability | Change log: one row per distinct value (15 today), `25 -> 0.42`, rule `unit_convert`, detail `minutes -> hours x 1/60, 2 decimals; 149 rows` |
| Suspect values | `ACCESS_CLEAN_UNIT_SUSPECT` (warning, to review): the value, why it looks wrong, and the fix ("confirm the unit with the data source; if it is already hours, correct the source") |
| Unit in the header | Export header `Labour Time (hours)`, so nobody reads hours as minutes |

## What it gives on today's data

| Minutes | Hours (2 decimals) | Rows |
|---|---|---|
| 0 | 0.00 | 793 |
| 10 / 25 / 30 / 40 / 50 | 0.17 / 0.42 / 0.50 / 0.67 / 0.83 | 111 / 149 / 63 / 95 / 72 |
| 100 / 250 | 1.67 / 4.17 | 32 / 5 |
| 0.4 | 0.01, **flagged** `ACCESS_CLEAN_UNIT_SUSPECT` | 2 |

## Decisions

| # | Question | Proposed |
|---|---|---|
| L1 | Define units in a definitions table (`minutes: 60` per hour) rather than a literal multiplier? | ✅ 2026-10-27: Yes: exact, reusable, the multiplier is logged |
| L2 | Round hours to 2 decimals? | ✅ 2026-10-27: Yes (`decimals: 2`); 0.42 h. Set to 4 if billing needs more precision |
| L3 | Suspect values (fraction of a minute, more than 600 minutes): flag and still convert? | ✅ 2026-10-27: Yes: one rule for every row; the warning sends the 2 rows to review. Never guessed |
| L4 | Keep `labor_time_source` (raw minutes) in the dict for lineage; export hours only? | ✅ 2026-10-27: Yes |
| L5 | Export header `Labour Time (hours)`? | ✅ 2026-10-27: Yes |

## Build notes (2026-10-28)

Built together with idea 007, on the user's go-ahead (the plan was written up afterwards: [plans/006](../plans/006_labor_time_units.md)).

| Where | What |
|---|---|
| `config/accessories.yaml` | `units:` block as designed; export header `Labour Time (hours)` |
| `pipeline/config_helpers.py` | Validates units, columns, decimals and suspect rules (`CONFG_` errors); works out the multiplier (1/60) |
| `pipeline/accessory_helpers.py` | `convert_units` in the `clean` step: keeps `labor_time_source`, one change per distinct value (0 → 0 isn't logged), flags `ACCESS_CLEAN_UNIT_SUSPECT` once per part and value, and adds a `type = value` row to `accessory_review.csv` |
| Tests | `tests/test_text_helpers.py` (units section), config cases, end-to-end `test_labour_time_is_exported_in_hours` |

Real run (2026-10-20 file): log line `minutes -> hours x 0.0166667, 2 decimals`; 15 distinct values converted; 1 suspect (`3QF601025KAX1`, 0.4 min → 0.01 h, 2 rows) in review.
