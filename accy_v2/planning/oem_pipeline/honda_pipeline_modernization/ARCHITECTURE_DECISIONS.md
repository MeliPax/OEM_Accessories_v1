# Requirements Alignment & Architecture Review
## Honda Pipeline - raw_note.txt Requirements vs Current Plan

**Date:** 2026-10-12  
**Reviewer:** Claude Code  
**Status:** REVIEW IN PROGRESS - CLARIFICATION NEEDED

---

## Executive Summary

✅ **Overall Assessment:** Requirements align well with the 5-layer architecture  
⚠️ **Clarifications Needed:** 4 key questions about implementation scope and timing  
✅ **No Critical Conflicts Detected:** Design is logically sound

---

## Part 1: Metadata Extraction Requirements (Phase 1 - COMPLETE ✅)

### Raw Note Requirement:
```
Vehicle signature records (meta): model name, year, manufacture signature
- Located at file top before first section marker
- Need to extract and store for batch file identification

Publication Date records:
- Two rows at end of file after last section
- First row: "Publication Date"/"Date de publication" string
- Second row: date in YYYY-MM-DD format in description column
```

### Current Implementation (Phase 1):
- ✅ Model name extraction: DONE (from metadata rows)
- ✅ Vehicle year extraction: DONE (from metadata rows)
- ✅ Section detection: DONE (pattern-based, all 6 sections)
- ⚠️ **Publication date extraction:** Not yet implemented

### Status:
```
ALIGNED ✅ but INCOMPLETE
```

**Question 1:** Should publication date extraction be added to Phase 1C or deferred to Phase 2/3?

---

## Part 2: Data Row Classification Requirements

### Raw Note Categorizes:
```
1. PARENT RECORDS
   - Packages section: Have complete package data
   - Other sections: Have ALL price columns filled (Dealer Net, List, FRT, Installed)
   - Child records depend on parent for price data

2. CHILD RECORDS  
   - Missing some/all price data
   - Must inherit from first parent record before it
   - Only one parent per child (first parent rule)

3. SINGLE RECORDS
   - Complete data in ALL columns including prices
   - No child records dependent on them
   - No extraction needed

4. HEADER ROWS
   - Contain column keywords
   - Have transformation instructions

5. SECTION INDICATORS
   - Section markers showing start/end
```

### Current Implementation (Phase 1C):
- ✅ Row classification: DONE (valid_data_rows, empty_rows, publishing_rows)
- ❌ **Parent/Child relationship detection:** NOT DONE
- ❌ **Record type flagging (parent/child/single):** NOT DONE
- ✅ Header detection: DONE (keyword-based)
- ✅ Section markers: DONE (pattern-based)

### Architecture Impact:
The **Option A+C combined** logic (Phase 1C) counts rows as "valid" if they have ANY product/price data.  
This is good for **coverage**, but doesn't distinguish **record types** (parent vs child).

### Status:
```
PARTIALLY ALIGNED ⚠️
- Row classification works, but record type tracking is missing
- Will be needed for Phase 3 (Standardization & Rollup)
```

**Question 2:** Should parent/child relationship detection be:
- Option A: Added to Phase 1 as Phase 1D?
- Option B: Moved to Phase 2 (Header Normalization)?
- Option C: Moved to Phase 3 (Standardization & Rollup)?

---

## Part 3: Price Data Fill-Down Requirements (Non-Package Records)

### Raw Note Requirement:
```
"do we fill down at extract or leave the child record as they are from raw?"
User's decision: "fill them for non-package records"

Goal:
- Keep raw data complete for non-package rows (each row has all price data)
- Keep package data in original form (parent/child rows stay separate)
- Avoid redundant data processing across pipeline steps
- Extract once, use everywhere
```

### Current Plan:
- Phase 3 (Standardization): "Packages/Kits rollup logic (parent-child detection)"
- Phase 4 (Transformation): EN/FR reconciliation and trim melting

### Architecture Consideration:
This is a **data normalization** decision:
- **Fill-down in Phase 2/3:** Easier for downstream steps (Steps 4-5)
- **Keep raw format until Phase 3:** More audit trail, but more processing

### Status:
```
QUESTION ABOUT TIMING ⚠️
- Not conflicting with architecture
- Need to decide WHEN to fill-down prices
```

**Question 3:** Fill-down timing preference:
- Option A: Phase 2 (Header Normalization) - Early normalization
- Option B: Phase 3 (Standardization & Rollup) - At same step as rollup logic
- Option C: Split - Detect parent/child in Phase 2, fill in Phase 3

---

## Part 4: Raw Data Output Sheet Requirements (Phase 6)

### Raw Note Requirement:
```
Output sheets: EN_raw_data and FR_raw_data

Columns (12 total):
1. source_file - Excel file extracted from
2. source_sheet - EN or FR sheet name
3. Section - section name
4. Description - part description
5. Part Number - part number value
6. Dealer Net - dealer net price
7. List Price - list price value
8. FRT - FRT extracted value
9. Installed Price - installed price
10. Comments - additional comments
11. model - vehicle model name
12. records_type - parent/child/single flag

Behavior:
- Single file run: EN_raw_data + FR_raw_data for that file
- Multi-file run: EN_raw_data + FR_raw_data with ALL files combined
- Generated every pipeline run (auditable source)
```

### Current Plan (Phase 6):
```
Phase 6 Tasks:
- [ ] Implement step5_output.py
- [ ] Excel workbook generation (Main, Raw Data, Confidence, DQ sheets)
- [ ] Batch DQ aggregation
- [ ] Honda-specific DQ rules
```

**Alignment Analysis:**
- ✅ Phase 6 already plans for "Raw Data" sheet
- ✅ Workbook generation already in scope
- ❌ But NO details on **raw data column structure**
- ❌ No mention of **source_file, source_sheet tracking**
- ❌ No mention of **records_type field**

### Status:
```
ALIGNED IN CONCEPT ✅ but DETAILS MISSING ⚠️
- Raw data output is planned but needs specification
- Need to track source file/sheet throughout pipeline
```

**Question 4:** For raw data output columns - should we:
- Option A: Track source_file/source_sheet from Step 1 onwards
- Option B: Reconstruct source info in Step 5 from metadata
- Option C: Add source tracking to config/metadata structure

---

## Part 5: Record Type Naming Convention

### Raw Note Request:
```
"give me names that you think would fit better to define each data point"
Goal: Good naming for future developers
```

### Proposed Naming (for clarification):

**Record Types:**
- `record_type: "parent"` - Has all price columns, children depend on it
- `record_type: "child"` - Missing price data, inherits from parent
- `record_type: "single"` - Complete standalone record, no dependencies
- `record_type: "header"` - Header row (metadata)
- `record_type: "section_marker"` - Section boundary row

**Package Section Special Case:**
- `record_type: "package_parent"` - Parent package record
- `record_type: "package_child"` - Child/variant package record
- or keep as `parent`/`child` for simplicity?

**Other Metadata Fields:**
- `parent_row_index: int` - Row number of parent (for child records)
- `price_fill_status: "original" | "filled"` - Was price filled-down?
- `section_name: str` - Which section
- `source_file: str` - Original Excel file
- `source_sheet: str` - EN or FR

### Status:
```
RECOMMENDATION PENDING
Need your input on naming preference
```

---

## Alignment with 5-Layer Architecture

### Layer 1 (Data Ingestion - Steps 1-2): ✅ ALIGNED
```
Current: Phase 1 (Validation) + Phase 2 (Header Normalization)
Requirement: Extract metadata, detect sections, validate structure
STATUS: Good alignment, minor gap on publication date
```

### Layer 2 (Data Transformation - Steps 3-4): ⚠️ NEEDS CLARIFICATION
```
Current: Phase 3 (Standardization) + Phase 4 (EN/FR Reconciliation)
Requirement: Parent/child detection, price fill-down, section rollup
STATUS: General approach aligns, but timing/responsibility unclear
```

### Layer 3 (Model Lookup - Step 4.5): ✅ ALIGNED
```
Current: Phase 5 (Model Enrichment)
Requirement: Not mentioned in raw_note.txt (separate stream)
STATUS: Orthogonal, no conflict
```

### Layer 4 (Output - Step 5): ✅ ALIGNED with GAPS
```
Current: Phase 6 (Output & DQ)
Requirement: Raw data sheets with 12 columns, source tracking, record types
STATUS: Concept aligned, implementation details needed
```

### Layer 5 (Support Systems): ✅ ALIGNED
```
Current: Config system + logging
Requirement: EN/FR language-specific configs, batch tracking
STATUS: Already in place from Phase 1
```

---

## Logical Consistency Check

### ✅ Data Flow Makes Sense:
1. Step 1 extracts metadata ✓
2. Step 2 normalizes headers ✓
3. Step 3 standardizes & detects parent/child ✓
4. Step 4 reconciles EN/FR ✓
5. Step 5 generates raw data output ✓

### ✅ No Circular Dependencies:
- Each phase depends on previous, no backward refs ✓

### ✅ Metadata Threading:
- Metadata extracted in Phase 1, used throughout ✓
- Source tracking from Phase 1 → Phase 6 ✓

### ⚠️ Potential Issues Identified:

**Issue 1: Parent/Child Detection Timing**
- If detected in Phase 2, available for Phase 3 rollup
- If detected in Phase 3, harder to track dependencies
- **Risk:** Late detection could miss relationships

**Issue 2: Price Fill-Down Location**
- If Phase 2: Early normalization, clean downstream
- If Phase 3: Alongside rollup, but duplicate logic
- **Risk:** Unclear ownership could lead to redundant processing

**Issue 3: Source Tracking**
- Need to add `source_file` + `source_sheet` to dataframe
- Must thread through all 5 steps
- **Risk:** Could be forgotten if not explicit

**Issue 4: Record Type Field**
- Not yet captured in Option A+C row classification
- Will need to add to metadata/row annotations
- **Risk:** Late addition in Phase 6 = difficult retrofit

---

## Summary Table

| Requirement | Current Status | Architecture Fit | Risk Level | Phase |
|---|---|---|---|---|
| Vehicle signature extraction | ✅ DONE | ✅ Good | Low | 1 |
| Publication date extraction | ❌ NOT DONE | ✅ Good | Low | 1/2 |
| Section detection | ✅ DONE | ✅ Good | Low | 1 |
| Parent/child detection | ❌ NOT DONE | ⚠️ Timing? | Medium | 2/3? |
| Price fill-down logic | ❌ NOT DONE | ⚠️ Timing? | Medium | 2/3? |
| Raw data output (concept) | ⚠️ PLANNED | ✅ Good | Low | 6 |
| Raw data output (detail spec) | ❌ NOT DONE | ⚠️ Spec needed | Medium | 6 |
| Source tracking | ❌ NOT DONE | ⚠️ Need threading | Medium | 1-6 |
| Record type field | ❌ NOT DONE | ⚠️ Late addition? | Medium | 3+? |

---

## Blockers to Implementation

**None Critical**, but need clarification on:

1. ❓ **Publication date extraction** - Phase 1 or defer?
2. ❓ **Parent/child detection** - Phase 1D, 2, or 3?
3. ❓ **Price fill-down** - Phase 2 or 3?
4. ❓ **Record type naming** - Which names do you prefer?
5. ❓ **Source tracking architecture** - Metadata field or separate tracking?

---

## Recommendation

**PROPOSAL:** Proceed with Phase 2 as planned, but:

1. **Add to Phase 2 scope (Header Normalization):**
   - Publication date extraction
   - Parent/child detection (identify relationships)
   - Add `record_type` and `parent_row_index` to metadata

2. **Add to Phase 3 scope (Standardization & Rollup):**
   - Price fill-down logic for non-package records
   - Keep package data in original form

3. **Add to Phase 1 metadata threading:**
   - `source_file` and `source_sheet` fields
   - Thread through all steps

4. **Phase 6 (Output):**
   - Use tracked record types and source info
   - Generate raw data sheets with all 12 columns

This keeps logical grouping while ensuring parent/child is detected early (Phase 2) and filled-down at appropriate time (Phase 3).

---

## Decisions Confirmed ✅

### **Q1: Publication Date Handling → PHASE 1 ✅**
**Decision:** Extract publication date in Phase 1 (metadata extraction phase)

**Rationale:**
- Publication date is **file-level metadata**, same category as model_name and vehicle_year
- Belongs in Layer 1 (Data Ingestion) metadata extraction
- Needed for batch audit trail ("which file, when published?")
- Small isolated function, no cross-dependencies

**Implementation:** Add `_extract_publication_date()` to step1_validation.py, store as `meta_data["publication_date"]` in YYYY-MM-DD format.

---

### **Q2: Parent/Child Detection Timing → PHASE 2 (OPTION B) ✅**
**Decision:** Detect parent/child relationships in Phase 2 (Header Normalization)

**Rationale:**
- Parent/child is a **data pattern recognition** problem (like headers), not structure validation
- Natural home with header normalization (column definitions are now clear)
- Early enough for DQ logging in Steps 1–2 ("X parts have no parent")
- Can use normalized column names → cleaner code, better error messages
- Easy to unit-test (headers already resolved)

**Implementation:** Create detection logic in Phase 2, add to metadata:
- `meta_data["record_type_per_row"]` — tracks "parent" / "child" / "single" / "package_parent" / "package_child"
- `meta_data["parent_row_index"]` — for each child, index of its parent row

---

### **Q3: Price Fill-Down Strategy → SPLIT (PHASE 2 detect, PHASE 3 fill) ✅**
**Decision:** 
- **Phase 2:** Detect parent/child relationships, store metadata
- **Phase 3:** Fill prices for non-package child records using parent data

**Rationale (Split approach best for audit trail):**
- Detect early (Phase 2): metadata available for Step 1–2 DQ logging
- Fill late (Phase 3): happens **after standardization** (prices validated), **after** understanding which records are valid
- If parent rejected by business rules, children never get fake-filled prices
- Matches your audit goal: raw data preserved, fills are traceable

**Implementation Details:**
- Phase 2: Identify parent/child, store `parent_row_index`
- Phase 3: For non-package sections, if child, look up parent index and fill `[Dealer Net, List Price, FRT, Installed Price]` from parent
- Keep original price columns as-is (audit trail), add `price_fill_status: "original" | "filled"` flag

---

### **Q4: Record Type Naming ✅**
**Decision:** Use explicit naming as proposed

**Record Types:**
- `parent` — non-package sections, has complete prices + description, children depend on it
- `child` — non-package sections, missing prices, inherits from parent
- `single` — complete standalone record, no dependencies
- `package_parent` — packages section, parent package record
- `package_child` — packages section, package variant (inherits from parent)

**Why:** Explicit, no ambiguity, symmetric structure (package_X mirrors non-package), DQ-friendly.

---

### **Q5: Raw Data Output & Source Tracking → OPTION C (METADATA) ✅**
**Decision:** Track source info in metadata structure, thread through all phases, write to output in Step 5

**Architecture:**
```
Step 1: Capture source metadata
  ├─ meta_data["source_file"] = file_path
  ├─ meta_data["source_sheet"] = sheet_name (EN or FR)
  └─ meta_data["source_row_index"] = original row number (for audit)

Steps 2–4: Transform data, keep metadata thread alive
  └─ Every step: return (df, updated_metadata)

Step 5: Write final output sheets
  ├─ main sheet: all processed parts with model numbers
  ├─ raw_data sheet: original rows + source tracking + record types
  │   (Columns: source_file, source_sheet, source_row_index, section, description, 
  │    part_number, dealer_net, list_price, frt, installed_price, comments, model, record_type)
  └─ confidence/DQ sheets: as normal
```

**Why this achieves your audit goal:**
- ✅ Source never lost — threaded through metadata from Step 1 onwards
- ✅ If pipeline crashes mid-phase, source info is preserved (can write intermediate raw_data sheet)
- ✅ Raw data stays clean throughout (source isn't a dataframe column)
- ✅ DQ team can always trace "which row came from which file/sheet"
- ✅ Debugging: "Where did this part number come from?" → metadata tells you

**Optional resilience:** Save (df, metadata) checkpoints after each major step → if Phase 3 fails, can write partial raw_data sheet.

---

### **Q6: Source Tracking as Columns → NO (Keep in Metadata) ✅**
**Decision:** Do NOT add source_file/source_sheet as dataframe columns throughout pipeline

**Rationale:**
- Source info is **audit/tracking data**, not processing data
- Keeps transformation logic clean (doesn't work with source columns)
- Metadata is the right home for non-data context
- Reduces dataframe bloat, prevents accidental use in transforms

---

## Summary: Phase Structure (Updated)

| Phase | Responsibility | Parent/Child | Price Fill | Source Tracking |
|-------|---|---|---|---|
| **Phase 1C** | Metadata extraction | — | — | Capture in metadata |
| **Phase 1D** | Pub date extraction | — | — | ✅ Added |
| **Phase 2** | Header normalization + parent/child detection | ✅ Detect here | — | Thread metadata |
| **Phase 3** | Standardization + price fill-down + rollup | Use relationships | ✅ Fill here | Thread metadata |
| **Phase 4** | EN/FR reconciliation | — | — | Thread metadata |
| **Phase 5** | Output + DQ reporting | — | — | Write raw_data sheet |

---

**Ready for Phase 2 detailed design doc.** No further clarification needed.
