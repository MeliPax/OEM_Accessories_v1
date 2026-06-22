# Final Implementation Plan: Model Lookup Integration

## Overview
Refactor the pipeline to use actual Step 3 data flow instead of creating test files. Model numbers will be looked up BEFORE melting, using unique (year, trim) combinations, then populated directly into the output DataFrame.

---

## Data Flow Architecture

### Step 3: Standardization
**Input**: Raw file (Excel/CSV)
**Output**: `standardized_df` with columns:
- Standard columns: `part_number`, `description_en`, `description_fr`, `msrp`, `dnp`, etc.
- Trim columns: `ES`, `SEL`, `Limited`, etc. (with "X" values for applicable trims)

**Example**:
```
part_number | description_en | ES | SEL | Limited
ACC-001     | Floor Mats      | X  |     |
ACC-002     | Roof Rack       | X  | X   | X
```

### Step 3.5: Extract Vehicle Year
**Input**: `standardized_df`, `meta_data` with `sheet_name`
**Process**:
- Extract 4-digit year from `sheet_name` (e.g., "2026_Outlander_ES_EN" → 2026)
- Validate year against `config["model_lookup_rules"]["valid_year_range"]`
- Store in `meta_data["vehicle_year"]`

**Output**: Same `standardized_df` (unchanged), enriched `meta_data`

### Step 4: Transformation (MELT TRIMS)
**Input**: `standardized_df`
**Process**:
1. Identify valid trim columns (have "X" in at least one row)
2. Melt: Convert trim columns to rows
3. Split by language: Create "EN" and "FR" versions

**Output**: `Dict[str, pd.DataFrame]` = `{"EN": melted_df, "FR": melted_df}`

**Example After Melt**:
```
EN DataFrame:
  part_number | description | trim | language
  ACC-001     | Floor Mats   | ES   | EN
  ACC-002     | Roof Rack    | ES   | EN
  ACC-002     | Roof Rack    | SEL  | EN
  ACC-002     | Roof Rack    | Limited | EN
```

### NEW: Batch Model Lookup (BEFORE melting was added to Step 4.5)
**Input**: `meta_data["vehicle_year"]`, `meta_data["model_name"]`, unique trims from melted data
**Process**:
1. **Extract Keywords**:
   - Get `sheet_name` from meta_data (e.g., "2026_Outlander_ES_EN")
   - Get list of unique trims (e.g., ["ES", "SEL", "Limited"])
   - Use `KeywordExtractor` to parse sheet_name and extract base keywords
   - For EACH unique trim:
     - Extract keywords from `sheet_name` (model details, fuel type, etc.)
     - Combine with trim name
     - Result: keywords list for this (year, trim) combination

2. **Lookup Model Numbers**:
   - For EACH unique `(vehicle_year, model_name, trim)` combination:
     ```python
     keywords = extract_keywords(sheet_name=meta_data["sheet_name"], trim=trim)
     result = search_models_by_description(
         year=meta_data["vehicle_year"],
         keywords=keywords
     )
     ```
   
   - Outcomes:
     - ✓ Found exactly 1 match → store in mapping: `{trim: model_number}`
     - ✗ Found 0 matches → flag in DQ, mark trim as MISSING
     - ✗ Found >1 matches → flag in DQ, mark trim as MISSING

3. **Store Mapping**:
   ```python
   model_mapping = {
       "ES": "CO45-B",           # ✓ Found
       "SEL": "CO45-C",          # ✓ Found
       "Limited": None,          # ✗ Missing (0 matches or ambiguous)
   }
   
   missing_trims = ["Limited"]   # For DQ reporting
   ```

4. **DQ Logging** (for missing):
   ```json
   {
       "trim_name": "Limited",
       "vehicle_year": 2026,
       "model_name": "Outlander",
       "keywords_searched": ["outlander", "limited"],
       "lookup_result": "no_match_found",  // or "ambiguous_multiple_matches"
       "message": "No model found for 2026 Outlander Limited",
       "rows_excluded": 12
   }
   ```

### Step 4.5: Model Enrichment (ADD MODEL_NUMBER COLUMN)
**Input**:
- `transformed`: `{"EN": melted_df, "FR": melted_df}`
- `model_mapping`: `{trim: model_number}` from Step 4 lookup
- `missing_trims`: list of trims without model numbers
- `meta_data`

**Process**:
1. For each language (EN, FR):
   - Add `model_number` column by mapping trim → model_number
   - Add `model_number_status` column:
     - `"yes - Model number found"` if model_number exists
     - `"no - missing model number"` if trim in missing_trims
   - Remove all rows where trim is in missing_trims (excluded from output)

2. Add `vehicle_year` column (from meta_data)

**Output**: `Dict[str, pd.DataFrame]` with enriched data, missing trims excluded

**Example After Enrichment**:
```
EN DataFrame (after model enrichment):
  part_number | description | trim | vehicle_year | model_number | model_number_status
  ACC-001     | Floor Mats   | ES   | 2026         | CO45-B       | yes - Model number found
  ACC-002     | Roof Rack    | ES   | 2026         | CO45-B       | yes - Model number found
  ACC-002     | Roof Rack    | SEL  | 2026         | CO45-C       | yes - Model number found
  
  (Limited trim EXCLUDED because lookup failed)
```

### Step 5: Output
**Input**: Enriched DataFrames from Step 4.5
**Process**:
- Rename columns to rate-import format
- Filter to required columns
- Create sheet keys: `{model_name}_{language}` (e.g., "Outlander_EN")

**Output**: Excel file with:
- Sheet names: "Outlander_EN", "Outlander_FR", etc.
- Columns include: `model_number`, `vehicle_year`, `model_number_status`
- Only rows with successful model lookups
- DQ Report with all warnings/errors

---

## Implementation Changes

### 1. Remove (No Longer Needed)
- ✗ `setup_test_data.py` (sample file creation)
- ✗ `test_model_lookup_pipeline.py` (test runner with sample files)
- ✗ Landing zone files (no test files created)

### 2. Modify: Step 4 Transformation
**File**: `accy_v2/oems/mitsubishi/pipeline/step4_transformation.py`
- After melting and before returning: **DO NOT DO MODEL LOOKUP HERE**
- Return dict as-is: `{"EN": melted_df, "FR": melted_df}`
- This is where we identify unique trims (for next step)

### 3. Create: Batch Model Lookup (Within Step 4.5)
**File**: `accy_v2/oems/mitsubishi/pipeline/step4_5_model_enrichment.py`

**Structure**:
```python
def run(
    transformed: Dict[str, pd.DataFrame],  # {"EN": df, "FR": df}
    meta_data: Dict,                       # Contains sheet_name, model_name, vehicle_year
    config: dict,                          # Contains model_lookup_rules
    dq_logger: DQLogger,
    pipeline_logger: PipelineLogger,
) -> Dict[str, pd.DataFrame]:
    """
    1. Identify unique trims from transformed data
    2. Batch lookup model numbers (one per unique trim)
    3. Enrich each DataFrame with model_number column
    4. Exclude rows for missing trims
    5. Return enriched {"EN": df, "FR": df}
    """
    # Get unique trims from any language version (same trims in both)
    unique_trims = _get_unique_trims(transformed["EN"])
    
    # Batch lookup: one per unique trim
    model_mapping, missing_trims = _batch_lookup_model_numbers(
        year=meta_data["vehicle_year"],
        model_name=meta_data["model_name"],
        sheet_name=meta_data["sheet_name"],
        trims=unique_trims,
        config=config,
        dq_logger=dq_logger,
        pipeline_logger=pipeline_logger,
    )
    
    # Enrich each language version
    enriched = {}
    for lang, df in transformed.items():
        enriched_df = _add_model_number_column(df, model_mapping, missing_trims)
        enriched[lang] = enriched_df
    
    return enriched


def _get_unique_trims(df: pd.DataFrame) -> List[str]:
    """Get list of unique trim values from melted DataFrame."""
    return df["trim"].unique().tolist()


def _batch_lookup_model_numbers(
    year: int,
    model_name: str,
    sheet_name: str,
    trims: List[str],
    config: dict,
    dq_logger: DQLogger,
    pipeline_logger: PipelineLogger,
) -> Tuple[Dict[str, str], List[str]]:
    """
    Lookup model number for each unique trim.
    
    Returns:
    - model_mapping: {trim: model_number} where model_number is string or None
    - missing_trims: [trim1, trim2] where lookup failed
    """
    from core.helpers.keyword_extractor import KeywordExtractor
    from model_lookup.models.manufacture_module import search_models_by_description
    
    model_mapping = {}
    missing_trims = []
    
    keyword_extractor = KeywordExtractor()
    
    for trim in trims:
        # Extract keywords from sheet_name and trim
        keywords = keyword_extractor.extract_keywords(
            sheet_name=sheet_name,
            trim=trim,
            config=config
        )
        
        pipeline_logger.debug(
            f"Lookup for {model_name} {year} {trim}: keywords={keywords}"
        )
        
        # Search for model number
        results = search_models_by_description(keywords)
        
        if len(results) == 1:
            model_number = results[0]
            model_mapping[trim] = model_number
            pipeline_logger.debug(f"  ✓ Found: {model_number}")
        else:
            missing_trims.append(trim)
            
            if len(results) == 0:
                dq_logger.warning(
                    f"Model lookup: No model found for {model_name} {year} {trim}",
                    details={
                        "trim_name": trim,
                        "vehicle_year": year,
                        "model_name": model_name,
                        "keywords_searched": keywords,
                        "lookup_result": "no_match_found",
                    }
                )
                pipeline_logger.warning(
                    f"  ✗ Not found: {model_name} {year} {trim} keywords={keywords}"
                )
            else:
                dq_logger.warning(
                    f"Model lookup: Ambiguous match for {model_name} {year} {trim}",
                    details={
                        "trim_name": trim,
                        "vehicle_year": year,
                        "model_name": model_name,
                        "keywords_searched": keywords,
                        "lookup_result": "ambiguous_multiple_matches",
                        "matches_found": results,
                    }
                )
                pipeline_logger.warning(
                    f"  ✗ Ambiguous ({len(results)} matches): {model_name} {year} {trim}"
                )
    
    return model_mapping, missing_trims


def _add_model_number_column(
    df: pd.DataFrame,
    model_mapping: Dict[str, str],
    missing_trims: List[str],
) -> pd.DataFrame:
    """
    Add model_number and model_number_status columns.
    Exclude rows where trim is in missing_trims.
    """
    df = df.copy()
    
    # Map model_number based on trim
    df["model_number"] = df["trim"].map(model_mapping)
    
    # Add status column
    df["model_number_status"] = df["model_number"].apply(
        lambda x: "yes - Model number found" if pd.notna(x) else "no - missing model number"
    )
    
    # Exclude rows with missing model numbers (missing_trims)
    df_filtered = df[~df["trim"].isin(missing_trims)].copy()
    
    return df_filtered
```

### 4. Modify: Step 5 Output
**File**: `accy_v2/oems/mitsubishi/pipeline/step5_output.py`
- Already adds `model_name` and `sheet_name` columns
- Ensure `model_number` and `vehicle_year` columns are preserved
- Update to include `model_number_status` in final output

### 5. Update: KeywordExtractor
**File**: `accy_v2/core/helpers/keyword_extractor.py`
- Add method: `extract_keywords(sheet_name, trim, config)`
- Parses sheet_name to get model details and keywords
- Combines with trim name
- Returns list of keywords for model lookup

---

## Data Flow Summary

```
Input File (Excel/CSV)
    ↓
Step 1: Validation → meta_data populated
    ↓
Step 2: Header Normalization → trim columns identified
    ↓
Step 3: Standardization → standardized_df with trim columns
    ↓
Step 3.5: Extract Year → meta_data["vehicle_year"] = 2026
    ↓
Step 4: Transformation → Melt trims, split by language
    ├─ {"EN": melted_df, "FR": melted_df}
    ├─ Unique trims identified: ["ES", "SEL", "Limited"]
    ↓
[NEW] Batch Model Lookup → One lookup per unique trim
    ├─ Keywords from sheet_name + trim
    ├─ search_models_by_description(keywords)
    ├─ Results: {"ES": "CO45-B", "SEL": "CO45-C", "Limited": None}
    ├─ Missing: ["Limited"]
    ↓
Step 4.5: Model Enrichment
    ├─ Add model_number column (map trim → model_number)
    ├─ Add model_number_status column ("yes" or "no")
    ├─ Add vehicle_year column
    ├─ Exclude rows where trim in missing_trims
    ├─ Result: {"EN": enriched_df, "FR": enriched_df}
    ↓
Step 5: Output
    ├─ Rename columns to rate-import format
    ├─ Create sheet keys: "Outlander_EN", "Outlander_FR"
    ├─ Write to Excel file
    ↓
Output File (Ready to Upload)
    └─ Columns: part_number, description, model_number, vehicle_year, model_number_status, ...
    └─ Only rows with successful model lookups
    └─ DQ Report: missing trims logged with details
```

---

## DQ Report Structure

### For Each Sheet Processed:

**Success Case** (Trim found):
```json
{
  "trim_name": "ES",
  "status": "model_found",
  "vehicle_year": 2026,
  "model_name": "Outlander",
  "model_number": "CO45-B",
  "rows_processed": 45
}
```

**Failure Case** (No match):
```json
{
  "trim_name": "Limited",
  "status": "missing",
  "vehicle_year": 2026,
  "model_name": "Outlander",
  "keywords_searched": ["outlander", "limited"],
  "lookup_result": "no_match_found",
  "message": "No model found for 2026 Outlander Limited",
  "rows_excluded": 12
}
```

**Ambiguous Case** (Multiple matches):
```json
{
  "trim_name": "SE",
  "status": "missing",
  "vehicle_year": 2026,
  "model_name": "Outlander",
  "keywords_searched": ["outlander", "se"],
  "lookup_result": "ambiguous_multiple_matches",
  "matches_found": ["CO45-A", "CO45-B"],
  "message": "Ambiguous match (2 results) for 2026 Outlander SE",
  "rows_excluded": 8
}
```

---

## Key Benefits

✅ **No sample files needed** - Uses actual pipeline data
✅ **Efficient lookups** - One per unique trim, not per row
✅ **Clear visibility** - model_number_status in output file
✅ **Seamless integration** - Data flows directly through pipeline
✅ **Easy troubleshooting** - DQ report shows exactly what failed and why
✅ **Automatic filtering** - Missing model numbers excluded from output
✅ **Year validation** - Happens in Step 3.5 before lookup

---

## Remaining Implementation Notes

1. **Keywords Extraction**: Use existing `KeywordExtractor` class, extend to accept `sheet_name` + `trim` and return combined keyword list

2. **Model Lookup Call**: Use existing `search_models_by_description()` function from `manufacture_module.py`

3. **Database**: Must be pre-populated with `populate_vehicle_database.py` before running pipeline

4. **Error Handling**: All failures logged to DQ report with clear categorization (no_match vs ambiguous)

5. **Output Structure**: Final Excel file includes `model_number`, `vehicle_year`, and `model_number_status` columns for full visibility

---

This plan creates a clean, efficient pipeline where model numbers are integrated seamlessly without any temporary files or workarounds.
