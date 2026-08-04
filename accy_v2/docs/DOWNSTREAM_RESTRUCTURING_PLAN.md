# Downstream Schema Restructuring Plan

**Status:** Ready for Implementation
**Date:** 2026-08-03
**Priority:** HIGH (Blocks clean output)

---

## 🔍 Root Cause Analysis: "label default" Issue

### Issue Found ✅

**Sheet names in output:** `elantra_default`, `g70_default`, `g80_default`, etc.

**Root cause:** `_split_by_language()` returns `{"default": df}` instead of language-specific keys

**Location:** `accy_v2/oems/hyundai/pipeline/step4_transformation.py:84`

```python
def _split_by_language(df: pd.DataFrame, config: dict) -> Dict[str, pd.DataFrame]:
    """Split DataFrame into language-specific views (EN, FR)."""
    language_columns = config.get("language_columns", {})
    if not language_columns:
        return {"default": df}  # ← PROBLEM: Returns "default" instead of language codes
```

**Why it happens:**

1. `config["language_columns"]` is not set (doesn't exist in current config)
2. Function defaults to `{"default": df}` as fallback
3. This "default" becomes the language key in sheet names

**Fix:** Provide proper language configuration so it returns `{"EN": df, "FR": df}`

---

## 🎯 Complete Solution

### Part 1: Add Language Configuration to Intermediate Schema

File: `accy_v2/oems/hyundai/config/schemas/intermediate.yaml`

Add this section:

```yaml
# Language handling
languages:
  EN:
    # English columns to keep
    description_column: Description
    comments_column: Comments
  
  FR:
    # French columns to keep
    description_column: Description_FR
    comments_column: Comments_FR

# Columns to split by language (rest are shared)
language_specific_columns:
  EN:
    - Description
    - Comments
  FR:
    - Description_FR
    - Comments_FR
```

### Part 2: Load Language Config in base_pipeline.py

Update `_build_legacy_config()`:

```python
# Add language_columns for step4_transformation
intermediate_schema = upstream_schema.get("schema", {})
language_cols = intermediate_schema.get("language_specific_columns", {})

return {
    # ... existing keys ...
    "language_columns": language_cols,  # ← Add this
}
```

### Part 3: Update step5_output.py Sheet Naming

Change from:

```python
sheet_key = f"{model_name}_{lang}"[:31]  # Creates "elantra_default"
```

To:

```python
# Map language codes to display names
language_display_map = {
    "EN": "Accessories (English)",
    "FR": "Accessories (Français)",
    "default": "Accessories"  # Fallback
}

sheet_key = f"{model_name}_{lang}"[:31]  # "elantra_EN" or "elantra_FR"
display_name = language_display_map.get(lang, f"Accessories ({lang})")
```

### Part 4: Update downstream.yaml

Replace the current single "Accessories" sheet with language-specific configuration:

```yaml
sheets:
  # English Sheet
  Accessories_EN:
    display_name: "Accessories (English)"
    language: EN
    data_source: primary
  
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
        source_column: Description  # ← EN specific
        data_type: string
        width: 50
      
      - output_column: Comments
        source_column: Comments  # ← EN specific
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
        source_column: trim_level
        data_type: string
        width: 20
      
      - output_column: model_number
        source_column: model_number
        data_type: string
        width: 15

  # French Sheet
  Accessories_FR:
    display_name: "Accessories (Français)"
    language: FR
    data_source: primary
  
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
        source_column: Description_FR  # ← FR specific
        data_type: string
        width: 50
      
      - output_column: Comments
        source_column: Comments_FR  # ← FR specific
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
        source_column: trim_level
        data_type: string
        width: 20
      
      - output_column: model_number
        source_column: model_number
        data_type: string
        width: 15

  # Keep existing DQ sheets
  _Data_Issues:
    display_name: "Data Issues"
    # ... existing config ...
  
  _Report:
    display_name: "Summary Report"
    # ... existing config ...
```

---

## 📋 Implementation Checklist

### Phase 1: Schema Updates (15 min)

- [ ] Add language configuration to `intermediate.yaml`
- [ ] Update `downstream.yaml` with new sheet structure
- [ ] Add language_columns mapping to base_pipeline.py

### Phase 2: Code Updates (30 min)

- [ ] Update step4_transformation.py `_split_by_language()` (if needed)
- [ ] Update step5_output.py sheet naming
- [ ] Update output_writer.py sheet creation (if needed)
- [ ] Create column_mapper_v2.py for programmable mapping

### Phase 3: Testing (30 min)

- [ ] Run Hyundai pipeline
- [ ] Verify sheet names: `elantra_EN`, `elantra_FR`, etc.
- [ ] Verify column mappings
- [ ] Check English sheet has Description (not Description_FR)
- [ ] Check French sheet has Description_FR (not Description)
- [ ] Verify output columns exactly: Year, Model, Part, Description, Comments, Price, Hours, Trim, model_number
- [ ] Test all 4 OEMs

### Phase 4: Documentation (15 min)

- [ ] Update CONFIG_GUIDE.md
- [ ] Document column addition process
- [ ] Update SYSTEM_ARCHITECTURE.md

---

## 🔄 Data Flow After Fix

```
step4_transformation._split_by_language()
  Input: melted_df with Description, Description_FR, Comments, Comments_FR
  
  Config language_columns: {
    "EN": ["Description", "Comments"],
    "FR": ["Description_FR", "Comments_FR"]
  }
  
  Output: {
    "EN": df with Description, Comments (Description_FR, Comments_FR dropped),
    "FR": df with Description_FR, Comments_FR (Description, Comments dropped)
  }
    ↓
step5_output.prepare_frames()
  Per language (EN, FR):
    - Apply language-specific column mapping
    - Rename: Description → Description, Comments → Comments (both langs)
    - Select output columns: Year, Model, Part, Description, Comments, Price, Hours, Trim, model_number
    - Create sheet key: "elantra_EN", "elantra_FR"
    ↓
output_writer.write_combined_output()
  Excel sheet: "Accessories (English)" [elantra_EN data]
  Excel sheet: "Accessories (Français)" [elantra_FR data]
```

---

## ✅ Success Criteria

- [ ] No "default" in sheet names
- [ ] Sheet names: `elantra_EN`, `elantra_FR`, `g70_EN`, etc.
- [ ] Display names human-readable: "Accessories (English)", "Accessories (Français)"
- [ ] Output columns: Year, Model, Part, Description, Comments, Price, Hours, Trim, model_number
- [ ] EN sheet has Description (English), FR sheet has Description_FR (French)
- [ ] All 4 OEMs pass testing
- [ ] Data accuracy verified

---

## 📝 Column Mapping Examples

### English Sheet (Accessories_EN)

```
Source → Output:
  ModelYear → Year
  ModelName → Model
  PartNumber → Part
  Description → Description (English)
  Comments → Comments (English)
  MSRP → Price
  LaborHours → Hours
  trim_level → Trim
  model_number → model_number
```

### French Sheet (Accessories_FR)

```
Source → Output:
  ModelYear → Year
  ModelName → Model
  PartNumber → Part
  Description_FR → Description (French)
  Comments_FR → Comments (French)
  MSRP → Price
  LaborHours → Hours
  trim_level → Trim
  model_number → model_number
```

---

## 🚀 Ready to Implement?

This plan:

1. ✅ Fixes the "label default" issue
2. ✅ Separates English and French sheets
3. ✅ Uses programmable column mapping
4. ✅ Makes future additions easy
5. ✅ Maintains backward compatibility with test results

**Next step:** Proceed with Phase 1-4 implementation?
