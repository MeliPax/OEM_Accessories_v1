# OEM Config Schema Reference

This document describes every key in the OEM configuration JSON file. Use this as a reference when authoring a new `<oem_name>_config.json`.

**Quick start:** Copy `oems/mitsubishi/config/mitsubishi_config.json` as a template and modify the values for your OEM.

---

## Top-Level Structure

```json
{
  "non_null_threshold": 0.5,
  "column_definition": { ... },
  "required_columns": [ ... ],
  "non_null_columns": [ ... ],
  "col_data_type_dict": { ... },
  "trim_bounds_config": { ... },
  "trim_validation_config": { ... },
  "non_acceptable_sheet_names": [ ... ],
  "sheet_name_pattern": "...",
  "drop_columns": [ ... ],
  "language_columns": { ... },
  "rate_import_column_mapping": { ... },
  "rate_import_required_columns": [ ... ],
  "output": { ... }
}
```

---

## Section: `non_null_threshold`

**Type:** Float (0.0 to 1.0)  
**Default:** `0.5`  
**Description:** Controls how tolerant the pipeline is toward null values in required columns.

- If a required column has ≥ this rate of nulls → **FATAL** (skip entire sheet)
- If a required column has < this rate of nulls → log each null record as a DQ warning, exclude those rows, continue

**Example:**
```json
"non_null_threshold": 0.5
```

**Typical values:**
- `0.5` — Skip sheet if > 50% of a column is null (strict)
- `0.1` — Skip sheet if > 10% of a column is null (lenient)

---

## Section: `column_definition`

**Type:** Object of objects  
**Description:** Defines what keywords identify each standard column in the raw data.

The pipeline uses keyword matching to recognize columns by name, handling variations like "Part Number", "Part_Number", "PART_NUMBER".

### Structure

Each standard column name maps to keyword rules:

```json
"column_definition": {
  "part_number": {
    "key_words": {
      "must_have": ["part", "number"],
      "must_have_one_of": [],
      "not_have": []
    }
  },
  "english_description": {
    "key_words": {
      "must_have": ["description"],
      "must_have_one_of": ["english", "EN"],
      "not_have": []
    }
  },
  ...
}
```

### Matching rules (applied in order)

1. **`not_have`** — If ANY of these keywords appear in the column name, skip this column (reject)
2. **`must_have`** — ALL of these keywords must appear in the column name (as whole word tokens)
3. **`must_have_one_of`** — At least ONE of these keywords must appear in the column name

All matching is **case-insensitive** and uses **word-token matching** (column name is split by `_`, not substring matching).

### Examples

Column name: `"Part Number"` → cleaned to `"part_number"` → tokens: `["part", "number"]`
- Matches `must_have: ["part", "number"]` ✓

Column name: `"English Description"` → cleaned to `"english_description"` → tokens: `["english", "description"]`
- Matches `must_have: ["description"]` ✓ AND `must_have_one_of: ["english", "EN"]` ✓

Column name: `"Install Time"` → cleaned to `"install_time"` → tokens: `["install", "time"]`
- Matches `must_have: ["install", "time"]` ✓

---

## Section: `required_columns`

**Type:** Array of strings  
**Description:** List of standard column names that must be found in the input.

If any required column is not found, the sheet is skipped (FATAL).

**Example:**
```json
"required_columns": [
  "part_number",
  "english_description",
  "french_description",
  "msrp",
  "dnp",
  "install_time",
  "labour_rate"
]
```

---

## Section: `non_null_columns`

**Type:** Array of strings  
**Description:** A subset of `required_columns` that must have values (no nulls/blanks) for each record.

If a non-null column has nulls below the threshold, those rows are excluded. If above the threshold, the sheet is skipped.

**Example:**
```json
"non_null_columns": [
  "part_number",
  "english_description",
  "msrp",
  "install_time"
]
```

**Note:** Typically a strict subset of `required_columns`. For example, `french_description` might be optional (can be blank) even though it's required to exist as a column.

---

## Section: `col_data_type_dict`

**Type:** Object with `to_string` and `to_float` arrays  
**Description:** Specifies which columns should be coerced to string or float types.

### `to_string`

Columns to convert to string. Nulls are preserved; non-null values are cast to string.

```json
"to_string": ["part_number", "english_description", "french_description"]
```

### `to_float`

Columns to convert to float. If conversion fails (non-numeric value), the pipeline raises a FATAL error.

```json
"to_float": ["msrp", "dnp", "install_time", "labour_rate"]
```

**Example:**
```json
"col_data_type_dict": {
  "to_string": ["part_number", "english_description", "french_description"],
  "to_float": ["msrp", "dnp", "install_time", "labour_rate"]
}
```

---

## Section: `trim_bounds_config`

**Type:** Object with `left_bound` and `right_bound`  
**Description:** Defines which columns mark the boundaries of the trim column range.

Columns between these boundaries are assumed to be trim levels (e.g., ES, SE, LE, XLE).

### Structure

```json
"trim_bounds_config": {
  "left_bound": {
    "must_contain": ["remarks"]
  },
  "right_bound": {
    "must_contain_one_of": ["photo", "image"]
  }
}
```

- **`left_bound.must_contain`** — Keywords that identify the leftmost boundary column
- **`right_bound.must_contain_one_of`** — Keywords for the rightmost boundary column

All keywords must match as substrings (case-insensitive). Columns strictly between these two are considered trim candidates.

**Example:**
```json
"trim_bounds_config": {
  "left_bound": {
    "must_contain": ["remarks"]
  },
  "right_bound": {
    "must_contain_one_of": ["photo", "image"]
  }
}
```

---

## Section: `trim_validation_config`

**Type:** Object with `expected_data` and `must_have_only`  
**Description:** Rules for validating that suspected trim columns actually contain trim data.

### `expected_data`

```json
"expected_data": {
  "data": "X",
  "perc_thresh": 60
}
```

- **`data`** — The value expected in trim columns (e.g., "X" to indicate applicability)
- **`perc_thresh`** — Percentage of non-null cells that must contain this value

A column passes if ≥ 60% of its non-null values are "X".

### `must_have_only`

```json
"must_have_only": {
  "expected_value_types": ["X", "", "__na__"]
}
```

- **`expected_value_types`** — Array of acceptable values. Use `"__na__"` as a sentinel for null/empty.

A column passes if every non-null value is one of the expected types. For trim columns, typically only "X", blank, and null are acceptable.

**Example:**
```json
"trim_validation_config": {
  "expected_data": {
    "data": "X",
    "perc_thresh": 60
  },
  "must_have_only": {
    "expected_value_types": ["X", "", "__na__"]
  }
}
```

---

## Section: `non_acceptable_sheet_names`

**Type:** Array of strings  
**Description:** Sheet names that should be skipped (e.g., admin sheets, templates).

Matching is **case-insensitive**.

**Example:**
```json
"non_acceptable_sheet_names": ["meta_data", "luxwood"]
```

---

## Section: `sheet_name_pattern`

**Type:** String (regex pattern)  
**Description:** A regex pattern that valid sheet names must match.

If a sheet name doesn't match, it's skipped (FATAL).

**Example:**
```json
"sheet_name_pattern": "^\\d{4}\\s+.+"
```

This pattern requires: 4 digits, space, at least one more character. Matches "2026 Outlander", rejects "Luxwood English".

---

## Section: `drop_columns`

**Type:** Array of strings  
**Description:** Keywords of columns to drop from processing.

Columns whose names contain any of these keywords are excluded from the output.

**Example:**
```json
"drop_columns": ["photo", "image", "installed_price", "imc", "install_sheet", "category"]
```

---

## Section: `language_columns`

**Type:** Object mapping language codes to column name arrays  
**Description:** Specifies which columns belong to which language, enabling language split.

```json
"language_columns": {
  "EN": ["english_description"],
  "FR": ["french_description"]
}
```

For each language:
- The specified columns are kept
- Columns for other languages are dropped
- The language-specific column is renamed to the neutral name "description"

Result: Each language gets its own dataframe with the same structure (both have a "description" column).

---

## Section: `rate_import_column_mapping`

**Type:** Object mapping standard column names to output column names  
**Description:** Renames internal columns to the format expected by the rate importer.

The pipeline builds data internally with names like `part_number`, `english_description`, `msrp`. This mapping renames them to the final output format: `Part`, `Description`, `Price`, etc.

**Note:** After language split (Step 4), description columns are already renamed to the neutral name `"description"`, so the mapping uses that key.

**Example:**
```json
"rate_import_column_mapping": {
  "part_number":  "Part",
  "description":  "Description",
  "remarks":      "Comments",
  "msrp":         "Price",
  "install_time": "Hours",
  "trim_level":   "Trim"
}
```

---

## Section: `rate_import_required_columns`

**Type:** Array of strings  
**Description:** Final column names that must be present in the output.

Columns not in this list are dropped from the final Excel file.

**Example:**
```json
"rate_import_required_columns": ["Part", "Description", "Comments", "Price", "Hours", "Trim"]
```

---

## Section: `output`

**Type:** Object with `ready_to_upload_path`, `dq_report_path`, `pipeline_log_path`  
**Description:** Paths where outputs are written.

All paths are created automatically; specify them relative to the working directory.

```json
"output": {
  "ready_to_upload_path": "output/ready_to_upload/mitsubishi/",
  "dq_report_path": "output/dq_reports/mitsubishi/",
  "pipeline_log_path": "output/pipeline_logs/mitsubishi/"
}
```

**Keys:**
- **`ready_to_upload_path`** — Where to save the final Excel files (one per model)
- **`dq_report_path`** — Where to save the JSON DQ report
- **`pipeline_log_path`** — Where to save the text execution log

---

## Full Example

See `oems/mitsubishi/config/mitsubishi_config.json` for a complete working example.

---

## Validation

After authoring a config:

1. **Check JSON syntax:** Valid JSON (use a linter)
2. **Run the pipeline:** If config keys are missing or invalid, `config_loader.py` will raise an error with details
3. **Review DQ report:** Check that the column names are being recognized correctly in the first run

---

## Tips for New OEMs

- **Start with Mitsubishi:** Copy the Mitsubishi config and modify column keywords to match your OEM's naming conventions
- **Column keywords:** Keep keywords short and unambiguous. "part", "number" are better than "part_number" (the latter might not match all variants)
- **Trim bounds:** Identify which columns mark the left and right of the trim range in your OEM's file
- **Language handling:** If your OEM doesn't have EN/FR split, set `"language_columns": { "default": [] }` to skip the language split step
