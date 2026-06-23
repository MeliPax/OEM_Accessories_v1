"""
Model Lookup Module - Vehicle Model Identification & Management

Clean, modular interface for searching and managing OEM vehicle models.

CORE FUNCTIONS:
  search()           : Search for vehicle models by keywords
  save_models()      : Save models to CSV database
  load_models()      : Load models from CSV database
  build_vocabulary() : Build/rebuild token vocabulary
  load_vocabulary()  : Load pre-built vocabulary

OPTIONAL SEMANTIC ENHANCEMENT:
When use_semantic=True (default), applies:
  - OEM-specific keyword translation (s-awc→awd, i-activ→awd, etc.)
  - Semantic classification (MODEL, TRIM, DRIVETRAIN, ENGINE_TYPE, etc.)
  - Weighted confidence scoring (0.0-1.0)
  - Validation gates (require MODEL, reject contradictions)

MODULE STRUCTURE:
  model_lookup/
  ├── core/                    - Core search and database operations
  │   ├── search.py           - Main search interface
  │   ├── database.py         - CSV I/O and validation
  │   └── vocabulary.py       - Vocabulary building and loading
  │
  ├── semantic/               - Optional semantic enhancement layer
  │   ├── search.py           - Semantic search wrapper
  │   ├── translator.py       - OEM-specific abbreviation normalization
  │   ├── classifier.py       - Semantic token classification
  │   └── scorer.py           - Confidence scoring
  │
  ├── configs/                - Auto-generated configuration files
  │   ├── {make}_translator.json        (hand-authored)
  │   └── {make}_classification.json    (auto-generated)
  │
  ├── db/                     - CSV database
  │   └── db_vehicle_models.csv
  │
  └── tests/                  - Test suite
      └── test_search.py

QUICK START:

  # Search with semantic processing (default)
  from model_lookup import search, SearchResult

  result = search(
      make="Mitsubishi",
      year=2026,
      keywords=["outlander", "phev", "gt"]
  )

  if result:
      print(f"Model: {result.model_number}")
      print(f"Match: {result.match}")
      print(f"Confidence: {result.confidence:.2f}")  # 0.0-1.0

  # Search without semantic processing
  result = search(
      make="Mitsubishi",
      year=2026,
      keywords=["outlander", "phev", "gt"],
      use_semantic=False  # Use basic AND-logic matching
  )

  # Manage database
  from model_lookup import save_models, load_models

  df_models = load_models()
  print(f"Total models in database: {len(df_models)}")

  import pandas as pd
  new_df = pd.DataFrame({...})
  result = save_models(new_df)
  if result["success"]:
      print(f"Saved {result['records_saved']} records")

  # Manage vocabulary
  from model_lookup import build_vocabulary, load_vocabulary

  # Auto-generated from CSV when saving models
  vocab = load_vocabulary("Mitsubishi")
  print(f"Mitsubishi vocabulary: {len(vocab)} tokens")

  # Manual rebuild if needed
  build_result = build_vocabulary("Mitsubishi")
  if build_result["saved"]:
      print("Vocabulary rebuilt")

DESIGN PRINCIPLES:
  ✓ Modular architecture (core / semantic separation)
  ✓ Optional semantic layer (backward compatible)
  ✓ Config-driven customization (no hardcoding)
  ✓ Clear separation of concerns
  ✓ Easy to maintain and extend
"""

from .core import (
    search,
    SearchResult,
    save_models,
    load_models,
    build_vocabulary,
    load_vocabulary,
)

__all__ = [
    "search",
    "SearchResult",
    "save_models",
    "load_models",
    "build_vocabulary",
    "load_vocabulary",
]
