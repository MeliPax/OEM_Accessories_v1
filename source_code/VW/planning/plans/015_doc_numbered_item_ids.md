# 015 — Pending Items Numbered by Their Doc: Plan

**Status:** Built — in user testing (2026-11-03)
**Updated:** 2026-11-03
**Next:** user signs off testing (015-T)
**Links:** idea [015](../ideas/015_doc_numbered_item_ids_design.md) · extends plan [010](010_work_process_and_tracking.md) · [open_items.md](../open_items.md) · [data_issues.md](../data_issues.md)
**Summary:** Every open and closed item in `open_items.md` is renamed to `NNN-Kn` / `DInn-Sn` with a Was column, each plan shows its own `NNN-T` sign-off, open decisions are renumbered, and `tests/test_planning_docs.py` enforces the scheme.

## Outcome

Any ID names the file to open: `013-D2` → `planning/ideas/013_*`, `003-A1` → `planning/plans/003_*`, `DI07-S1` → `data_issues.md#di-07`. No new `OI-NN` is created; old ones still resolve through the Was column.

**Success criteria**

- [x] `open_items.md`: every row renamed per the map below, sorted by ID, columns ID · Where · What · Owner · Status · Was; nothing deleted.
- [x] Each plan in user testing shows `NNN-T` in its `Next:` line and its index row; no `OI-01`.
- [x] Idea 005's R4–R12 read `005-D4` – `005-D12`; idea 011's DOC-1 – DOC-10 read `011-D1` – `011-D10`; approved ideas carry the one-line ID note.
- [x] `grep -rn "OI-[0-9]" planning CLAUDE.md` finds only Was cells and dated decision-log / changelog history.
- [x] `tests/test_planning_docs.py` fails on: an unknown prefix, an open ID missing from its doc, a new `OI-NN`; passes on the real docs. Full suite passes.

## The rename map

| Was | New | Owner | Status |
|---|---|---|---|
| OI-01 | `001-T` `002-T` `003-T` `006-T` `007-T` `008-T` `009-T` `010-T` `012-T` `013-T` `014-T` (11 rows) | user | Open |
| OI-02 | `003-A1` | Claude | Open |
| OI-03 | `001-U1` | user | Open |
| OI-04 | `DI05-S1` | data source | Open |
| OI-05 | `DI06-S1` | data source | Open |
| OI-06 | `DI07-S1` | data source | Closed 2026-11-03 |
| OI-07 | `DI03-S1` | data source | Open |
| OI-08 | `DI16-S1` | data source | Open |
| OI-09 | `003-D18` | user | Open |
| OI-10 | `009-D1` – `009-D8` (one row, range) | user | Closed 2026-10-28 |
| OI-11 | `005-D4` – `005-D12` (one row, range) | user | Open |
| OI-12 | `009-U1` | user | Closed 2026-10-28 |
| OI-13 | `011-D1` – `011-D10` (one row, range) | user | Open |
| OI-14 | `005-U1` | user | Closed 2026-10-28 |
| OI-15 | `012-D4` – `012-D6` | user | Closed 2026-10-29 |
| OI-16 | `013-D1` – `013-D7` | user | Closed 2026-11-02 |
| OI-17 | `013-P` | user | Closed 2026-11-02 |
| OI-18 | `014-D1` – `014-D7` | user | Closed 2026-11-03 |
| OI-19 | `014-P` | user | Closed 2026-11-03 |
| OI-20 | `015-D1` – `015-D8` | user | Closed 2026-11-03 |
| OI-21 | `015-P` | user | Closed when this plan is approved |

A decision set stays one row with a range (`005-D4 – 005-D12`), as today; the doc's Decisions table holds each one.

## Phase I1 — Rename the items

- [x] `open_items.md`: rebuilt per the map (sorted by ID; Was column); its "Adding or closing an item" rules rewritten for the scheme.
- [x] `data_issues.md`: each `S` item named in its DI section (`**Ask the data source (DI07-S1):**`).
- [x] Plans 001–003, 006–010, 012–014: `Next:` lines name `NNN-T` (and `001-U1`, `003-A1`, `003-D18` where they apply); index `Next` cells match.
- [x] Ideas 005, 011: open decision rows renumbered (`005-D4`…, `011-D1`…), `Next:` lines updated. Approved ideas 001–004, 006–010, 012–015 and data issues: a one-line note under **Decisions** (`IDs: H1–H7 are 013-D1 – 013-D7`).

## Phase I2 — Rules and checks

- [x] `tests/test_planning_docs.py`:
  - item ID pattern `(\d{3}|DI\d{2})-[DTUASP]\d*`; every prefix is an existing doc number (or `000`) or data issue;
  - every open row's ID appears in its doc (`Next:` line or Decisions table, ranges expanded);
  - no `OI-NN` outside Was cells and dated history rows;
  - index `Next` cells may cite new IDs (the existing `Next` match check stays);
  - negative cases in `planning_copy` for each rule.
- [x] `CLAUDE.md` (VW) and `planning/README.md`: the ID scheme, the kinds table, "`Next:` names the ID", "in chat, always write an ID with a link to its doc".
- [x] Full suite; commit (approved and tested; not pushed).

**Done when:** the suite passes and the success criteria are ticked → `Built — in user testing`.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-11-03 | N1–N8 approved as proposed | User |
| 2026-11-03 | Plan approved with kind `P`; build started | User |
| 2026-11-03 | **Build.** `015-T` added (this plan's own sign-off); decision IDs in approved ideas are not open items, so a `D` ID mentioned in its own idea needs no row; `000` IDs are checked only once a `000` row exists | Claude |
| 2026-11-03 | **Build.** `OI-NN` kept where it is dated history (decision logs, CHANGELOG, idea 010's original table, the rename maps in idea / plan 015); the test checks each resolves through a Was cell | Claude |
| 2026-11-03 | **Build.** Data-source questions repeated in DV-08 / DV-09 carry `DI05-S1` | Claude |
| 2026-11-03 | **Build.** Suite: 304 passed (planning tests 9 → 15) | Claude |
| 2026-11-03 | **Proposed with the plan:** add kind `P` (plan approval, `NNN-P`), not in N2, for items like OI-17 / OI-19 | Every plan has one approval gate; it needs an ID too |

## Risks

| Risk | Mitigation |
|---|---|
| Old IDs in commits and closed docs stop making sense | Was column; approved ideas keep their tables with an ID note |
| A rename misses a reference and the index drifts | The planning test checks index ↔ file `Next:` and open IDs ↔ docs; grep check in the success criteria |
| The scheme is ignored next time | Rules in `CLAUDE.md`; the test rejects a new `OI-NN` |
