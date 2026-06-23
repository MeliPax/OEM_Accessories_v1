"""
Bootstrap script to generate keyword vocabulary JSON files for all manufacturers.
Run this once after updating the model database, or whenever you want to refresh vocabularies.

Usage:
    python bootstrap_vocabs.py
"""

from models.manufacture_module import bootstrap_all_vocabs
from pathlib import Path

if __name__ == "__main__":
    csv_path = str(Path(__file__).parent / "db" / "db_vehicle_models.csv")
    configs_dir = str(Path(__file__).parent / "configs")

    print(f"CSV path: {csv_path}")
    print(f"Configs dir: {configs_dir}")
    print()

    result = bootstrap_all_vocabs(csv_path, configs_dir)

    if result.get("status") == "success":
        manufacturers = result.get("manufacturers", {})
        print(f"[OK] Successfully generated vocabularies for {len(manufacturers)} manufacturers:")
        print()
        for make, vocab_result in manufacturers.items():
            if vocab_result.get("saved", False):
                keyword_count = vocab_result.get("keyword_count", 0)
                print(f"  {make}: {keyword_count} unique keywords")
                print(f"    -> {vocab_result.get('file_path')}")
            else:
                print(f"  {make}: ERROR - {vocab_result.get('error', 'Unknown error')}")
    else:
        print(f"[FAIL] Bootstrap failed: {result.get('message')}")
