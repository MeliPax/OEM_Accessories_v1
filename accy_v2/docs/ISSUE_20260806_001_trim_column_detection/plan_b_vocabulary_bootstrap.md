# Plan B: Vocabulary Bootstrapping from Database

**Status:** Follow-up to Plan A  
**Dependencies:** Plan A complete + database with OEM data  
**Deliverables:**
- Vocabulary fetching from `db_vehicle_models.csv`
- Config fallback for resilience
- Hybrid strategy (DB + config)
- Bootstrap script to populate `fallback_trims`

---

## 1. Architecture Decision: Where Does Vocabulary Live?

**Three options:**

| Option | Pros | Cons | Recommendation |
|--------|------|------|-----------------|
| **Config-embedded** | Simple; static; versionable | Manual maintenance; duplication; stales as DB changes | ❌ Avoid |
| **DB-sourced (live)** | Single source of truth; auto-updated | Requires DB query at runtime; fails if DB is empty/missing | ⚠️ Risky alone |
| **Hybrid (DB + config fallback)** | Live + resilience; detects gaps | More code; reconciliation logic | ✅ **Recommended** |

**Decision: Implement Hybrid Strategy**

Try to fetch vocabulary from the live database first. If the DB is empty, unavailable, or has no rows for this OEM, fall back to a hardcoded `fallback_trims` list in config. This gives you:
- **Live updates:** When ADS data is added, vocabulary grows automatically.
- **Resilience:** If DB is missing/corrupted, fallback ensures the pipeline doesn't break.
- **Gap detection:** If DB + fallback both yield different results, you'll spot missing data.

---

## 2. Enhanced Config Structure

Update `enrichment.yaml` (Plan A's config):

```yaml
# accy_v2/oems/mitsubishi/config/enrichment.yaml

trim_detection:
  enabled: true
  confidence_threshold: 0.5
  ambiguity_threshold: 0.45
  
  scoring_rules:
    # ... header_keywords, data_density, data_shape as in Plan A ...
    
    vocabulary_overlap:
      enabled: true
      weight: 0.4
      
      # Hybrid strategy: try DB first, fall back to config
      source: "hybrid"  # Options: "database", "config", "hybrid"
      min_overlap_ratio: 0.1
      
      # Fallback hardcoded list (populated by Phase C bootstrap script)
      # Used if DB is empty, unavailable, or doesn't match this OEM
      fallback_trims:
        - ES
        - ES_S-AWC
        - LS
        - LS_S-AWC
        - XLS
        - XLS_S-AWC
        - PHEV
        # ... add all known trims from your landing files ...
        # Populated via bootstrap_trim_vocabulary.py script in Phase C
      
      # Optional: diagnostics
      # If true, logs when DB and fallback diverge (e.g., DB has [ES, LS] but fallback has [ES, LS, XLS])
      warn_on_vocabulary_mismatch: false
  
  filtering:
    # ... as in Plan A ...
    enabled: true
    strategy: "data_only"
```

---

## 3. Implement Vocabulary Fetching

Update `accy_v2/core/helpers/trim_column_detection.py`:

```python
# In the existing TrimColumnDetector class, replace the _fetch_vocabulary placeholder:

def _fetch_vocabulary(self, source: str) -> set:
    """
    Fetch trim vocabulary from source.
    
    Args:
        source: "database" (live DB only), "config" (fallback only),
                or "hybrid" (try DB, fall back to config)
    
    Returns:
        Set of known trim values (as uppercase strings for matching)
    """
    vocab = set()
    vocab_from_db = set()
    vocab_from_config = set()
    
    # Try database first (if requested)
    if source in ["database", "hybrid"]:
        try:
            vocab_from_db = self._fetch_from_database()
            if vocab_from_db:
                logger.debug(
                    f"Fetched {len(vocab_from_db)} trim values for {self.oem_name} from database"
                )
        except Exception as e:
            logger.warning(f"Failed to fetch vocabulary from database: {str(e)}")
    
    # Fall back to config (if DB didn't work or source == "config")
    if not vocab_from_db and source in ["config", "hybrid"]:
        try:
            vocab_from_config = self._fetch_from_config()
            if vocab_from_config:
                logger.debug(
                    f"Fetched {len(vocab_from_config)} trim values for {self.oem_name} from config fallback"
                )
        except Exception as e:
            logger.warning(f"Failed to fetch vocabulary from config: {str(e)}")
    
    # Combine and return
    vocab = vocab_from_db or vocab_from_config
    
    # Optional: warn if DB and config both exist but differ
    if vocab_from_db and vocab_from_config:
        if self.config.get("scoring_rules", {}).get("vocabulary_overlap", {}).get("warn_on_vocabulary_mismatch"):
            if vocab_from_db != vocab_from_config:
                missing_in_db = vocab_from_config - vocab_from_db
                extra_in_db = vocab_from_db - vocab_from_config
                logger.warning(
                    f"Vocabulary mismatch for {self.oem_name}:\n"
                    f"  In config but not DB: {missing_in_db}\n"
                    f"  In DB but not config: {extra_in_db}"
                )
    
    return vocab


def _fetch_from_database(self) -> set:
    """
    Query db_vehicle_models.csv for known trims (ModelNumber values) of this OEM.
    
    Returns:
        Set of trim/model-code values (uppercase), or empty set if DB is not found/empty
    
    Raises:
        Exception: If DB file is corrupted or CSV read fails
    """
    from accy_v2.model_lookup.models.manufacture_module import load_existing_csv
    from pathlib import Path
    
    # Construct path to database
    db_path = (
        Path(__file__).parent.parent.parent 
        / "model_lookup" / "db" / "db_vehicle_models.csv"
    )
    
    if not db_path.exists():
        logger.debug(f"Database file not found: {db_path}")
        return set()
    
    try:
        df = load_existing_csv(str(db_path))
    except Exception as e:
        logger.warning(f"Failed to load database CSV: {str(e)}")
        return set()
    
    if df.empty:
        logger.debug(f"Database is empty: {db_path}")
        return set()
    
    # Filter to this OEM (case-insensitive match on Manufacturer column)
    oem_upper = self.oem_name.upper()
    df_oem = df[df["Manufacturer"].str.upper() == oem_upper]
    
    if df_oem.empty:
        logger.debug(f"No rows for {self.oem_name} in database")
        return set()
    
    # Extract ModelNumber column (the OEM's trim/model code)
    # NOTE: Adjust column name if your DB schema uses a different name
    try:
        trims = set(
            df_oem["ModelNumber"]
            .dropna()
            .astype(str)
            .str.strip()
            .str.upper()
            .tolist()
        )
        
        # Remove empty strings
        trims.discard("")
        
        logger.debug(
            f"Extracted {len(trims)} unique trim values for {self.oem_name} from database"
        )
        return trims
    
    except KeyError:
        logger.warning(
            f"Column 'ModelNumber' not found in database. "
            f"Available columns: {list(df.columns)}"
        )
        return set()


def _fetch_from_config(self) -> set:
    """
    Fall back to hardcoded trims in enrichment.yaml.
    
    Returns:
        Set of fallback trim values (uppercase)
    """
    fallback_trims = (
        self.scoring_rules.get("vocabulary_overlap", {})
        .get("fallback_trims", [])
    )
    
    vocab = set(str(t).upper().strip() for t in fallback_trims if t)
    
    # Remove empty strings
    vocab.discard("")
    
    logger.debug(
        f"Loaded {len(vocab)} trim values for {self.oem_name} from config fallback"
    )
    return vocab
```

---

## 4. Vocabulary Scoring (Updated from Plan A)

The `_score_vocabulary_overlap` method in Plan A now calls the real `_fetch_vocabulary`:

```python
def _score_vocabulary_overlap(self, col_data: List) -> float:
    """
    0.0–1.0: what % of column values match known trim vocabulary?
    
    Now uses actual database/config vocabulary (Plan B implementation).
    """
    vocab_config = self.scoring_rules.get("vocabulary_overlap", {})
    source = vocab_config.get("source", "hybrid")
    
    # PLAN B: Fetch vocabulary from DB + config (real implementation)
    known_trims = self._fetch_vocabulary(source)
    
    if not known_trims:
        logger.debug(
            f"No vocabulary available for {self.oem_name} (source={source}); "
            f"skipping vocabulary overlap scoring"
        )
        return 0.5  # Neutral score (not confidence boost, not penalty)
    
    # Case-insensitive matching
    known_trims_upper = {str(t).upper() for t in known_trims}
    
    # Count matches in column
    matches = sum(
        1 for v in col_data
        if v and str(v).strip().upper() in known_trims_upper
    )
    total_non_empty = sum(1 for v in col_data if v and str(v).strip())
    
    if total_non_empty == 0:
        return 0.0  # All empty; can't validate
    
    # Calculate overlap ratio
    overlap_ratio = matches / total_non_empty
    min_ratio = vocab_config.get("min_overlap_ratio", 0.1)
    
    # Soft score: proportional to overlap, but only if >= min_ratio
    if overlap_ratio < min_ratio:
        logger.debug(
            f"Column overlap {overlap_ratio:.2f} below minimum {min_ratio:.2f}; "
            f"not scoring as trim column"
        )
        return 0.0
    
    return min(overlap_ratio, 1.0)
```

---

## 5. Bootstrap Script (Phase C)

One-time script to populate `fallback_trims` from existing landing files.

**File:** `scripts/bootstrap_trim_vocabulary.py`

```python
#!/usr/bin/env python3
"""
Bootstrap trim vocabulary for OEM config.

Scans all landing files for an OEM, extracts unique trim values,
and outputs a YAML snippet to add to enrichment.yaml.

Usage:
    python bootstrap_trim_vocabulary.py --oem mitsubishi
    python bootstrap_trim_vocabulary.py --oem hyundai --output ~/trim_vocab.yaml
"""

import sys
import argparse
import logging
from pathlib import Path
from collections import Counter

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from openpyxl import load_workbook
from accy_v2.core.helpers.trim_column_detection import TrimColumnDetector


def bootstrap_vocabulary(oem_name: str, landing_dir: Path = None) -> dict:
    """
    Scan landing files for an OEM and extract unique trim values.
    
    Args:
        oem_name: OEM name (e.g., "mitsubishi")
        landing_dir: Path to landing files directory (default: auto-detect)
    
    Returns:
        Dict with extracted trims and metadata
    """
    oem_lower = oem_name.lower()
    
    if landing_dir is None:
        # Auto-detect: look for accy_v2/oems/{oem}/landing/
        landing_dir = (
            Path(__file__).parent.parent
            / "accy_v2" / "oems" / oem_lower / "landing"
        )
    
    if not landing_dir.exists():
        logger.error(f"Landing directory not found: {landing_dir}")
        return {}
    
    logger.info(f"Scanning landing files in: {landing_dir}")
    
    # Collect all trim values from all sheets
    all_trims = Counter()
    files_processed = 0
    
    for excel_file in sorted(landing_dir.glob("*.xlsx")):
        logger.info(f"  Reading: {excel_file.name}")
        files_processed += 1
        
        try:
            wb = load_workbook(excel_file, data_only=True)
            
            for sheet_name in wb.sheetnames:
                if sheet_name.startswith("_"):
                    continue  # Skip meta sheets
                
                ws = wb[sheet_name]
                
                # Find trim column (use detector if possible, or fallback to heuristics)
                trim_col = _find_trim_column_heuristic(ws)
                
                if not trim_col:
                    logger.warning(f"    Sheet '{sheet_name}': Could not identify trim column; skipping")
                    continue
                
                # Extract trim values from this sheet
                trim_col_idx = list(ws.iter_cols(1, ws.max_column, 1, 1))[0]
                
                for row_idx, cell in enumerate(ws.iter_rows(min_row=2, max_row=ws.max_row), start=1):
                    if row_idx >= len(trim_col_idx):
                        break
                    
                    trim_cell = cell[trim_col_idx]
                    trim_value = trim_cell.value
                    
                    if trim_value and str(trim_value).strip():
                        trim_clean = str(trim_value).strip().upper()
                        all_trims[trim_clean] += 1
        
        except Exception as e:
            logger.warning(f"  Error reading {excel_file.name}: {str(e)}")
            continue
    
    if not files_processed:
        logger.error("No Excel files found in landing directory")
        return {}
    
    # Sort by frequency (most common first)
    sorted_trims = sorted(all_trims.items(), key=lambda x: -x[1])
    
    logger.info(f"\nExtracted {len(all_trims)} unique trim values:")
    for trim, count in sorted_trims:
        logger.info(f"  {trim:30s} {count:3d} occurrences")
    
    return {
        "oem_name": oem_name,
        "files_processed": files_processed,
        "unique_trims": len(all_trims),
        "trims": [trim for trim, _ in sorted_trims],
    }


def _find_trim_column_heuristic(ws) -> int:
    """
    Simple heuristic to find trim column (fallback if detector unavailable).
    
    Returns column index (0-based) or None.
    """
    keywords = ["trim", "level", "variant", "code", "grade", "spec"]
    
    for col_idx, cell in enumerate(ws.iter_rows(min_row=1, max_row=1)):
        header = cell[0].value
        if not header:
            continue
        
        header_lower = str(header).lower()
        for kw in keywords:
            if kw in header_lower:
                return col_idx
    
    return None


def generate_yaml_snippet(result: dict) -> str:
    """
    Generate YAML snippet to add to enrichment.yaml.
    """
    if not result or "trims" not in result:
        return ""
    
    yaml_lines = [
        "# Generated by bootstrap_trim_vocabulary.py",
        f"# OEM: {result['oem_name']}",
        f"# Unique trims found: {result['unique_trims']}",
        f"# Files scanned: {result['files_processed']}",
        "# Add this to enrichment.yaml under trim_detection.scoring_rules.vocabulary_overlap.fallback_trims:",
        "",
        "fallback_trims:",
    ]
    
    for trim in result["trims"]:
        yaml_lines.append(f"  - {trim}")
    
    return "\n".join(yaml_lines)


def main():
    parser = argparse.ArgumentParser(
        description="Bootstrap trim vocabulary from landing files"
    )
    parser.add_argument("--oem", required=True, help="OEM name (e.g., mitsubishi)")
    parser.add_argument("--landing", help="Path to landing directory (auto-detect if not specified)")
    parser.add_argument("--output", help="Output file for YAML snippet (print to console if not specified)")
    
    args = parser.parse_args()
    
    landing_dir = Path(args.landing) if args.landing else None
    result = bootstrap_vocabulary(args.oem, landing_dir)
    
    if not result:
        logger.error("Failed to bootstrap vocabulary")
        return 1
    
    yaml_snippet = generate_yaml_snippet(result)
    
    if args.output:
        output_path = Path(args.output)
        output_path.write_text(yaml_snippet)
        logger.info(f"\nYAML snippet written to: {output_path}")
    else:
        print("\n" + "=" * 70)
        print(yaml_snippet)
        print("=" * 70)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

**Usage:**

```bash
# Scan Mitsubishi landing files and print YAML to console
python scripts/bootstrap_trim_vocabulary.py --oem mitsubishi

# Scan and write to file
python scripts/bootstrap_trim_vocabulary.py --oem mitsubishi --output /tmp/mitsubishi_trims.yaml
```

**Output example:**
```yaml
# Generated by bootstrap_trim_vocabulary.py
# OEM: mitsubishi
# Unique trims found: 12
# Files scanned: 8
# Add this to enrichment.yaml under trim_detection.scoring_rules.vocabulary_overlap.fallback_trims:

fallback_trims:
  - ES
  - ES_S-AWC
  - LS
  - LS_S-AWC
  - XLS
  - XLS_S-AWC
  - PHEV
  - ECLIPSE_CROSS
  - OUTLANDER
  - RVR
  - MIRAGE
  - G4
```

Then manually copy the `fallback_trims` block into your `enrichment.yaml`.

---

## 6. Testing Plan B

Test the hybrid strategy:

```python
# accy_v2/tests/test_trim_column_detection_vocabulary.py

def test_fetch_vocabulary_database():
    """Should fetch trims from database if available."""
    config = {
        "trim_detection": {
            "scoring_rules": {
                "vocabulary_overlap": {
                    "source": "database",
                    "fallback_trims": ["FALLBACK_TRIM"],  # Should not be used
                }
            }
        }
    }
    
    detector = TrimColumnDetector(config, oem_name="Hyundai")
    
    # Mock database with Hyundai trims
    # (requires mocking load_existing_csv or using a test DB)
    vocab = detector._fetch_from_database()
    
    assert len(vocab) > 0
    assert "SEL" in vocab or "XLE" in vocab  # Expected Hyundai trims


def test_fetch_vocabulary_hybrid_fallback():
    """Hybrid: should use fallback if DB is empty."""
    config = {
        "trim_detection": {
            "scoring_rules": {
                "vocabulary_overlap": {
                    "source": "hybrid",
                    "fallback_trims": ["ES", "LS", "XLS"],
                }
            }
        }
    }
    
    detector = TrimColumnDetector(config, oem_name="Mitsubishi")
    
    # Mock empty DB (will fall back to config)
    vocab = detector._fetch_vocabulary("hybrid")
    
    # Should contain fallback trims
    assert "ES" in vocab
    assert "LS" in vocab
    assert "XLS" in vocab


def test_score_vocabulary_overlap_with_db():
    """Should score column high if values match known trims."""
    config = {
        "trim_detection": {
            "scoring_rules": {
                "vocabulary_overlap": {
                    "enabled": True,
                    "weight": 0.4,
                    "source": "config",
                    "min_overlap_ratio": 0.1,
                    "fallback_trims": ["ES", "LS", "XLS"],
                }
            }
        }
    }
    
    detector = TrimColumnDetector(config, oem_name="Mitsubishi")
    
    # Column with high trim match
    col_data = ["ES", "LS", "XLS", "ES_S-AWC", "LS_S-AWC"]
    score = detector._score_vocabulary_overlap(col_data)
    
    # 3/5 match (60%) >= min_overlap_ratio (10%), so score should be high
    assert score > 0.5
```

---

## 7. Integration Checklist

- [ ] Implement `_fetch_from_database()` in TrimColumnDetector
- [ ] Implement `_fetch_from_config()` in TrimColumnDetector
- [ ] Update `_fetch_vocabulary()` to use hybrid strategy
- [ ] Update `_score_vocabulary_overlap()` to use real vocabulary
- [ ] Add `fallback_trims` to `enrichment.yaml` (empty initially)
- [ ] Create bootstrap script `scripts/bootstrap_trim_vocabulary.py`
- [ ] Run bootstrap script for Mitsubishi: `python scripts/bootstrap_trim_vocabulary.py --oem mitsubishi`
- [ ] Copy output into `enrichment.yaml` under `fallback_trims`
- [ ] Test with Phase A integration (run step 1 on sample Mitsubishi file)
- [ ] Repeat for other OEMs (Hyundai, Mazda, etc.)

---

## Summary

**Phase B adds:**
1. ✅ Database vocabulary fetching via `_fetch_from_database()`
2. ✅ Config fallback via `_fetch_from_config()`
3. ✅ Hybrid strategy (try DB, fall back to config)
4. ✅ Bootstrap script to extract vocabulary from landing files
5. ✅ Updated scoring to use real vocabulary

**Phase B depends on:**
- Phase A complete and integrated
- `db_vehicle_models.csv` populated with at least one OEM (e.g., Hyundai from prior runs)
- Bootstrap script run once per OEM to populate `fallback_trims`

**When to proceed:**
- After Phase A passes integration tests
- After at least one OEM has data in `db_vehicle_models.csv`
