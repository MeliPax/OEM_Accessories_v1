"""
Test script to verify exact keyword matching with vocabulary filtering.
"""

from models.manufacture_module import search_models_by_description
from pathlib import Path

if __name__ == "__main__":
    csv_path = str(Path(__file__).parent / "db" / "db_vehicle_models.csv")
    configs_dir = str(Path(__file__).parent / "configs")

    print("=" * 80)
    print("Test 1: Search for Mitsubishi 2026 Outlander PHEV GT (should exclude Premium variant)")
    print("=" * 80)
    results = search_models_by_description(
        make="Mitsubishi",
        year=2026,
        keywords=["outlander", "phev", "gt"],
        csv_path=csv_path,
        configs_dir=configs_dir,
        exclude_ev=False
    )
    print(f"Results: {len(results)} row(s)")
    if not results.empty:
        for idx, row in results.iterrows():
            print(f"  - {row['ModelNumber']}: {row['Description']}")
    print()

    print("=" * 80)
    print("Test 2: Search for Mitsubishi 2026 Outlander PHEV GT Premium")
    print("=" * 80)
    results = search_models_by_description(
        make="Mitsubishi",
        year=2026,
        keywords=["outlander", "phev", "gt", "premium"],
        csv_path=csv_path,
        configs_dir=configs_dir,
        exclude_ev=False
    )
    print(f"Results: {len(results)} row(s)")
    if not results.empty:
        for idx, row in results.iterrows():
            print(f"  - {row['ModelNumber']}: {row['Description']}")
    print()

    print("=" * 80)
    print("Test 3: Search for Mitsubishi 2026 RVR ES (should find RVR ES)")
    print("=" * 80)
    results = search_models_by_description(
        make="Mitsubishi",
        year=2026,
        keywords=["rvr", "es"],
        csv_path=csv_path,
        configs_dir=configs_dir,
        exclude_ev=False
    )
    print(f"Results: {len(results)} row(s)")
    if not results.empty:
        for idx, row in results.iterrows():
            print(f"  - {row['ModelNumber']}: {row['Description']}")
    print()

    print("=" * 80)
    print("Test 4: Search without configs_dir (graceful fallback - no vocab filtering)")
    print("=" * 80)
    results = search_models_by_description(
        make="Mitsubishi",
        year=2026,
        keywords=["outlander", "phev", "gt"],
        csv_path=csv_path,
        exclude_ev=False,
        configs_dir=None
    )
    print(f"Results: {len(results)} row(s) [may include Premium variant without filtering]")
    if not results.empty:
        for idx, row in results.iterrows():
            print(f"  - {row['ModelNumber']}: {row['Description']}")
    print()

    print("=" * 80)
    print("Test 5: Debug - what does the basic keyword search return?")
    print("=" * 80)
    from models.manufacture_module import load_existing_csv, build_word_boundary_pattern
    df = load_existing_csv(csv_path)
    df_make = df[df["Manufacturer"] == "Mitsubishi"]
    df_year = df_make[df_make["ModelYear"] == 2026]
    print(f"Mitsubishi 2026: {len(df_year)} rows")

    # Manual filter
    df_filtered = df_year.copy()
    for keyword in ["outlander", "phev", "gt"]:
        pattern = build_word_boundary_pattern(keyword)
        df_filtered = df_filtered[
            df_filtered["Description"].str.contains(pattern, case=False, na=False, regex=True)
        ]
    print(f"After keyword filtering: {len(df_filtered)} rows")
    if not df_filtered.empty:
        for idx, row in df_filtered.iterrows():
            print(f"  - {row['ModelNumber']}: {row['Description']}")
    print()
