# Model Lookup Module Architecture

**Date:** June 23, 2026  
**Status:** Redesigned for modularity and maintainability

---

## Overview

The model_lookup module provides **vehicle model identification and management** with a clean, layered architecture:

- **Core Layer** (`core/`): Essential search and database operations
- **Semantic Layer** (`semantic/`): Optional enhancement for translation, classification, and confidence scoring
- **Configuration** (`configs/`): Auto-generated and hand-authored configs
- **Database** (`db/`): CSV-based vehicle model storage

**Key Design:** Semantic processing is **optional**. The core layer works independently. This enables both simple AND-logic searches and sophisticated semantic matching with confidence scores.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ PUBLIC API (model_lookup/__init__.py)                       │
│  - search()                                                 │
│  - save_models()                                            │
│  - load_models()                                            │
│  - build_vocabulary()                                       │
│  - load_vocabulary()                                        │
└─────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        v                   v                   v
  ┌──────────────┐  ┌──────────────────┐  ┌──────────────┐
  │ CORE LAYER   │  │ SEMANTIC LAYER   │  │ CONFIG/DB    │
  │ (Always On)  │  │ (Optional)       │  │              │
  └──────────────┘  └──────────────────┘  └──────────────┘
        │                   │                   │
        ├─ search()         ├─ search()         ├─ configs/
        │  (basic)          │  (semantic)       ├─ db/
        │                   │                   │
        ├─ database.py      ├─ translator.py    └─ models.csv
        │                   ├─ classifier.py
        ├─ vocabulary.py    └─ scorer.py
        │
        └─ ...
```

**Control Flow:**

```
INPUT: keywords → [search()] → {use_semantic: True/False}
                      │
                      ├─ use_semantic=False
                      │   └─→ core.search() → basic AND-logic → SearchResult or None
                      │
                      └─ use_semantic=True (default)
                          └─→ semantic.search()
                              ├─ [translator] OEM-specific abbreviations
                              ├─ [classifier] semantic token buckets
                              ├─ [scorer] weighted confidence
                              └─→ SearchResult or None

OUTPUT: SearchResult { model_number, match, confidence, score, tokens_matched }
```

---

## Directory Structure

```
model_lookup/
├── __init__.py                  # Public API (clean exports)
│
├── ARCHITECTURE.md              # This file
│
├── core/                        # CORE LAYER - Essential operations
│   ├── __init__.py
│   ├── search.py                # Main search interface
│   │                             # - search(make, year, keywords, use_semantic=True)
│   │                             # - SearchResult dataclass
│   │                             # - Helper functions for regex/filtering
│   │
│   ├── database.py              # CSV I/O and validation
│   │                             # - load_models(csv_path)
│   │                             # - save_models(df, csv_path, configs_dir)
│   │                             # - Validators and helpers
│   │
│   └── vocabulary.py            # Vocabulary management
│                                 # - build_vocabulary(make, csv_path, configs_dir)
│                                 # - load_vocabulary(make, configs_dir)
│
├── semantic/                    # SEMANTIC LAYER (Optional Enhancement)
│   ├── __init__.py
│   │
│   ├── search.py                # Semantic search wrapper
│   │                             # - Orchestrates translator → classifier → scorer
│   │                             # - Applies all semantic processing
│   │
│   ├── translator.py            # Keyword normalization (OEM-specific)
│   │                             # - load_oem_translator(make, configs_dir)
│   │                             # - translate_keywords(keywords, translations)
│   │                             # - Example: "s-awc" → "awd" (Mitsubishi)
│   │
│   ├── classifier.py            # Semantic token classification
│   │                             # - load_classification_config(make, configs_dir)
│   │                             # - classify_tokens(tokens, config)
│   │                             # - build_classification_config() for auto-generation
│   │                             # - Seed rules for bootstrapping
│   │
│   └── scorer.py                # Confidence scoring
│                                 # - CATEGORY_WEIGHTS, MINIMUM_SCORE constants
│                                 # - compute_score(classified)
│                                 # - compute_confidence(score, candidate_count)
│
├── configs/                     # Configuration files (auto & manual)
│   ├── mitsubishi_translator.json          # Hand-authored
│   ├── mazda_translator.json               # Hand-authored
│   ├── ...
│   │
│   ├── mitsubishi_classification.json      # Auto-generated
│   ├── mazda_classification.json           # Auto-generated
│   └── ... (one per manufacturer)
│
├── db/                          # Database files
│   └── db_vehicle_models.csv    # CSV database (9 columns)
│                                 # Columns: Manufacturer, ModelYear, ModelNumber, Description,
│                                 #          TrimName, Package, Style_ID, Drivetrain, PassDoors
│
└── tests/                       # Test suite
    └── test_search.py           # Comprehensive tests
                                 # - Unit tests for each component
                                 # - Integration tests (core + semantic)
                                 # - Backward compatibility tests
```

---

## Core Layer (`core/`)

### Purpose
Provides essential vehicle model search and database operations without any semantic processing.

### Key Modules

**`search.py`**
```python
def search(make, year, keywords, csv_path=None, exclude_ev=True, 
           configs_dir=None, use_semantic=True) -> SearchResult | None:
    """
    Search for vehicle models.

    - Basic AND-logic: all keywords must be present in Description
    - Whole-word matching: "SE" won't match "SEL"
    - Post-filter: excludes rows with extra TRIM discriminators
    - If use_semantic=True: delegates to semantic.search()
    - If use_semantic=False: uses basic filtering only

    Args:
        make: Manufacturer (e.g., "Mitsubishi")
        year: Model year (e.g., 2026)
        keywords: List of search keywords (tokenized, lowercased)
        csv_path: Path to CSV database
        exclude_ev: Exclude EV models unless EV keyword present
        configs_dir: Directory for configs
        use_semantic: Apply semantic processing (default: True)

    Returns:
        SearchResult(model_number, match, confidence, score, tokens_matched)
        or None if no match/ambiguous/below minimum score
    """
```

**`database.py`**
```python
def load_models(csv_path=None) -> pd.DataFrame:
    """Load vehicle models from CSV."""

def save_models(df, csv_path=None, configs_dir=None) -> dict:
    """Save models to CSV with validation and auto-vocabulary rebuild."""
    # - Validates year and required fields
    # - Checks for duplicates
    # - Rebuilds vocabulary for all manufacturers in saved data
    # - Returns result dict with save_status, records_saved, etc.
```

**`vocabulary.py`**
```python
def build_vocabulary(make, csv_path=None, configs_dir=None) -> dict:
    """Build vocabulary from CSV (all unique tokens in Descriptions)."""

def load_vocabulary(make, configs_dir=None) -> set:
    """Load pre-built vocabulary for a manufacturer."""
```

---

## Semantic Layer (`semantic/`)

### Purpose
Optional enhancement providing OEM-specific translation, semantic classification, and confidence scoring.

### Key Modules

**`search.py`**
Orchestrates the full semantic pipeline:
```
keywords → [translator] → [classifier] → [validator] → [scorer] →
[database search] → [confidence calc] → SearchResult
```

**`translator.py`**
Normalizes abbreviations using OEM-specific configs:
```python
# Example: Mitsubishi
translate_keywords(["outlander", "s-awc", "gt"], 
                  {"s-awc": "awd", "p": "premium"})
# Returns: ["outlander", "awd", "gt"]

# Example: Mazda (different rules)
translate_keywords(["cx-5", "i-activ"],
                  {"i-activ": "awd", "p": "preferred"})
# Returns: ["cx-5", "awd"]
```

**`classifier.py`**
Assigns tokens to semantic categories:
```python
classify_tokens(["outlander", "gt", "awd", "phev"], config)
# Returns:
# {
#   "MODEL": ["outlander"],
#   "TRIM": ["gt"],
#   "DRIVETRAIN": ["awd"],
#   "ENGINE_TYPE": ["phev"]
# }
```

**`scorer.py`**
Computes weighted confidence:
```python
CATEGORY_WEIGHTS = {
    "MODEL": 10,
    "ENGINE_TYPE": 8,
    "DRIVETRAIN": 6,
    "TRIM": 5,
    "TRANSMISSION": 3,
    "PACKAGE": 1,
}

compute_score(classified)  # Sum weights for non-empty categories
# Example: 10 + 8 + 6 + 5 = 29

compute_confidence(score=29, min_score=12, candidate_count=1)
# Returns: 0.0-1.0 (or 0.0 if ambiguous/below minimum)
```

---

## Configuration Files

### `{make}_translator.json` (Hand-Authored)

Maps OEM-specific abbreviations to normalized forms. Created once per manufacturer, manually maintained.

```json
{
  "make": "Mitsubishi",
  "version": "1.0",
  "translations": {
    "s-awc": "awd",
    "awc": "awd",
    "prem": "premium",
    "p": "premium",
    "n": "noir"
  }
}
```

### `{make}_classification.json` (Auto-Generated)

Semantic classification of all vocabulary tokens. Auto-generated when models saved to CSV, can be manually edited.

```json
{
  "make": "Mitsubishi",
  "generated_at": "2026-06-23T11:35:35",
  "token_map": {
    "outlander": "MODEL",
    "eclipse": "MODEL",
    "gt": "TRIM",
    "es": "TRIM",
    "awd": "DRIVETRAIN",
    "phev": "ENGINE_TYPE"
  },
  "unclassified": ["ltd"]  # Tokens not yet classified
}
```

---

## Usage Examples

### Basic Search (With Semantic Processing)

```python
from model_lookup import search

result = search(
    make="Mitsubishi",
    year=2026,
    keywords=["outlander", "phev", "gt"]
)

if result:
    print(f"Model: {result.model_number}")
    print(f"Match: {result.match}")
    print(f"Confidence: {result.confidence:.2f}")  # 0.0-1.0
    print(f"Score: {result.score}")
    print(f"Tokens: {result.tokens_matched}")
else:
    print("No match found or ambiguous")
```

### Search Without Semantic Processing

```python
result = search(
    make="Mitsubishi",
    year=2026,
    keywords=["outlander", "phev", "gt"],
    use_semantic=False  # Use basic AND-logic only
)
```

### Database Management

```python
from model_lookup import save_models, load_models, build_vocabulary

# Load all models
df = load_models()
print(f"Total models: {len(df)}")

# Save new models (automatically rebuilds vocabulary)
import pandas as pd
new_models = pd.DataFrame({
    "Manufacturer": ["Mitsubishi"],
    "ModelYear": [2026],
    "ModelNumber": ["ABC123"],
    "Description": ["Outlander PHEV GT Premium"]
})

result = save_models(new_models)
print(f"Saved: {result['records_saved']}, Vocab rebuilt: {result['vocabulary_rebuilt']}")

# Rebuild vocabulary manually if needed
vocab_result = build_vocabulary("Mitsubishi")
if vocab_result["saved"]:
    print("Vocabulary rebuilt")
```

---

## Design Principles

### 1. **Modularity**
Clear separation: Core (essential) vs. Semantic (enhancement). Semantic is optional and can be disabled.

### 2. **Config-Driven**
Translator and classifier configs in JSON, not hardcoded. Easy to customize per OEM.

### 3. **Backward Compatibility**
Existing `search_models_by_description()` still works. New API is additive, not replacing.

### 4. **Graceful Degradation**
Missing configs don't break the engine. Unclassified tokens handled gracefully (with warnings).

### 5. **Auto-Update**
Classification regenerated automatically when models saved. No manual config management required.

### 6. **Senior Developer Friendly**
Clear code structure, good separation of concerns, easy to extend, comprehensive documentation.

---

## Common Tasks

### Add a New Manufacturer

1. **Create translator config** → `configs/{make}_translator.json`
2. **Save models** → runs `save_models()` which auto-generates classification
3. **Review unclassified tokens** → edit `{make}_classification.json` if needed
4. **Test** → `search(make="{make}", year=..., keywords=[...])`

### Fix Unclassified Tokens

1. Run `save_models()` → generates new classification config
2. Check console for warnings: `"[WARNING] Mazda: 13 unclassified tokens: [...]"`
3. Edit `configs/mazda_classification.json` → move tokens from `unclassified` to appropriate category
4. Test search again

### Extend Semantic Processing

All semantic functionality lives in `semantic/`. To add new features:
1. Add new helper in appropriate module (translator, classifier, scorer)
2. Integrate into `semantic/search.py`
3. Update tests in `tests/test_search.py`
4. Document in this file

---

## Testing

Test suite covers:
- Unit tests for each module (translator, classifier, scorer)
- Integration tests (core + semantic together)
- Backward compatibility (old function still works)
- Edge cases (ambiguous matches, contradictions, missing configs)

Run tests:
```bash
python -m pytest accy_v2/model_lookup/tests/test_search.py -v
```

---

## Performance Considerations

- **Vocabulary loading**: Loaded once at search time (JSON parse ~1ms)
- **Classification loading**: Loaded once at search time (JSON parse ~1ms)
- **Database search**: CSV filtered by make/year, then by keywords (regex matching)
- **Semantic processing**: Translation (~0.1ms), Classification (~0.1ms), Scoring (~0.1ms)

**Total search time**: ~5-20ms depending on CSV size and database filtering

---

## Phase 7: Mitsubishi Model Lookup Enhancements (2026-08-26)

### Extended SearchResult with Vehicle Metadata

**New Fields (all Optional[str]):**
- `drivetrain: Optional[str]` — Drivetrain type from database (e.g., "FRONT_WHEEL_DRIVE", "ALL_WHEEL_DRIVE")
- `fuel_type: Optional[str]` — Fuel type classification (e.g., "phev", "electric", "hybrid")
- `color: Optional[str]` — Color keyword from config (e.g., "noir", "carbon") for output tagging
- `package: Optional[str]` — ADS numeric style ID from database (e.g., "481877")

**Extraction Logic:**
- `drivetrain`: Direct column read, no fallback (0 empty values in DB)
- `fuel_type`: 3-tier fallback (column → classified tokens → text classification)
- `color`: Config-driven lookup, output tagging only (not a matching gate)
- `package`: Direct column read, no fallback (0 empty values in Mitsubishi rows)

### Exact TRIM Token-Set Matching Layer

**Problem:** Searching for "GT" returns multiple candidates: "GT", "GT Premium", "GT NOIR"

**Solution:** New narrowing step applies after substring search:
1. Extract TRIM tokens from searched keywords
2. For each candidate DB row, extract its TRIM tokens
3. Keep only candidates with **exact TRIM token set match** (not superset, not subset)
4. Result: "GT" query → only matches plain GT trim (CO45-X), not GT Premium or GT NOIR

**Why Safe:** Strictly additive, never removes a match that would have succeeded before. Unaffected for 1-candidate searches (early return).

**New Helper Methods:**
- `_extract_trim_token_set(description, classification_config) → set`
- `_extract_row_metadata(row, classification_config, color_keywords) → tuple`

### Diagnostic Failure Categorization

**New Function:** `diagnose_search_failure(make, year, classified, csv_path) → Dict[str, str]`

Replaces generic "NOT_FOUND" with specific reasons, walking Year → Model → Trim hierarchy:
- `MANUFACTURER_NOT_IN_DB`
- `MODEL_YEAR_NOT_IN_DB` (includes available_years list)
- `MODEL_NAME_NOT_FOUND_FOR_YEAR` (includes available_models list)
- `TRIM_VARIANT_NOT_FOUND` (includes available_trims list)
- `AMBIGUOUS_TRIM_MULTIPLE_MODEL_NUMBERS`
- `SCORE_BELOW_THRESHOLD`

Integrated into `step4_5_model_enrichment.py` NOT_FOUND logging path. Zero performance impact (failure path only).

---

## Future Enhancements

1. **Database upgrade** → Replace CSV with SQLite or PostgreSQL
2. **Caching** → Cache vocabulary/classification in memory
3. **Fuzzy matching** → Add similarity scoring for typos
4. **Analytics** → Track search patterns, common queries
5. **API** → REST API wrapper for external systems

All changes can be made without affecting the public API due to modular structure.

---

## Summary

**The model_lookup module is now:**
- ✅ Modular (core / semantic separation)
- ✅ Maintainable (clear structure, easy to extend)
- ✅ Flexible (semantic processing optional)
- ✅ Production-ready (comprehensive tests, error handling)
- ✅ Senior-developer friendly (clean code, good docs)

**Clean public API:**
```python
from model_lookup import search, save_models, load_models, build_vocabulary, load_vocabulary
```

No need to know internal structure — just call the functions!

