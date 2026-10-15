# Honda Transformation Configuration

**Version:** 2.0  
**Last Updated:** 2026-10-15  
**Status:** ✅ Complete

## Overview

Honda data transformations are defined in a **config-driven architecture** that follows the established pattern used across all OEMs (Hyundai, Genesis, Mazda, Mitsubishi).

### Key Files

| File | Location | Purpose |
|------|----------|---------|
| `transformations.yaml` | `config/` | **Primary:** Per-column transformation pipelines |
| `translator.yaml` | `model_lookup/configs/honda/` | Abbreviation mappings (HEV→Hybrid, etc.) |
| `step2_string_standardization.py` | `pipeline/` | **Implementation:** Executes Honda-specific operations |

---

## transformations.yaml Structure

### File Organization

```yaml
columns:
  ColumnName:
    operations:
      - name: operation_name
        param1: value1
        param2: value2
        description: "What this operation does"
    validation:
      nullable: true/false
      pattern: "regex"
      allowed_values: [...]

global:
  missing_value_strategy:
    empty_string: "treat_as_null"
    "N/A": "treat_as_null"
  log_transformations: true
  unicode_normalization:
    enabled: true
    normalize_form: "NFC"
  error_handling:
    type_coercion_errors: "raise"
    range_validation_errors: "log_warning"
```

### Column Categories

#### 1. **Metadata Columns**
- `model_name` — Vehicle model (Civic Hatch, Civic Type R, etc.)
- `model_year` — Model year (2020-2100)

Operations: `trim_whitespace`, `standardize_case`

#### 2. **Part Identification**
- `part_number` — OEM part number (e.g., 25CIV5-ARO-PK)

Operations:
- **normalize_unicode** — Smart quotes → ASCII
- **split_composite** — "X or Y" → X (keep first, note in comments)
- `uppercase` — Ensure uppercase
- `trim_whitespace`

#### 3. **Description** (Main Cleaning)
- `description` — English description
- `description_fr` — French description

Operations (in order):
1. **normalize_unicode** — Smart quotes, dashes → ASCII
2. **remove_newlines** — Literal \n → space (Excel multi-line cells)
3. `trim_whitespace` — Leading/trailing spaces
4. `standardize_case` → Title Case
5. `standardize_abbreviations` — HEV→Hybrid (references translator.yaml)
6. `deduplicate_words` — "Hybrid Hybrid" → "Hybrid"
7. `remove_markup` — Remove "(EN)", "(FR)" tags

#### 4. **Pricing Columns**
- `dealer_net`, `list_price`, `frt`, `installed_price`

Operations: `convert_to_float`, `remove_currency_symbols`, `validate_range`

#### 5. **Trim Applicability**
- `trim_columns` — All trim-specific columns (e.g., LX, EX, Sport, etc.)

Operations:
- **normalize_trim_markers** → Canonical states:
  - `•`, `✓` → "applicable"
  - `S` → "standard"
  - `T` → "tire_change"
  - `E` → "exchange"
  - `0`, `0.0`, `""`, `"N/A"` → null
- `trim_whitespace`

#### 6. **Comments**
- `comments` — English notes
- `comments_fr` — French notes

Operations:
- **normalize_unicode** — Fix smart quotes
- **remove_newlines** — Handle multi-line cells
- `normalize_whitespace` — Collapse spaces
- `trim_whitespace`

---

## Honda-Specific Operations

### 1. normalize_unicode

**Purpose:** Convert smart quotes, unicode dashes, and unicode spaces to ASCII

**Config Structure:**
```yaml
operations:
  - name: normalize_unicode
    from_chars: ["'", "'", """, """, "…", "–", "—"]
    to_chars: ["'", "'", '"', '"', "...", "-", "-"]
```

**Implementation:** `step2_string_standardization.py:_normalize_unicode()`

**Input Examples:**
- `"Platinum White Pearl (NH‐883P)"` (unicode dash U+2010)
- `"Civic "Type R""` (smart quotes U+201C, U+201D)

**Output:**
- `"Platinum White Pearl (NH-883P)"` (ASCII dash)
- `"Civic "Type R""` (ASCII quotes)

---

### 2. remove_newlines

**Purpose:** Remove literal `\n` from Excel multi-line cells

**Config Structure:**
```yaml
operations:
  - name: remove_newlines
    replace_with: " "
    collapse_multiple_spaces: true
```

**Implementation:** `step2_string_standardization.py:_remove_newlines()`

**Input:**
```
"SPORT\nHybrid"  (literal newline in Excel cell)
```

**Output:**
```
"Sport Hybrid"  (space replaces \n, case normalized)
```

---

### 3. split_composite

**Purpose:** Handle composite part numbers like "X or Y" (keep X, note original in comments)

**Config Structure:**
```yaml
operations:
  - name: split_composite
    delimiter: " or "
    delimiter_fr: " ou "
    action: "keep_first_priority_left"
    note_field: "comments"
```

**Implementation:** `step2_string_standardization.py:_split_composite_part_numbers()`

**Input:**
```
Part Number: "480-670-6545-SP or 480-670-6545-GB"
Comments: "Standard replacement"
```

**Output:**
```
Part Number: "480-670-6545-SP"
Comments: "Standard replacement | [Composite parts: 480-670-6545-SP or 480-670-6545-GB]"
DQ Log: "Composite part number split: original → primary"
```

---

### 4. normalize_trim_markers

**Purpose:** Map special characters and placeholders to canonical trim applicability states

**Config Structure:**
```yaml
operations:
  - name: normalize_trim_markers
    mapping:
      "•": "applicable"
      "✓": "applicable"
      "S": "standard"
      "T": "tire_change"
      "E": "exchange"
      "0": null
      "0.0": null
      "": null
      "N/A": null
```

**Implementation:** `step2_string_standardization.py:_normalize_trim_markers()`

**Mapping Logic:**

| Input | Output | Meaning |
|-------|--------|---------|
| `•` | `applicable` | Bullet symbol = applicable |
| `✓` | `applicable` | Checkmark = applicable |
| `S` | `standard` | Standard equipment |
| `T` | `tire_change` | Tire size change |
| `E` | `exchange` | Exchange (same size as OE) |
| `0`, `0.0` | `null` | Placeholder = empty |
| `""` | `null` | Empty string = empty |
| `N/A` | `null` | Not applicable = empty |

---

## translator.yaml (Abbreviation Mappings)

**Location:** `accy_v2/model_lookup/configs/honda/translator.yaml`

**Purpose:** Define how abbreviations in trim/description text are normalized

**Structure:**
```yaml
make: Honda
version: '1.0'
categories:
  trim_levels:
    lx: luxury
    ex: executive
    sport: sport
    touring: touring
    pkg: package
  fuel_drivetrain:
    hybrid: hybrid
    hev: hybrid
    ev: electric
    awd: all-wheel drive
  accessories:
    tech: technology
    camera: camera
```

**How It's Used:**
1. Config loader reads `translator.yaml`
2. `standardize_abbreviations` operation references it
3. During step3 (standardization), abbreviations are replaced before classification
4. Example: "HEV Sport" → "Hybrid Sport"

---

## Implementation Details

### step2_string_standardization.py

**Location:** `accy_v2/oems/honda/pipeline/step2_string_standardization.py`

**Runs:** Between Step 2 (Header Normalization) and Step 3 (Standardization)

**Function Signature:**
```python
def run(
    working_df: pd.DataFrame,
    config: dict,          # From ModularConfigLoader.load_all()
    meta_data: Dict,
    dq_logger: DQLogger,
    pipeline_logger: PipelineLogger,
) -> pd.DataFrame:
```

**Config Flow:**
```
transformations.yaml (config file)
      ↓ (loaded by ModularConfigLoader)
config["transformations"]
      ↓ (step2 reads from this key)
step2_string_standardization.run()
      ↓ (calls helpers)
_normalize_unicode()
_remove_newlines()
_split_composite_part_numbers()
_normalize_trim_markers()
```

**Helper Function: _extract_operation_params()**

Extracts operation parameters from the transformations config:

```python
_extract_operation_params(
    trans_config,
    operation_name: str,      # e.g., "normalize_unicode"
    param_key: str = None     # e.g., "mapping" for trim markers
)
```

**Special Handling:**
- `normalize_unicode`: Converts `from_chars`/`to_chars` lists → mapping dict
- `normalize_trim_markers`: Extracts the `mapping` parameter directly

---

## Data Flow: Before → After

### Example 1: Description with Unicode Issues

**Before (Raw Excel):**
```
"Aero Kit "Premium Package""  (smart quotes U+201C, U+201D)
"SPORT\nHybrid"              (literal newline)
```

**Step 2.5 (String Standardization):**
1. normalize_unicode: "" → "
2. remove_newlines: \n → space
3. trim_whitespace: Remove extra spaces
4. standardize_case: Title case

**After:**
```
"Aero Kit "Premium Package""  (ASCII quotes)
"Sport Hybrid"                (single line, title case)
```

---

### Example 2: Composite Part Numbers

**Before:**
```
Part Number: "480-670-6545-SP or 480-670-6545-GB"
Comments: null
Trim Columns: (LX, EX, Sport, Touring) → "•", "•", "0", "0"
```

**Step 2.5:**
1. split_composite: Keep first part, note in comments
2. normalize_trim_markers: Map • → applicable, 0 → null

**After:**
```
Part Number: "480-670-6545-SP"
Comments: "[Composite parts: 480-670-6545-SP or 480-670-6545-GB]"
Trim Columns: LX→"applicable", EX→"applicable", Sport→null, Touring→null
DQ Log: composite_part_number_split entry created
```

---

## Configuration Rules

### Global Settings

All configured in `transformations.yaml` → `global` section:

1. **missing_value_strategy** — How to treat missing/placeholder values
   - `empty_string: "treat_as_null"`
   - `"N/A": "treat_as_null"`
   - etc.

2. **log_transformations** — Enable/disable transformation logging
   - Default: `true`
   - Used for audit trail and debugging

3. **unicode_normalization** — Unicode handling
   - Form: `"NFC"` (Canonical Decomposition)
   - Ensures consistent matching

4. **error_handling** — Strategy for different error types
   - `type_coercion_errors: "raise"` — Fail on type errors
   - `range_validation_errors: "log_warning"` — Log but continue

---

## Validation Rules

Each column can have validation rules applied AFTER transformations:

```yaml
validation:
  nullable: true/false           # Can this column be empty?
  pattern: "^[A-Z0-9-]+$"        # Regex pattern match
  minimum_length: 5              # Min character count
  allowed_values: [...]          # Restricted set of values
  minimum_length: 3
```

**Example:** `part_number`
```yaml
validation:
  nullable: false
  pattern: "^[A-Z0-9\\-]+$"      # Only uppercase, numbers, hyphens
  minimum_length: 3              # At least 3 characters
```

---

## Testing & Verification

### Unit Tests

For each Honda-specific operation:
- `test_normalize_unicode.py` — Smart quotes, unicode spaces, dashes
- `test_remove_newlines.py` — Literal \n handling, space collapse
- `test_split_composite.py` — "X or Y" splitting, comment appending
- `test_normalize_trim_markers.py` — All marker mappings

### Integration Test

Run full pipeline on actual Honda data (`data/landing_zone/honda/may_2026/CVIC5D.xlsx`):
1. Verify no smart quotes remain
2. Verify no literal newlines in output
3. Verify composite parts properly split
4. Verify trim markers normalized to canonical states
5. Check DQ logs for expected entries

---

## Future Enhancements

### Unified Transformation Registry

Move all transformation operations (standard + Honda-specific) to a central registry:
- `accy_v2/config/transformations/operations_registry.yaml`
- Each OEM references shared operations + its own
- Reduces duplication, improves maintainability

**Current Status:** Documented in research (not yet implemented)

### Support for Additional OEMs

The Honda config pattern can be extended to other OEMs:
- Add similar operations as needed
- Create translator.yaml for each OEM
- Reuse implementation code

---

## References

- [PROJECT_STATUS.md](PROJECT_STATUS.md) — Overall Honda pipeline status
- [DESIGN_RULES.md](DESIGN_RULES.md) — Architectural constraints
- [step2_string_standardization.py](pipeline/step2_string_standardization.py) — Implementation
- [OEM Comparison](../../planning/oem_pipeline/honda_pipeline_modernization/phases/phase_2_5/OEM_COMPARISON.md) — How other OEMs structure configs

---

## Quick Links

- **Config Files:** `accy_v2/oems/honda/config/`
- **Implementation:** `accy_v2/oems/honda/pipeline/step2_string_standardization.py`
- **Translator:** `accy_v2/model_lookup/configs/honda/translator.yaml`
- **Tests:** `accy_v2/tests/` (to be created)

