# Implementation Plan: Downstream Schema Restructuring

**Date:** 2026-08-03  
**Objective:** Restructure downstream config to use explicit source→output column mapping with language-specific sheets  
**Goal:** Programmable, modular column configuration for easy future additions  

---

## 🎯 Problem Summary

### Current State (Broken)
```
Output columns: Year, model_name, group_key, year_from, model, english_description, 
               french_description, part_number, dnet, msrp, labour_rate, labour_hours
```

**Issues:**
1. ❌ Unwanted columns in output (group_key, year_from, dnet, labour_rate, model_name duplicated)
2. ❌ Mixed English/French in single sheet (inefficient for downstream systems)
3. ❌ "label default" appearing on sheets (unclear origin - need to investigate)
4. ❌ Column mapping is implicit/hardcoded (not modular)
5. ❌ No language-specific column selection
6. ❌ Trim column missing entirely

### Desired State (Target)
```
English Sheet (Accessories_EN):
  Columns: Year, Model, Part, Description, Comments, Price, Hours, Trim, model_number

French Sheet (Accessories_FR):
  Columns: Year, Model, Part, Description, Comments, Price, Hours, Trim, model_number
```

**Benefits:**
1. ✅ Separate sheets per language (cleaner for consumers)
2. ✅ Only relevant columns in output
3. ✅ Explicit source→output mapping (programmable)
4. ✅ Easy to add/remove columns in future
5. ✅ Language-specific column selection (Description vs Description_FR)

---

## 📋 Files That Need Changes

### 1. **downstream.yaml** (Schema Definition)
   - Current: Single sheet, implicit column mapping
   - Target: Separate EN/FR sheets with explicit source mappings
   - Complexity: HIGH (structural change)

### 2. **step5_output.py** (Implementation)
   - Current: Hardcoded metadata enrichment, basic renaming
   - Target: Programmable column mapping, language selection
   - Complexity: MEDIUM (logic refactor)

### 3. **output_writer.py** (Writing)
   - Likely: Check sheet naming (investigate "label default")
   - Complexity: LOW (probably naming fix)

### 4. **base_pipeline.py** (Config Loading)
   - Current: Uses old `rate_import_*` keys
   - Target: Use new downstream schema keys
   - Complexity: LOW (config key update)

---

## 🔍 Investigation Required

### Issue: "label default" on Sheets

**Where to look:**
1. Check `accy_v2/core/helpers/output_writer.py` - sheet creation logic
2. Check Excel output file sheet tab names
3. Search codebase for "label" or "default" in sheet context

**Likely causes:**
- Openpyxl/xlsxwriter default sheet naming
- Uninitialized sheet display name
- Excel reserved names ("Sheet1", "Sheet2", etc.)

**Action:** Read output_writer.py and check latest Excel output for sheet names

---

## 💡 Solution Design

### Step 1: New downstream.yaml Structure

```yaml
# NEW STRUCTURE - Explicit source→output mapping per sheet

sheets:
  Accessories_EN:
    display_name: "Accessories (English)"
    language: EN
    data_source: primary  # Output from step5 after language split
    
    # Explicit column configuration (programmable format)
    columns:
      - output_column: Year
        source_column: ModelYear
        data_type: integer
        width: 10
        
      - output_column: Model
        source_column: ModelName
        data_type: string
        width: 20
        
      - output_column: Part
        source_column: PartNumber
        data_type: string
        width: 15
        
      - output_column: Description
        source_column: Description  # EN sheet uses Description
        data_type: string
        width: 50
        
      - output_column: Comments
        source_column: Comments  # EN sheet uses Comments
        data_type: string
        width: 30
        
      - output_column: Price
        source_column: MSRP
        data_type: float
        width: 12
        formatting: currency
        
      - output_column: Hours
        source_column: LaborHours
        data_type: float
        width: 10
        
      - output_column: Trim
        source_column: trim_level  # From runtime processing
        data_type: string
        width: 20
        
      - output_column: model_number
        source_column: model_number  # From enrichment step
        data_type: string
        width: 15
        note: "Fetched from database during enrichment"
    
    sorting:
      - column: Year
        order: ascending
      - column: Model
        order: ascending
      - column: Part
        order: ascending

  Accessories_FR:
    display_name: "Accessories (Français)"
    language: FR
    data_source: primary
    
    columns:
      - output_column: Year
        source_column: ModelYear
        data_type: integer
        
      - output_column: Model
        source_column: ModelName
        data_type: string
        
      - output_column: Part
        source_column: PartNumber
        data_type: string
        
      - output_column: Description
        source_column: Description_FR  # FR sheet uses Description_FR
        data_type: string
        
      - output_column: Comments
        source_column: Comments_FR  # FR sheet uses Comments_FR
        data_type: string
        
      - output_column: Price
        source_column: MSRP
        data_type: float
        formatting: currency
        
      - output_column: Hours
        source_column: LaborHours
        data_type: float
        
      - output_column: Trim
        source_column: trim_level
        data_type: string
        
      - output_column: model_number
        source_column: model_number
        data_type: string
        note: "Fetched from database during enrichment"
    
    sorting:
      - column: Year
        order: ascending
      - column: Model
        order: ascending
      - column: Part
        order: ascending

  # Keep existing DQ sheets (unchanged)
  _Data_Issues:
    # ... existing config
    
  _Report:
    # ... existing config
    
  _Audit:
    # ... existing config
```

### Step 2: Programmable Column Mapping System

Create helper function in a new file: `accy_v2/core/helpers/column_mapper_v2.py`

```python
def build_column_mapping(sheet_config: dict) -> dict:
    """
    Build programmable column mapping from downstream schema.
    
    Returns: {source_column: output_column}
    
    This allows:
    1. Easy column additions (just add to downstream.yaml)
    2. Language-specific selection (Description vs Description_FR)
    3. Runtime type conversion based on data_type
    4. Format specification (currency, percentage, etc.)
    """
    mapping = {}
    for col_spec in sheet_config.get("columns", []):
        source = col_spec.get("source_column")
        output = col_spec.get("output_column")
        if source and output:
            mapping[source] = output
    return mapping


def get_columns_for_sheet(sheet_config: dict) -> list:
    """Get ordered list of output columns for a sheet."""
    return [col["output_column"] for col in sheet_config.get("columns", [])]


def get_column_spec(sheet_config: dict, output_column: str) -> dict:
    """Get specification for a column (data_type, width, formatting, etc.)"""
    for col_spec in sheet_config.get("columns", []):
        if col_spec.get("output_column") == output_column:
            return col_spec
    return {}
```

### Step 3: Refactored step5_output.py

```python
def prepare_frames(
    transformed: Dict[str, pd.DataFrame],
    meta_data: Dict[str, Any],
    config: dict,
) -> Dict[str, pd.DataFrame]:
    """
    Prepare output frames using programmable downstream schema.
    
    Process:
    1. Split by language (EN, FR from transformed dict)
    2. For each language, get corresponding sheet config from downstream
    3. Apply language-specific column mapping
    4. Rename and filter to output columns
    5. Return keyed by sheet name (Accessories_EN, Accessories_FR)
    """
    # Load downstream schema
    downstream_config = config.get("downstream", {})
    sheets_config = downstream_config.get("sheets", {})
    
    frames: Dict[str, pd.DataFrame] = {}
    
    for lang, df in transformed.items():
        # Find corresponding sheet config (Accessories_EN, Accessories_FR, etc.)
        sheet_key = _find_sheet_for_language(sheets_config, lang)
        if not sheet_key:
            continue
            
        sheet_config = sheets_config[sheet_key]
        
        # Build column mapping for this language
        col_mapping = _build_language_specific_mapping(sheet_config)
        
        # Apply transformations
        df = _apply_column_mapping(df, col_mapping)
        df = _enrich_with_metadata(df, meta_data)
        df = _filter_to_output_columns(df, sheet_config)
        df = _apply_sorting(df, sheet_config)
        
        frames[sheet_key] = df
    
    return frames
```

### Step 4: Update base_pipeline.py Config Loading

Change from:
```python
config["rate_import_column_mapping"] = ...
config["rate_import_required_columns"] = ...
```

To:
```python
# Load full downstream schema (not just mapping)
downstream_schema = loader.load_downstream_schema()
config["downstream"] = downstream_schema
```

---

## 🛠️ Implementation Steps

### Phase A: Schema Design & Investigation (1 hour)

- [ ] Read `output_writer.py` to find "label default" issue
- [ ] Check latest output file sheet names to confirm issue
- [ ] Review current Hyundai downstream.yaml structure
- [ ] Validate proposed downstream.yaml structure

**Deliverable:** Investigation report + proposed downstream.yaml

### Phase B: Core Implementation (2 hours)

#### Step B1: Update downstream.yaml
- [ ] Create new schema with explicit source→output mapping
- [ ] Add separate EN/FR sheet definitions
- [ ] Include all column specifications
- [ ] Document each column's origin and purpose

#### Step B2: Create column_mapper_v2.py
- [ ] Implement `build_column_mapping()`
- [ ] Implement `get_columns_for_sheet()`
- [ ] Implement `get_column_spec()`
- [ ] Add unit tests

#### Step B3: Refactor step5_output.py
- [ ] Replace hardcoded metadata enrichment
- [ ] Implement programmable column mapping
- [ ] Add language-specific column selection
- [ ] Handle Trim column from runtime
- [ ] Add sorting support

#### Step B4: Update base_pipeline.py
- [ ] Change config loading keys
- [ ] Pass full downstream schema to step5

#### Step B5: Fix "label default" Issue
- [ ] Update sheet creation to use display_name
- [ ] Verify Excel output has correct sheet names

**Deliverable:** All files updated, tests passing

### Phase C: Testing & Validation (1 hour)

- [ ] Run Hyundai pipeline end-to-end
- [ ] Verify output columns match expected
- [ ] Check sheet names are correct (no "label default")
- [ ] Verify English/French separation works
- [ ] Spot check data accuracy (Trim, model_number, etc.)
- [ ] Test all OEMs (Mazda, Mitsubishi, Honda)

**Deliverable:** Test results, all OEMs passing

### Phase D: Future-Proofing (30 min)

- [ ] Document how to add new columns
- [ ] Create example: "Add a new column to downstream"
- [ ] Update CONFIG_GUIDE.md with column addition steps

**Deliverable:** Documentation update

---

## 📊 Impact Analysis

### What Changes
| Component | Change | Risk |
|-----------|--------|------|
| downstream.yaml | Complete restructure | MEDIUM - schema change |
| step5_output.py | Refactor logic | MEDIUM - behavior change |
| base_pipeline.py | Config key changes | LOW - isolated |
| output_writer.py | Sheet naming | LOW - likely fix |

### What Stays the Same
- ✅ Step 1-4 pipeline (validation through transformation)
- ✅ Model enrichment (step 4.5)
- ✅ DQ logging (separate sheets)
- ✅ Audit trail (separate sheets)

### Backward Compatibility
- ❌ NOT backward compatible with old output
- ✅ But all code is fresh (just deployed Phase 5)
- ✅ No existing consumers yet

---

## ✅ Success Criteria

1. **Output columns match exactly:**
   - [ ] Year, Model, Part, Description, Comments, Price, Hours, Trim, model_number
   - [ ] No extra columns (no group_key, year_from, etc.)
   - [ ] No missing columns

2. **Language separation:**
   - [ ] EN sheet has "Accessories (English)" tab
   - [ ] FR sheet has "Accessories (Français)" tab
   - [ ] EN uses Description + Comments
   - [ ] FR uses Description_FR + Comments_FR

3. **No "label default":**
   - [ ] All sheet names are human-readable
   - [ ] No Excel default names ("Sheet1", etc.)
   - [ ] display_name used correctly

4. **Programmatic:**
   - [ ] Adding new column requires only downstream.yaml edit
   - [ ] No code changes needed for new columns
   - [ ] Column mapping is data-driven

5. **Testing:**
   - [ ] All 4 OEMs pass with new schema
   - [ ] Data accuracy verified
   - [ ] Performance acceptable

---

## 📝 Questions for Clarification

Before implementation:

1. **"label default" issue** — Can you:
   - [ ] Show me the Excel output file with the issue?
   - [ ] Tell me the exact sheet names you see?
   - [ ] Check if it's on the "Accessories" sheet or DQ sheets?

2. **Trim column** — Should it:
   - [ ] Always be present (required)?
   - [ ] Be optional if not available?
   - [ ] Sort by Trim value?

3. **Model column** — Should it:
   - [ ] Be second column (after Year)?
   - [ ] Or somewhere else in the order?

4. **Sorting** — Current order:
   - Year ascending, Model ascending, Part ascending
   - Is this correct?

5. **Future columns** — Can you provide examples of columns you might add later?
   - This helps validate the design is truly future-proof

---

## 📅 Timeline

| Phase | Duration | Effort |
|-------|----------|--------|
| A: Investigation | 1 hour | Clarify issues |
| B: Implementation | 2 hours | Code changes |
| C: Testing | 1 hour | Validation |
| D: Documentation | 30 min | Future-proofing |
| **TOTAL** | **4.5 hours** | **All phases** |

---

## 🚀 Next Steps

1. **Read this plan** and provide answers to clarification questions
2. **Approve proposed downstream.yaml structure** (especially sheet names, column order)
3. **Start Phase A** (investigate "label default")
4. **Proceed with Phase B-D** once schema approved

**Ready to proceed?** Answer the clarification questions above and I'll create the implementation!

