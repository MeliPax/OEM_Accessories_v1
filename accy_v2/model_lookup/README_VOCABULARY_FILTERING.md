# Vocabulary-Based Exact Keyword Matching

Quick reference for the vocabulary filtering system.

## What Problem Does This Solve?

**Before:** `search_models_by_description("Mitsubishi", 2026, ["outlander", "phev", "gt"])` returned:
- "Outlander PHEV GT S-AWC" ✓
- "Outlander PHEV GT Premium S-AWC" ✗ (unwanted match)
- Result: False "Ambiguous match" DQ warning

**After:** Same search returns only:
- "Outlander PHEV GT S-AWC" ✓
- Result: Unambiguous match ✓

## How It Works

1. Vocabulary files in `configs/` contain all tokens from each manufacturer's database
2. Tokens are categorized as:
   - **Trim discriminators**: premium, noir, se, es, gt, le, limited, sport, etc. (differentiates trim level)
   - **Specifications**: fwd, awc, s-awc, manual, cvt, pkg, etc. (optional features, not trim)
3. Search results are filtered: if a result has extra trim discriminators, it's excluded
4. Results with extra specs (like "S-AWC" when not searched) are still included

## Quick Start

### First Time Setup
```bash
cd model_lookup
python bootstrap_vocabs.py
```
Creates vocabulary JSON files for all manufacturers.

### Using in Code
```python
from model_lookup.models.manufacture_module import search_models_by_description

# Exact match (vocab filtering active if files exist)
results = search_models_by_description(
    make="Mitsubishi",
    year=2026,
    keywords=["outlander", "phev", "gt"],
    csv_path="db/db_vehicle_models.csv"
)
# Returns: 1 row - "Outlander PHEV GT S-AWC" only
```

## Vocabulary Files

Location: `model_lookup/configs/`

Format: `{make_lowercase}_keywords.json`
```json
{
  "make": "Mitsubishi",
  "generated_at": "2026-06-23T09:01:31.612545",
  "keyword_count": 33,
  "keywords": ["awc", "eclipse", "es", "gt", "noir", ...]
}
```

**Auto-updated:** Files regenerate whenever `save_vehicle_models_to_csv()` is called with new data.

## Trim Discriminators

Keywords that differentiate trim levels (in `_get_trim_discriminator_keywords()`):
- Common trim names: es, se, sel, gt, le, limited, touring, premium, noir
- OEM-specific: ex-l, lx, sx, glx, comfortline, trendline, execline, etc.

**NOT discriminators** (specs that vary within a trim):
- Drive: fwd, awc, s-awc, awd, rwd, 4wd
- Transmission: manual, cvt, at, auto, dsg
- Other: pkg, avail*, *ltd, w/tech, edition, carbon, black

## Testing

```bash
# Run all test cases
python test_exact_matching.py

# Expected output:
# Test 1: ["outlander", "phev", "gt"] → 1 row (✓ excludes Premium/NOIR)
# Test 2: ["outlander", "phev", "gt", "premium"] → 1 row (✓ includes Premium)
# Test 3: ["rvr", "es"] → 2 rows (✓ all drive types for this trim)
```

## Troubleshooting

**Q: Searches return 0 results (but did before)**
- Check if `model_lookup/configs/` directory exists
- Run `python bootstrap_vocabs.py` to generate vocab files
- If vocab missing, filter gracefully falls back to no-op (shouldn't return 0)

**Q: Searches still return ambiguous results**
- Check `model_lookup/configs/{make_lowercase}_keywords.json` exists
- Verify keywords list contains expected trim names (es, se, gt, premium, etc.)
- If keyword missing, it won't be filtered — add to database and regenerate vocab

**Q: Want to disable vocabulary filtering**
- Delete `configs/` directory or vocab files
- Filter gracefully falls back to no-op
- Search will behave like before (no trim discriminator filtering)

**Q: Got 2 results for the same search that should be unambiguous**
- Likely case-sensitivity issue in manufacturer name matching
- Database might have duplicate entries with different Description text
- Check database for `(make, year, keywords)` uniqueness

## Files

- `bootstrap_vocabs.py` — One-time setup script
- `test_exact_matching.py` — Test cases for verification
- `debug_vocab_filter.py` — Debug script to inspect filtering
- `inspect_db.py` — Inspect available manufacturers and years
- `configs/` — Vocabulary JSON files (generated)

## API Reference

### `build_manufacturer_keyword_vocab(make, csv_path, configs_dir) -> dict`
Build and save vocabulary for one manufacturer.

### `load_manufacturer_keyword_vocab(make, configs_dir) -> set[str]`
Load vocabulary for a manufacturer. Returns empty set if file missing.

### `bootstrap_all_vocabs(csv_path, configs_dir) -> dict`
Build vocabulary for all manufacturers in the database.

### `_get_trim_discriminator_keywords() -> set[str]`
Get the hardcoded set of trim discriminator keywords.

### `search_models_by_description(make, year, keywords, csv_path, exclude_ev, configs_dir)`
Search with optional vocabulary-based exact matching. See docstring for full details.

