# 015 — Pending Items Numbered by Their Doc: Design

**Status:** Idea — waiting for decisions
**Updated:** 2026-11-03
**Next:** user decides N1–N8 (OI-20)
**Links:** extends idea [010](010_work_process_and_tracking_design.md) / plan [010](../plans/010_work_process_and_tracking.md) (tracking) · [open_items.md](../open_items.md) · [data_issues.md](../data_issues.md) · `tests/test_planning_docs.py`
**Summary:** Every pending item gets an ID that starts with the number of the doc (or data issue) it belongs to, e.g. `013-D2` or `DI07-S1`, so the ID alone says which file to open.
**Applies to:** planning docs, `open_items.md`, the VW `CLAUDE.md` rules, `tests/test_planning_docs.py`. No pipeline code, config or output changes.
**Asked for:** pending items and decisions use IDs (`OI-06`, `H3`, `B1`, `DOC-4`) that don't say where they live. Number them all by the doc ID so it's clear where to find each one.

## What's wrong today

| Today | Problem |
|---|---|
| `OI-06` | a running number; you need `open_items.md` to learn it belongs to DI-07 |
| `OI-01` | one item covering 11 plans' sign-offs; no plan shows its own |
| `H3`, `B1`, `R4`, `DOC-4`, `A17` | a different letter per idea; the letter doesn't say which idea |
| `Next: … (OI-11)` in the index | names the item, not where to act |

## The idea: the doc number is the first part of every ID

```
013-D2     doc 013 (planning/ideas/013_* or plans/013_*) · kind D (decision) · 2nd one
DI07-S1    data issue DI-07 (data_issues.md#di-07)       · kind S (ask the source) · 1st one
```

| Kind | Meaning | Lives in | Owner |
|---|---|---|---|
| `D` | a decision | the idea's **Decisions** table | user |
| `T` | testing sign-off (one per plan) | the plan's header `Next:` line | user |
| `U` | another task for the user (review a config, …) | the plan | user |
| `A` | a task for Claude | the plan | Claude |
| `S` | a question for the data source | the data issue section | data source |

Work that belongs to no single doc uses `000` (the planning process itself), e.g. `000-U1`.

## Today's open items, renamed

| Now | New | Where | What |
|---|---|---|---|
| OI-01 | `001-T`, `002-T`, `003-T`, `006-T`, `007-T`, `008-T`, `009-T`, `010-T`, `012-T`, `013-T`, `014-T` | each plan | sign off testing |
| OI-02 | `003-A1` | plan 003 | notebook cells for plans 001–003 |
| OI-03 | `001-U1` | plan 001 | review `config/vehicles/*.yaml` (9 of 10 drafted) |
| OI-04 | `DI05-S1` | DI-05 | Atlas 2020 parts without a vehicle |
| OI-05 | `DI06-S1` | DI-06 | no parts for model year 2027 |
| OI-07 | `DI03-S1` | DI-03 | export `stockCode` as text |
| OI-08 | `DI16-S1` | DI-16 | "ReferAlways install" wording |
| OI-09 | `003-D18` | idea 003 | lookup misses as warnings? |
| OI-11 | `005-D4` … `005-D12` | idea 005 | run report decisions (now R4–R12) |
| OI-13 | `011-D1` … `011-D10` | idea 011 | documentation decisions (now DOC-1 – DOC-10) |
| OI-20 (this) | `015-D1` … `015-D8` | idea 015 | these decisions |

## How it's kept honest

| Practice | How |
|---|---|
| One list | `open_items.md` stays the single list of everything pending, **sorted by ID** (so all of 013's items sit together), columns: ID · Where (link) · What · Owner · Status · Was |
| History kept | A **Was** column (`OI-06`, `H3`) so old references in commits and closed docs still resolve. Closed rows are kept, renamed the same way |
| In each doc | The idea's Decisions table and the plan's `Next:` line use the new IDs; approved ideas get a one-line note: "Decision IDs: H1–H7 are 013-D1 – 013-D7" |
| In chat | Claude always writes an ID with a link to its doc, never a bare code |
| Checked | `tests/test_planning_docs.py`: every ID's prefix is an existing doc number or data issue; every open ID appears in its doc (`Next:` line or Decisions table); no new `OI-NN` |

## Decisions

| # | Question | Proposed |
|---|---|---|
| N1 | ID format `NNN-Kn` for docs and `DInn-Sn` for data issues (`000-` for process work)? | Yes |
| N2 | Kinds `D` decision, `T` test sign-off, `U` user task, `A` Claude task, `S` data source? | Yes |
| N3 | Split OI-01 into one `NNN-T` per plan, shown in each plan's `Next:` line? | Yes |
| N4 | Rename open **and** closed items, with a **Was** column? (Alternative: only open items) | Open and closed: one scheme everywhere; Was keeps history |
| N5 | Decisions: renumber the **open** ones now (005 R4–R12 → `005-D4`…, 011 DOC-1–10 → `011-D1`…); approved ideas keep their tables with a one-line "H1–H7 are 013-D1 – 013-D7" note rather than being rewritten? | Yes: approved tables match the commits that cite them |
| N6 | `open_items.md` sorted by ID with columns ID · Where · What · Owner · Status · Was? | Yes |
| N7 | Enforce it in `tests/test_planning_docs.py` (prefix exists, open IDs appear in their doc, no new `OI-NN`)? | Yes |
| N8 | Update the VW `CLAUDE.md` and `planning/README.md` rules (header `Next:` names the ID; chat always links IDs)? | Yes |
