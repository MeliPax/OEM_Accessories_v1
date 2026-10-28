# 007 — Comment Text Cleaning: Plan

**Status:** Built — in user testing (2026-10-28)
**Updated:** 2026-10-28
**Next:** user signs off testing (OI-01)
**Links:** idea [007](../ideas/007_comment_text_cleaning_design.md) · depends on plan [003](003_accessory_model_matching.md)
**Summary:** A clean_text step before dedupe turns comments into readable sentences, replaces the dead Salsify link and flags unreviewed links.
**Note:** written after the build, on 2026-10-28, from the idea's decisions and build notes. The plan step was skipped at build time, and this file records the work in the standard format.

## Outcome

The `comments` column (`dealerNotes` in the file) reaches the dict and the export as readable sentences:
- no HTML tags or `|` separators;
- tidy spaces;
- the dead Salsify link replaced by `Thule.com`;
- every rule, tag list and link rule in config;
- every change logged before → after;
- the raw text kept as `comments_source`.

**Success criteria (2026-10-20 file)**

- [x] 62 distinct comment texts are cleaned once each and mapped back to their rows. 54 change (2,969 rows in the year window).
- [x] No `<` tag or `|` is left in the exported comments.
- [x] 1 link is replaced (Salsify → `Thule.com`), 3 `www.vwhub.com` links are kept whole, and 0 links are flagged.
- [x] Each changed text has one change-log row (step `clean_text`), naming the rules that fired and the row count.
- [x] Cleaning runs before duplicate removal, and dedupe still ends at 1,357 rows (C5).
- [x] A link no rule or allowed host covers is flagged `ACCESS_CLEAN_UNREVIEWED_LINK` (warning) and listed in `accessory_review.csv` (C4). An unlisted tag is removed and logged `ACCESS_CLEAN_UNKNOWN_TAG` (info).
- [x] A bad `text_cleaning` block (a column that isn't text, a bad `match_type`, an empty `replace_with`, a tag in both lists) stops the run with a `CONFG_` error.
- [x] `accessory_runs.csv` gains `texts_cleaned` (54) and `links_flagged` (0).

---

## Phase T1 — Config and validation

- [x] `config/accessories.yaml`: add a `text_cleaning:` block with these settings:
  - `columns`, `decode_html_entities`;
  - `separators` (pipes; tags `p, br, li, div`), `remove_tags`;
  - `sentence_end`, `ending_punctuation`, `join_with`;
  - `link_rules` (Salsify → Thule.com), `allowed_link_hosts` (`www.vwhub.com`).
- [x] `pipeline/config_helpers.py` `_text_cleaning_spec`: validate it; tag names are lower-cased.

**Done when:** the real config loads, and each broken case in `test_config_helpers.py` fails with its message.

## Phase T2 — Cleaning rules (`pipeline/text_helpers.py`, new)

- [x] `clean_text(text, rules)` → `{text, rules, links, unknown_tags}`. It works in this order:
  1. decode entities;
  2. normalize spaces;
  3. protect links;
  4. split on separators;
  5. remove other tags;
  6. trim each segment and add a full stop;
  7. join and tidy (C1).
- [x] `find_links`, `link_host`, `link_rule_for`: a link rule replaces only the URL, so the sentence stays (C2).

**Done when:** each rule has a before → after test.

## Phase T3 — The `clean_text` step

- [x] `clean_text_columns` in `pipeline/accessory_helpers.py` runs as a new step after `year_window` and before `dedupe` (C5). It cleans once per distinct text, keeps `comments_source` (C6), and logs one change per changed text.
- [x] Flags `ACCESS_CLEAN_UNREVIEWED_LINK` (review row `type = value`) and `ACCESS_CLEAN_UNKNOWN_TAG` (log only), with entries in `config/messages.yaml`.
- [x] Dedupe ignores lineage columns (`*_source`), so `<p>A.</p>` and `A.` become one row.

**Done when:** the step tests pass and the end-to-end run gives the success-criteria numbers.

## Phase T4 — Docs and data issues

- [x] `README.md` (the step and its config), `db/README.md` (the flags and review rows).
- [x] `planning/data_issues.md`: DI-08 to DI-11 set to Handled. The DI-16 glued text ("ReferAlways install") is Accepted and left as it is (user, 2026-10-28).

---

## Tests

| File | Covers |
|---|---|
| `tests/test_text_helpers.py` | Each rule before → after; a part reference (`5G0.071.644.B .GRU`) left alone; the Salsify replacement; vwhub links kept whole with no full stop added; links stop at a tag and before trailing punctuation; unreviewed links; unknown tags; the step (once per distinct text, raw text kept, review rows); markup-only copies becoming one row after dedupe |
| `tests/test_config_helpers.py` | Non-text column, bad `match_type`, empty `replace_with`, a tag in both lists |
| `tests/test_accessories_end_to_end.py` | `test_comments_are_clean_and_keep_the_raw_text` on the real file |

All 221 tests pass (2026-10-28).

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-10-27 | C1–C8 approved: one split / clean / join model; URL-only link rules; keep vwhub links; flag other links; clean before dedupe; keep `comments_source`; `comments` only; no curly-quote change | User |
| 2026-10-28 | Built together with plan 006, in one change | Same steps and config file |
| 2026-10-28 | **Build.** `remove_tags` is a list (`b, i, u, strong, em, span, font`), not `any_other`. Any other tag is still removed and logged `ACCESS_CLEAN_UNKNOWN_TAG` | New markup stays visible in the log instead of being removed silently |
| 2026-10-28 | **Build.** Links stop at `<` | The vwhub links run straight into the next tag (`.../trailer-hitch<p>Always`) |
| 2026-10-28 | **Build.** No full stop is added after a sentence that ends with a link | A trailing `.` would break the link when someone copies it |
| 2026-10-28 | **Build.** A space before punctuation is removed only when the mark ends the word | `5G0.071.644.B .GRU` is a part reference |
| 2026-10-28 | **Build.** 54 texts change, not the estimated 40 | Every text without a final full stop now gets one (C1) |
| 2026-10-28 | "ReferAlways install" is left as it is; no rule splits or rewrites it (DI-16 Accepted) | User: "leave the text as it is" |
| 2026-10-28 | **Build.** The plan was written after the build | The plan step was skipped; recorded so the process is followed from now on (see `CLAUDE.md`) |

## Risks

| Risk | Mitigation |
|---|---|
| A new link in a future file | Flagged `ACCESS_CLEAN_UNREVIEWED_LINK`, kept as it is, in review: add a link rule or an allowed host |
| New markup in a future file | Removed and logged `ACCESS_CLEAN_UNKNOWN_TAG`; add it to a tag list |
| A rule changes text it shouldn't | Every change is in the change log with its rule; `comments_source` holds the raw text |

## Follow-ups

- Clean `product_description` too if needed (C7): a one-word change to `text_cleaning.columns`.
