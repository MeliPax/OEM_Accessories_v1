# Phase 1: Step 2 Header Normalization → Metadata Dict

**Objective:** Refactor Honda Step 2 to return metadata dict (col_mapping, valid_trim_cols) matching standard OEM pattern.

**Status:** Design phase  
**Files affected:**
- `accy_v2/oems/honda/pipeline/step2_header_normalization.py` (main refactor)
- `accy_v2/oems/honda/pipeline/orchestrator.py` (implement stub)

---

## Current State

**Location:** `accy_v2/oems/honda/pipeline/step2_header_normalization.py`

**Current behavior:**
```python
def run(df, config, meta_data, dq_logger, logger) -> Tuple[pd.DataFrame, Dict]:
    # ... section-by-section processing ...
    return df, updated_meta  # Returns tuple
```

**Current output in meta_data:**
- `normalized_headers`: dict of section → list of header names
- `column_mapping`: dict of section → dict of (col_idx → normalized_name)
- `record_type_per_row`: dict of row_idx → record type
- `parent_row_index`: dict of row_idx → parent_row_idx
- `record_type_counts`: dict of record_type → count

**Problem:** Returns tuple instead of dict; section-based column mapping instead of global mapping.

---

## Desired State

**New behavior:**
```python
def run(df, config, meta_data, dq_logger, logger) -> Dict[str, Any]:
    # ... extract headers and build global col_mapping ...
    return {
        "col_mapping": {...},
        "valid_trim_cols": [...],
        "trim_validation_log": {}
    }
```

**Output structure:**
```python
{
    "col_mapping": {
        0: None,              # Column 0 is empty
        1: None,              # Column 1 is fallback codes
        2: "description",     # Column 2 → description
        3: "part_number",     # Column 3 → part_number
        4: "dealer_net",      # Column 4 → dealer_net
        5: "list_price",      # Column 5 → list_price
        6: "frt",             # Column 6 → frt
        7: "installed_price", # Column 7 → installed_price
        8: "application",     # Column 8 → application
        9: None,              # Column 9 is trim (not mapped)
        10: None,             # Column 10 is trim (not mapped)
        11: None,             # Column 11 is trim (not mapped)
        12: None,             # Column 12 is trim (not mapped)
        13: None,             # Column 13 is trim (not mapped)
        14: None,             # Column 14 is trim (not mapped)
        15: None,             # Column 15 is trim (not mapped)
        16: None,             # Column 16 is comments or trim
    },
    "valid_trim_cols": ["LX", "EX", "Sport", "Touring", "SI", "Type-R"],
    "trim_validation_log": {}
}
```

**meta_data updated in-place (by reference):**
- `record_type_counts`: dict of record_type → count (parents, children, subsections, etc.)
- `parent_row_index`: dict of row_idx → parent_idx or None
- `record_types`: dict of row_idx → record_type

---

## Design: col_mapping

### What is col_mapping?

Maps numeric column indices (0-16) to their **canonical names** that Step 3 will use.

- Keys: 0 through 16 (all column indices in raw Honda data)
- Values: canonical name string (e.g., "description", "part_number") OR None (column to drop)

### How to build col_mapping?

**Algorithm:**
1. Extract header row from first section (headers are same across all sections)
2. For each column index (0-16):
   - Normalize the header value (lowercase, strip accents, remove punctuation)
   - Match against config's column definitions (upstream.yaml)
   - If matches a standard column (description, part_number, prices, application): use canonical name
   - If doesn't match any standard: set to None (will be dropped or used as-is)
3. Return the mapping dict

**Example processing:**
```
Column 0: "" (empty) → None
Column 1: "" (empty) → None
Column 2: "Description" → matches config → "description"
Column 3: "Part #" → matches config → "part_number"
Column 4: "Dealer Net" → matches config → "dealer_net"
...
Column 9: "LX" → doesn't match standard → None (this is a trim)
Column 10: "EX" → doesn't match standard → None (this is a trim)
...
```

### Why use numeric indices?

- Honda's 6 sections all have the same column structure (same headers in same order)
- Allows Step 3 to apply the mapping uniformly across all data rows
- Matches Hyundai pattern (col_mapping uses original column names, not indices)
- Numeric indices are stable even if header text varies slightly

---

## Design: valid_trim_cols

### What is valid_trim_cols?

List of **trim column names** that apply to this sheet (e.g., ["LX", "EX", "Sport", "Touring"]).

- These are the actual VALUES of the trim columns, extracted from the section headers
- Not "Trim_1", "Trim_2" like Hyundai
- Actual trim names: LX, EX, Sport, Touring, SI, Type-R, etc.

### How to extract valid_trim_cols?

**Algorithm:**
1. Extract header row from first section
2. For each column index (9-16, the trim region):
   - Get the raw header value (e.g., "LX", "EX", "Sport")
   - Normalize it (strip, lowercase for matching, but preserve original case)
   - If it looks like a trim name (matches pattern or isn't a standard column): add to list
3. Return the list of trim names

**Example:**
```
Column 9: "LX" → trim name
Column 10: "EX" → trim name
Column 11: "Sport" → trim name
Column 12: "Touring" → trim name
Column 13: "SI" → trim name
Column 14: "Type-R" → trim name
Column 15: "" (empty) → skip
Column 16: "Comments" → not a trim
```

Result: `["LX", "EX", "Sport", "Touring", "SI", "Type-R"]`

---

## Design: Parent/Child Metadata

### What metadata to update?

**In meta_data (updated in-place by Step 2):**

```python
meta_data.update({
    "record_type_counts": {
        "parent": 80,
        "child": 6,
        "package_parent": 9,
        "subsection_label": 33,
    },
    "parent_row_index": {
        2: 0,      # Row 2's parent is row 0
        5: 3,      # Row 5's parent is row 3
        ...
    },
    "record_types": {
        0: "parent",
        1: None,  # Empty row, skip
        2: "child",
        3: "package_parent",
        ...
    }
})
```

### Reuse existing logic

The current `step2_header_normalization.py` already computes this! Functions to keep:
- `_classify_record_type()` - determines if row is parent/child/subsection
- `_build_parent_index()` - maps children to parents
- `_fill_part_numbers_from_fallback()` - fills missing part numbers

**What to change:**
- Keep all the classification logic as-is
- Just don't return it in the dataframe; put it in meta_data
- Return only the metadata dict

---

## Implementation Steps

### Step 1: Extract col_mapping building logic

**Create helper function:**
```python
def _build_col_mapping(df, config, language="EN") -> Dict[int, Optional[str]]:
    """
    Build global col_mapping from first section's header row.
    
    Returns:
        {col_idx: canonical_name or None}
    """
    # Extract header from first section
    # Use config's upstream.yaml to match columns
    # Build mapping for all 17 columns
```

**Leverage existing code:**
- `_extract_header_row()` - already extracts header row
- `_extract_column_names()` - already gets raw names
- `_normalize_header_names()` - already matches to canonical names

### Step 2: Extract valid_trim_cols building logic

**Create helper function:**
```python
def _extract_valid_trim_cols(col_mapping, header_row) -> List[str]:
    """
    Extract list of trim column names from header row.
    
    Trim columns are those not mapped to standard names.
    Extract the actual values (e.g., "LX", "EX") from header.
    
    Returns:
        ["LX", "EX", "Sport", "Touring", "SI", "Type-R"]
    """
    # For each index where col_mapping[i] is None
    # If index is in trim region (9-16) and has a value
    # Add that value to trim list
```

### Step 3: Change return type and orchestrator

**Modify `step2_header_normalization.run()`:**
```python
def run(df, config, meta_data, dq_logger, logger) -> Dict[str, Any]:
    # ... existing parent/child classification logic ...
    
    # Build col_mapping
    col_mapping = _build_col_mapping(df, config, meta_data.get("language", "EN"))
    
    # Extract valid trim columns
    valid_trim_cols = _extract_valid_trim_cols(col_mapping, header_row)
    
    # Update meta_data in-place with parent/child info
    meta_data.update({
        "record_type_counts": record_type_counts,
        "parent_row_index": parent_index,
        "record_types": record_types
    })
    
    # Return metadata dict
    return {
        "col_mapping": col_mapping,
        "valid_trim_cols": valid_trim_cols,
        "trim_validation_log": {}
    }
```

**Update orchestrator stub:**
```python
def run_step2_header_normalization(self, working_df, config, meta_data, dq_logger, pipeline_logger):
    return step2_header_normalization.run(working_df, config, meta_data, dq_logger, pipeline_logger)
```

---

## Testing Strategy

**Test with real Honda data (CVIC5D.xlsx EN sheet):**

1. **col_mapping correctness:**
   - Check that columns 0-1 map to None
   - Check that columns 2-8 map to correct canonical names
   - Check that columns 9-16 are None or trim names

2. **valid_trim_cols correctness:**
   - Verify list contains expected trim names (LX, EX, Sport, Touring, SI, Type-R)
   - Verify no duplicate trim names
   - Verify trim names are actual header values, not indices

3. **meta_data updates:**
   - Verify record_type_counts has all record types (parent, child, package_parent, subsection_label)
   - Verify parent_row_index maps children to valid parent rows
   - Verify record_types dict covers all data rows

4. **Base pipeline integration:**
   - Verify Step 3 can consume the col_mapping dict
   - Verify Step 3 uses valid_trim_cols correctly
   - Verify meta_data is passed through intact

---

## Rollback Plan

If Phase 1 fails:
- Revert `step2_header_normalization.py` to return Tuple (can do both for backward compat)
- Keep orchestrator unchanged
- No data changes, so safe to revert

---

## Acceptance Criteria

- [ ] Step 2 returns Dict[str, Any] with col_mapping, valid_trim_cols, trim_validation_log
- [ ] col_mapping is Dict[int, Optional[str]] with 17 entries
- [ ] valid_trim_cols is List[str] with actual trim names
- [ ] meta_data updated in-place with record_type_counts, parent_row_index, record_types
- [ ] Orchestrator calls step2_header_normalization.run() and returns result
- [ ] All tests pass with real Honda data
