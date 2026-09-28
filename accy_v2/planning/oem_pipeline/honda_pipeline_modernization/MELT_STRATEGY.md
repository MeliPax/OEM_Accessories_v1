# Honda Melt Strategy: Pipeline Flow & Batch Processing Plan

**Date:** 2026-09-28
**Status:** Ready for Implementation
**Scope:** Single file + Batch processing (multiple files)
**Objective:** Transform raw Excel (wide) → melted DataFrame (long) for one OR many files

---

## Executive Summary

**What We're Building:**
A pipeline that can:

1. **Single File Mode:** Process CVIC5D.xlsx → melted DataFrame (~300-400 rows)
2. **Batch Mode:** Process all Honda files in `landing_zone/honda/may_2026/` → combined output with file tracking

**Key Requirement:**
All files melted the SAME WAY, then optionally combined into one dataset with a `source_file` column for traceability.

---

## Architecture: Single File vs Batch

### Option 1: Single File Pipeline

```
Input: CVIC5D.xlsx (single file)
  ↓
Step 1: Validate & extract sections/trims
  ↓
Step 2: Extract headers
  ↓
Step 3: Standardize data
  ↓
Step 4: MELT (wide → long)
  ↓
Output: df_melted (~300-400 rows)
        Columns: [Description, Part#, Prices, trim_level]
```

**Usage:**

```bash
python run_pipeline.py --file CVIC5D.xlsx
```

### Option 2: Batch Pipeline (Multiple Files)

```
Input Directory: landing_zone/honda/may_2026/
  Files: [CVIC5D.xlsx, ACCORD.xlsx, CRV.xlsx, ...]
  
For Each File:
  ├─ CVIC5D.xlsx
  │  ├─ Step 1-3: Process
  │  ├─ Step 4: Melt
  │  └─ Add column: source_file="CVIC5D.xlsx"
  │
  ├─ ACCORD.xlsx
  │  ├─ Step 1-3: Process
  │  ├─ Step 4: Melt
  │  └─ Add column: source_file="ACCORD.xlsx"
  │
  └─ ... (more files)

COMBINE: Concatenate all melted dfs → one big dataset

Output: df_combined_melted
  (~1000-2000 rows if 5 files × 300-400 rows each)
  Columns: [source_file, Description, Part#, Prices, trim_level]
```

**Usage:**

```bash
python run_pipeline.py --batch --input-dir landing_zone/honda/may_2026/
```

---

## Pipeline Flow: Steps 1-4 (Detailed)

### STEP 1: Validation & Metadata Extraction

**Input (Single File):**

```
File: CVIC5D.xlsx
Sheets: 26MY_CIV5D_APP_EN, 26MY_CIV5D_APP_FR, ...
Raw: 170 rows × 17 columns (Unnamed columns)
```

**Input (Batch):**

```
Directory: landing_zone/honda/may_2026/
Files:
  - CVIC5D.xlsx (170 rows)
  - ACCORD.xlsx (150 rows)
  - CRV.xlsx (180 rows)
  - ... (repeat for each file)
```

**Process (Same for Single or Batch):**

1. Load EN sheet (skip SELL sheets)
2. Load FR sheet (if exists)
3. Detect 6 sections using regex: `^\d+\.\d+\s+(.+)$`
4. For each section:
   - Find marker row
   - Identify data range (start_row, end_row)
   - Extract trim columns from header row
5. Compile metadata dictionary

**Output (Per File):**

```python
# For CVIC5D.xlsx:
metadata = {
  "file_name": "CVIC5D.xlsx",
  "model_name": "Civic 5D",
  "vehicle_year": 2026,
  
  "section_structure": {
    "packages": {
      "en_row": 9,
      "fr_row": 9,
      "data_start": 10,
      "data_end": 55,
      "total_rows": 46
    },
    "wheels": {...},
    # ... (5 more sections)
  },
  
  "trim_columns_per_section": {
    "packages": ["LX", "SPORT", "EX", "EX-L", "TOURING"],
    "wheels": ["LX", "EX"],
    # ... (5 more sections)
  },
  
  "validation_status": "PASS"
}

(en_df, fr_df) = (170 rows × 17 cols, 170 rows × 17 cols)
```

**Batch Handling:**

- Run Step 1 independently for EACH file
- Each file gets its own metadata dict
- Store file name in metadata for traceability

---

### STEP 2: Header Normalization (Per Section)

**Critical:** Step 2 must work on sections, not entire sheet!

**Input (Single File, Packages Section):**

```
Section: Packages (from metadata: rows 10-55)
Columns: Still "Unnamed: 0" through "Unnamed: 16"

Row 10 (HEADER): [Description, Part Number, Dealer Net, ..., LX, SPORT, EX, ...]
Rows 11-55: Data
```

**Process:**

1. For each section (packages, wheels, exterior, ...):
   a. Extract rows from `data_start` to `data_end` (from Step 1 metadata)
   b. Identify header row = `data_start - 1`
   c. Extract headers from that row
   d. Rename all columns to proper names
   e. Keep only the data rows (drop header row itself)

**Output (Per Section):**

```python
df_packages_normalized:
  Columns: ["Description", "Part Number", "Dealer Net", "List Price", 
            "FRT", "Installed Price", "LX", "SPORT", "EX", "EX-L", "TOURING"]
  Rows: 46 (just the data, no headers)

# Similarly for wheels, exterior, etc.
```

**Then Combine All Sections:**

```python
df_all_sections = pd.concat([
  df_packages_normalized,  # 46 rows
  df_wheels_normalized,     # 15 rows
  df_exterior_normalized,   # 50 rows
  df_interior_normalized,   # 19 rows
  df_electrical_normalized, # 9 rows
  df_paint_pens_normalized  # 16 rows
])

Result: 155 rows × 10 columns
```

**Batch Handling:**

- Each file gets normalized separately
- Output is one concatenated DF per file (all sections combined)

---

### STEP 3: Standardization & Cleanup

**Input (Single File, After Section Concat):**

```
155 rows × 10 columns
Columns: [Description, Part Number, ..., Trim columns...]
Some cells have whitespace, some prices are strings
```

**Process (Same as Step 3 in orchestrator):**

1. Drop completely empty rows
2. Drop completely empty columns
3. Strip whitespace from all strings
4. Convert numeric columns to float (List Price, FRT, etc.)
5. Handle NaN column names

**Output:**

```python
df_standardized:
  155 rows × 10 columns
  All strings trimmed
  All prices numeric
  No NaN rows
```

**Batch Handling:**

- Each file standardized independently
- Standardized dfs stored in list: `[df_std_file1, df_std_file2, ...]`

---

### STEP 4: TRANSFORMATION (MELT) ← CORE OPERATION

**Input (Single File):**

```
df_standardized:
  155 rows (all 6 sections combined)
  Columns: [Description, Part Number, ..., LX, SPORT, EX, EX-L, TOURING, ...]
  
Example rows (mixed sections):
  Row 1 (Packages): Description="Racing Pkg", LX="•", SPORT="•", ...
  Row 47 (Wheels): Description="Wheel Lock Set", LX="•", EX="•", ...
  Row 62 (Exterior): Description="Door Guard", LX="•", SPORT="", ...
```

**Melt Process:**

```python
def melt_all_sections(df_standardized, metadata):
    """
    Melt entire standardized DataFrame to long format.
    Handle all sections in one go.
    Track which section each row came from.
    """
  
    # Step 4a: Identify product vs trim columns
    product_cols = [
        "Description", "Part Number", "Dealer Net", "List Price", 
        "FRT", "Installed Price"
    ]
  
    # Trim columns = everything that's NOT a product column
    trim_cols = [col for col in df.columns if col not in product_cols]
    # trim_cols = ["LX", "SPORT", "EX", "EX-L", "TOURING", ...]
  
    # Step 4b: Add section column (from metadata) BEFORE melting
    # Use section_structure from metadata to map row index to section name
    section_structure = metadata.get("section_structure", {})
    df_with_section = df_standardized.copy()
    df_with_section["section"] = df_with_section.index.map(
        lambda idx: _get_section_for_row(idx, section_structure)
    )
  
    # Step 4c: Melt
    df_melted = pd.melt(
        df_with_section,
        id_vars=product_cols + ["section"],  # Keep section column
        value_vars=trim_cols,                 # Pivot these columns to rows
        var_name="trim_level",                # New column name for trim
        value_name="applicability"            # Marker: "•", "", NaN, etc.
    )
  
    # Step 4d: Filter to only marked trims
    # Keep rows where applicability is NOT empty/NaN
    df_melted = df_melted[
        (df_melted["applicability"].notna()) & 
        (df_melted["applicability"].astype(str).str.strip() != "")
    ]
  
    # Step 4e: Drop applicability (no longer needed)
    df_melted = df_melted.drop(columns=["applicability"])
  
    # Step 4f: Filter garbage rows
    # Keep only valid part numbers
    if "Part Number" in df_melted.columns:
        valid = (
            (df_melted["Part Number"].astype(str).str.len() >= 2) &
            (df_melted["Part Number"].astype(str).str.lower() != "part number") &
            (df_melted["Part Number"].astype(str) != "nan")
        )
        df_melted = df_melted[valid]
  
    # Step 4g: Reset index
    df_melted = df_melted.reset_index(drop=True)
  
    return df_melted

def _get_section_for_row(row_idx, section_structure):
    """
    Map a row index to its section name using metadata.
    section_structure = {
        "packages": {"data_start": 10, "data_end": 55, ...},
        "wheels": {"data_start": 56, "data_end": 70, ...},
        ...
    }
    """
    for section_name, boundaries in section_structure.items():
        data_start = boundaries.get("data_start")
        data_end = boundaries.get("data_end")
        if data_start is not None and data_end is not None:
            if data_start <= row_idx <= data_end:
                return section_name
    return "unknown"
```

**Output (Single File):**

```python
df_melted:
  ~300-400 rows (155 rows × avg 2-3 trims per row)
  Columns: [Description, Part Number, Dealer Net, List Price, FRT, 
            Installed Price, section, trim_level]
  
  Example rows:
  ┌────────────────────┬─────────────┬────────┬──────────┬─────────┐
  │Description         │Part Number  │ FRT    │section   │trim_lev │
  ├────────────────────┼─────────────┼────────┼──────────┼─────────┤
  │Racing Package - R  │26TYPER-RACE │6612.0  │packages  │LX       │
  │Racing Package - R  │26TYPER-RACE │6612.0  │packages  │SPORT    │
  │Racing Package - R  │26TYPER-RACE │6612.0  │packages  │TOURING  │
  │Wheel Lock Set      │50320-AXX-.. │120.0   │wheels    │LX       │
  │Wheel Lock Set      │50320-AXX-.. │120.0   │wheels    │EX       │
  │Door Guard          │08P05-AXX... │95.0    │exterior  │LX       │
  │...                 │...          │...     │...       │...      │
  └────────────────────┴─────────────┴────────┴──────────┴─────────┘
```

**Batch Handling:**

- Melt each file's df independently (each gets its own `section` column)
- Store melted dfs in list: `[df_melted_file1, df_melted_file2, ...]`
- Add `source_file` column to each:
  ```python
  df_melted_file1["source_file"] = "CVIC5D.xlsx"
  df_melted_file2["source_file"] = "ACCORD.xlsx"
  ```
- Concatenate all:
  ```python
  df_combined = pd.concat(
    [df_melted_file1, df_melted_file2, ...],
    ignore_index=True
  )
  # Result: 1000-2000+ rows (if 5+ files)
  # Columns: [source_file, Description, Part#, Prices, section, trim_level]
  ```

---

## Data Shape Transformation Examples

### Single File Transformation

```
CVIC5D.xlsx:
  INPUT:  170 raw rows × 17 columns (wide)
  After Step 1-3: 155 rows (removed headers/metadata) × 10 columns
  After Step 4 (melt):
    - Packages: 46 rows → ~180 rows (avg 3.9 trims marked per part)
    - Wheels: 15 rows → ~30 rows (avg 2 trims marked per part)
    - Exterior: 50 rows → ~120 rows (avg 2.4 trims per part)
    - Interior: 19 rows → ~50 rows (avg 2.6 trims per part)
    - Electrical: 9 rows → ~20 rows (avg 2.2 trims per part)
    - Paint Pens: 16 rows → ~35 rows (avg 2.2 trims per part)
  
  TOTAL OUTPUT: ~435 rows × 7 columns (long format)
```

### Batch Processing Transformation

```
5 Honda Files (CVIC5D, ACCORD, CRV, RIDGELINE, PILOT):
  File 1 (CVIC5D):    170 rows → 435 melted rows
  File 2 (ACCORD):    180 rows → 460 melted rows
  File 3 (CRV):       165 rows → 420 melted rows
  File 4 (RIDGELINE): 190 rows → 475 melted rows
  File 5 (PILOT):     175 rows → 440 melted rows
  
  COMBINED OUTPUT: 2230 rows × 8 columns
  (7 product/trim columns + 1 source_file column)
```

---

## Implementation Plan

### Phase 1: Ensure Steps 1-3 Work (Prerequisite)

**Step 1 Must Return:**

```python
metadata = {
  "section_structure": {...},           # 6 sections with boundaries
  "trim_columns_per_section": {...},    # Trim cols per section
  "header_row_per_section": {...}       # Header row location per section
}
(en_df, fr_df) = (full sheets, unchanged)
```

**Step 2 Must:**

- Process each section independently
- Extract headers using metadata
- Concatenate all sections into one DataFrame

**Step 3 Must:**

- Standardize the concatenated DF
- Return single DF ready for melt

### Phase 2: Implement Step 4 (Melt)

**Requirements:**

- [ ] Accept `df_standardized` + `metadata` from Step 3
- [ ] Identify all trim columns (use metadata or fallback to pattern matching)
- [ ] Melt using `pd.melt()`
- [ ] Filter empty applicability markers
- [ ] Filter garbage rows
- [ ] Return `df_melted` with 300-400+ rows

### Phase 3: Integrate Batch Processing

**Single File Mode:**

```python
# orchestrator.py - single file
file_path = "CVIC5D.xlsx"
df_melted, metadata = run_pipeline(file_path)
# Output: df_melted with 400+ rows
```

**Batch Mode:**

```python
# run_pipeline.py --batch
landing_zone = Path("landing_zone/honda/may_2026/")
files = list(landing_zone.glob("*.xlsx"))

melted_dfs = []
for file in files:
  df_melted, metadata = run_pipeline(file)
  df_melted["source_file"] = file.name
  melted_dfs.append(df_melted)

df_combined = pd.concat(melted_dfs, ignore_index=True)
# Output: df_combined with 1000-2000+ rows, trackable by source_file
```

### Phase 4: Output Generation (Steps 4.5-5)

After melting, next steps:

- Step 4.5: Model enrichment (add model_number column)
- Step 5: Output to Excel + DQ reports

---

## Files to Modify

```
accy_v2/oems/honda/
├── pipeline/
│   ├── step1_validation.py          ← ADD: identify_section_boundaries()
│   ├── step2_header_normalization.py ← MODIFY: Handle sections, concat
│   ├── step3_standardization.py      ← OK
│   ├── step4_transformation.py       ← MODIFY: Use metadata for trim cols
│   └── (other steps)
├── orchestrator.py                   ← MODIFY: Call steps in correct order
└── run_pipeline.py (at root)         ← MODIFY: Support --batch mode
```

---

## Success Criteria

### Single File Mode

- [ ] CVIC5D.xlsx → 400+ melted rows
- [ ] All sections processed (6 sections concatenated before melt)
- [ ] No garbage rows (headers filtered)
- [ ] trim_level column contains actual trim names (LX, SPORT, etc.)
- [ ] section column populated with original section (packages, wheels, exterior, interior, electrical, paint_pens)

### Batch Mode

- [ ] 5 files × 400+ rows = 2000+ combined melted rows
- [ ] source_file column added to track which file each row came from
- [ ] section column preserved for each row to track origin section
- [ ] All files processed independently, then concatenated
- [ ] One final combined melted DataFrame with [source_file, section, trim_level, ...] columns

### Metadata Flow

- [ ] Step 1 metadata flows to Step 2 (header row location)
- [ ] Step 2 metadata flows to Step 3
- [ ] Step 3 metadata flows to Step 4 (trim columns, section info)
- [ ] Step 4 output includes melted_shape in metadata

---

## Questions Before Implementation

1. **All files in one batch or separate batches?**

   - Recommendation: Load all files in landing_zone, melt each, combine with source_file tracking
2. **Combine before or after model enrichment?**

   - Recommendation: Melt all → combine all → THEN enrich (one big enrichment pass)
3. **Error handling for batch?**

   - If one file fails, skip it or halt whole batch?
   - Recommendation: Log error, skip bad file, continue with others
4. **Output format?**

   - One Excel file with multiple sheets (one per source file)?
   - Or one combined Excel with all rows + source_file column?
   - Recommendation: Combined + source_file (easier downstream)
