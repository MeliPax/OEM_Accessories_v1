# Phase 2: Step 3 Standardization → Wide-Format with Parent/Child Resolved

**Objective:** Refactor Step 3 to apply col_mapping, forward-fill parent/child, enforce data types, normalize trim values, and output wide-format DataFrame ready for Step 4 melting.

**Status:** Design phase  
**Files affected:**
- `accy_v2/oems/honda/pipeline/step3_standardization.py` (main refactor)

---

## Current State

**Location:** `accy_v2/oems/honda/pipeline/step3_standardization.py`

**Current behavior:**
- Receives: working_df, config, meta_data, dq_logger, logger
- Returns: standardized_df (section-by-section)

**Current processing:**
- (Likely exists but needs review)

---

## Desired State

**New behavior:**
Step 3 receives col_mapping and valid_trim_cols from Step 2, then:
1. Apply col_mapping to rename/drop columns
2. Forward-fill parent/child pricing (children inherit from parents)
3. Enforce data types (prices to float, etc.)
4. Normalize trim values
5. Return single wide-format DataFrame (all sections merged, both languages separate)

**Input:**
```python
working_df: pd.DataFrame          # From Step 1
step2_result: Dict[str, Any]      # From Step 2
{
    "col_mapping": {0: None, 1: None, 2: "description", ...},
    "valid_trim_cols": ["LX", "EX", "Sport", "Touring"],
    "trim_validation_log": {}
}
config: Dict                       # Pipeline config
meta_data: Dict                    # Metadata from Steps 1-2
```

**Output:**
```python
pd.DataFrame  # Wide-format with:
# - Column names: description, part_number, prices, LX, EX, Sport, Touring, ...
# - One row per part (not melted)
# - Parent/child pricing resolved (children have prices)
# - Data types enforced (prices are float, not string)
# - Trim values normalized (whitespace stripped, markers preserved)
```

**Example output:**
```
    description  part_number  dealer_net  list_price   frt  installed_price      LX      EX    Sport  Touring
0   Exterior Pkg      25CIV-ENK     1200.00     1800.00  25.00         1825.00       •       •       •        •
1   Wheel Kit A      25CIV-WHL     800.00      1200.00  15.00         1215.00       •              •       
2   Interior Set     25CIV-INT     500.00       750.00  10.00          760.00                 •       
```

---

## Design: Apply col_mapping

### What is col_mapping application?

Use Step 2's col_mapping to rename columns and drop unwanted columns.

### Algorithm:

```python
def _apply_col_mapping(df, col_mapping, valid_trim_cols):
    """
    Apply col_mapping to rename/drop columns.
    
    1. Drop columns where col_mapping[idx] is None (except trim columns)
    2. Rename columns where col_mapping[idx] is a name
    3. Keep trim columns as-is (will have actual names like "LX", "EX")
    """
    # Columns to drop: those with None mapping AND not trim columns
    cols_to_drop = []
    rename_dict = {}
    
    for col_idx, canonical_name in col_mapping.items():
        # If mapped to a name: rename
        if canonical_name is not None:
            rename_dict[col_idx] = canonical_name
        # If mapped to None AND not a trim column: drop
        elif col_idx not in [9, 10, 11, 12, 13, 14, 15]:  # Not trim region
            cols_to_drop.append(col_idx)
    
    # Apply: drop, then rename
    df = df.drop(columns=cols_to_drop, errors="ignore")
    df = df.rename(columns=rename_dict)
    
    return df
```

### Expected outcome:

Before:
```
   0    1       2                3           4        5      6   7        8  9   10  11  12  13  14  15    16
0  NaN  NaN  'Exterior Pkg'  '25CIV-ENK'  '1200'  '1800'  '25' '1825'  'EN'  '•' '•' ... (empty)
```

After:
```
  description    part_number  dealer_net list_price frt installed_price  9   10  11  12  13  14  15   16
0 'Exterior Pkg' '25CIV-ENK'  '1200'     '1800'     '25' '1825'         '•' '•' ... (empty)
```

(Columns renamed, 0-1 dropped, trim columns renamed after lookup)

---

## Design: Forward-Fill Parent/Child

### What is forward-fill?

Child records inherit **pricing data** from their parent records.

- Parent: has description, part_number, **AND prices** (dealer_net, list_price, frt, installed_price)
- Child: has description, part_number, **but NO prices**
- After forward-fill: child row gets parent's prices copied

### Why forward-fill?

- Honda uses parent/child to group related products without repeating prices
- Example: Package parent has one price; child variants (colors, sizes) share that price
- After forward-fill, each record is complete and can be processed independently

### Algorithm:

```python
def _forward_fill_parent_pricing(df, meta_data):
    """
    For each child row, copy prices from its parent.
    
    Uses parent_row_index from meta_data to find parent of each child.
    """
    price_cols = ["dealer_net", "list_price", "frt", "installed_price"]
    parent_index = meta_data.get("parent_row_index", {})
    
    for child_idx, parent_idx in parent_index.items():
        if parent_idx is None:
            continue  # Row is a parent, not a child
        
        # Copy prices from parent to child
        for price_col in price_cols:
            if price_col in df.columns:
                child_val = df.loc[child_idx, price_col]
                # If child is missing price, inherit from parent
                if pd.isna(child_val) or str(child_val).strip() == "":
                    parent_val = df.loc[parent_idx, price_col]
                    if pd.notna(parent_val):
                        df.loc[child_idx, price_col] = parent_val
    
    return df
```

### Expected outcome:

Before:
```
Row 0 (parent):  part='25CIV-ENK', dealer_net=1200, list_price=1800, frt=25, installed_price=1825
Row 1 (child):   part='25CIV-ENK-RED', dealer_net=NaN, list_price=NaN, frt=NaN, installed_price=NaN
```

After:
```
Row 0 (parent):  part='25CIV-ENK', dealer_net=1200, list_price=1800, frt=25, installed_price=1825
Row 1 (child):   part='25CIV-ENK-RED', dealer_net=1200, list_price=1800, frt=25, installed_price=1825
```

---

## Design: Enforce Data Types

### What is data type enforcement?

Convert price columns from string → float, ensuring no invalid values.

### Algorithm:

```python
def _enforce_data_types(df, config):
    """
    Enforce data types per config (transformations.yaml).
    """
    col_data_types = config.get("col_data_type_dict", {})
    
    # Convert price columns to float
    price_cols = ["dealer_net", "list_price", "frt", "installed_price"]
    for col in price_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    
    # If conversion produces NaN where there should be values: raise error
    # (This catches invalid data in the input)
    
    return df
```

### Expected outcome:

Before:
```
dealer_net: ['1200', '800', '500']        # strings
list_price: ['1800.00', '1200.00', ...]   # strings
```

After:
```
dealer_net: [1200.0, 800.0, 500.0]        # floats
list_price: [1800.0, 1200.0, ...]         # floats
```

---

## Design: Normalize Trim Values

### What is trim value normalization?

Clean up trim applicability marker values (•, S, T, E, etc.) while preserving their meaning.

### Algorithm:

```python
def _normalize_trim_values(df, valid_trim_cols):
    """
    For each trim column:
    - Strip whitespace
    - Preserve markers: •, S, T, E, null, ""
    - Convert to standard form if needed
    
    Markers from transformations.yaml:
    • = "applicable"
    S = "standard"
    T = "tire_change"
    E = "exchange"
    0, 0.0, "", N/A = null
    """
    for col in valid_trim_cols:
        if col in df.columns:
            # Strip whitespace, preserve non-whitespace values
            df[col] = df[col].apply(
                lambda v: str(v).strip() if pd.notna(v) and str(v).strip() else None
            )
    
    return df
```

### Expected outcome:

Before:
```
LX: [' • ', '  ', None, 'E']
EX: ['S', ' S ', None, '  ']
Sport: ['T', None, '  ', '  ']
```

After:
```
LX: ['•', None, None, 'E']
EX: ['S', 'S', None, None]
Sport: ['T', None, None, None]
```

---

## Design: Validate Trim Applicability

### What is trim applicability validation?

Ensure each record has at least one non-empty trim column (the part applies to at least one trim).

### Algorithm:

```python
def _validate_trim_applicability(df, valid_trim_cols, group_key, dq_logger):
    """
    For each row, check that at least one trim column has a value.
    
    If a row has NO trim markers:
    - Log warning (part doesn't apply to any trim)
    - Exclude from output
    """
    valid_rows = []
    
    for idx, row in df.iterrows():
        # Check if any trim column has data
        has_any_trim = False
        for col in valid_trim_cols:
            if col in df.columns:
                val = row[col]
                if pd.notna(val) and str(val).strip():
                    has_any_trim = True
                    break
        
        if has_any_trim:
            valid_rows.append(idx)
        else:
            # Log warning: part has no applicable trims
            dq_logger.log_warning(
                sheet_name=group_key,
                rule_violated="trim_applicability_rule",
                issue_description=f"Part has no applicable trims"
            )
    
    return df.loc[valid_rows]
```

### Expected outcome:

Before:
```
part='Part A', LX=None, EX=None, Sport=None, Touring=None  (invalid)
part='Part B', LX='•', EX=None, Sport=None, Touring=None   (valid)
part='Part C', LX=None, EX=None, Sport=None, Touring=None  (invalid)
```

After:
```
part='Part B', LX='•', EX=None, Sport=None, Touring=None   (only valid row)
```

---

## Design: EN/FR Handling

### Orchestration Pattern

Step 3 is called **separately** for EN and FR:

```python
# In orchestrator or base pipeline:
standardized_en = run_step3_standardization(en_working_df, step2_result, config, meta_data_en, ...)
standardized_fr = run_step3_standardization(fr_working_df, step2_result, config, meta_data_fr, ...)

# Collect for Step 4
results_dict["EN"] = standardized_en
results_dict["FR"] = standardized_fr
```

### Step 3 doesn't combine EN+FR

- Step 3 processes each language independently
- Returns language-specific DataFrame
- Step 4 will merge EN and FR outputs if needed

### Example:

Step 3 called with EN sheet:
```
Input:  en_working_df with EN description values
Output: standardized_en with EN descriptions
```

Step 3 called with FR sheet:
```
Input:  fr_working_df with FR description values
Output: standardized_fr with FR descriptions
```

---

## Implementation Steps

### Step 1: Implement helper functions

- `_apply_col_mapping(df, col_mapping, valid_trim_cols)`
- `_forward_fill_parent_pricing(df, meta_data, price_cols)`
- `_enforce_data_types(df, config)`
- `_normalize_trim_values(df, valid_trim_cols)`
- `_validate_trim_applicability(df, valid_trim_cols, dq_logger)`

### Step 2: Update run() function

```python
def run(df, step2_result, config, meta_data, dq_logger, logger):
    col_mapping = step2_result["col_mapping"]
    valid_trim_cols = step2_result["valid_trim_cols"]
    
    # Apply transformations in order
    df = _apply_col_mapping(df, col_mapping, valid_trim_cols)
    df = _forward_fill_parent_pricing(df, meta_data)
    df = _enforce_data_types(df, config)
    df = _normalize_trim_values(df, valid_trim_cols)
    df = _validate_trim_applicability(df, valid_trim_cols, meta_data.get("group_key"), dq_logger)
    
    return df
```

### Step 3: Test with real data

- Process CVIC5D.xlsx EN sheet
- Verify col_mapping applied correctly
- Verify parent/child pricing forward-filled
- Verify prices are floats
- Verify trim values normalized
- Verify output ready for Step 4

---

## Testing Strategy

**Test scenarios:**

1. **col_mapping application:**
   - Verify columns 0-1 dropped
   - Verify columns 2-8 renamed to canonical names
   - Verify trim columns renamed from index to trim names

2. **Parent/child forward-fill:**
   - Verify children inherit parent prices
   - Verify parents keep their prices
   - Verify no price overwriting

3. **Data type enforcement:**
   - Verify price columns are float
   - Verify no invalid values left as NaN
   - Verify empty/null prices stay as NaN

4. **Trim value normalization:**
   - Verify whitespace stripped
   - Verify markers (•, S, T, E) preserved
   - Verify empty values become None

5. **Trim applicability validation:**
   - Verify rows with no trims excluded
   - Verify DQ warnings logged
   - Verify row count reduced appropriately

---

## Acceptance Criteria

- [ ] col_mapping applied: columns renamed, unwanted columns dropped
- [ ] Parent/child pricing forward-filled correctly
- [ ] Price columns converted to float
- [ ] Trim values normalized (whitespace stripped)
- [ ] Each record has ≥1 non-empty trim column
- [ ] Output is wide-format (not melted)
- [ ] Output ready for Step 4 melting
- [ ] All DQ logging working
- [ ] Tests pass with real Honda data (EN and FR)
