# Plan: Enforce a single canonicalization point for translator → classifier → DB matching

## Ordering principle

**Translation happens exactly once, immediately after raw extraction, before any other consumer sees
the tokens. Every downstream consumer — classifier, scorer, DB matcher — operates only on canonical
vocabulary, never on raw OEM spelling.**

```
Pipeline side (extraction — stays dumb, OEM-agnostic):
  1. KeywordExtractor pulls RAW tokens verbatim from sheet name / trim column / model_name.
     Does NOT normalize anything — it doesn't own OEM vocab rules.

Model-lookup side (query time — single canonicalization point):
  2. translate_keywords()   ← the ONLY place raw→canonical conversion happens
  3. classify_tokens()      ← consumes canonical vocabulary only
  4. compute_score()        ← scores the canonical, classified buckets
  5. DB matching            ← matches the SAME canonical keyword list against DB text

Ingestion side (write time, independent of any query):
  6. _standardize_description() ← writes DB text in that same canonical vocabulary,
                                    across every column search matches against
```

If step 6 fully canonicalizes every matched column, step 5 never needs to re-translate — collapsing
today's three independent translation call sites (steps 2, 5-internal, 6) down to two, with one shared
target vocabulary between them.

## Concrete steps

### Step 1 — Immediate unblock: fix `classification.yaml` (5 min)

**File:** `accy_v2/model_lookup/configs/mitsubishi/classification.yaml`

Add the post-translation form as a token_map key:
```yaml
token_map:
  phev: ENGINE_TYPE           # keep — still needed if "phev" ever appears untranslated
  plug-in hybrid: ENGINE_TYPE # add — translator's actual output for phev
```

Verified in a scratch copy of the configs (not the real file) against the live DB:
```
GT (PHEV sheet)  → COEV-X  ✓ (was None)
ES (PHEV sheet)  → COEV-B  ✓ (was silently CO45-B, the gas code)
GT NOIR (PHEV)   → COEV-N  ✓ (clean single match)
```

After applying for real: re-run the Mitsubishi pipeline and spot-check any previously-"resolved" DQ
entries for ES/SE/LE/SEL trims to confirm none of the already-processed output has a gas model number
baked in from before this fix.

### Step 2 — Add the contract test (30 min, highest leverage)

**New file:** `accy_v2/model_lookup/tests/test_translator_classifier_contract.py`

For every OEM with a `translator.yaml` + `classification.yaml` pair, assert every value the translator
can produce is a key in that OEM's classification `token_map`:

```python
import pytest
from pathlib import Path
from model_lookup.semantic.translator import load_oem_translator
from model_lookup.semantic.classifier import load_classification_config

CONFIGS_DIR = Path(__file__).parent.parent / "configs"

def _oems_with_translators():
    return [p.name for p in CONFIGS_DIR.iterdir() if (p / "translator.yaml").exists()]

@pytest.mark.parametrize("make", _oems_with_translators())
def test_translator_outputs_are_classifiable(make):
    translator = load_oem_translator(make, str(CONFIGS_DIR))
    classification = load_classification_config(make, str(CONFIGS_DIR))
    token_map = classification.get("token_map", {})

    unclassifiable = sorted({
        translated for translated in translator.values()
        if translated not in token_map
    })

    assert not unclassifiable, (
        f"{make}: translator produces tokens with no classification entry: {unclassifiable}. "
        f"Add each to {make}/classification.yaml's token_map, or the translation will be "
        f"silently dropped by classify_tokens() (UNCLASSIFIED tokens are removed, not scored, "
        f"and never reach DB search)."
    )
```

This single test would have caught the `phev: plug-in hybrid` regression the moment it was added,
instead of surfacing as a silent wrong-model-number bug days later. Run it as part of whatever suite
gates config changes to `translator.yaml`/`classification.yaml`.

### Step 3 — Extend ingestion-time standardization to `ModelName` (~1-2 hrs)

**File:** `accy_v2/model_lookup/models/manufacture_module.py`

`_standardize_description()` currently only normalizes the `Description` column when
`save_vehicle_models_to_csv()` writes new rows (see the loop around `df_valid.loc[mask, "Description"]`).
`ModelName` — the column that actually distinguishes "Outlander" from "Outlander Plug-In Hybrid" — is
never touched, so it stays exactly as ADS spells it.

Apply the same standardization to `ModelName` (and any other free-text column search matches against —
currently `TrimName`, `Description`, `ModelName`):
```python
for make in df_valid["Manufacturer"].unique():
    translator = load_oem_translator(make, configs_dir)
    if translator:
        mask = df_valid["Manufacturer"] == make
        for col in ("Description", "ModelName"):
            if col in df_valid.columns:
                df_valid.loc[mask, col] = df_valid.loc[mask, col].apply(
                    lambda d: _standardize_description(d, translator)
                )
```

This is a one-time backfill concern too: existing rows in `db_vehicle_models.csv` were written before
this change and won't have canonicalized `ModelName` values. Either re-run ingestion for affected makes,
or write a small one-off script to apply `_standardize_description()` to the existing `ModelName` column
in place (same non-destructive pattern as the Part 1 archive-recovery from the prior Mitsubishi
model-lookup plan — read, transform, write back, no archive/rename step).

### Step 4 — Collapse the redundant query-time re-translation (~30 min, do after Step 3 lands)

**File:** `accy_v2/model_lookup/models/manufacture_module.py`, inside `search_models_by_description()`

Once Step 3 ensures DB text is already in canonical vocabulary, the independent
`load_oem_translator()` + `translate_keywords()` call at the top of `search_models_by_description()`
(lines ~1126-1140) becomes redundant — the keywords arriving here were already translated once by
`VehicleSearchEngine.search()` before this function was called. Remove the second translation call, or
if kept intentionally as defense-in-depth for callers that bypass `VehicleSearchEngine`, add a comment
pointing at the Step 2 contract test so it's clear the two call sites are not allowed to diverge.

Do this after Step 3, not before — removing it first would re-expose the original "phev never matches
DB text" failure mode for any `ModelName` rows not yet backfilled.

### Step 5 — Flag or remove dead architecture docs/code (~15 min)

**Files:** `accy_v2/model_lookup/ARCHITECTURE.md`, `accy_v2/model_lookup/core/search.py`,
`accy_v2/model_lookup/semantic/search.py`

Confirmed via grep: nothing in production imports these. Both Hyundai's and Mitsubishi's
`step4_5_model_enrichment.py` use `accy_v2.model_lookup.search_engine.VehicleSearchEngine` and
`accy_v2.model_lookup.models.manufacture_module` directly — a different, undocumented path from what
`ARCHITECTURE.md` describes. `core/search.py`/`semantic/search.py` are only imported by each other and
by `__init__.py` files nothing else touches.

Either:
- **Delete** `core/search.py`, `semantic/search.py`, and rewrite `ARCHITECTURE.md` to describe the
  actual live path (`search_engine.py` + `models/manufacture_module.py` + `semantic/translator.py` +
  `semantic/classifier.py` + `semantic/scorer.py`), including the ordering principle from this plan, or
- At minimum, add a header comment to each dead file and to `ARCHITECTURE.md`:
  `# NOT USED IN PRODUCTION — see search_engine.py + models/manufacture_module.py instead`

Recommend deleting + rewriting — a stale "this is the architecture" doc is worse than no doc, since it
actively misdirects the next person debugging this area (nearly did so during this investigation).

## Priority / sequencing

| Step | Priority | Depends on |
|------|----------|------------|
| 1. Fix classification.yaml | Do now — unblocks live DQ failures | none |
| 2. Contract test | Do next — prevents recurrence | Step 1 (so it passes immediately) |
| 3. Extend ingestion to ModelName | This week | none, but backfill existing rows after |
| 4. Collapse redundant re-translation | After Step 3 | Step 3 |
| 5. Fix/remove dead docs | Anytime, low risk | none |

## Verification

1. Re-run Mitsubishi pipeline (`python run_pipeline.py mitsubishi`), confirm PHEV sheet trims (ES, SE,
   LE, SEL, GT, GT NOIR) all resolve to `COEV-*` codes, not `CO45-*` gas codes.
2. Run the new contract test: `python -m pytest accy_v2/model_lookup/tests/test_translator_classifier_contract.py -v`
3. Spot-check `db_vehicle_models.csv` after Step 3's backfill: Mitsubishi `ModelName` values should read
   consistently (e.g., whatever canonical casing `_standardize_description()` produces), not raw ADS text.
4. Regression: Hyundai and Mazda pipelines unchanged (57 and 14 sheets respectively) — Step 3/4 changes
   are shared code, so confirm no other OEM's search behavior shifted.