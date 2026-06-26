# Test Strategy

**Document:** Planning  
**Created:** June 26, 2026  
**Status:** Draft - For Review  
**Related:** `02_AUTOMATED_CHECKS.md`

---

## Overview

This document outlines the testing strategy for the OEM Accessory Pipeline: what to test, where to put tests, and how to measure coverage.

**Key Principle:** Tests are organized by type (unit, integration), each type has specific responsibilities.

---

## Test Folder Structure

```
accy_v2/
├── tests/
│   ├── __init__.py
│   ├── conftest.py                    # Shared fixtures
│   ├── unit/
│   │   ├── test_config_loader.py
│   │   ├── test_column_mapper.py
│   │   ├── test_header_helpers.py
│   │   ├── test_trim_helpers.py
│   │   ├── test_dq_logger.py
│   │   ├── test_pipeline_logger.py
│   │   ├── mitsubishi/
│   │   │   ├── test_step1_validation.py
│   │   │   ├── test_step2_header_normalization.py
│   │   │   ├── test_step3_standardization.py
│   │   │   ├── test_step4_transformation.py
│   │   │   └── test_step5_output.py
│   │   ├── mazda/
│   │   │   ├── test_step1_validation.py
│   │   │   ├── test_step2_header_normalization.py
│   │   │   ├── test_step3_standardization.py
│   │   │   ├── test_step4_transformation.py
│   │   │   └── test_step5_output.py
│   │   └── model_lookup/
│   │       └── test_manufacture_module.py
│   ├── integration/
│   │   ├── test_mitsubishi_pipeline_e2e.py
│   │   ├── test_mazda_pipeline_e2e.py
│   │   └── test_output_schema.py
│   └── fixtures/
│       ├── sample_mitsubishi.xlsx     # Small sample input
│       ├── sample_mazda.csv           # Small sample input
│       ├── expected_output.json       # Expected schema
│       ├── config_test.json           # Test config
│       └── dq_report_sample.json      # Expected DQ report format
```

---

## Unit Tests

**Purpose:** Test individual functions in isolation

**Scope:** Core logic, helpers, utilities

**Data:** Synthetic / mock data (no real pricing)

**Test framework:** pytest

### Test Categories

#### 1. Config Loading & Validation
**File:** `test_config_loader.py`

```python
def test_load_config_valid():
    """Config with valid schema loads without error"""
    
def test_load_config_missing_required_key():
    """Config without required key raises error"""
    
def test_load_config_invalid_type():
    """Config with wrong value type raises error"""
```

#### 2. Column Mapper
**File:** `test_column_mapper.py`

```python
def test_find_column_exact_match():
    """Column name matches exactly"""
    
def test_find_column_keyword_match():
    """Column name matches keywords"""
    
def test_find_column_no_match():
    """No matching column returns None"""
    
def test_word_token_matching():
    """Word-token logic correctly matches/rejects"""
```

#### 3. Header Helpers
**File:** `test_header_helpers.py`

```python
def test_promote_header_row():
    """Row 1 becomes header"""
    
def test_clean_column_name():
    """Column names cleaned and normalized"""
    
def test_strip_values():
    """String values trimmed"""
```

#### 4. Trim Helpers
**File:** `test_trim_helpers.py`

```python
def test_identify_trim_candidates():
    """Columns between boundaries identified"""
    
def test_exclude_category_columns():
    """Category columns excluded by config"""
    
def test_validate_trim_by_datatype():
    """Trim columns validated by X-rate"""
    
def test_trim_validation_threshold():
    """Columns below 60% X-rate fail validation"""
```

#### 5. Data Quality Logger
**File:** `test_dq_logger.py`

```python
def test_log_warning_creates_record():
    """DQ warning logged with all required fields"""
    
def test_log_warning_groups_by_rule():
    """Warnings grouped by rule type"""
    
def test_dq_report_json_valid():
    """DQ report generates valid JSON"""
```

#### 6. Step 1: Validation
**File:** `mitsubishi/test_step1_validation.py`

```python
def test_extract_metadata():
    """Model name extracted from cell A1"""
    
def test_validate_header_keywords():
    """Required columns identified"""
    
def test_drop_brochure_records():
    """YYYY*BROE/BROF records removed"""
    
def test_trim_data_range():
    """Data bounded by first/last part numbers"""
    
def test_validate_non_null_columns():
    """Records with nulls in required columns excluded"""
    
def test_validate_profitability():
    """Unprofitable records flagged in DQ"""
```

#### 7. Step 2: Header Normalization
**File:** `mitsubishi/test_step2_header_normalization.py`

```python
def test_map_columns_to_standard_names():
    """Columns mapped per config keywords"""
    
def test_exclude_trim_candidates():
    """Category columns excluded before validation"""
    
def test_validate_trim_columns():
    """Trim columns validated by datatype"""
```

#### 8. Step 3: Standardization
**File:** `mitsubishi/test_step3_standardization.py`

```python
def test_apply_column_mapping():
    """Columns renamed to standard names"""
    
def test_standardize_data_types():
    """Values converted to expected types"""
    
def test_drop_unwanted_columns():
    """Configured columns dropped"""
```

#### 9. Step 4: Transformation
**File:** `mitsubishi/test_step4_transformation.py`

```python
def test_validate_trim_applicability():
    """Rows with no trim marked 'X' excluded"""
    
def test_melt_trim_columns():
    """Wide-format melted to long-format"""
    
def test_split_by_language():
    """Correct EN/FR split achieved"""
```

#### 10. Step 5: Output
**File:** `mitsubishi/test_step5_output.py`

```python
def test_enrich_output_columns():
    """Output columns selected correctly"""
    
def test_format_for_rate_importer():
    """Rate importer column mapping applied"""
    
def test_generate_report_sheet():
    """Report sheet generated with correct structure"""
```

---

## Integration Tests

**Purpose:** Test end-to-end pipeline behavior

**Scope:** Multiple steps working together

**Data:** Small sample input files (~20-30 rows, fake pricing)

**Test framework:** pytest

**Trigger:** Only on merge to staging (not every push)

### Test Cases

#### 1. Mitsubishi E2E Pipeline
**File:** `integration/test_mitsubishi_pipeline_e2e.py`

```python
def test_mitsubishi_pipeline_success():
    """Full Mitsubishi pipeline runs without FATAL errors"""
    # Load sample data
    # Run pipeline
    # Assert: records_in > 0
    # Assert: records_out > 0
    # Assert: output file exists
    # Assert: output has correct sheets
    
def test_mitsubishi_output_schema():
    """Output columns match expected schema"""
    # Load output
    # Assert: all required columns present
    # Assert: no extra columns in output
    # Assert: data types correct
    
def test_mitsubishi_dq_report_generated():
    """DQ report created with valid structure"""
    # Load DQ report
    # Assert: valid JSON
    # Assert: summary section present
    # Assert: records section present with issues
```

#### 2. Mazda E2E Pipeline
**File:** `integration/test_mazda_pipeline_e2e.py`

```python
def test_mazda_pipeline_success():
    """Full Mazda pipeline runs without FATAL errors"""
    
def test_mazda_output_schema():
    """Output columns match Mazda's structure"""
    
def test_mazda_use_model_lookup_false():
    """Mazda skips step 4.5 (use_model_lookup=false)"""
```

#### 3. Output Schema Validation
**File:** `integration/test_output_schema.py`

```python
def test_output_file_columns():
    """Output file has expected columns in order"""
    expected = ["Part", "Description", "Comments", "Price", "Hours", "Trim", "model_number"]
    
def test_output_data_types():
    """Column values are correct types"""
    # Part: string
    # Price: float
    # Hours: float
    # Trim: string
    
def test_report_sheet_structure():
    """Report sheet has Run Summary, Model Profile, DQ Records"""
    
def test_no_regressions_in_dq_warnings():
    """DQ warning count hasn't increased unexpectedly"""
```

---

## Shared Fixtures

**File:** `conftest.py`

Pytest fixtures shared across all tests:

```python
@pytest.fixture
def sample_mitsubishi_df():
    """Small sample DataFrame with Mitsubishi structure"""
    return pd.DataFrame({
        'part_number': ['MMS001', 'MMS002'],
        'english_description': ['Part A', 'Part B'],
        'french_description': ['Partie A', 'Partie B'],
        'remarks': ['Note 1', 'Note 2'],
        'es': ['X', ''],
        'se': ['X', 'X'],
        'msrp_$': [100.0, 200.0],
        'dnp_$': [50.0, 100.0],
        'install_time': [1.0, 2.0],
        'labour_rate': [125, 125],
    })

@pytest.fixture
def sample_config_mitsubishi():
    """Test configuration for Mitsubishi"""
    return {...}  # Minimal valid config

@pytest.fixture
def sample_config_mazda():
    """Test configuration for Mazda"""
    return {...}  # Minimal valid config
```

---

## Coverage Targets

**Minimum coverage by module:**

| Module | Target |
|--------|--------|
| core/base_pipeline.py | 85% |
| core/config_loader.py | 90% |
| core/helpers/column_mapper.py | 90% |
| core/helpers/header_helpers.py | 85% |
| core/helpers/trim_helpers.py | 90% |
| core/helpers/dq_logger.py | 85% |
| core/helpers/pipeline_logger.py | 80% |
| oems/mitsubishi/pipeline/*.py | 85% |
| oems/mazda/pipeline/*.py | 85% |
| model_lookup/models/manufacture_module.py | 80% |

**Overall target:** >80% coverage

**Measured by:** `pytest --cov=accy_v2 --cov-report=html`

---

## Test Data Management

### Input Fixtures

**Location:** `tests/fixtures/`

**Rules:**
- Small files only (20-30 rows)
- No real pricing or sensitive data
- Designed to cover edge cases:
  - Empty/null values
  - Missing columns
  - Extra columns
  - Boundary cases (first/last row)
  - Brochure records
  - Unprofitable records

**Example structure:**
```
sample_mitsubishi.xlsx
├── 2024 Sample Model   (15 rows)
├── 2023 Sample Model   (12 rows)
└── Test Edge Cases     (8 rows with nulls, extras)
```

### Expected Output Fixtures

**Location:** `tests/fixtures/expected_output.json`

Used to validate output schema:

```json
{
  "sheets": ["_Report", "2024_sample_model_EN", "2024_sample_model_FR"],
  "columns": {
    "_Report": ["Run Summary", "Model Profile", "DQ Records"],
    "data_sheets": ["Part", "Description", "Comments", "Price", "Hours", "Trim", "model_number"]
  },
  "dtypes": {
    "Price": "float64",
    "Hours": "float64",
    "Trim": "object"
  }
}
```

---

## Running Tests Locally

### Run All Tests
```bash
pytest accy_v2/tests/ -v
```

### Run Only Unit Tests
```bash
pytest accy_v2/tests/unit/ -v
```

### Run Only Integration Tests
```bash
pytest accy_v2/tests/integration/ -v --timeout=60
```

### Run with Coverage Report
```bash
pytest accy_v2/tests/ -v --cov=accy_v2 --cov-report=html
# Open htmlcov/index.html in browser
```

### Run Single Test File
```bash
pytest accy_v2/tests/unit/test_column_mapper.py -v
```

### Run Single Test
```bash
pytest accy_v2/tests/unit/test_column_mapper.py::test_find_column_exact_match -v
```

---

## CI Integration

### On Every Push
- ✅ Run unit tests only
- ✅ Report coverage
- ❌ Fail if coverage < 80%
- ❌ Fail if any test fails

### On Merge to Staging
- ✅ Run unit tests
- ✅ Run integration tests
- ✅ Longer timeout for integration tests (60s)
- ❌ Fail if any test fails

---

## Questions for Team

- [ ] Should we use mocking for external dependencies (model lookup DB)?
- [ ] Should integration tests use actual pipeline classes or mock steps?
- [ ] What's the minimum coverage threshold? (80% recommended)
- [ ] Should test data be in fixtures/ or generated programmatically?
- [ ] Do we need performance tests (e.g., "pipeline completes in <5 min")?
- [ ] Should failed tests block production deployment? (yes recommended)

---

**Next Document:** Planning README — index of all documents  
**Related:** `02_AUTOMATED_CHECKS.md`
