# Summary: Translator/Classifier ordering — quick reference

## 30-second version

**Problem:** `translator.yaml` feeds three different consumers (DB ingestion, classification, DB
matching) that each need a different output vocabulary, with nothing enforcing they agree. Fixing one
consumer silently breaks another — happened twice in a row on the same Mitsubishi PHEV bug.

**Solution:** Translate exactly once, right after extraction. Every value translator can produce must
be a classification `token_map` key (enforced by a test, not convention). Ingestion should canonicalize
every DB column search matches against (`ModelName` currently missing), so query-time DB matching never
needs to re-translate independently.

## The two failures that motivated this (both verified against the live DB, not just traced)

1. **Before fix:** `phev` untranslated → never matches DB text (DB says "Plug-In Hybrid") → every PHEV
   trim lookup returns `None` → loud DQ failure.
2. **After the "obvious" fix** (`phev: plug-in hybrid` in translator.yaml): fixes DB matching, but
   `classification.yaml` has no `"plug-in hybrid"` key → token silently dropped → GT still fails (now
   ambiguous instead of empty), and **ES/SE/LE/SEL silently return the gas model number instead of the
   PHEV one**, with no error at all. Confirmed by running the search engine directly:
   `ES (PHEV sheet) → model_number='CO45-B'` (should be `COEV-B`).

## Five-step plan (see `plan.md` for full detail)

| # | Action | File(s) | Priority |
|---|--------|---------|----------|
| 1 | Add `plug-in hybrid: ENGINE_TYPE` to classification.yaml | `configs/mitsubishi/classification.yaml` | Now |
| 2 | Add contract test: translator output ⊆ classifier token_map | new `tests/test_translator_classifier_contract.py` | Now |
| 3 | Extend `_standardize_description()` to also normalize `ModelName` (+ backfill existing rows) | `models/manufacture_module.py` | This week |
| 4 | Remove redundant second translation call in `search_models_by_description()` | `models/manufacture_module.py` | After #3 |
| 5 | Delete or fix stale `ARCHITECTURE.md` / dead `core/search.py`, `semantic/search.py` (describe a code path nothing in production uses) | `model_lookup/ARCHITECTURE.md`, `core/search.py`, `semantic/search.py` | Anytime |

## Files to read for details

- `issue.md` — full root-cause diagnosis, evidence from live test runs, the three-consumers table
- `plan.md` — ordering principle, step-by-step fix with code, priority/sequencing, verification steps

## Success criteria

- Contract test passes for every OEM with a translator config.
- Mitsubishi PHEV sheet: all trims resolve to `COEV-*` codes (not `CO45-*` gas codes, not `None`).
- No independent re-translation needed inside `search_models_by_description()` once ingestion covers
  `ModelName`.
- Nobody debugging this area again lands on `ARCHITECTURE.md`, `core/search.py`, or `semantic/search.py`
  expecting them to reflect production behavior.