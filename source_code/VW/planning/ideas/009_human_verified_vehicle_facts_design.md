# 009 — Human-Verified Vehicle Facts: Design

**Status:** Idea — approved 2026-10-28 (V1–V8 as proposed). Plan: [plans/009](../plans/009_human_verified_vehicle_facts.md)
**Applies to:** both pipelines. Facts live in `config/vehicles/<model>.yaml`; the check runs on the vehicle ingest's validation flags and the accessory lookup and coverage flags.
**Asked for:** a way to record that a person has confirmed some facts about specific vehicles, especially what was **never offered** (years, trims, other options). Flags those facts explain stop coming back as errors and warnings. The config acts as a final check on whether a flag is still valid.

## What exists today, and where the noise is

| Already there | What it does | What it doesn't do |
|---|---|---|
| `status: drafted / reviewed` + `reviewed_by` / `reviewed_on` per file | Says whether a person checked the **whole** file | Doesn't record **what** was confirmed, and doesn't change any flag |
| Option sets (`years`, `trim`, ...) | List what each year range **can** have; anything not listed means "not offered" | When drafted from the data, "not listed" is only an assumption, not a confirmed absence |

The latest runs (2026-10-28):

| Pipeline | Flags to review | Explained by a fact a person could confirm |
|---|---|---|
| Vehicle ingest | 0 (the option sets were drafted from the same data) | — today. Becomes useful when the next VW export adds or changes vehicles |
| Accessories | 7 lookup errors (accessory years with no vehicle), 14 vehicles with no parts | Golf R 2020–2021 and Arteon 2022–2023: **never offered** (user, 2026-10-27). Atlas 2020, ID.4 2026, ID. Buzz 2026: probably missing from the export, so they **can't** be verified away; ask the source |

## The idea: a `verified:` section per model file

Each entry is one fact a person confirmed: what it covers, and who confirmed it, when and why.

```yaml
# config/vehicles/golf.yaml
verified:
  - submodel: R                       # omit for the base model
    never_offered:
      years: [2020, 2021]             # Golf R wasn't sold in Canada these years
    reason: Golf R returned to Canada for model year 2022
    verified_by: <name>
    verified_on: 2026-10-28

  - submodel: GTI
    years: [2024, 2026]               # the years the fact applies to
    never_offered:
      transmission: [Manual]          # any taxonomy category: trim, engine, appearance_package, ...
    reason: 2024+ GTI is DSG only
    verified_by: <name>
    verified_on: 2026-10-28

# config/vehicles/arteon.yaml
verified:
  - never_offered:
      years: [2022, 2023]
    reason: Arteon discontinued in Canada after model year 2021
    verified_by: <name>
    verified_on: 2026-10-28
```

Two kinds of fact:

| Fact | Means | Flags it explains |
|---|---|---|
| `never_offered.years` | The model / submodel didn't exist in those years | `ACCESS_LOOKUP_YEAR_AFTER_LAST_KNOWN`, `_BEFORE_FIRST_KNOWN`, `_IN_GAP`, `_IN_CONFIG_NOT_IN_DB` and `ACCESS_COVER_*` for those years |
| `never_offered.<category>` (with `years`) | That option didn't exist on the vehicle in those years | None to silence. It turns a drafted "not listed" into a confirmed absence: if a future export shows the option, the flag becomes a precise error (the contradiction rule below) instead of a vague `VEH_VALID_OPTION_NOT_OFFERED` warning |

## How a flag is checked: the final step, never a silent delete

A new last step, **`verify`**, runs in both pipelines after every other check. For each flag whose code is marked as verifiable:

```
flag ──► does a verified entry cover it (model, submodel, year, category, value)?
           ├─ no ──────────────► flag stays as it is (review, run status, exit code)
           └─ yes ─► does the data contradict the fact?
                      ├─ no ──► flag becomes "verified": severity info, kept in the flag log with the entry,
                      │         left out of review files, run status and exit code
                      └─ yes ─► new ERROR VERIFIED_CONTRADICTED: the export now has a vehicle the entry says
                                was never offered. Either the data changed or the entry is wrong
```

Rules that keep it safe:

| Rule | Why |
|---|---|
| **Exact match only**: model, submodel, year and value; no wildcards for a whole model | A fact can't silence more than a person confirmed |
| **Only verifiable codes**: a `verifiable: true` line in `messages.yaml` per code. Availability codes only (the lookup and coverage codes above, plus the vehicle option codes) | Fatals and data-integrity flags (missing files, part number mismatches, bad config) can never be verified away |
| **Contradictions are errors**: e.g. a 2021 Golf R appears in a future VW export, or a vehicle shows a `never_offered` option | Verification can never hide a real change in the data |
| **Nothing is deleted**: verified flags stay in `logs/flags/<run_id>.csv` with `verified_by`, `verified_on`, `reason` and the entry | Full audit trail; you can always see what was verified away |
| **Unused entries are reported** (info): an entry no flag matched this run | Keeps the config tidy; shows facts that may no longer be needed |
| **Validated at load**: unknown category or value, years outside the file's range, missing `reason` / `verified_by` / `verified_on` → `CONFG_` error | A typo can't silently cover the wrong thing |

## What it gives on today's data (estimate)

| | Before | After (Golf R 2020–21, Arteon 2022–23 verified) |
|---|---|---|
| Accessory lookup errors | 7 | 3 (Atlas 2020, ID.4 2026, ID. Buzz 2026: still to ask the source) |
| Unmatched part-years in review | 451 | about 451 minus the Golf R and Arteon part-years |
| Run exit code | 1 | still 1 until the other 3 are answered |

The **vehicles with no parts** (14 in 2027) aren't "never offered": the vehicles exist, and the accessory file hasn't caught up yet. See V6.

## Outputs

- **Run log:** `VERIFIED | code=... | entry=golf.yaml #1 (Golf R never offered 2020-2021, <name> 2026-10-28) | flags=2`.
- **New report `db/dq/verified_flags.csv`:** one row per verified flag, with the entry that covered it.
- **Run summary:** `flags_verified` and `verified_contradicted` added to `ingest_runs.csv` / `accessory_runs.csv`.
- **Review files:** verified flags are left out; contradictions are added.

## Decisions

| # | Question | Proposed |
|---|---|---|
| V1 | Facts go in a `verified:` section of each `config/vehicles/<model>.yaml`, each with `reason`, `verified_by` and `verified_on` (required)? | ✅ 2026-10-28: Yes |
| V2 | Fact types: `never_offered.years`, and `never_offered.<category>` with `years`? | ✅ 2026-10-28: Yes. Start with these two; add more when a flag needs one |
| V3 | A verified flag is downgraded to info and kept in the flag log, left out of review, run status and exit code, never deleted? | ✅ 2026-10-28: Yes |
| V4 | Only codes marked `verifiable: true` in `messages.yaml` can be verified; fatals and integrity flags never? | ✅ 2026-10-28: Yes |
| V5 | Data that contradicts a verified fact becomes an **error** `VEH_VERIFY_CONTRADICTED` / `ACCESS_VERIFY_CONTRADICTED`? | ✅ 2026-10-28: Yes |
| V6 | Vehicles with no parts (2027): a separate `no_parts_expected: {years: [2027], until: 2027-06-30, reason}` that expires, so the flag comes back if the accessory file still hasn't caught up by then? | ✅ 2026-10-28: Yes, with an `until` date. Otherwise leave these flags as they are |
| V7 | Does `status: reviewed` (whole file) still mean "the option sets were checked", separate from `verified:` (specific facts)? | ✅ 2026-10-28: Yes: both are kept; `verified:` works whatever the file status is |
| V8 | First entries: Golf R `never_offered.years [2020, 2021]` and Arteon `never_offered.years [2022, 2023]`, with you as `verified_by`? | ✅ 2026-10-28: Yes, if you confirm both. Atlas 2020, ID.4 2026 and ID. Buzz 2026 stay open |
