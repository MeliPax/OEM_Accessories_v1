# Genesis: Package/Qualifier Keyword Classification Gap — Translation vs. Classifier Mismatch

**Date:** 2026-08-31  
**Status:** Research findings (minimal surgical fix identified)  
**Impact:** Silent failure for "5p"/"7p" keywords; year-dependent "pkg" availability

---

## Executive Summary

Genesis's translator rewrites abbreviated keywords (`5p→5-passenger`, `7p→7-passenger`, `tech→technology`, `pkg→package`) **before** classification runs. However, `genesis/classification.yaml` is missing token-map entries for the post-translation forms, causing `5p`/`7p` to become UNCLASSIFIED and be silently dropped.

**Mitigation:** Add two lines to `genesis/classification.yaml` to match Hyundai's already-correct pattern. No code changes needed.

---

## Finding 1: Genesis Translator Rewrites Before Classification

### Confirmed Behavior

`genesis/translator.yaml:29-37`:
```yaml
pkg: package
tech: technology
5p: 5-passenger
7p: 7-passenger
```

Pipeline execution order (`search_engine.py:102-110`):
1. **Step 1 (translate):** Raw keywords pass through translator → `"5p"` becomes `"5-passenger"`
2. **Step 2 (classify):** Translated tokens look up in token_map → must find `"5-passenger"` key
3. **Step 3+ (filter/search):** Classified tokens used for DB matching

### The Mismatch

`genesis/classification.yaml:43-50` **contains dead `5p: PACKAGE` and `7p: PACKAGE` entries**:
```yaml
pkg: PACKAGE
package: PACKAGE
tech: PACKAGE
technology: PACKAGE
entertainment: PACKAGE
plus: PACKAGE
5p: PACKAGE        # ← DEAD: never seen post-translation
7p: PACKAGE        # ← DEAD: never seen post-translation
```

But Genesis's token_map **lacks entries for post-translation forms**:
- No `5-passenger: ...` entry
- No `7-passenger: ...` entry

When `"5p"` is translated to `"5-passenger"`, the classifier looks for `5-passenger` in the token_map, finds nothing, and marks it UNCLASSIFIED. The `_classify_tokens()` function (`classifier.py:90-91,103`) drops UNCLASSIFIED tokens before returning:

```python
result.pop("UNCLASSIFIED", None)  # discarded, not used
```

**Confirmed impact:** A search containing raw `"5p"` keyword silently fails due to strict AND filtering (`manufacture_module.py:1198-1246`). No error, no warning — just an empty candidate set.

---

## Finding 2: Hyundai Already Has the Correct Config

### Comparison

`hyundai/classification.yaml:86`:
```yaml
5-passenger: SEATING
```

Hyundai's translator has **no** `5p→5-passenger` mapping (no translator file at hyundai path, or it's absent from there), so raw Hyundai `"5p"` keywords would theoretically hit the same gap. However, Hyundai's classification.yaml has the post-translation form mapped correctly, so **if** Hyundai data ever includes `"5-passenger"` tokens (whether from source, translator, or vendor), they classify correctly.

Genesis is missing this entry entirely.

---

## Finding 3: Other Keywords Round-Trip Correctly

| Keyword | Translation | Classification | Status |
|---------|-------------|---|--------|
| pkg | package | `package: PACKAGE` ✓ | Works |
| tech | technology | `technology: PACKAGE` ✓ | Works |
| 5p | 5-passenger | (missing) ✗ | **BROKEN** |
| 7p | 7-passenger | (missing) ✗ | **BROKEN** |
| 5-passenger | (no translation) | (missing) ✗ | **BROKEN** (latent) |
| 7-passenger | (no translation) | (missing) ✗ | **BROKEN** (latent) |

`pkg` and `tech` work because both pre- and post-translation forms are mapped in `genesis/classification.yaml`.

---

## Data Evidence: Year-Dependent Availability

### GV80 2025 (4 rows total)

| TrimName | Description | tech? | pkg? | 5p? |
|----------|------------|-------|--------|---------|
| 2.5T Advanced | "2.5t Advanced Awd 5-Passenger" | No ("tech" literal) | No ("Package" full) | Yes ("5-Passenger") |
| 2.5T Advanced | "2.5t Advanced With-**Technology Package** Awd 5-Passenger" | **Yes** ("Technology") | **Yes** ("Package") | Yes ("5-Passenger") |
| 3.5T Advanced | "3.5t Advanced With-**Technology Package** Awd 7-Passenger" | **Yes** ("Technology") | **Yes** ("Package") | No |
| 3.5T Prestige | "3.5t Prestige Awd 7-Passenger" | No | No | No |

Search for `["gv80","advanced","tech","5p"]` 2025: both 2.5T rows contain "technology" but only one contains both "technology" AND "5-passenger" AND "package" (rows are different). The strict AND filter would narrow down, but the `"5p"` token, being UNCLASSIFIED, **causes the entire search to fail** before the more-nuanced matching logic runs.

### GV80 2027 (2 rows total)

| TrimName | Description | pkg? | 5p? |
|----------|------------|---------|-------|
| 2.5T Advanced w/Tech Pkg | "2.5t Advanced With-Technology Package Awd" | **Yes** ("Pkg" abbr) | No |
| 3.5T Advanced w/Tech Pkg | "3.5t Advanced With-Technology Package Awd" | **Yes** ("Pkg" abbr) | No |

In 2027, `TrimName` abbreviates to `"Pkg"`, so a search for `"pkg"` can find it (keyword "pkg" can match "Pkg" with case-insensitive substring search in TrimName). But `Description` still spells out "Package" in full. Year-dependent mismatch.

---

## Mitigation

### Option A: Minimal Config Fix (Recommended)

Add two lines to `genesis/classification.yaml`, matching Hyundai's pattern:

```yaml
5-passenger: SEATING
7-passenger: SEATING
```

This is **config-only, zero code changes**, and reuses an existing category (Hyundai's `SEATING` classification). Classification weight for SEATING = 2 (`scorer.py:18`), which is reasonable for passenger-count attributes.

**Time to implement:** ~1 minute. **Risk:** None (additive only).

---

### Option B: Broader Keyword Pass (Optional)

While fixing this gap, check both Hyundai and Genesis's translators and classifiers for **any other** missing round-trip entries:

- Hyundai's translator: does it have `5p→5-passenger` mapping or equivalent? If not, add it + add classification.
- Genesis's translator: any other abbreviations that might have the same issue?

**Time:** 15-30 min discovery pass + updates. **Risk:** Minimal (all additive).

---

## Known Unknowns

### Does Hyundai Have the Same Latent Gap?

Hyundai's `hyundai/translator.yaml` — I did not find it or read it directly. If Hyundai has **no** translator, then raw Hyundai `"5p"`/`"7p"` keywords would pass through untranslated and look up directly in `hyundai/classification.yaml`. Since Hyundai has `5-passenger: SEATING` (line 86), it would classify correctly *if* source data ever provides the full form.

But if Hyundai *does* have a translator that rewrites `5p→5-passenger`, and that translator is active, then raw Hyundai `"5p"` would hit the same round-trip path as Genesis. Worth checking.

### Is "5-Passenger" Actually Used in ADS Source Data?

The DB dump shows literal `"5-Passenger"` strings in Description (DB already has the full form). But ADS source data (the user's input spreadsheets) only provides shortened trim names like `"advanced"`, `"tech"`, etc. The question: does any OEM's ADS export ever provide raw `"5p"`/`"5-passenger"` keywords?

If not, then Genesis's translator rewrites them (so the fix is necessary), but Hyundai's might never receive them in the first place (so the latent gap might be harmless). Worth verifying against ADS export specs.

---

## References

- **Code:** `genesis/translator.yaml` (translation rules), `genesis/classification.yaml:43-50` (token_map), `classifier.py:90-91,103` (drops UNCLASSIFIED)
- **Comparison:** `hyundai/classification.yaml:86` (has `5-passenger: SEATING`)
- **Data:** GV80 2025/2027 rows in db_vehicle_models.csv
