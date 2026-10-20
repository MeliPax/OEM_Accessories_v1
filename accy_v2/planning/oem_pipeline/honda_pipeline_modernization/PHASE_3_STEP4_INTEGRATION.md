# Phase 3: Step 4 Integration — Verify Melting & Merging

**Objective:** Verify that Step 4 correctly receives EN and FR outputs from Step 3, melts trim columns to long format, combines EN+FR, and produces final long-format output.

**Status:** Design phase (Phase 1 and 2 must complete first)  
**Files affected:**
- `accy_v2/oems/honda/pipeline/step4_transformation.py` (may need adjustment)
- Base pipeline orchestration (may need adjustment)

---

## Current State

**Step 4 responsibility in standard OEM pipeline:**
- Receives: standardized_df from Step 3
- Performs: applicability validation, trim column melting, long-format transformation
- Returns: Dict[str, pd.DataFrame] (one per language or one combined)

**Honda's Step 4 needs to handle:**
- Receiving **separate EN and FR DataFrames** from Step 3 (not combined)
- Melting trim columns (wide to long)
- Combining EN and FR into single output
- Final applicability validation

---

## Input to Step 4

### From Step 3:

```python
# Step 3 is called separately for EN and FR
standardized_en = run_step3_standardization(en_working_df, step2_result, config, meta_data_en, ...)
standardized_fr = run_step3_standardization(fr_working_df, step2_result, config, meta_data_fr, ...)

# Collected as dict for Step 4
step3_outputs = {
    "EN": standardized_en,  # pd.DataFrame with wide-format EN data
    "FR": standardized_fr,  # pd.DataFrame with wide-format FR data
}
```

### Example EN DataFrame:

```
    description  part_number  dealer_net  list_price   frt  installed_price      LX      EX    Sport  Touring
0   Exterior Pkg      25CIV-ENK     1200.0     1800.0  25.0         1825.0       •       •       •        •
1   Wheel Kit A      25CIV-WHL     800.0      1200.0  15.0         1215.0       •              •       
2   Interior Set     25CIV-INT     500.0       750.0  10.0          760.0                 •       
```

### Example FR DataFrame:

```
    description      part_number  dealer_net  list_price   frt  installed_price      LX      EX    Sport  Touring
0   Ensemble Ext.      25CIV-ENK     1200.0     1800.0  25.0         1825.0       •       •       •        •
1   Kit Roue A         25CIV-WHL     800.0      1200.0  15.0         1215.0       •              •       
2   Interieur Ens.     25CIV-INT     500.0       750.0  10.0          760.0                 •       
```

---

## Desired Output from Step 4

### Final long-format structure:

```
    description   part_number  dealer_net  list_price   frt  installed_price  trim  applicability  language
0   Exterior Pkg  25CIV-ENK    1200.0      1800.0      25.0      1825.0       LX    •              EN
1   Exterior Pkg  25CIV-ENK    1200.0      1800.0      25.0      1825.0       EX    •              EN
2   Exterior Pkg  25CIV-ENK    1200.0      1800.0      25.0      1825.0       Sport •              EN
3   Exterior Pkg  25CIV-ENK    1200.0      1800.0      25.0      1825.0       Touring •             EN
4   Ensemble Ext 25CIV-ENK    1200.0      1800.0      25.0      1825.0       LX    •              FR
5   Ensemble Ext 25CIV-ENK    1200.0      1800.0      25.0      1825.0       EX    •              FR
6   Ensemble Ext 25CIV-ENK    1200.0      1800.0      25.0      1825.0       Sport •              FR
7   Ensemble Ext 25CIV-ENK    1200.0      1800.0      25.0      1825.0       Touring •             FR
8   Wheel Kit A  25CIV-WHL    800.0       1200.0      15.0      1215.0       LX    •              EN
9   Wheel Kit A  25CIV-WHL    800.0       1200.0      15.0      1215.0       Sport •              EN
...
```

**Key characteristics:**
- One row per (part, trim, language) combination
- Non-applicable trims excluded (where trim column was empty)
- Trim column contains the trim name (LX, EX, Sport, Touring, etc.)
- Language column distinguishes EN and FR
- Applicability column preserves the marker (•, S, T, E, etc.)

---

## Design: Orchestration Changes

### Current orchestrator flow (needs verification):

```python
# In base_pipeline.run() or Honda orchestrator:

for sheet_name, df_raw in filtered_data_units.items():
    working_df = run_step1_validation(df_raw, ...)
    step2_result = run_step2_header_normalization(working_df, ...)
    standardized_df = run_step3_standardization(working_df, step2_result, ...)
    transformed = run_step4_transformation(standardized_df, step2_result, ...)
    enriched = run_step4_5_model_enrichment(transformed, ...)
    sheet_frames = run_step5_output(enriched, ...)
```

### Proposed Honda-specific flow:

```python
# Load both EN and FR sheets in Step 1
for language in ["EN", "FR"]:
    df_raw = load_sheet(sheet_name, language)
    working_df = run_step1_validation(df_raw, ...)
    step3_outputs[language] = None  # Placeholder

step2_result = run_step2_header_normalization(en_working_df, ...)  # Once, using EN

# Run Step 3 separately for EN and FR
for language in ["EN", "FR"]:
    standardized_df = run_step3_standardization(working_df_lang, step2_result, ...)
    step3_outputs[language] = standardized_df

# Step 4 receives both EN and FR outputs
transformed = run_step4_transformation(step3_outputs, step2_result, ...)

# Continue as normal
enriched = run_step4_5_model_enrichment(transformed, ...)
sheet_frames = run_step5_output(enriched, ...)
```

### What needs to change:

1. **Step 1:** Load both EN and FR sheets (may already do this)
2. **Step 2:** Run once (uses EN sheet to build col_mapping)
3. **Step 3:** Run separately for EN and FR, collect outputs
4. **Step 4:** Receive Dict[language: DataFrame], melt and merge them
5. **Steps 4.5+:** Process as normal (no changes expected)

---

## Design: Step 4 Melting Logic

### What is melting?

Convert wide-format (trim columns) to long-format (one row per trim).

### Algorithm:

```python
def _melt_trim_columns(df, valid_trim_cols, language):
    """
    Melt trim columns from wide to long format.
    
    Input:  one row per part with columns LX, EX, Sport, Touring, ...
    Output: multiple rows per part (one per trim with non-empty value)
    """
    # Columns to preserve in output
    id_vars = [col for col in df.columns if col not in valid_trim_cols]
    
    # Melt trim columns
    melted = pd.melt(
        df,
        id_vars=id_vars,
        value_vars=valid_trim_cols,
        var_name="trim",
        value_name="applicability"
    )
    
    # Filter out rows where applicability is empty (trim not applicable)
    melted = melted[melted["applicability"].notna()]
    melted = melted[melted["applicability"].astype(str).str.strip() != ""]
    
    # Add language column
    melted["language"] = language
    
    return melted
```

### Example:

**Input (1 row):**
```
part_number  description   LX  EX  Sport  Touring
25CIV-ENK    Exterior Pkg  •   •   •      •
```

**Output after melt (4 rows):**
```
part_number  description   trim   applicability  language
25CIV-ENK    Exterior Pkg  LX     •              EN
25CIV-ENK    Exterior Pkg  EX     •              EN
25CIV-ENK    Exterior Pkg  Sport  •              EN
25CIV-ENK    Exterior Pkg  Touring •             EN
```

---

## Design: EN+FR Merging

### Algorithm:

```python
def _merge_en_fr(melted_en, melted_fr):
    """
    Merge EN and FR melted DataFrames into single output.
    
    Both have same columns (description, part_number, ..., trim, applicability, language)
    Just concatenate them.
    """
    combined = pd.concat([melted_en, melted_fr], ignore_index=True)
    return combined
```

### Example:

**melted_en (4 rows for Part A):**
```
part_number  trim   language
25CIV-ENK    LX     EN
25CIV-ENK    EX     EN
25CIV-ENK    Sport  EN
25CIV-ENK    Touring EN
```

**melted_fr (4 rows for Part A):**
```
part_number  trim   language
25CIV-ENK    LX     FR
25CIV-ENK    EX     FR
25CIV-ENK    Sport  FR
25CIV-ENK    Touring FR
```

**combined (8 rows):**
```
part_number  trim   language
25CIV-ENK    LX     EN
25CIV-ENK    EX     EN
25CIV-ENK    Sport  EN
25CIV-ENK    Touring EN
25CIV-ENK    LX     FR
25CIV-ENK    EX     FR
25CIV-ENK    Sport  FR
25CIV-ENK    Touring FR
```

---

## Design: Step 4 Implementation

### Pseudocode:

```python
def run(step3_outputs, step2_result, config, meta_data, dq_logger, logger):
    """
    Transform standardized data from Step 3.
    
    Input: step3_outputs = {"EN": df_en, "FR": df_fr}
    Output: {"model_variant": melted_df}  (or similar, per existing contract)
    """
    valid_trim_cols = step2_result["valid_trim_cols"]
    
    # Melt each language separately
    melted_en = _melt_trim_columns(step3_outputs["EN"], valid_trim_cols, "EN")
    melted_fr = _melt_trim_columns(step3_outputs["FR"], valid_trim_cols, "FR")
    
    # Merge EN and FR
    transformed = _merge_en_fr(melted_en, melted_fr)
    
    # Additional validation/processing if needed
    # ...
    
    # Return in format expected by Step 4.5 and Step 5
    # (may need to be Dict[key: DataFrame] per existing contract)
    return {"combined": transformed}  # Or whatever the expected format is
```

---

## Verification Strategy

### Test data flow:

1. **Load EN and FR sheets**
   - [ ] Both sheets load correctly
   - [ ] Both have same structure (same columns, same row count)

2. **Run Step 1 for each language**
   - [ ] EN working_df correct
   - [ ] FR working_df correct

3. **Run Step 2 once**
   - [ ] col_mapping built from EN
   - [ ] valid_trim_cols extracted
   - [ ] Can be applied to both EN and FR

4. **Run Step 3 for each language**
   - [ ] EN standardized_df correct format
   - [ ] FR standardized_df correct format
   - [ ] Both have same column structure (after col_mapping applied)

5. **Run Step 4**
   - [ ] Melting works: 1 row → N rows (one per trim)
   - [ ] Empty trims filtered out (no rows with empty applicability)
   - [ ] Language column added correctly
   - [ ] EN and FR merged correctly
   - [ ] Output has expected columns: (part_number, description, trim, applicability, language, ...)

6. **Validate output structure**
   - [ ] Long-format (one row per part-trim-language)
   - [ ] No duplicate rows
   - [ ] All trims represented for all parts
   - [ ] Language column has only "EN" and "FR"
   - [ ] Applicability column has only valid markers (•, S, T, E, null)

---

## Testing Scenarios

### Scenario 1: Simple part with all trims

Part A applies to all 4 trims (LX, EX, Sport, Touring):
```
Input (EN):  1 row, 4 trim columns with •
Output:      4 rows (one per trim)
Input (FR):  1 row, 4 trim columns with •
Output:      4 rows (one per trim)
Combined:    8 rows (4 EN + 4 FR)
```

### Scenario 2: Part with partial trims

Part B applies to only 2 trims (LX, Sport):
```
Input (EN):  1 row, LX and Sport have •, EX and Touring are empty
Output:      2 rows (LX and Sport only)
Input (FR):  1 row, LX and Sport have •, EX and Touring are empty
Output:      2 rows (LX and Sport only)
Combined:    4 rows (2 EN + 2 FR)
```

### Scenario 3: Different applicability markers

Part C has mixed markers (•, S, E):
```
Input (EN):  LX has •, EX has S, Sport has E, Touring empty
Output:      3 rows (LX, EX, Sport with their respective markers preserved)
Input (FR):  Same structure
Output:      3 rows (with markers preserved)
Combined:    6 rows (3 EN + 3 FR)
```

---

## Potential Issues & Solutions

| Issue | Symptom | Solution |
|-------|---------|----------|
| EN/FR mismatch | Different row counts or columns | Verify Step 1 loads same rows for both languages |
| Trim column mismatch | valid_trim_cols doesn't match actual columns | Verify col_mapping extracted correctly in Step 2 |
| Missing applicability | Rows with no trim markers not filtered | Ensure empty trim check works correctly in melt logic |
| Language column missing | Can't distinguish EN from FR in output | Verify language column added in melt logic |
| Duplicate rows | Same part-trim-language appears twice | Check melt logic doesn't duplicate |

---

## Integration Checklist

- [ ] Step 3 returns separate EN and FR DataFrames (not combined)
- [ ] Step 4 receives Dict["EN": df_en, "FR": df_fr]
- [ ] Step 4 melts EN and FR separately
- [ ] Step 4 filters out empty trim rows
- [ ] Step 4 adds language column correctly
- [ ] Step 4 merges EN and FR into single output
- [ ] Output is long-format (one row per part-trim-language)
- [ ] All downstream steps (4.5, 5) work with melted output
- [ ] DQ logging works through all steps
- [ ] End-to-end test passes with real Honda data

---

## Success Criteria

✅ **Phase 3 complete when:**
- Step 4 correctly melts trim columns
- EN and FR are merged in output
- Long-format output matches expected structure
- All row counts correct (no lost/duplicate rows)
- All downstream steps work with output
- End-to-end pipeline produces correct final output
