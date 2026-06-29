"""
Inspect the database to see what manufacturers and years are available.
"""

from models.manufacture_module import load_existing_csv
from pathlib import Path

if __name__ == "__main__":
    csv_path = str(Path(__file__).parent / "db" / "db_vehicle_models.csv")
    df = load_existing_csv(csv_path)

    print(f"Total rows in database: {len(df)}")
    print()

    print("Manufacturers:")
    for make in sorted(df["Manufacturer"].unique()):
        count = len(df[df["Manufacturer"] == make])
        years = sorted(df[df["Manufacturer"] == make]["ModelYear"].unique())
        print(f"  {make}: {count} rows, years: {years}")
    print()

    print("Mitsubishi data:")
    df_mits = df[df["Manufacturer"] == "Mitsubishi"]
    print(f"Total: {len(df_mits)} rows")
    print(f"Years available: {sorted(df_mits['ModelYear'].unique())}")
    print()

    # Show Mitsubishi 2026 data if available
    df_2026 = df_mits[df_mits["ModelYear"] == 2026]
    if not df_2026.empty:
        print("Mitsubishi 2026 models:")
        for idx, row in df_2026.iterrows():
            print(f"  {row['ModelNumber']}: {row['Description']}")
    else:
        print("No Mitsubishi 2026 data found")
        # Show what IS available
        if not df_mits.empty:
            earliest_year = df_mits["ModelYear"].min()
            print(f"\nShowing {earliest_year} Mitsubishi data instead:")
            df_sample = df_mits[df_mits["ModelYear"] == earliest_year].head(5)
            for idx, row in df_sample.iterrows():
                print(f"  {row['ModelNumber']}: {row['Description']}")
