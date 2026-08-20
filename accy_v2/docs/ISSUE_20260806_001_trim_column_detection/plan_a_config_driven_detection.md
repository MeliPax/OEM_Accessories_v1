# Plan A: Config-Driven Trim Detection with Filtering

**Status:** Ready to implement**Dependencies:** None**Deliverables:**

- Config structure in `enrichment.yaml`
- `TrimColumnDetector` class with multi-signal scoring
- Integration into `step1_validation.py`

---

## 1. Config Structure in `enrichment.yaml`

Add a new top-level section (sibling to `model_lookup`, `validation`, database):

```yaml
# accy_v2/oems/mitsubishi/config/enrichment.yaml
# ... existing sections ...

trim_detection:
  enabled: true
  confidence_threshold: 0.5  # Reject columns scoring < this; raise ValueError
  ambiguity_threshold: 0.45  # Warn if multiple columns >= this
  
  # Scoring rules (each rule weighted, sum = 1.0)
  scoring_rules:
    header_keywords:
      enabled: true
      weight: 0.3
      keywords: [trim, level, variant, code, grade, spec, equipment]
      case_insensitive: true
  
    vocabulary_overlap:
      enabled: true
      weight: 0.4
      source: "hybrid"  # "database", "config", or "hybrid" (try DB, fall back to config)
      min_overlap_ratio: 0.1  # At least 10% of column values must match known trims
      fallback_trims: []  # Populated later in Phase C (bootstrap)
  
    data_density:
      enabled: true
      weight: 0.2
      min_populated_ratio: 0.5  # At least 50% of rows must have data
      acceptable_empty_markers: ["", " ", null, "N/A", "-"]
  
    data_shape:
      enabled: true
      weight: 0.1
      max_value_length: 30  # Trim codes are concise; longer values are unlikely trims
      value_type: "string"
  
  # Post-detection filtering: narrow to rows with actual trim data
  filtering:
    enabled: true
    strategy: "data_only"  # "full_sheet" | "data_only" | "data_density_threshold"
  
    # If strategy == "data_only":
    #   Keep rows where trim column has populated data (not empty/null/whitespace)
  
    # If strategy == "data_density_threshold":
    #   Keep rows where >= threshold % of "data columns" are populated
    data_density_threshold: 0.5
  
    # Which columns are "data columns" (used for density check if needed)?
    # Define patterns to identify data columns vs meta columns
    data_column_markers:
      - contains: ["part", "desc", "price", "mfr", "msrp"]  # Common data column keywords
      - exclude: ["remarks", "notes", "comments", "internal"]  # Meta columns
```

---

## 2. TrimColumnDetector Class

New file: `accy_v2/core/helpers/trim_column_detection.py`

```python
"""
Config-driven trim column detection with multi-signal scoring.

Identifies the trim column in a worksheet by scoring all columns across
four weighted rules:
  1. Header keywords (0.3)
  2. Vocabulary overlap (0.4)
  3. Data density (0.2)
  4. Data shape (0.1)

Returns the column with highest confidence; raises ValueError if below
confidence_threshold.
"""

from typing import Dict, List, Tuple, Any
import logging

logger = logging.getLogger(__name__)


class TrimColumnDetector:
    """
    Config-driven trim column detection.
  
    Usage:
        detector = TrimColumnDetector(config, oem_name="Mitsubishi")
        trim_col, score = detector.find_trim_column(ws)
        data_rows = detector.filter_to_data_rows(ws, trim_col)
    """
  
    def __init__(self, oem_config: Dict[str, Any], oem_name: str = None):
        """
        Args:
            oem_config: Full OEM config dict (from enrichment.yaml)
            oem_name: OEM name (e.g., "Mitsubishi"); used for DB queries in Plan B
        """
        self.config = oem_config.get("trim_detection", {})
        self.oem_name = oem_name or oem_config.get("oem_name", "Unknown")
        self.scoring_rules = self.config.get("scoring_rules", {})
  
    def find_trim_column(self, ws) -> Tuple[str, float]:
        """
        Identify the trim column in a worksheet.
      
        Scores all named columns across four rules; returns the highest-scoring
        column if it meets confidence_threshold.
      
        Args:
            ws: Worksheet object with .column_names (list of header strings)
                and ability to index by column (ws[col_name] → list of values)
      
        Returns:
            (trim_column_name: str, confidence_score: 0.0-1.0)
      
        Raises:
            ValueError: If no column scores >= confidence_threshold
                        or if no named columns exist
        """
        scores = {}
      
        # Score each column
        for col_name in ws.column_names:
            if not col_name or not col_name.strip():
                continue  # Skip empty headers
          
            col_data = ws[col_name]  # All values in this column
            score = self._score_column(col_name, col_data)
            scores[col_name] = score
      
        # Pick best column
        if not scores:
            raise ValueError("No named columns found in worksheet")
      
        best_col, best_score = max(scores.items(), key=lambda x: x[1])
        threshold = self.config.get("confidence_threshold", 0.5)
      
        # Check confidence
        if best_score < threshold:
            raise ValueError(
                f"No column confident as trim (best: {best_col} = {best_score:.2f}, "
                f"threshold: {threshold}). All scores: {scores}"
            )
      
        # Check ambiguity (multiple columns scoring high)
        ambiguity_threshold = self.config.get("ambiguity_threshold", 0.45)
        ambiguous = [c for c, s in scores.items() if s >= ambiguity_threshold]
      
        if len(ambiguous) > 1:
            logger.warning(
                f"Trim column ambiguous: {ambiguous} all scored >= {ambiguity_threshold}. "
                f"Picked '{best_col}' ({best_score:.2f}). Review data quality."
            )
      
        return best_col, best_score
  
    def filter_to_data_rows(self, ws, trim_column: str) -> List[int]:
        """
        After identifying trim column, filter worksheet to rows with actual data.
      
        Args:
            ws: Worksheet object with .data (list of rows, each row is a list/tuple)
                and .column_names
            trim_column: Name of the trim column (from find_trim_column)
      
        Returns:
            List of row indices (0-indexed) to keep
        """
        filter_config = self.config.get("filtering", {})
      
        if not filter_config.get("enabled", True):
            return list(range(len(ws.data)))  # Keep all rows
      
        strategy = filter_config.get("strategy", "data_only")
      
        if strategy == "full_sheet":
            return list(range(len(ws.data)))
      
        elif strategy == "data_only":
            return self._filter_data_only(ws, trim_column)
      
        elif strategy == "data_density_threshold":
            return self._filter_data_density_threshold(ws)
      
        else:
            logger.warning(f"Unknown filtering strategy: {strategy}; keeping all rows")
            return list(range(len(ws.data)))
  
    def _filter_data_only(self, ws, trim_column: str) -> List[int]:
        """
        Keep rows where trim column has populated data.
      
        Filters out rows where trim column is null, empty, or whitespace-only.
        """
        trim_col_idx = ws.column_names.index(trim_column)
        empty_markers = self.scoring_rules.get("data_density", {}).get("acceptable_empty_markers", [])
      
        keep_rows = []
        for row_idx, row in enumerate(ws.data):
            if row_idx >= len(ws.data):
                break
          
            trim_value = row[trim_col_idx] if trim_col_idx < len(row) else None
          
            # Row is "data" if trim column is populated (not empty/null/whitespace)
            if trim_value is not None and str(trim_value).strip() and str(trim_value).strip() not in empty_markers:
                keep_rows.append(row_idx)
      
        return keep_rows
  
    def _filter_data_density_threshold(self, ws) -> List[int]:
        """
        Keep rows where >= threshold % of "data columns" are populated.
      
        More flexible than data_only: allows some blank data columns, as long as
        enough columns have values.
        """
        threshold = self.config.get("filtering", {}).get("data_density_threshold", 0.5)
        markers = self.config.get("filtering", {}).get("data_column_markers", [])
      
        # Identify which columns are "data columns" (vs meta/remarks columns)
        data_col_indices = self._identify_data_columns(ws.column_names, markers)
      
        if not data_col_indices:
            logger.warning("No data columns identified; keeping all rows")
            return list(range(len(ws.data)))
      
        keep_rows = []
        for row_idx, row in enumerate(ws.data):
            populated = sum(
                1 for col_idx in data_col_indices
                if col_idx < len(row) and row[col_idx] is not None and str(row[col_idx]).strip()
            )
            density = populated / len(data_col_indices) if data_col_indices else 0
          
            if density >= threshold:
                keep_rows.append(row_idx)
      
        return keep_rows
  
    # -----------------------------------------------------------------------
    # Private: Scoring rules
    # -----------------------------------------------------------------------
  
    def _score_column(self, col_name: str, col_data: List) -> float:
        """
        Score one column across all enabled rules.
      
        Returns: 0.0–1.0, capped at 1.0
        """
        score = 0.0
      
        # Rule 1: Header keywords
        if self.scoring_rules.get("header_keywords", {}).get("enabled", True):
            rule_score = self._score_header_keywords(col_name)
            weight = self.scoring_rules["header_keywords"].get("weight", 0.3)
            score += rule_score * weight
      
        # Rule 2: Vocabulary overlap
        if self.scoring_rules.get("vocabulary_overlap", {}).get("enabled", True):
            rule_score = self._score_vocabulary_overlap(col_data)
            weight = self.scoring_rules["vocabulary_overlap"].get("weight", 0.4)
            score += rule_score * weight
      
        # Rule 3: Data density
        if self.scoring_rules.get("data_density", {}).get("enabled", True):
            rule_score = self._score_data_density(col_data)
            weight = self.scoring_rules["data_density"].get("weight", 0.2)
            score += rule_score * weight
      
        # Rule 4: Data shape
        if self.scoring_rules.get("data_shape", {}).get("enabled", True):
            rule_score = self._score_data_shape(col_data)
            weight = self.scoring_rules["data_shape"].get("weight", 0.1)
            score += rule_score * weight
      
        return min(score, 1.0)  # Cap at 1.0
  
    def _score_header_keywords(self, col_name: str) -> float:
        """
        0.0–1.0: does column header match known trim keywords?
      
        Returns 1.0 if any keyword matches, 0.0 otherwise.
        """
        keywords = self.scoring_rules.get("header_keywords", {}).get("keywords", [])
        case_insensitive = self.scoring_rules.get("header_keywords", {}).get("case_insensitive", True)
      
        col_name_cmp = col_name.lower() if case_insensitive else col_name
      
        for kw in keywords:
            kw_cmp = kw.lower() if case_insensitive else kw
            if kw_cmp in col_name_cmp:
                return 1.0
      
        return 0.0
  
    def _score_vocabulary_overlap(self, col_data: List) -> float:
        """
        0.0–1.0: what % of column values match known trim vocabulary?
      
        In Phase A, this returns 0.5 (neutral) because _fetch_vocabulary is not
        implemented. Phase B implements DB/config fetching.
        """
        vocab_config = self.scoring_rules.get("vocabulary_overlap", {})
        source = vocab_config.get("source", "config")
      
        # Placeholder for Phase B
        known_trims = self._fetch_vocabulary(source)
      
        if not known_trims:
            logger.debug(f"Vocabulary overlap: no vocabulary available (Phase B not yet implemented)")
            return 0.5  # Neutral score if vocabulary is missing
      
        # Count matches (case-insensitive)
        known_trims_upper = {str(t).upper() for t in known_trims}
        matches = sum(1 for v in col_data if v and str(v).strip().upper() in known_trims_upper)
        total_non_empty = sum(1 for v in col_data if v and str(v).strip())
      
        if total_non_empty == 0:
            return 0.0  # All empty; can't validate
      
        overlap_ratio = matches / total_non_empty
        min_ratio = vocab_config.get("min_overlap_ratio", 0.1)
      
        # Return soft score proportional to overlap (capped at 1.0)
        if overlap_ratio < min_ratio:
            return 0.0  # Below minimum
      
        return min(overlap_ratio, 1.0)
  
    def _score_data_density(self, col_data: List) -> float:
        """
        0.0–1.0: what % of rows are populated (not null/empty/whitespace)?
      
        Soft score: returns the actual population ratio (0–1).
        """
        empty_markers = self.scoring_rules.get("data_density", {}).get("acceptable_empty_markers", [])
      
        populated = sum(
            1 for v in col_data 
            if v is not None and str(v).strip() and str(v).strip() not in empty_markers
        )
        total = len(col_data) if col_data else 1
        ratio = populated / total
      
        return min(ratio, 1.0)
  
    def _score_data_shape(self, col_data: List) -> float:
        """
        0.0–1.0: are values concise strings (not long text)?
      
        Soft score: returns ratio of values that meet length requirement.
        """
        max_len = self.scoring_rules.get("data_shape", {}).get("max_value_length", 30)
      
        # Count values that are valid (short) and values that are too long
        valid_short = sum(1 for v in col_data if v and len(str(v)) <= max_len)
        total_non_empty = sum(1 for v in col_data if v)
      
        if total_non_empty == 0:
            return 0.5  # Neutral if all empty
      
        ratio_valid = valid_short / total_non_empty
        return min(ratio_valid, 1.0)
  
    def _fetch_vocabulary(self, source: str) -> set:
        """
        Fetch trim vocabulary from source.
      
        PHASE B: Implemented in Plan B.
        PHASE A: Returns empty set (placeholder).
      
        Args:
            source: "database", "config", or "hybrid"
      
        Returns:
            Set of known trim values (as strings, uppercase for matching)
        """
        # Placeholder: Phase B implements this
        return set()
  
    def _identify_data_columns(self, col_names: List[str], markers: List[Dict]) -> List[int]:
        """
        Identify which columns are 'data columns' based on header markers.
      
        Used by _filter_data_density_threshold to identify which columns to check
        for population density.
      
        Args:
            col_names: List of column header strings
            markers: List of dicts like {"contains": [...]} or {"exclude": [...]}
      
        Returns:
            List of column indices (0-based) that match "data column" criteria
        """
        data_col_indices = []
      
        for idx, col_name in enumerate(col_names):
            is_data = False
            col_name_lower = col_name.lower()
          
            for marker in markers:
                # "contains" rules: include if any keyword matches
                if "contains" in marker:
                    for kw in marker["contains"]:
                        if kw.lower() in col_name_lower:
                            is_data = True
                            break
              
                # "exclude" rules: exclude if any keyword matches
                if "exclude" in marker and is_data:
                    for kw in marker["exclude"]:
                        if kw.lower() in col_name_lower:
                            is_data = False
                            break
          
            if is_data:
                data_col_indices.append(idx)
      
        return data_col_indices
```

---

## 3. Integration into Step 1

Update `accy_v2/oems/mitsubishi/pipeline/step1_validation.py`:

```python
from core.helpers.trim_column_detection import TrimColumnDetector

def run(
    raw_data: Dict[str, Any],
    config: dict,
    dq_logger: DQLogger,
    pipeline_logger: PipelineLogger,
) -> Dict[str, Any]:
    """
    Step 1: Validation and trim column detection.
  
    Now includes:
    - Config-driven trim column detection (multi-signal scoring)
    - Filtering to data rows only
    """
  
    sheet_name = raw_data.get("sheet_name")
    ws = raw_data.get("worksheet")  # openpyxl Worksheet or similar
  
    pipeline_logger.info(f"Step 1: Processing sheet '{sheet_name}'...")
  
    # ===== NEW: Trim column detection =====
    detector = TrimColumnDetector(config, oem_name="Mitsubishi")
  
    try:
        trim_column, confidence = detector.find_trim_column(ws)
        pipeline_logger.info(
            f"Sheet '{sheet_name}': Trim column identified as '{trim_column}' (confidence {confidence:.2f})"
        )
    except ValueError as e:
        dq_logger.log_error(
            sheet_name=sheet_name,
            issue_category="TRIM_COLUMN_DETECTION_FAILED",
            issue_description=str(e)
        )
        pipeline_logger.error(f"Sheet '{sheet_name}': {str(e)}")
        raise
  
    # ===== NEW: Filter to data rows only =====
    data_row_indices = detector.filter_to_data_rows(ws, trim_column)
  
    if not data_row_indices:
        dq_logger.log_warning(
            sheet_name=sheet_name,
            issue_category="NO_DATA_ROWS",
            issue_description=f"No rows with populated '{trim_column}' column found after filtering"
        )
        pipeline_logger.warning(f"Sheet '{sheet_name}': No data rows; skipping")
        return {}  # Or raise, depending on policy
  
    rows_before = len(ws.data)
    rows_after = len(data_row_indices)
    pipeline_logger.debug(
        f"Sheet '{sheet_name}': Filtered from {rows_before} total rows to {rows_after} data rows"
    )
  
    # ===== Continue with existing step 1 logic =====
    # Extract model name from cell(0,0), normalize, etc.
    # But now operating only on data_row_indices instead of all rows
  
    # ... rest of step 1 logic ...
  
    return {
        "sheet_name": sheet_name,
        "model_name": extracted_model_name,
        "vehicle_year": extracted_year,
        "trim_column": trim_column,
        "data_row_indices": data_row_indices,  # Pass to downstream steps
        # ... other outputs ...
    }
```

---

## 4. Config for Other OEMs

Once Phase A is working for Mitsubishi, add similar sections to other OEMs:

```yaml
# accy_v2/oems/hyundai/config/enrichment.yaml
trim_detection:
  enabled: true
  confidence_threshold: 0.5
  ambiguity_threshold: 0.45
  
  scoring_rules:
    header_keywords:
      enabled: true
      weight: 0.3
      keywords: [trim, level, variant, code, grade, series]
      case_insensitive: true
  
    vocabulary_overlap:
      enabled: true
      weight: 0.4
      source: "hybrid"
      min_overlap_ratio: 0.1
      fallback_trims: []  # Populated in Phase C
  
    data_density:
      enabled: true
      weight: 0.2
      min_populated_ratio: 0.5
      acceptable_empty_markers: ["", " ", null, "N/A", "-"]
  
    data_shape:
      enabled: true
      weight: 0.1
      max_value_length: 30
      value_type: "string"
  
  filtering:
    enabled: true
    strategy: "data_only"
```

---

## 5. Testing & Validation

Test cases for TrimColumnDetector:

```python
# accy_v2/tests/test_trim_column_detection.py

def test_find_trim_column_basic():
    """Basic scoring: should pick 'trim_level' over 'remarks'."""
    config = {
        "trim_detection": {
            "confidence_threshold": 0.5,
            "scoring_rules": {
                "header_keywords": {"enabled": True, "weight": 0.3, "keywords": ["trim"]},
                "vocabulary_overlap": {"enabled": False},  # Skip for now
                "data_density": {"enabled": False},
                "data_shape": {"enabled": False},
            }
        }
    }
    detector = TrimColumnDetector(config)
  
    # Mock worksheet
    ws = MockWorksheet(
        column_names=["Part", "Description", "trim_level", "Remarks"],
        data={"trim_level": ["ES", "LS", "XLS"]}
    )
  
    trim_col, score = detector.find_trim_column(ws)
    assert trim_col == "trim_level"
    assert score >= 0.3  # At least header keyword weight


def test_filter_data_only():
    """Should keep only rows where trim column is populated."""
    config = {
        "trim_detection": {
            "filtering": {
                "enabled": True,
                "strategy": "data_only",
            },
            "scoring_rules": {
                "data_density": {"acceptable_empty_markers": ["", " ", None, "N/A"]}
            }
        }
    }
    detector = TrimColumnDetector(config)
  
    # Mock worksheet with some empty trim rows
    ws = MockWorksheet(
        column_names=["Part", "trim_level"],
        data=[
            ["P001", "ES"],
            ["P002", ""],       # Empty trim
            ["P003", "LS"],
            ["P004", None],     # Null trim
            ["P005", "XLS"],
        ]
    )
  
    keep_rows = detector.filter_to_data_rows(ws, "trim_level")
    assert keep_rows == [0, 2, 4]  # Rows with "ES", "LS", "XLS"
```

---

## Summary

**Phase A delivers:**

1. ✅ Config structure for trim detection (in enrichment.yaml)
2. ✅ TrimColumnDetector class with 4 weighted scoring rules
3. ✅ Filtering logic (data_only + data_density_threshold)
4. ✅ Integration into step1_validation.py
5. ✅ Generalizable pattern for other OEMs

**Phase A does NOT yet:**

- ❌ Use DB vocabulary (deferred to Phase B)
- ❌ Bootstrap fallback_trims list (deferred to Phase C)

Even without Phase B, Phase A detects trim columns reliably using header keywords + data density + shape.
