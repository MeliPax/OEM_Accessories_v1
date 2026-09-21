# Genesis: Hyphenated Keyword Tokenization ("e-sc") — Open Hypothesis

**Date:** 2026-08-31  
**Status:** Research findings (root cause unconfirmed; needs live trace)  
**Impact:** Unknown; user's `['gv80','coupe','3.5t','e-sc']` test case fails for reason other than first three keywords

---

## Executive Summary

The user's test of `['gv80','coupe','3.5t','e-sc']` for 2026 Genesis GV80 Coupe fails. Tracing the first three keywords (gv80, coupe, 3.5t) shows they should each resolve correctly per the documented search-engine behavior:

- `"gv80"` matches ModelName ✓
- `"coupe"` is classified MODEL and found in ModelName ✓
- `"3.5t"` is classified ENGINE_SPEC and found in Description/TrimName ✓

Something else is failing. The leading unconfirmed hypothesis: `"e-sc"` (an engine variant designation in GV80 Coupe's TrimName) is being fragmented by the tokenizer before classification, similar to the already-fixed "Edt.HEV" period-splitting bug from prior work.

---

## Context: The Failing Test Case

From user's veh_model_service.ipynb:
```python
year = 2026
ModelName = 'gv80'
keywords = ['gv80', 'coupe', '3.5t', 'e-sc']
# Expected: find GV80 Coupe 3.5T e-SC rows (2 rows exist in DB)
# Actual: NOT_FOUND
```

GV80 Coupe 2026 data:
```
ModelName: "GV80 Coupe"
TrimName: "3.5T e-SC" or "3.5T e-SC Prestige Black"
Description: "3.5t Electric Awd" or "3.5t Electric Prestige Black-Package Awd"
ModelNumber: V8CC7K3BGP00, V8CC7K3BGPBL
```

---

## Why First Three Keywords Should Work

### "gv80"

Checked via substring match against ModelName (`manufacture_module.py:1233-1240`):
```python
pattern = build_word_boundary_pattern("gv70")  # → r"\bgv70\b"
model_matches = df["ModelName"].str.contains(pattern)
```

Matches both `"GV80"` and `"GV80 Coupe"` rows. ✓

### "coupe"

Classified as MODEL (`genesis/classification.yaml:12`). Same ModelName substring match as above. ✓

### "3.5t"

Classified as ENGINE_SPEC (`genesis/classification.yaml`, implicit mapping via engine-type matching logic). Appears in:
- Description: `"3.5t Electric Awd"` ✓
- TrimName: `"3.5T e-SC"` ✓ (case-insensitive substring match)

Both rows should match. ✓

---

## The Unresolved Keyword: "e-sc"

`"e-sc"` is a hyphenated compound: "electric supercharger" designation for these Coupe trims.

### Hypothesis: Hyphen-Based Fragmentation

Recent commit on this branch (`368a1a3 Fix: Allow multi-char keyword matching in hyphenated trim names`, dated 2026-08-28) suggests hyphenation has been a recurring source of bugs. The commit message implies the tokenizer was previously splitting hyphenated words incorrectly.

If the tokenizer in `keyword_extractor.py` fragments `"e-sc"` into single-character tokens (`"e"`, `"sc"`) or other unintended splits:
- Classification looks up `"e"` in token_map → not found → UNCLASSIFIED
- Classification looks up `"sc"` in token_map → not found → UNCLASSIFIED
- Or the hyphen itself is stripped, leaving `"e"` and `"sc"` as separate tokens

The strict AND filter (`manufacture_module.py:1198-1246`) then requires **every** classified token to appear in the DB. If `"e"` or `"sc"` (or UNCLASSIFIED tokens) don't match, the candidate set becomes empty → NOT_FOUND.

### Evidence for This Hypothesis

1. **Prior work already fixed period-splitting**: commit `fd07029` added regex to split `"Edt.HEV"` on periods (`r'(?<=[a-zA-Z])\.(?=[A-Za-z])'`) to separate `"Edt"` and `"HEV"` correctly.

2. **Recent hyphen-specific fix**: commit `368a1a3` explicitly addresses "hyphenated trim names," suggesting the tokenizer was not handling hyphens correctly before.

3. **Pattern matching**: both period and hyphen are punctuation that can either join or separate tokens, depending on the tokenizer logic. If the period fix was surgical but didn't handle hyphens, or if hyphen handling is still too aggressive, `"e-sc"` could be fragmented incorrectly.

---

## Needed: Live Debug Trace

To confirm this hypothesis, the code needs actual instrumentation:

```python
# Pseudo-code for test in search_engine.py or keyword_extractor.py:
from accy_v2.model_lookup.search_engine import VehicleSearchEngine

engine = VehicleSearchEngine(...)
make = "Genesis"
year = 2026
keywords = ['gv80', 'coupe', '3.5t', 'e-sc']

# After tokenization (keyword_extractor.py):
tokens_after_extraction = extract_keywords(keywords)  
print(f"After extraction: {tokens_after_extraction}")
# Expected: ['gv80', 'coupe', '3.5t', 'e-sc']
# If bug: ['gv80', 'coupe', '3.5t', 'e', 'sc'] or ['gv80', 'coupe', '3.5t', 'esc']?

# After translation (genesis/translator.yaml):
tokens_after_translation = translate_tokens(tokens_after_extraction, genesis_translator)
print(f"After translation: {tokens_after_translation}")
# Expected: (mostly unchanged, no rule for e-sc)

# After classification (genesis/classification.yaml):
classified_by_category = classify_tokens(tokens_after_translation, genesis_classification)
print(f"After classification: {classified_by_category}")
# Expected: MODEL=['gv80','coupe'], ENGINE_SPEC=['3.5t'], ...
# If bug: MODEL=['gv80','coupe'], ENGINE_SPEC=['3.5t'], UNCLASSIFIED=['e','sc']?

# Then run the search:
result = engine.search(make, year, keywords)
print(f"Result: {result}")
```

**What to verify:**
1. Is `"e-sc"` preserved as a single token through tokenization, or fragmented?
2. If fragmented, what fragments does it become?
3. Does it classify successfully, or fall to UNCLASSIFIED?
4. If UNCLASSIFIED, does the strict AND filter cause the failure?

---

## Potential Root Causes (Ranked by Likelihood)

### 1. Hyphen-Splitting in `keyword_extractor.py` (Most Likely)

`keyword_extractor.py` may have regex or split logic that treats hyphens as delimiters, similar to how spaces/underscores are handled. If the period fix (`r'(?<=[a-zA-Z])\.(?=[A-Za-z])'`) was added but hyphen-handling wasn't updated, `"e-sc"` could be split into `["e", "sc"]`.

### 2. "e-sc" is not in Translator or Classifier (Less Likely)

If `"e-sc"` is not explicitly mapped anywhere, it would remain unmapped post-translation and unclassified post-classification, but it would still be a single token (not fragmented). The strict AND filter would then fail because no DATABASE row contains the literal substring `"e-sc"` as a classified token (trimmed, tokenized rows have `"e"` and `"sc"` separate if they're split in the DB too, but source keywords are classifed before the DB is queried, so the mismatch would cause the failure).

Actually, re-reading the logic: keywords are classified BEFORE DB matching. So if `"e-sc"` is unclassified, it gets dropped (per `classifier.py:90-91,103`), and the search continues without it. But the DB row's `TrimName` contains `"e-sc"` (unsplit). The match would still succeed because the DB-side match is via substring search on raw TrimName, not on classified tokens.

Wait — need to re-examine the actual filter logic. The strict AND filter iterates over **classified keywords**, not raw keywords. So if `"e-sc"` is unclassified and dropped, it wouldn't be in the filter loop at all, and the search should NOT fail due to `"e-sc"` alone.

**This suggests the fragmentation hypothesis (1) is more likely:** if `"e-sc"` is fragmented into `["e", "sc"]`, then two unclassified tokens would be dropped, and (if one of the others, like `"coupe"`, has a subtle issue not yet traced) the search could fail.

---

## What I Would Ask the User

Before designing a fix, I'd request a live trace or simplified test:

```python
# Run this and share output:
from accy_v2.model_lookup.search_engine import VehicleSearchEngine
from accy_v2.core.config_loader_v2 import load_oem_config

config = load_oem_config('.')
engine = VehicleSearchEngine(config)

result = engine.search("Genesis", 2026, ['gv80', 'coupe', '3.5t', 'e-sc'])
print(f"Result: {result}")

# Also test subsets:
result_no_esc = engine.search("Genesis", 2026, ['gv80', 'coupe', '3.5t'])
print(f"Without e-sc: {result_no_esc}")

result_esc_only = engine.search("Genesis", 2026, ['gv80', 'e-sc'])
print(f"Just gv80 + e-sc: {result_esc_only}")
```

---

## References

- **Related commits:** `368a1a3 Fix: Allow multi-char keyword matching in hyphenated trim names`, `fd07029 Plan: Package column differentiator + search-correctness fixes`, commit history for keyword_extractor.py changes
- **Code:** `accy_v2/core/helpers/keyword_extractor.py` (tokenization logic)
- **Data:** GV80 Coupe 2026 TrimName `"3.5T e-SC"` in db_vehicle_models.csv
