# Honda Flat File Output - Current Status

**Date:** 2026-09-28  
**Objective:** Generate flat data files with required columns preserved as-is (no transformations)

## ✅ COMPLETED

### 1. **Sheet Filtering & Selection**
- ✅ Process only EN data sheets (_DATA, _APP_EN) and _APP_FR for FR
- ✅ Skip non-data sheets (SELL, SELECT PROVINCE, metadata)
- ✅ Orchestrator correctly identifies and loads correct sheets

### 2. **Section Detection**
- ✅ Identify section boundaries using "1.0 Packages", "2.0 Wheels", etc. markers
- ✅ Correctly extract data start/end rows per section
- ✅ Logic validated against playground v2 notebook

### 3. **Header Extraction**
- ✅ Extract headers from first row of each section
- ✅ Correctly name product columns: Description, Part Number, Dealer Net, List Price, FRT, Installed Price, Application
- ✅ Section-aware processing (6 sections per sheet)

### 4. **Data Structure**
- ✅ Preserve data as-is (no transformations per user requirement)
- ✅ Add _section_name column for traceability
- ✅ Support multi-section concatenation

### 5. **Batch Traceability**
- ✅ Add source_file column at position 0
- ✅ Track which file each row came from
- ✅ Batch processing of multiple files working

## 📋 REQUIRED OUTPUT COLUMNS

For flat file sheets (Accessories_EN, Accessories_FR):

```
1. source_file       ← File name (from batch processing)
2. section           ← Section name (Packages, Wheels, Exterior, etc.)
3. Description       ← Product description (preserved as-is)
4. Part Number       ← Part identifier (preserved as-is)
5. Dealer Net        ← Cost/dealer net price
6. List Price        ← List price
7. FRT               ← FRT value
8. Installed Price   ← Installed price
9. Application       ← Applicability column
10. [Trim columns]   ← DynamicColumns (SPORT, HYBRID, etc.) with • markers
```

## 🔄 CURRENT PIPELINE FLOW

1. **load_file()** → Filter and select sheets
2. **Step 1 (Validation)** → Identify sections, extract metadata
3. **Step 2 (Header Normalization)** → Extract headers per section, concatenate sections into reconciliation DF
4. **Step 3 (Standardization)** → Clean data, standardize types
5. **Step 4 (Transformation)** → Melt wide→long format (trims as rows)
6. **Step 5 (Output)** → Add source_file, output as flat sheets

## 📊 NEXT STEPS (IMPLEMENTATION)

### Phase 1: Reconciliation DataFrame
Modify **Step 2** to:
1. For each section identified in Step 1:
   - Extract headers from section's first row
   - Extract data rows (skip headers, empty rows)
   - Add _section_name column
   - Append to reconciliation DF
2. Return single DF with all sections combined
3. Preserve column order and names exactly

### Phase 2: EN/FR Reconciliation
Process both sheets:
1. Process _APP_EN → reconciliation_EN
2. Process _APP_FR → reconciliation_FR (if exists)
3. Reconcile on Part Number:
   - Match EN and FR rows
   - Merge on common product columns
   - Flag mismatches (different descriptions, prices, etc.)

### Phase 3: Output Generation
1. Save reconciliation_EN as Accessories_EN sheet
2. Save reconciliation_FR as Accessories_FR sheet
3. Add source_file column at position 0
4. Ensure column order matches specification above

## 🔧 ARCHITECTURE NOTES

- **Not transforming data** - preserve original values, columns, structure
- **Not melting yet** - flat file output is in original section-based format
- **Melt happens later** (if needed) - but user wants flat first
- **Reconciliation DF** - single accumulator for all sections in a sheet
- **Multi-language** - handle EN (_APP_EN) and FR (_APP_FR) separately

## 📝 TESTING STRATEGY

1. Test _APP_EN sheet:
   - [ ] All 6 sections detected
   - [ ] Headers extracted correctly
   - [ ] Data rows preserved (no data loss)
   - [ ] Section column correctly populated
   - [ ] Source file column added

2. Test _APP_FR sheet (when available):
   - [ ] Same as EN
   - [ ] FR descriptions preserved

3. Test batch mode:
   - [ ] Multiple files processed
   - [ ] source_file column distinct per file
   - [ ] All rows accounted for

## 💾 OUTPUT LOCATION

- Single file: `accy_v2/output/ready_to_upload/honda/honda_{run_id}_{timestamp}.xlsx`
- Sheets in file: `Accessories_EN`, `Accessories_FR`, `DQ`, `RawData`, `Confidence`
- Flat data only in: `Accessories_EN` and `Accessories_FR`

---

**Status:** Ready for Phase 1 implementation  
**Owner:** Claude + User  
**Target:** Complete flat file output with all sections properly reconciled
