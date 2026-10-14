# Honda Configuration Architecture

**Date:** 2026-10-14  
**Status:** Consolidated and aligned

## Overview

Honda configuration follows a **clear separation of concerns**: `upstream.yaml` (schema/detection) and `structure.yaml` (parsing rules).

## File Structure

```
accy_v2/oems/honda/config/schemas/

├── upstream.yaml
│   ├── File metadata (format, encoding)
│   ├── Metadata row locations (model, year)
│   ├── Sheet patterns (_APP_EN, _APP_FR, _DATA, etc.)
│   ├── Section structure overview (marker pattern, section list)
│   ├── COLUMNS with language-specific detection (EN/FR)
│   └── Data quality expectations
│
├── structure.yaml
│   ├── Metadata detection keywords
│   ├── Section detection (marker pattern, header/trim/data row rules)
│   ├── Column detection (product vs trim columns)
│   ├── Row classification (empty, publishing, valid data)
│   ├── Section classification (package vs non-package)
│   ├── Parent/child detection rules
│   └── DQ rule specifications
│
├── downstream.yaml
│   └── Output schema (loaded by Step 5)
│
├── enrichment.yaml
│   └── Model lookup configuration
│
├── pipeline.yaml
│   └── Pipeline settings & error handling
│
└── transformations.yaml
    └── Data transformation rules
```

## Key Design Decisions

### 1. **upstream.yaml** = Column Schema + Language-Aware Detection

**Purpose:** Single source of truth for "what columns exist and how to identify them"

**Contains:**
- **columns** section with language-specific `detection` rules
  ```yaml
  columns:
    part_number:
      type: "string"
      required: true
      standardized_name: "part_number"
      detection:
        EN:
          key_words:
            must_have: [part]
            must_have_one_of: [number, '#']
            not_have: [description]
        FR:
          key_words:
            must_have: []
            must_have_one_of: [numéro, numero, pièce, piece]
            not_have: [description]
  ```

**Why separated EN/FR:**
- French headers are fundamentally different from English
- Avoid collision: "description" might map to wrong column if rules aren't language-aware
- Clear intent: each language has explicit rules

**Loaded by:** Step 2 (header_normalization.py) → `config.get("columns")`

### 2. **structure.yaml** = Parsing Rules for File Structure

**Purpose:** Encapsulates all the "how to navigate" logic for structural elements

**Contains:**
- Metadata detection (keywords for model name, year)
- Section detection (marker pattern, header/trim/data row detection)
- Row classification (empty, publishing, valid data)
- Section classification (which sections are packages)
- Parent/child detection rules
- DQ rule specifications

**Why separate file:**
- Distinct concern: "how to find structural elements" vs "what columns exist"
- Reusable for other OEMs with similar section-based layouts
- Easier to audit: structural rules in one place

**Loaded by:** Step 1 (step1_validation.py) → referenced for parsing logic

### 3. **No Redundancy**

- ✅ `detection.yaml` consolidated into `upstream.yaml` + `structure.yaml`
- ✅ `honda_config.yaml` (temporary file) no longer needed
- ✅ Language-specific rules in ONE place: `upstream.yaml`

## Column Detection Flow (Step 2)

```
Raw header: "Numéro de pièce"
        ↓
1. Normalize: lowercase, remove accents → "numero de piece"
2. For each column in upstream.yaml:
   a. Check language (FR) detection rules
   b. Check must_have keywords → all must be present
   c. Check not_have keywords → none should be present
   d. Check must_have_one_of → at least one must be present
3. Match: standardized_name = "part_number"
```

**Key Features:**
- ✅ Position-independent (scans all columns)
- ✅ Language-specific (EN rules ≠ FR rules)
- ✅ Accent-agnostic (é → e, è → e, etc.)
- ✅ Robust to typos (substring matching)

## Structure Detection Flow (Step 1)

```
Raw file → scan for section markers (regex)
         ↓
For each section:
1. Detect header row (keyword scan, max 10 rows)
2. Detect trim sub-header (marker scan, max 5 rows)
3. Set data row boundaries
4. Extract column names from header
         ↓
Metadata output:
- section_structure: {section_name → marker_row, data_start, data_end}
- trim_columns_per_section: {section_name → [col_indices]}
- normalized_headers: {section_name → [col_names]}
- column_mapping: {section_name → {col_idx → std_name}}
```

## Future Extensions

**If Honda file format changes:**
- Update `structure.yaml` keywords/patterns (no code change needed)
- Update `upstream.yaml` columns or language rules (no code change needed)

**If expanding to other OEMs with similar structure:**
- Create `oems/[oem_name]/config/schemas/structure.yaml` (copy template, customize keywords)
- Create `oems/[oem_name]/config/schemas/upstream.yaml` (define columns + detection rules)
- Reuse parsing logic from Step 1/2 (already OEM-agnostic)

## Summary

| Aspect | File | Owner | Change Frequency |
|--------|------|-------|------------------|
| **What columns exist** | upstream.yaml | Product spec | Low (structural) |
| **How to identify columns (EN)** | upstream.yaml | Domain expert | Medium (mappings) |
| **How to identify columns (FR)** | upstream.yaml | Domain expert | Medium (mappings) |
| **How to find sections** | structure.yaml | Technical | Low (stable) |
| **How to find headers** | structure.yaml | Technical | Low (stable) |
| **What constitutes valid data** | structure.yaml | QA/Product | Low (stable) |

**File loading order:**
1. Step 0: Load orchestrator config → points to schemas/
2. Step 1: Load `structure.yaml` for parsing rules
3. Step 2: Load `upstream.yaml` columns for header normalization
4. Step 5: Load `downstream.yaml` for output schema

---

**Revision History:**
- 2026-10-14: Initial consolidation (merged detection.yaml + upstream.yaml)
