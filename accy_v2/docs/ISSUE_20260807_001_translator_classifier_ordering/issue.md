# Issue: No enforced ordering/contract between translator, classifier, and DB matching in model_lookup

**Date:** 2026-08-07
**Discovered while:** Debugging Mitsubishi 2026 Outlander PHEV model-number lookups (DQ: "No confident
model number match for Mitsubishi 2026 gt with keywords: ['outlander', 'phev', 'gt']")
**Status:** Root cause diagnosed, fix verified in a scratch config copy, not yet applied to real files.

## Summary

`accy_v2/model_lookup` has three places that each need OEM abbreviations translated to a "canonical"
form, but they're served by a single shared `translator.yaml` per OEM with no contract ensuring its
output actually satisfies all three consumers. Editing the translator to fix one consumer silently
breaks another. This already happened twice in the same investigation, back to back.

## The three consumers, and what each one actually needs

| # | Consumer | Where | Needs translator output to match... |
|---|----------|-------|----------------------------------|
| 1 | Ingestion-time DB text normalization | `_standardize_description()` in `manufacture_module.py` — runs when ADS data is saved to the CSV | nothing — this is meant to *be* the source of truth, but only touches the `Description` column, never `ModelName` |
| 2 | Query-time classification | `VehicleSearchEngine.search()`, calls `classify_tokens()` right after `translate_keywords()` | keys in `classification.yaml`'s `token_map` |
| 3 | Query-time DB matching | `search_models_by_description()` — **re-translates independently**, a second, separate call using the same translator config | literal words already sitting in the DB's `TrimName` / `Description` / `ModelName` columns |

Nothing enforces that translator's output vocabulary is a subset of classifier's input vocabulary, or
that ingestion actually normalizes every column search matches against. The two configs (`translator.yaml`,
`classification.yaml`) just happen to agree until someone edits one.

## How this manifested (two real, verified failures)

**Failure 1 — "phev" never translated, never matches DB text.**
Before any fix, `phev` passed through `translate_keywords()` unchanged (no entry in `translator.yaml`),
got classified correctly as `ENGINE_TYPE` (classification.yaml already had `phev: ENGINE_TYPE`), and was
included in the DB search keyword list as literal `"phev"`. But the DB never contains the string "phev"
anywhere — ADS spells it out as `"Outlander Plug-In Hybrid"` in the `ModelName` column. Every PHEV trim
lookup returned 0 candidates → `None` → DQ warning `MODEL_LINE_NOT_FOUND`, for every single Mitsubishi
PHEV trim.

**Failure 2 — fixing #1 broke classification, and silently corrupted a different set of rows.**
The fix applied was `translator.yaml`: `phev: plug-in hybrid` (mapping to a multi-word phrase, since
that's literally what `ModelName` contains). This fixed the DB-matching problem for consumer #3, but
`classification.yaml`'s `token_map` only has a key for `phev` (single word) — not `"plug-in hybrid"`. So
after translation, `classify_tokens()` can't find `"plug-in hybrid"` in the token map, buckets it as
`UNCLASSIFIED`, and **unconditionally drops it** (`classifier.py` line ~99: `result.pop("UNCLASSIFIED",
None)`). This has two effects:
  - `ENGINE_TYPE` never scores (lost weight: 8)
  - `"plug-in hybrid"` never reaches the DB search keyword list at all — the query silently degrades to
    just `outlander + <trim>`, which matches both the gas and PHEV rows equally (fuel type only lives in
    `ModelName`, never in `TrimName`/`Description`)

Verified by actually running the search engine against the live DB (not just tracing by hand):

```
GT (PHEV sheet), keywords=['outlander','phev','gt']
  → 5 ambiguous candidates (3 gas GT variants + 2 PHEV GT variants) → None → DQ failure (still)

ES (PHEV sheet), keywords=['outlander','phev','es']
  → 2 candidates, collapses into the "duplicate model code" fallback, picks results.iloc[0]
  → model_number='CO45-B'  ← WRONG. That's the GAS Outlander. The PHEV code is COEV-B.
```

So the "phev" translator fix didn't just leave GT broken — it made ES/SE/LE/SEL **silently return gas
model numbers for PHEV sheet rows**, with no DQ warning at all, because the search "succeeded" (just
with the wrong vehicle). That's worse than the original loud failure.

## Contributing gap: stale architecture doc describing dead code

While tracing every call site of `translate_keywords`/`classify_tokens`, found:
- `accy_v2/model_lookup/ARCHITECTURE.md` describes a `core/` + `semantic/` layered design with a public
  API (`from model_lookup import search, save_models, ...`) and files `core/search.py`, `semantic/search.py`.
- **Nothing in production imports any of it.** Both Hyundai's and Mitsubishi's `step4_5_model_enrichment.py`
  import directly from `accy_v2.model_lookup.search_engine.VehicleSearchEngine` and
  `accy_v2.model_lookup.models.manufacture_module` — a completely different, undocumented code path.
- `core/search.py` / `semantic/search.py` are only imported by each other and by `core/__init__.py` /
  `model_lookup/__init__.py` — never by anything that actually runs.

This isn't the direct cause of the PHEV bug, but it's a real risk: anyone reading `ARCHITECTURE.md` to
understand "how does translation/classification work" during a future fix would be looking at files that
don't run in production, and could easily patch the wrong `classifier.py` or `translator.py`.

## What's needed

See `plan.md` in this folder for the ordering principle and concrete fix. Short version: translation
must happen exactly once, immediately after raw extraction, and its output vocabulary must be a subset
of classification's input vocabulary — enforced by a test, not just convention. Ingestion should
normalize every DB column that search matches against (not just `Description`), so query-time DB
matching doesn't need its own independent re-translation step at all.