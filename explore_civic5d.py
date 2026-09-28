"""
Explore civic 5d.xlsx file structure
Find EN, FR, and "Select Province" sheets
"""

import pandas as pd
from pathlib import Path
import json

# Find civic 5d.xlsx
landing_zone = Path(r"C:\Users\paxm\OneDrive - PBS SYSTEMS\Desktop\Office\Projects\OEM Accessory project\OEM_Accessories_v1\landing_zone\2026\Honda")
test_file = landing_zone / "civic 5d.xlsx"

if not test_file.exists():
    print(f"❌ File not found: {test_file}")
    print("\nSearching for .xlsx files...")
    files = list(landing_zone.rglob("*.xlsx"))
    for f in files:
        print(f"  - {f.name}")
else:
    print(f"✓ Found file: {test_file.name}\n")

# ============================================================================
# STEP 1: Load and List All Sheets
# ============================================================================

print("="*80)
print("STEP 1: ALL SHEETS IN civic 5d.xlsx")
print("="*80 + "\n")

xl = pd.ExcelFile(test_file)
all_sheets = xl.sheet_names

print(f"Total sheets: {len(all_sheets)}\n")
for i, sheet in enumerate(all_sheets, 1):
    print(f"{i:2d}. {sheet}")

# ============================================================================
# STEP 2: Find EN and FR Sheets
# ============================================================================

print("\n" + "="*80)
print("STEP 2: IDENTIFY EN AND FR SHEETS")
print("="*80 + "\n")

en_sheets = [s for s in all_sheets if "_EN" in s.upper() or (s.endswith("EN") and not s.startswith("_"))]
fr_sheets = [s for s in all_sheets if "_FR" in s.upper() or (s.endswith("FR") and not s.startswith("_"))]
select_province = [s for s in all_sheets if "select province" in s.lower()]

print(f"EN Sheets ({len(en_sheets)}):")
for s in en_sheets:
    print(f"  • {s}")

print(f"\nFR Sheets ({len(fr_sheets)}):")
for s in fr_sheets:
    print(f"  • {s}")

print(f"\nSelect Province Sheets ({len(select_province)}):")
for s in select_province:
    print(f"  • {s}")

# ============================================================================
# STEP 3: Load and Display EN Sheets
# ============================================================================

if en_sheets:
    print("\n" + "="*80)
    print("STEP 3: EN SHEET DATA")
    print("="*80 + "\n")

    for en_sheet in en_sheets:
        print(f"\n🔹 Sheet: {en_sheet}")
        print("-" * 80)

        df_en = pd.read_excel(test_file, sheet_name=en_sheet)

        print(f"   Shape: {len(df_en)} rows × {len(df_en.columns)} columns")
        print(f"   Columns: {list(df_en.columns)}")
        print(f"\n   First 5 rows:")
        print(df_en.head(5).to_string())

# ============================================================================
# STEP 4: Load and Display FR Sheets
# ============================================================================

if fr_sheets:
    print("\n\n" + "="*80)
    print("STEP 4: FR SHEET DATA")
    print("="*80 + "\n")

    for fr_sheet in fr_sheets:
        print(f"\n🔹 Sheet: {fr_sheet}")
        print("-" * 80)

        df_fr = pd.read_excel(test_file, sheet_name=fr_sheet)

        print(f"   Shape: {len(df_fr)} rows × {len(df_fr.columns)} columns")
        print(f"   Columns: {list(df_fr.columns)}")
        print(f"\n   First 5 rows:")
        print(df_fr.head(5).to_string())

# ============================================================================
# STEP 5: Load and Display Select Province Sheet
# ============================================================================

if select_province:
    print("\n\n" + "="*80)
    print("STEP 5: SELECT PROVINCE SHEET")
    print("="*80 + "\n")

    for prov_sheet in select_province:
        print(f"\n🔹 Sheet: {prov_sheet}")
        print("-" * 80)

        df_prov = pd.read_excel(test_file, sheet_name=prov_sheet)

        print(f"   Shape: {len(df_prov)} rows × {len(df_prov.columns)} columns")
        print(f"   Columns: {list(df_prov.columns)}")
        print(f"\n   First 5 rows:")
        print(df_prov.head(5).to_string())

# ============================================================================
# STEP 6: Find Model Information
# ============================================================================

print("\n\n" + "="*80)
print("STEP 6: LOOK FOR MODEL INFORMATION")
print("="*80 + "\n")

if en_sheets:
    df_en = pd.read_excel(test_file, sheet_name=en_sheets[0])
    df_str = df_en.astype(str)

    print(f"Searching in: {en_sheets[0]}\n")

    # Look for "1.0 Packages and Kits" marker
    marker_row = None
    for idx, row in df_str.iterrows():
        row_text = " ".join(row.values)
        if "1.0 Packages" in row_text or "Packages and Kits" in row_text:
            marker_row = idx
            print(f"✓ Found '1.0 Packages and Kits' marker at row {idx}\n")
            break

    if marker_row is not None:
        print(f"Rows ABOVE marker (metadata):\n")
        print(df_en.iloc[0:marker_row].to_string())
    else:
        print(f"Marker '1.0 Packages and Kits' not found.")
        print(f"\nShowing first 15 rows to find model info:\n")
        print(df_en.head(15).to_string())

# ============================================================================
# SUMMARY
# ============================================================================

print("\n\n" + "="*80)
print("SUMMARY")
print("="*80 + "\n")

summary = {
    "file": test_file.name,
    "total_sheets": len(all_sheets),
    "en_sheets": en_sheets,
    "fr_sheets": fr_sheets,
    "select_province_sheets": select_province,
    "findings": {
        "has_en": len(en_sheets) > 0,
        "has_fr": len(fr_sheets) > 0,
        "has_select_province": len(select_province) > 0,
    }
}

print(json.dumps(summary, indent=2))

if en_sheets and fr_sheets:
    print(f"\n✓ Ready to load:")
    print(f"  EN: {en_sheets[0]}")
    print(f"  FR: {fr_sheets[0]}")
    if select_province:
        print(f"  Province: {select_province[0]}")
