"""
Debug the vocabulary post-filter to see what's going wrong.
"""

from models.manufacture_module import (
    load_existing_csv,
    load_manufacturer_keyword_vocab,
    _extract_description_tokens,
    build_word_boundary_pattern,
)
from pathlib import Path

if __name__ == "__main__":
    csv_path = str(Path(__file__).parent / "db" / "db_vehicle_models.csv")
    configs_dir = str(Path(__file__).parent / "configs")

    # Load vocab
    vocab = load_manufacturer_keyword_vocab("Mitsubishi", configs_dir)
    print(f"Loaded vocabulary for Mitsubishi: {len(vocab)} keywords")
    print(f"Sample keywords: {sorted(list(vocab))[:10]}")
    print()

    # Get the test descriptions
    df = load_existing_csv(csv_path)
    df_make = df[df["Manufacturer"] == "Mitsubishi"]
    df_year = df_make[df_make["ModelYear"] == 2026]

    # Filter by keywords manually
    df_filtered = df_year.copy()
    keywords = ["outlander", "phev", "gt"]
    for keyword in keywords:
        pattern = build_word_boundary_pattern(keyword)
        df_filtered = df_filtered[
            df_filtered["Description"].str.contains(pattern, case=False, na=False, regex=True)
        ]

    print(f"Rows matching keywords {keywords}: {len(df_filtered)}")
    print()

    # Check each row
    search_kw_set = {kw.lower() for kw in keywords}
    print(f"Search keyword set: {search_kw_set}")
    print()

    for idx, row in df_filtered.iterrows():
        desc = row["Description"]
        tokens = set(_extract_description_tokens(desc))
        extra_tokens = tokens & vocab - search_kw_set
        has_extra = bool(extra_tokens)

        print(f"Description: {desc}")
        print(f"  Tokens: {tokens}")
        print(f"  Extra vocab tokens: {extra_tokens}")
        print(f"  Would be filtered out: {has_extra}")
        print()
