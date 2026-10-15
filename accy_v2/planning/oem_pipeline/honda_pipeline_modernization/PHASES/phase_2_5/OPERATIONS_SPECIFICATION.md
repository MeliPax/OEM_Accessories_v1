# Phase 2.5: Honda-Specific Operations — Detailed Specification

**Phase:** 2.5  
**Date:** 2026-10-15  
**Type:** Technical Specification  

---

## Operation 1: normalize_unicode

### Purpose
Convert smart quotes, unicode dashes, and unicode spaces to ASCII equivalents.

### Problem Statement
Honda Excel data contains:
- Smart quotes: U+201C ("), U+201D (")  
- Unicode spaces: U+00A0 (non-breaking space)  
- Unicode dashes: U+2013 (–), U+2014 (—)  

These cause encoding issues in downstream tools and look inconsistent in output.

### Solution
Apply NFC unicode normalization, then explicit character replacement.

### Configuration
```yaml
operations:
  - name: normalize_unicode
    from_chars: ["'", "'", """, """, "…", "–", "—"]
    to_chars: ["'", "'", '"', '"', "...", "-", "-"]
    description: "Convert smart quotes and unicode to ASCII equivalents"
```

### Input/Output

| Character | Unicode | Input | Output |
|-----------|---------|-------|--------|
| Left single quote | U+2018 | ' | ' |
| Right single quote | U+2019 | ' | ' |
| Left double quote | U+201C | " | " |
| Right double quote | U+201D | " | " |
| Ellipsis | U+2026 | … | ... |
| En dash | U+2013 | – | - |
| Em dash | U+2014 | — | - |

### Examples

**Input:** `"Civic "Type R" (NH‐883P)"`  
**Output:** `"Civic "Type R" (NH-883P)"`

**Input:** `"SPORT Hybrid Package"`  (with U+00A0 non-breaking space)  
**Output:** `"SPORT Hybrid Package"` (with ASCII space)

### Applied To
- `part_number` (e.g., "480‐SP" → "480-SP")
- `description` (e.g., primary trim names)
- `description_fr` (French translations)
- `comments` (customer notes)

### Implementation Details
**File:** `step2_string_standardization.py`  
**Function:** `_normalize_unicode()`

**Algorithm:**
1. For each string column in DataFrame:
   - Apply `unicodedata.normalize('NFC', value)`  
     (Canonical Decomposition Composition)
   - For each from_char → to_char mapping:
     - Replace from_char with to_char (regex=False, literal match)
2. Return updated DataFrame

**Validation:**
- No smart quotes remain (check for U+201C, U+201D, U+2018, U+2019)
- No unicode dashes remain (check for U+2013, U+2014)
- No unicode spaces remain (check for U+00A0)

---

## Operation 2: remove_newlines

### Purpose
Remove literal newline characters (\n) from Excel multi-line cells.

### Problem Statement
Excel can store multi-line cells with literal \n characters:
- `"SPORT\nHybrid"` appears as:
  ```
  SPORT
  Hybrid
  ```
  But when exported/parsed, the \n is literal text, not a line break.

This breaks downstream parsing and creates inconsistent strings.

### Solution
1. Replace all \n with space
2. Collapse consecutive spaces into one
3. Trim leading/trailing whitespace

### Configuration
```yaml
operations:
  - name: remove_newlines
    replace_with: " "
    collapse_multiple_spaces: true
    description: "Strip literal \\n from descriptions (Excel multi-line cells)"
```

### Examples

**Input:**
```
"SPORT\nHybrid"
"Racing\nPackage\nPremium"
"Premium   Package"  (extra spaces)
```

**Output:**
```
"Sport Hybrid"
"Racing Package Premium"
"Premium Package"
```

### Applied To
- `description` (main product descriptions)
- `description_fr` (French descriptions)
- `comments` (customer notes)
- `comments_fr` (French notes)

### Implementation Details
**File:** `step2_string_standardization.py`  
**Function:** `_remove_newlines()`

**Algorithm:**
1. For each target column:
   - Replace `\n` with space: `str.replace(r'\n', ' ', regex=True)`
   - Collapse spaces: `str.replace(r'\s+', ' ', regex=True)`
   - Trim edges: `str.strip()`
2. Return updated DataFrame

**Regex Patterns:**
- Newline match: `r'\n'`
- Whitespace collapse: `r'\s+'`

---

## Operation 3: split_composite

### Purpose
Handle composite part numbers (e.g., "X or Y") by keeping the first option and noting the original.

### Problem Statement
Honda sometimes lists part numbers as alternatives:
- English: `"480-670-6545-SP or 480-670-6545-GB"`
- French: `"480-670-6545-SP ou 480-670-6545-GB"`

Part matching requires a single canonical part number, not alternatives.

### Solution
1. Detect composite part numbers (contain " or " or " ou ")
2. Split on the delimiter and keep first part (left-priority)
3. Append original composite note to comments field
4. Log to DQ for audit trail

### Configuration
```yaml
operations:
  - name: split_composite
    delimiter: " or "
    delimiter_fr: " ou "
    action: "keep_first_priority_left"
    note_field: "comments"
    description: "Handle 'part1 or part2' syntax (keep first, note in comments)"
```

### Examples

**Input:**
```
Part Number: "480-670-6545-SP or 480-670-6545-GB"
Comments: "Standard replacement"
```

**Output:**
```
Part Number: "480-670-6545-SP"
Comments: "Standard replacement | [Composite parts: 480-670-6545-SP or 480-670-6545-GB]"
```

**DQ Log Entry:**
```
rule_name: composite_part_number_split
issue_detail: "Original: '480-670-6545-SP or 480-670-6545-GB' → Primary: '480-670-6545-SP'"
```

### Applied To
- `part_number` only (not trim columns, not descriptions)

### Implementation Details
**File:** `step2_string_standardization.py`  
**Function:** `_split_composite_part_numbers()`

**Algorithm:**
1. For each row where `part_number` contains " or " or " ou ":
   - Save original value
   - Split on regex `r'\s+(or|ou)\s+'`
   - Keep first element: `parts[0].strip()`
   - Update `part_number` column
   - If comments field exists:
     - Append `[Composite parts: {original}]`
   - If comments field is null:
     - Create new entry: `[Composite parts: {original}]`
   - Log to DQ logger with composite_part_number_split rule
2. Return updated DataFrame

**Regex Pattern:** `r'\s+(or|ou)\s+'` — matches " or " or " ou " with flexible whitespace

**DQ Logging:**
```python
dq_logger.log_info(
    sheet_name=sheet_name,
    model_name=model_name,
    record_index=idx,
    rule_name="composite_part_number_split",
    issue_description="Composite part number detected and split",
    issue_detail=f"Original: '{original}' → Primary: '{primary}'"
)
```

---

## Operation 4: normalize_trim_markers

### Purpose
Map special characters and placeholder values to canonical trim applicability states.

### Problem Statement
Honda uses inconsistent markers for trim applicability:
- **Applicability indicators:** •, ✓
- **Conditional markers:** S (standard), T (tire change), E (exchange)
- **Placeholders:** 0, 0.0, "", "N/A" (not applicable, but sometimes used as "not applicable")

These need to be normalized to a consistent set of canonical states.

### Solution
Map all variations to canonical states:
- `"applicable"` — Accessory applies to this trim
- `"standard"` — Standard equipment (comes with trim)
- `"tire_change"` — Requires tire size change
- `"exchange"` — Exchange for same size as OE
- `null` — Not applicable / empty

### Configuration
```yaml
operations:
  - name: normalize_trim_markers
    mapping:
      "•": "applicable"           # Bullet
      "✓": "applicable"           # Checkmark
      "S": "standard"             # Standard equipment
      "T": "tire_change"          # Tire change
      "E": "exchange"             # Exchange same size
      "0": null                   # Placeholder empty
      "0.0": null                 # Placeholder empty
      "": null                    # Empty string
      "N/A": null                 # Not applicable
    description: "Map special characters and placeholders to canonical states"
```

### Input/Output Mapping

| Input | Output | Meaning |
|-------|--------|---------|
| `•` | `"applicable"` | Bullet symbol = applicable |
| `✓` | `"applicable"` | Checkmark = applicable |
| `S` | `"standard"` | Standard equipment |
| `T` | `"tire_change"` | Tire size change needed |
| `E` | `"exchange"` | Exchange for OE size |
| `0` | `null` | Placeholder = empty |
| `0.0` | `null` | Placeholder = empty |
| `""` | `null` | Empty string = empty |
| `"N/A"` | `null` | Not applicable = empty |

### Examples

**Input Row (Civic EX package):**
```
LX Column: "•"
EX Column: "•"
Sport Column: "0"
Touring Column: ""
SI Column: "N/A"
Type-R Column: "✓"
Standard Column: "S"
TireChange Column: "T"
Exchange Column: "E"
```

**Output Row:**
```
LX Column: "applicable"
EX Column: "applicable"
Sport Column: null
Touring Column: null
SI Column: null
Type-R Column: "applicable"
Standard Column: "standard"
TireChange Column: "tire_change"
Exchange Column: "exchange"
```

### Applied To
- **All trim columns** (LX, EX, Sport, Touring, SI, Type-R, etc.)
- One column per distinct trim level

### Implementation Details
**File:** `step2_string_standardization.py`  
**Function:** `_normalize_trim_markers()`

**Algorithm:**
1. Identify trim columns (all except core product/metadata columns)
2. For each trim column:
   - For each cell value:
     - Convert to string: `str(value).strip()`
     - Look up in mapping dict
     - If found: use mapped value
     - If not found: keep original value
     - If value is NaN/null: keep as null
3. Return updated DataFrame

**Core vs. Trim Column Distinction:**
```python
core_cols = {
    'model_name', 'model_year', 'part_number', 'description',
    'description_fr', 'dealer_net', 'list_price', 'frt',
    'installed_price', 'comments', 'comments_fr', 'application'
}
trim_cols = [col for col in df.columns if col not in core_cols]
```

---

## Helper Function: _extract_operation_params

### Purpose
Extract operation parameters from transformations.yaml for runtime use.

### Why Needed
Operations are defined in YAML, but implementation needs the parameters at runtime.
This function bridges the gap between config and code.

### Input
```yaml
transformations:
  columns:
    description:
      operations:
        - name: normalize_unicode
          from_chars: ["'", "'", """, """]
          to_chars: ["'", "'", '"', '"']
```

### Output
```python
{
  "'": "'",
  "'": "'",
  """: '"',
  """: '"'
}
```

### Special Handling

**For normalize_unicode:**
- Input: `from_chars` list + `to_chars` list
- Output: Dict mapping (from → to)
- Zips lists together: `dict(zip(from_chars, to_chars))`

**For normalize_trim_markers:**
- Input: `mapping` key in operation
- Output: The mapping dict directly
- Extracted with: `op.get("mapping", {})`

### Implementation
**File:** `step2_string_standardization.py`  
**Function:** `_extract_operation_params()`

```python
def _extract_operation_params(
    trans_config: dict,
    operation_name: str,
    param_key: str = None
) -> dict:
    """Extract and convert operation parameters from config."""
    
    columns = trans_config.get("columns", {})
    
    for col_name, col_config in columns.items():
        operations = col_config.get("operations", [])
        for op in operations:
            if op.get("name") == operation_name:
                # Special case: normalize_unicode
                if operation_name == "normalize_unicode":
                    from_chars = op.get("from_chars", [])
                    to_chars = op.get("to_chars", [])
                    if from_chars and to_chars and len(from_chars) == len(to_chars):
                        return dict(zip(from_chars, to_chars))
                    return {}
                
                # General case: extract specific parameter or all
                if param_key:
                    return op.get(param_key, {})
                else:
                    return {k: v for k, v in op.items() 
                           if k not in ["name", "description"]}
    
    return {}
```

---

## Summary Table

| Operation | Input Format | Output Format | Columns | Config Key |
|-----------|--------------|---------------|---------|------------|
| normalize_unicode | from_chars, to_chars lists | Dict mapping | description, comments, part_number | `from_chars`, `to_chars` |
| remove_newlines | replace_with string | Clean string | description, comments | `replace_with` |
| split_composite | delimiter string | Primary + comment | part_number | `delimiter`, `delimiter_fr` |
| normalize_trim_markers | mapping dict | Canonical state | All trim columns | `mapping` |

---

**Document:** Technical specification for Phase 2.5 operations.  
**Status:** Complete and ready for implementation.

