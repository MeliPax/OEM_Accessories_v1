# Honda Pipeline Design Rules

## Rule 1: Configuration-Driven Column Definitions

**Principle**: All column names, categories, and relationships MUST be defined in configuration files, NOT hard-coded in Python source code.

**Why**: 
- Enables code reuse across OEMs without modification
- Makes Honda pipeline testable with different data structures
- Centralizes changes: update config, not code
- Follows DRY principle and separation of concerns

### Declaration Level (Config)

All column definitions go in `accy_v2/oems/honda/config/schemas/detection.yaml`:

```yaml
column_categories:
  # Product columns required for parent/child classification
  product_columns:
    - "part_number"
    - "description"

  # Price columns required for parent classification  
  price_columns:
    - "dealer_net"
    - "list_price"
    - "frt"
    - "installed_price"
```

### Usage Level (Code)

Read from config in all phases:

```python
# Phase 1: Validation
column_categories = detection_config.get("column_categories", {})
product_columns = column_categories.get("product_columns", [])
price_columns = column_categories.get("price_columns", [])
```

**DO NOT DO THIS** (❌ Hard-coded):
```python
# WRONG: Hard-coded column names
price_columns = ["dealer_net", "list_price", "frt", "installed_price"]  # NO!
```

### Audit Checklist

- [ ] All column names defined in `column_categories` section of `detection.yaml`
- [ ] All phases read from config, not hard-coded
- [ ] Functions accept column names as parameters where needed
- [ ] Default fallbacks use config values, not new hard-coded values
- [ ] Tests verify columns are read from config, not bypassed

### Current Implementation Status

✅ **Phase 2 (Header Normalization)**
- Column definitions now read from config at line 40-42
- `_classify_record_type()` accepts `product_columns`, `price_columns` parameters
- `price_columns` in metadata output uses config value

---

## Rule 2: Section Classifications by Config

**Principle**: Section type (package vs non-package) MUST be determined from config, not string matching.

**Why**:
- Enables EN/FR support without code changes
- Section names vary by language but config maps them consistently

### Declaration Level (Config)

```yaml
section_classification:
  sections:
    - name: "Packages and Kits"
      is_package: true
      markers_en:
        - "packages and kits"
        - "packages & kits"
      markers_fr:
        - "groupes et ensembles"
```

### Usage Level (Code)

Lookup section type from config:

```python
# Right way
is_package = False
for section_def in config.get("section_classification", {}).get("sections", []):
    markers_en = section_def.get("markers_en", [])
    markers_fr = section_def.get("markers_fr", [])
    all_markers = [m.lower() for m in markers_en + markers_fr]
    if section_name.lower() in all_markers:
        is_package = section_def.get("is_package", False)
        break
```

**DO NOT DO THIS** (❌ String matching):
```python
# WRONG: Hard-coded section name matching
is_package = "package" in section_name.lower()  # NO!
```

### Current Implementation Status

✅ **Phase 2 (Header Normalization)**
- Section classification lookup implemented at lines 73-84
- Supports both EN and FR section names via markers

---

## Rule 3: Language-Aware Column Normalization

**Principle**: Column name variants for ALL supported languages MUST be in `column_normalizations`.

**Why**:
- Ensures reproducible behavior across translations
- Prevents encoding/Unicode surprises
- Centralizes translation maintenance

### Declaration Level (Config)

```yaml
column_normalizations:
  part_number:
    - "part number"
    - "part#"
    - "pièce"
    - "numéro de pièce"
    - "num´ro de pi´ce"      # Exact variant from actual Excel file
```

### Usage Level (Code)

Read variants from config, apply uniformly:

```python
column_normalizations = config.get("column_normalizations", {})
for norm_name, variations in column_normalizations.items():
    for variation in variations:
        reverse_mapping[variation.lower()] = norm_name
```

### Current Implementation Status

⚠️ **Phase 2 (Header Normalization)**
- Config variants are used for mapping
- **Known Issue**: Unicode accent matching incomplete for FR file
  - File has: `'Num´ro de pi´ce'` (specific accent encoding)
  - Config has: `'num´ro de pi´ce'` (may use different Unicode)
  - **Action needed**: Determine exact Unicode chars in Excel file and match exactly in config

---

## Rule 4: No Hard-Coded DQ Rule Names

**Principle**: DQ (Data Quality) rule names and messages MUST be defined in config, not code.

**Why**:
- Ensures consistent error messages across phases
- Enables translation/localization of messages
- Allows changing rules without code review

### Declaration Level (Config)

```yaml
dq_rules:
  column_name_mismatch_rule:
    name: "column_name_mismatch_rule"
    description: "Raw column name doesn't match any mapping"
  
  orphaned_child_rule:
    name: "orphaned_child_rule"
    description: "Child record found with no preceding parent"
```

### Usage Level (Code)

Reference rule name from config:

```python
rule_name = config["dq_rules"]["orphaned_child_rule"]["name"]
dq_logger.log_warning(
    rule_violated=rule_name,
    issue_description="..."
)
```

### Current Implementation Status

⚠️ **Phase 2**
- DQ rule names currently hard-coded in code
- **Action needed**: Move all rule names to `dq_rules` section of `detection.yaml`

---

## Implementation Roadmap

### Phase 2 (Complete ✅)
- [x] Extract `column_categories` from config
- [x] Extract `section_classification` lookup
- [x] Remove hard-coded column names
- [ ] Move DQ rule names to config

### Phase 3 (Planned)
- [ ] Ensure column names read from config
- [ ] Ensure price fill-down uses configured `price_columns`
- [ ] Validate all hard-coded column references removed

### Phase 4-5 (Future)
- [ ] Apply same rules to standardization, transformation, model enrichment
- [ ] Audit all OEM implementations for hard-coded columns

---

## Violation Detection

To find violations, search for:

```bash
# Hard-coded column name lists
grep -n '\["dealer_net".*"list_price".*"frt"' accy_v2/oems/honda/pipeline/*.py

# Hard-coded string matching for section types
grep -n '"package" in section_name' accy_v2/oems/honda/pipeline/*.py

# DQ rule names in code (not config)
grep -n 'log_warning.*rule' accy_v2/oems/honda/pipeline/*.py | grep -v config
```

---

## Testing Strategy

All tests MUST verify config is used, not hard-coded:

```python
def test_column_categories_from_config():
    """Verify Phase 2 reads columns from config, not hard-coded"""
    config = load_config()
    meta_data = {"sheet_name": "test"}
    df_out, meta_out = step2.run(df, config, meta_data, dq_logger, logger)
    
    # Verify metadata uses config values
    config_prices = config["step1_detection"]["column_categories"]["price_columns"]
    assert meta_out["price_columns"] == config_prices, \
        "Price columns must match config, not hard-coded values"
```

---

**Last Updated**: 2026-10-13  
**Status**: Active Design Rule  
**Owner**: Phase 2 Implementation
