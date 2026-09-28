"""Quick inspection of Honda file sheet structure."""
import pandas as pd

file_path = r"C:\Users\paxm\OneDrive - PBS SYSTEMS\Desktop\Office\Projects\OEM Accessory project\OEM_Accessories_v1\landing_zone\2026\Honda\2025-06\2025 Honda Accessories - June25.xlsx"

xl = pd.ExcelFile(file_path)

print(f"File: 2025 Honda Accessories - June25.xlsx")
print(f"Total sheets: {len(xl.sheet_names)}\n")

print("All sheet names:")
for i, sheet in enumerate(xl.sheet_names, 1):
    print(f"  {i}. {sheet}")

# Check a few sheets for structure
print("\n" + "="*80)
print("INSPECTING SHEET STRUCTURES")
print("="*80)

for sheet in xl.sheet_names[:3]:
    print(f"\nSheet: {sheet}")
    df = pd.read_excel(file_path, sheet_name=sheet)
    print(f"  Shape: {df.shape}")
    print(f"  Columns: {list(df.columns[:5])}{'...' if len(df.columns) > 5 else ''}")
    print(f"  First row: {df.iloc[0, :3].to_list()}")
