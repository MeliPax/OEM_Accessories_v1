# Phase 2: Header Normalization + Parent/Child Detection

**Date**: 2026-10-13
**Phase**: Phase 2 (Weeks 3–4)
**Status**: 🔄 READY
**Effort**: ~24 hours

---

## Overview

Phase 2 has two interconnected responsibilities:

1. **Header Normalization** — Standardize column names within each section (case-insensitive, handle variations)
2. **Parent/Child Detection** — Identify which records are parents (have complete prices) vs. children (inherit prices)

Both feed metadata that downstream steps use:

- **Phase 3** fills prices for children
- **Phase 4** performs EN/FR reconciliation
- **Phase 5** outputs raw_data sheet with record types

---

## Data Flow

```
Phase 1 Output:
  df (raw data, unchanged)
  metadata {
    "model_name", "vehicle_year", "section_structure", 
    "row_metrics_per_section"
  }

         ↓ Phase 2

Phase 2 Output:
  df (unchanged)
  metadata {
    + "normalized_headers"          {section_name: [header_names]}
    + "column_mapping"               {section_name: {col_idx: norm_name}}
    + "price_columns"                ["dealer_net", "list_price", "frt", "installed_price"]
    + "record_type_per_row"          {row_idx: type}
    + "parent_row_index"             {row_idx: parent_idx or None}
    + "record_type_counts"           {type: count}
  }
```

---

## Responsibility 1: Header Normalization

### Algorithm

```python
For each section:
  1. Extract header row (at section_bounds["header_row"])
  2. Extract raw column names from row
  3. Map raw names to normalized names using config
  4. Store mapping for Phase 3+ to use
```

### Implementation

```python
def _extract_header_row(df, section_bounds):
    """Extract the header row for a section."""
    header_row_idx = section_bounds.get("header_row")
    return df.iloc[header_row_idx]

def _extract_column_names(header_row, language="EN"):
    """Convert header row to normalized names."""
    # Convert to lowercase, strip whitespace
    # Replace NaN with "unnamed_N"

def _normalize_header_names(raw_names, config, language):
    """Map raw names to normalized names using config mappings."""
    # Use config["column_normalizations"] to match variations
    # part_number, description, dealer_net, list_price, frt, 
    # installed_price, comments, etc.
```

### Config Mappings (in detection.yaml)

```yaml
column_normalizations:
  part_number:
    - "part number"
    - "part#"
    - "part num"
  description:
    - "description"
    - "desc"
  dealer_net:
    - "dealer net"
    - "dealer cost"
  list_price:
    - "list price"
    - "list"
  frt:
    - "frt"
    - "f.r.t."
  installed_price:
    - "installed price"
    - "installed"
  comments:
    - "comments"
    - "notes"
```

---

## Responsibility 2: Parent/Child Detection

### Classification Rules

**For Non-Package Sections** (Wheels, Exterior, Interior, Electrical, Paint Pens):

- **`parent`**: Complete data record = BOTH product columns (part_number AND description) filled AND ALL price columns filled
- **`child`**: Incomplete data record = BOTH product columns filled AND ALL price columns EMPTY (no prices at all)
- **DEFECT (not classified)**: 
  - Missing product data (both part_number AND description empty) → flag `record_type_defect_no_product`
  - Partial prices (some prices filled, some empty) → flag `record_type_defect_partial_prices`
  - Missing trim applicability (no trim columns have data) → flag `record_type_defect_missing_trim`

**For Package Sections**:

- **`package_parent`**: Complete data record = (part_number OR description) filled AND ALL price columns filled
- **`package_child`**: Incomplete data record = product columns filled AND ALL price columns EMPTY (no prices at all)
- **DEFECT (not classified)**:
  - Missing product data (both part_number AND description empty) → flag `record_type_defect_no_product`
  - Partial prices (some prices filled, some empty) → flag `record_type_defect_partial_prices`

**Parent-Child Relationship**:
- Child row immediately follows parent; child inherits missing prices from that parent
- Multiple children can follow same parent (parent-child clusters)
- No inheritance chains (no grandparents; child inherits only from immediate preceding parent)

### Algorithm

```python
def _classify_record_type(row, section_name, is_package, normalized_headers, dq_logger):
    """Determine record type for a single row.
    
    Returns: "package_parent" | "package_child" | "parent" | "child" | None (defect)
    
    Parent (complete): ALL product columns filled + ALL price columns filled
    Child (incomplete): ALL product columns filled + ALL price columns EMPTY
    Defects (returns None, logs warning):
      - Missing product data
      - Partial prices (some filled, some empty)
    """
  
    # Check which columns have data
    has_part_number = check_column("part_number", row, normalized_headers)
    has_description = check_column("description", row, normalized_headers)
    has_all_prices = check_all_columns(["dealer_net", "list_price", "frt", 
                                        "installed_price"], row, normalized_headers)
    has_any_price = check_any_columns(["dealer_net", "list_price", "frt", 
                                        "installed_price"], row, normalized_headers)
  
    has_complete_product_np = has_part_number and has_description  # Non-package needs BOTH
    has_product_pkg = has_part_number or has_description              # Package needs ONE OR
  
    if is_package_section:
        # Package section: parent/child distinguished by price completeness
        
        # Defect: No product data
        if not has_product_pkg:
            dq_logger.log("record_type_defect_no_product", row_data=row)
            return None
        
        # Defect: Partial prices
        if has_any_price and not has_all_prices:
            dq_logger.log("record_type_defect_partial_prices", row_data=row)
            return None
        
        # Valid classifications
        if has_all_prices:
            return "package_parent"  # Complete: all prices + product
        elif not has_any_price:
            return "package_child"   # Incomplete: no prices, but has product
        
    else:
        # Non-package section: parent/child distinguished by price completeness
        # Non-package requires BOTH product columns (part_number AND description)
        
        # Defect: Missing product data (need BOTH)
        if not has_complete_product_np:
            dq_logger.log("record_type_defect_no_product", row_data=row)
            return None
        
        # Defect: Partial prices (some filled, some empty)
        if has_any_price and not has_all_prices:
            dq_logger.log("record_type_defect_partial_prices", row_data=row)
            return None
        
        # Valid classifications (has complete product data)
        if has_all_prices:
            return "parent"   # Complete: all product + all prices
        elif not has_any_price:
            return "child"    # Incomplete: all product + no prices (inherits from parent)
```

### Parent Index (First-Parent-Rule)

```python
def _build_parent_index(df, section_bounds, record_types, dq_logger):
    """For each child row, find its parent (most recent preceding parent).
    
    Returns: {row_idx: parent_row_idx or None}
    - If parent_index[row] = None → row is a parent (or defect/orphan)
    - If parent_index[row] = some_idx → row inherits from row some_idx
    """
  
    parent_index = {}
    current_parent = None
  
    for row_idx in range(section_start, section_end + 1):
        record_type = record_types[row_idx]
      
        # Parent types: set as current parent source
        if record_type in ("parent", "package_parent"):
            current_parent = row_idx
            parent_index[row_idx] = None  # This IS a parent
        
        # Child types: inherit from current parent
        elif record_type in ("child", "package_child"):
            if current_parent is None:
                # Defect: orphaned child (no parent to inherit from)
                dq_logger.log("orphaned_child_rule", row_idx=row_idx)
                parent_index[row_idx] = None  # Mark as orphan
            else:
                parent_index[row_idx] = current_parent  # Inherit from parent
        
        # Defect rows (None) and others: no parent relationship
        else:
            parent_index[row_idx] = None
  
    return parent_index
```

---

## Configuration Requirements

Phase 2 requires the following configuration (all in `accy_v2/oems/honda/config/schemas/detection.yaml`):

### 1. Column Categories (for classification)

```yaml
column_categories:
  product_columns:
    - "part_number"
    - "description"
  
  price_columns:
    - "dealer_net"
    - "list_price"
    - "frt"
    - "installed_price"
```

### 2. Section Classification (package vs non-package)

```yaml
section_classification:
  sections:
    - name: "Packages and Kits"
      is_package: true
    
    - name: "Wheels and Wheel Accessories"
      is_package: false
    
    - name: "Exterior"
      is_package: false
    
    - name: "Interior"
      is_package: false
    
    - name: "Electrical"
      is_package: false
    
    - name: "Paint Pens"
      is_package: false
```

### 3. Parent/Child Detection Rules

```yaml
parent_child_detection:
  package_parent_requirement:
    product_columns: "ANY"  # part_number OR description
    price_columns: "ALL"    # ALL prices filled
  
  package_child_requirement:
    product_columns: "ANY"
    price_columns: "NONE"   # ALL prices empty
  
  non_package_parent_requirement:
    product_columns: "BOTH"  # part_number AND description
    price_columns: "ALL"     # ALL prices filled
  
  non_package_child_requirement:
    product_columns: "BOTH"
    price_columns: "NONE"    # ALL prices empty
  
  defects:
    no_product: true
    partial_prices: true
    missing_trim: true
```

---

## Implementation Files

### Create: `accy_v2/oems/honda/pipeline/step2_header_normalization.py`

```python
def run(df, config, meta_data, dq_logger, logger) -> (DataFrame, Dict):
    """Phase 2: Header Normalization + Parent/Child Detection"""
  
    updated_meta = meta_data.copy()
    detection_config = config.get("step1_detection", {})
    language = meta_data.get("language", "EN")
    section_structure = meta_data.get("section_structure", {})
  
    normalized_headers = {}
    column_mapping = {}
    record_types = {}
    parent_index = {}
  
    # For each section
    for section_name, section_bounds in section_structure.items():
        # 1. Extract and normalize headers
        header_row = _extract_header_row(df, section_name, section_bounds)
        raw_names = _extract_column_names(header_row, language)
        norm_names = _normalize_header_names(raw_names, detection_config, language)
      
        normalized_headers[section_name] = list(norm_names.values())
        column_mapping[section_name] = norm_names
      
        # 2. Detect parent/child for all data rows
        is_package = "package" in section_name.lower()
        section_start = section_bounds.get("data_start_row")
        section_end = section_bounds.get("data_end_row")
      
        for row_idx in range(section_start, section_end + 1):
            row = df.iloc[row_idx]
            rtype = _classify_record_type(row, section_name, is_package, norm_names, dq_logger)
            record_types[row_idx] = rtype
      
        # 3. Build parent index
        section_parent_index = _build_parent_index(df, section_bounds, record_types, norm_names)
        parent_index.update(section_parent_index)
  
    # 4. Build parent index for all sections
    for section_name, section_bounds in section_structure.items():
        section_start = section_bounds.get("data_start_row")
        section_end = section_bounds.get("data_end_row")
        section_parent_index = _build_parent_index(
            df, section_start, section_end, record_types, dq_logger
        )
        parent_index.update(section_parent_index)
    
    # 5. Enrich metadata with normalization, parent/child, and price columns
    updated_meta["normalized_headers"] = normalized_headers
    updated_meta["column_mapping"] = column_mapping
    updated_meta["price_columns"] = ["dealer_net", "list_price", "frt", "installed_price"]  # Option B
    updated_meta["record_type_per_row"] = record_types
    updated_meta["parent_row_index"] = parent_index
    
    # 6. Compute record type counts for summary
    record_type_counts = {}
    for rtype in record_types.values():
        if rtype is None:
            rtype = "defect"
        record_type_counts[rtype] = record_type_counts.get(rtype, 0) + 1
    updated_meta["record_type_counts"] = record_type_counts
  
    return df, updated_meta
```

---

## DQ Rules for Phase 2

### Rule 1: `header_not_found_rule`

- **Severity**: WARNING
- **Condition**: Section has no recognizable header row
- **Action**: Log warning, use default column order, continue

### Rule 2: `column_name_mismatch_rule`

- **Severity**: INFO
- **Condition**: Raw column name doesn't match any expected header
- **Action**: Keep raw name, flag for manual review

### Rule 3: `orphaned_child_rule`

- **Severity**: WARNING
- **Condition**: Child record with no preceding parent in section
- **Action**: Log warning, mark in metadata

### Rule 4: `record_type_defect_partial_prices`

- **Severity**: WARNING
- **Condition**: Row has some prices filled and some empty (not all/none)
- **Action**: Do NOT classify; flag as data quality issue for manual review

### Rule 5: `record_type_defect_no_product`

- **Severity**: INFO
- **Condition**: Row has no product data (missing both part_number AND description)
- **Action**: Do NOT classify; flag as data quality issue for manual review

### Rule 6: `record_type_defect_missing_trim`

- **Severity**: INFO
- **Condition**: Row has product data but missing trim applicability (all trim columns empty)
- **Action**: Do NOT classify; flag as data quality issue for manual review

---

## Testing Strategy

### Unit Tests

```python
# Header extraction & normalization
test_extract_header_row_basic()
test_normalize_column_names_en()
test_normalize_column_names_fr()
test_normalize_unknown_columns()

# Parent/child classification - NON-PACKAGE
test_classify_non_package_parent()  # BOTH product + ALL prices
test_classify_non_package_child()   # BOTH product + NO prices
test_classify_non_package_defect_no_product()  # Missing product data
test_classify_non_package_defect_partial_prices()  # Some prices filled, some empty

# Parent/child classification - PACKAGE
test_classify_package_parent()  # (product OR product) + ALL prices
test_classify_package_child()   # product + NO prices
test_classify_package_defect_no_product()  # Missing product data
test_classify_package_defect_partial_prices()  # Some prices filled, some empty

# Parent index building & relationships
test_parent_index_first_parent_rule()  # Most recent parent rule
test_parent_index_multiple_parents()  # Consecutive parents handled correctly
test_parent_index_orphaned_child()  # Child before parent detected and logged

# Integration test
test_phase2_cvic5d()  # Full run on CVIC5D.xlsx
```

### Success Criteria

- ✅ All 6 sections have normalized headers
- ✅ All data rows classified with record_type
- ✅ Parent index built correctly
- ✅ DQ rules firing appropriately
- ✅ Test coverage ≥80%
- ✅ Passes on CVIC5D.xlsx EN/FR

---

## Design Clarifications (User Answers)

### Parent/Child Classification (Confirmed Q1, Q5)

**Non-Package Sections**:
- **Parent**: BOTH product columns (part_number AND description) filled + ALL price columns filled = complete record
- **Child**: BOTH product columns filled + ALL price columns EMPTY = incomplete record (inherits prices from parent)

**Package Sections**:
- **Parent**: (part_number OR description) filled + ALL price columns filled = complete record
- **Child**: product columns filled + ALL price columns EMPTY = incomplete record (inherits prices from parent)

**Parent-Child Relationship**:
- Child row immediately follows parent; inherits missing prices from that parent
- Multiple children can follow same parent (parent-child clusters)
- Orphaned children (child before any parent) = data defect → `orphaned_child_rule`
- No inheritance chains (child inherits only from most recent preceding parent)

### Column Index Mapping Strategy (Option B Chosen)
- **Phase 2 passes normalized column names** (not indices) to Phase 3
- Store in metadata: `price_columns = ["dealer_net", "list_price", "frt", "installed_price"]`
- Phase 3 uses these names to look up actual column indices dynamically
- **Benefit**: Robust to column reordering, self-documenting, follows accy_v2 patterns

### Section-Specific Rules (Design Decision)
- All 5 non-package sections (Wheels, Exterior, Interior, Electrical, Paint Pens) use **identical parent/child rules**
- Paint Pens is treated as a regular section (publishing rows handled by Phase 1, not special here)

### Data Defect Detection Strategy (Design Decision - Updated Q5)
- **Partial prices** (some filled, some empty) → **DO NOT CLASSIFY** → flag `record_type_defect_partial_prices`
- **Missing product data** (both part_number AND description empty) → **DO NOT CLASSIFY** → flag `record_type_defect_no_product`
- **Missing trim applicability** (no trim columns filled) → **DO NOT CLASSIFY** → flag `record_type_defect_missing_trim`
- These are data quality issues, not valid parent/child/single records
- Log defect flags for manual review and data cleanup

---

## Next Phase

**Phase 3** will use this metadata to:

1. Standardize data values (type coercion, trimming)
2. Fill prices for non-package child records using parent_row_index
3. Perform package rollup logic
4. Extract vehicle year (Step 3.5)
