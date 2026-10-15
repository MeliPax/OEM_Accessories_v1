# Honda Data Cleaning Summary — What Gets Cleaned & When

---

## CLEANING PIPELINE OVERVIEW

```
┌────────────────────────────────────────────────────────────────┐
│ STEP 1: VALIDATION (step1_validation.py)                       │
├────────────────────────────────────────────────────────────────┤
│ INPUT:  Raw Excel file (171 rows)                              │
│                                                                 │
│ DETECTS (doesn't fix, just logs):                              │
│  • Empty rows (17 rows → not defects, data cleanup)            │
│  • Unicode issues (smart quotes, unicode spaces)               │
│  • Newlines in headers/descriptions                            │
│  • Composite part numbers ("X or Y")                           │
│  • Special trim markers (•, ✓, 0, 0.0)                         │
│                                                                 │
│ OUTPUT: Validation report + metadata                           │
│         File passes (no fatal errors)                          │
└────────────────────────────────────────────────────────────────┘
                          ↓
┌────────────────────────────────────────────────────────────────┐
│ STEP 2: HEADER NORMALIZATION (step2_header_normalization.py)   │
├────────────────────────────────────────────────────────────────┤
│ INPUT:  Validated df (128-130 data rows)                       │
│                                                                 │
│ ACTIONS:                                                       │
│  ✓ Extract section headers                                    │
│  ✓ Normalize column names (numéro→part_number, prix→list_price)│
│  ✓ Detect trim columns (per section)                          │
│  ✓ Classify records (parent/child/subsection_label)           │
│  ✓ Skip empty rows (return None, omit from record_types)      │
│                                                                 │
│ NOT CLEANED HERE:                                              │
│  ✗ Unicode normalization (happens later in step 2.5)          │
│  ✗ Newline removal                                             │
│  ✗ Composite part splitting                                    │
│                                                                 │
│ OUTPUT: Normalized column names, classification metadata       │
└────────────────────────────────────────────────────────────────┘
                          ↓
┌────────────────────────────────────────────────────────────────┐
│ STEP 2.5: STRING STANDARDIZATION (NEW FILE)                    │
│ (step2_string_standardization.py)                              │
├────────────────────────────────────────────────────────────────┤
│ INPUT:  Classified df (clean structure, dirty strings)         │
│                                                                 │
│ CLEANING OPERATIONS (in order):                                │
│                                                                 │
│ 1. UNICODE NORMALIZATION                                       │
│    "Platinum White Pearl (NH-883P)"  ← curly quotes            │
│    ↓                                                            │
│    "Platinum White Pearl (NH-883P)"  ← ASCII quotes ✓          │
│                                                                 │
│ 2. NEWLINE REMOVAL                                             │
│    "SPORT \nHybrid" (literal newline)                          │
│    ↓                                                            │
│    "Sport Hybrid" ✓                                            │
│                                                                 │
│ 3. WHITESPACE NORMALIZATION                                    │
│    "  Racing   Package  "                                      │
│    ↓                                                            │
│    "Racing Package" ✓                                          │
│                                                                 │
│ 4. COMPOSITE PART SPLITTING                                    │
│    Part: "480-670-6545-SP or 480-670-6545-GB"                 │
│    ↓                                                            │
│    Part: "480-670-6545-SP"                                    │
│    Comments: "[Composite: 480-670-6545-SP or 480-670-6545-GB]"│
│                                                                 │
│ 5. CASE STANDARDIZATION                                        │
│    "RACING package"                                            │
│    ↓                                                            │
│    "Racing Package" ✓                                          │
│                                                                 │
│ 6. ABBREVIATION EXPANSION (translator.yaml)                    │
│    "HEV Sport"                                                 │
│    ↓                                                            │
│    "Hybrid Sport" ✓                                            │
│                                                                 │
│ 7. DUPLICATE WORD REMOVAL                                      │
│    "Hybrid Hybrid Sport"                                       │
│    ↓                                                            │
│    "Hybrid Sport" ✓                                            │
│                                                                 │
│ 8. TRIM MARKER NORMALIZATION                                   │
│    Trim cell: "•"                                              │
│    ↓                                                            │
│    Trim cell: "applicable" ✓                                   │
│                                                                 │
│ 9. MARKUP REMOVAL                                              │
│    "Racing Package (EN)"                                       │
│    ↓                                                            │
│    "Racing Package" ✓                                          │
│                                                                 │
│ 10. TYPE COERCION (numeric columns)                            │
│    "6612.00" (string)                                          │
│    ↓                                                            │
│    6612.0 (float) ✓                                            │
│                                                                 │
│ 11. RANGE VALIDATION                                           │
│    list_price: 6612.0 (within 0-50000)                        │
│    ✓ PASS                                                      │
│                                                                 │
│ 12. PATTERN VALIDATION                                         │
│    part_number: "26TYPER-RACE"                                │
│    Matches pattern: ^[A-Z0-9-]+$                               │
│    ✓ PASS                                                      │
│                                                                 │
│ OUTPUT: Clean df (strings normalized, types enforced)          │
│ DQ LOG: Unicode normalizations=10, composite splits=5,         │
│         marker normalizations=42                               │
└────────────────────────────────────────────────────────────────┘
                          ↓
┌────────────────────────────────────────────────────────────────┐
│ STEP 3: STANDARDIZATION (step3_standardization.py)             │
├────────────────────────────────────────────────────────────────┤
│ INPUT:  String-standardized df                                 │
│                                                                 │
│ VALIDATION ONLY (no further cleaning):                         │
│  ✓ Trim applicability validation (no all-empty rows)          │
│  ✓ Parent-child relationship validation                        │
│  ✓ Rollup price validation                                     │
│                                                                 │
│ OUTPUT: Classification metadata, DQ validation log             │
└────────────────────────────────────────────────────────────────┘
                          ↓
┌────────────────────────────────────────────────────────────────┐
│ STEP 4: TRANSFORMATION (step4_transformation.py)               │
├────────────────────────────────────────────────────────────────┤
│ INPUT:  Classified, validated df                               │
│                                                                 │
│ TRANSFORMATION:                                                │
│  • Melt wide-to-long format (one row per trim)                │
│  • Explode parent-child relationships                         │
│  • EN/FR reconciliation                                        │
│                                                                 │
│ OUTPUT: Long-format df (ready for enrichment)                  │
└────────────────────────────────────────────────────────────────┘
                          ↓
┌────────────────────────────────────────────────────────────────┐
│ STEP 4.5: MODEL ENRICHMENT (step4_5_model_enrichment.py)       │
├────────────────────────────────────────────────────────────────┤
│ INPUT:  Long-format df                                         │
│                                                                 │
│ ENRICHMENT:                                                    │
│  • Tokenize trim level                                        │
│  • Query VehicleSearchEngine                                  │
│  • Resolve model numbers                                       │
│                                                                 │
│ OUTPUT: Enriched df (with model_number, model_status)          │
└────────────────────────────────────────────────────────────────┘
                          ↓
┌────────────────────────────────────────────────────────────────┐
│ STEP 5: OUTPUT (step5_output.py)                               │
├────────────────────────────────────────────────────────────────┤
│ INPUT:  Enriched df                                            │
│                                                                 │
│ FINAL FORMATTING:                                              │
│  • Uppercase ModelNumber                                       │
│  • Title Case Description                                      │
│  • Format currencies                                           │
│                                                                 │
│ OUTPUT: Excel workbook (multiple sheets)                       │
└────────────────────────────────────────────────────────────────┘
```

---

## CLEANING BY COLUMN

### description (Most Cleaning Operations)

| Operation | Input | Output | Status |
|-----------|-------|--------|--------|
| Normalize Unicode | `"Platinum White Pearl (NH-883P)"` (curly quotes) | `"Platinum White Pearl (NH-883P)"` (ASCII) | ✅ NEW |
| Remove Newlines | `"SPORT \nHybrid"` | `"Sport Hybrid"` | ✅ NEW |
| Trim Whitespace | `"  Racing Package  "` | `"Racing Package"` | ✅ Existing |
| Standardize Case | `"RACING PACKAGE"` | `"Racing Package"` | ✅ Existing |
| Abbreviations | `"HEV Sport"` | `"Hybrid Sport"` | ✅ Existing |
| Deduplicate | `"Hybrid Hybrid"` | `"Hybrid"` | ✅ Existing |
| Remove Markup | `"Racing Package (EN)"` | `"Racing Package"` | ✅ Existing |

---

### part_number (Part/Combo Handling)

| Operation | Input | Output | Status |
|-----------|-------|--------|--------|
| Normalize Unicode | `"480-670-6545-SP"` (if smart quotes) | `"480-670-6545-SP"` | ✅ NEW |
| Split Composite | `"480-670-6545-SP or 480-670-6545-GB"` | Primary: `"480-670-6545-SP"` | ✅ NEW |
| Uppercase | `"abc123"` | `"ABC123"` | ✅ Existing |
| Trim Whitespace | `"  ABC123  "` | `"ABC123"` | ✅ Existing |
| Pattern Validation | `"ABC-123"` | `"ABC-123"` (matches `^[A-Z0-9-]+$`) | ✅ Existing |

---

### list_price (Numeric Cleaning)

| Operation | Input | Output | Status |
|-----------|-------|--------|--------|
| Remove Currency | `"$6,612.00"` | `"6612.00"` | ✅ Existing |
| Convert Float | `"6612.00"` | `6612.0` | ✅ Existing |
| Range Validation | `6612.0` | ✓ (within 0-50000) | ✅ Existing |

---

### Trim Columns (applicability markers)

| Operation | Input | Output | Status |
|-----------|-------|--------|--------|
| Normalize Markers | `"•"` | `"applicable"` | ✅ NEW |
| Normalize Markers | `"✓"` | `"applicable"` | ✅ NEW |
| Normalize Markers | `"S"` | `"standard"` | ✅ NEW |
| Normalize Markers | `"T"` | `"tire_change"` | ✅ NEW |
| Normalize Markers | `"E"` | `"exchange"` | ✅ NEW |
| Normalize Markers | `"0"` or `"0.0"` | `null` | ✅ NEW |
| Normalize Markers | `""` or `"N/A"` | `null` | ✅ NEW |

---

### comments (Minimal Cleaning)

| Operation | Input | Output | Status |
|-----------|-------|--------|--------|
| Normalize Unicode | `"10% Discount..."` (curly quotes) | ASCII quotes | ✅ NEW |
| Remove Newlines | `"Priced as a set\n\nIncludes..."` | `"Priced as a set Includes..."` | ✅ NEW |
| Trim Whitespace | `"  Note  "` | `"Note"` | ✅ Existing |

---

## Before/After Example

**Row 26 from Honda data (Aero Kit package):**

### BEFORE (Raw Excel)

```
Description:  "Aero Kit"
Part Number:  "25CIV5-ARO-PK"
List Price:   "1101.6"
Dealer Net:   "660.6"
FRT:          "2.2"
Installed:    "1499.8"
Comments:     "10% Discount Applied.  \n\nIncludes body coloured front underbody spoiler..."
Trim Col 1:   "•"
Trim Col 2:   "•"
Trim Col 3:   "0"
```

### AFTER (Step 2.5 Standardization)

```
Description:  "Aero Kit"  ← Cleaned (already good, just verified)
Part Number:  "25CIV5-ARO-PK"  ← Uppercase, validated
List Price:   1101.6  ← Converted to float
Dealer Net:   660.6  ← Converted to float
FRT:          2.2  ← Converted to float
Installed:    1499.8  ← Converted to float
Comments:     "10% Discount Applied. Includes body coloured front..."  ← Newlines removed, normalized
Trim Col 1:   "applicable"  ← Marker normalized
Trim Col 2:   "applicable"  ← Marker normalized
Trim Col 3:   null  ← Placeholder converted to empty
```

---

## Comparison: Existing OEMs vs Honda

### Hyundai/Genesis (Full Feature Set)

```yaml
Description operations:
  - trim_whitespace ✓
  - standardize_case ✓
  - standardize_abbreviations ✓
  - deduplicate_words ✓
  - remove_markup ✓
```

### Honda (Extended for Section-Based Data)

```yaml
Description operations:
  - normalize_unicode ✓ (NEW)
  - remove_newlines ✓ (NEW)
  - trim_whitespace ✓
  - standardize_case ✓
  - standardize_abbreviations ✓
  - deduplicate_words ✓
  - remove_markup ✓

part_number operations:
  - normalize_unicode ✓ (NEW)
  - split_composite ✓ (NEW)
  - uppercase ✓
  - trim_whitespace ✓

trim_columns operations:
  - normalize_trim_markers ✓ (NEW)
  - trim_whitespace ✓
```

---

## Implementation Files Required

### NEW FILES

1. **`accy_v2/oems/honda/config/standardization.yaml`** (90 lines)
   - Per-column transformation pipeline definitions
   - Extends Hyundai pattern with 4 Honda-specific operations

2. **`accy_v2/oems/honda/pipeline/step2_string_standardization.py`** (200 lines)
   - Implements config-based transformations from standardization.yaml
   - Functions: normalize_unicode, remove_newlines, split_composite, map_trim_markers
   - Integrates with DQ logger for audit trail

### UPDATED FILES

1. **`accy_v2/oems/honda/config/schemas/upstream.yaml`**
   - Add `data_quality` section (detection rules, not fixes)
   - Document known issues (unicode, newlines, composite parts)

2. **`accy_v2/oems/honda/pipeline/step3_standardization.py`**
   - No changes (Phase 2 validation already complete)

---

## Testing Strategy

### Unit Tests (test file per operation)

```
test_normalize_unicode.py
  - Test smart quotes → ASCII
  - Test unicode spaces → space
  - Test various unicode dashes → hyphen

test_remove_newlines.py
  - Test literal \n removal
  - Test multiple consecutive newlines
  - Test preservation of meaningful spaces

test_split_composite.py
  - Test "X or Y" split (keep first)
  - Test "X ou Y" (FR variant)
  - Test notes added to comments

test_normalize_trim_markers.py
  - Test • → applicable
  - Test ✓ → applicable
  - Test 0, 0.0, "", N/A → null
  - Test S, T, E → correct states
```

### Integration Tests

```
test_phase2_with_real_data.py
  - Load CVIC5D.xlsx (actual Honda file)
  - Run Step 1-2 full pipeline
  - Verify:
    - 128-130 classified records
    - 0 false defects
    - Unicode issues normalized
    - Composite parts split
    - Trim markers mapped
    - All types validated
```

---

## Effort Breakdown

| Task | Hours | Notes |
|------|-------|-------|
| Create standardization.yaml | 2 | Config-based, mirrors Hyundai |
| Implement step2_string_standardization.py | 6 | 4 operations, DQ logging |
| Unit tests (5 test files) | 3 | Coverage for all 4 operations |
| Integration test | 2 | End-to-end with real data |
| Documentation | 1 | Update README, config docs |
| **TOTAL** | **~14 hours** | Phase 2.5 (between normalization & standardization) |

---

## Key Decisions

✅ **Extend Hyundai pattern** — Don't reinvent wheel; use proven architecture  
✅ **Config-driven operations** — New operations defined in standardization.yaml  
✅ **Insert at Step 2.5** — After header extraction, before step 3 validation  
✅ **Audit trail** — All transformations logged to DQ logger  
✅ **Non-destructive** — Original data preserved in comments (composite parts)  

