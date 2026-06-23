"""
Test that model_lookup has been successfully moved to accy_v2 and all paths work.
"""

import sys
from pathlib import Path

def test_import_from_accy_v2():
    """Test importing from accy_v2 directory."""
    print("Test 1: Import from accy_v2")
    sys.path.insert(0, str(Path(__file__).parent / "accy_v2"))

    try:
        from model_lookup.models.manufacture_module import search_models_by_description
        print("  [OK] Import successful")
        return True
    except Exception as e:
        print(f"  [FAIL] Import failed: {e}")
        return False


def test_search_function():
    """Test the search function works."""
    print("\nTest 2: Search function")
    try:
        from model_lookup.models.manufacture_module import search_models_by_description

        result = search_models_by_description(
            "Mitsubishi", 2026, ["outlander", "phev", "gt"]
        )

        if len(result) == 1:
            print(f"  [OK] Search works - found 1 result (exact match)")
            return True
        else:
            print(f"  [FAIL] Search returned {len(result)} results (expected 1)")
            return False
    except Exception as e:
        print(f"  [FAIL] Search failed: {e}")
        return False


def test_vocabulary_loading():
    """Test vocabulary loading."""
    print("\nTest 3: Vocabulary loading")
    try:
        from model_lookup.models.manufacture_module import load_manufacturer_keyword_vocab

        vocab = load_manufacturer_keyword_vocab("Mitsubishi")
        if len(vocab) > 0:
            print(f"  [OK] Vocab loaded - {len(vocab)} keywords")
            return True
        else:
            print(f"  [FAIL] Vocab is empty")
            return False
    except Exception as e:
        print(f"  [FAIL] Vocab loading failed: {e}")
        return False


def test_csv_path():
    """Test that CSV path resolves correctly."""
    print("\nTest 4: CSV path resolution")
    try:
        from pathlib import Path
        csv_path = Path(__file__).parent / "accy_v2" / "model_lookup" / "db" / "db_vehicle_models.csv"

        if csv_path.exists():
            print(f"  [OK] CSV found at: {csv_path}")
            return True
        else:
            print(f"  [FAIL] CSV not found at: {csv_path}")
            return False
    except Exception as e:
        print(f"  [FAIL] Path check failed: {e}")
        return False


def test_configs_dir():
    """Test that configs directory exists."""
    print("\nTest 5: Configs directory")
    try:
        from pathlib import Path
        configs_dir = Path(__file__).parent / "accy_v2" / "model_lookup" / "configs"

        if configs_dir.exists() and configs_dir.is_dir():
            vocab_files = list(configs_dir.glob("*_keywords.json"))
            if vocab_files:
                print(f"  [OK] Configs found - {len(vocab_files)} vocab files")
                return True
            else:
                print(f"  [FAIL] No vocab files in configs")
                return False
        else:
            print(f"  [FAIL] Configs directory not found at: {configs_dir}")
            return False
    except Exception as e:
        print(f"  [FAIL] Configs check failed: {e}")
        return False


def test_step4_5_import():
    """Test that step4_5 module can be imported."""
    print("\nTest 6: Step 4.5 import")
    try:
        sys.path.insert(0, str(Path(__file__).parent / "accy_v2"))
        from oems.mitsubishi.pipeline.step4_5_model_enrichment import run
        print("  [OK] Step 4.5 import successful")
        return True
    except Exception as e:
        print(f"  [FAIL] Step 4.5 import failed: {e}")
        return False


def test_old_model_lookup_still_exists():
    """Test that old model_lookup directory still exists (not deleted yet)."""
    print("\nTest 7: Old model_lookup still exists")
    try:
        old_path = Path(__file__).parent / "model_lookup"
        if old_path.exists():
            print(f"  [OK] Old model_lookup still exists at: {old_path}")
            print("    (This is expected - you may want to delete it after verifying everything works)")
            return True
        else:
            print(f"  [INFO] Old model_lookup not found (already deleted)")
            return True
    except Exception as e:
        print(f"  [FAIL] Check failed: {e}")
        return False


if __name__ == "__main__":
    print("=" * 70)
    print("Testing model_lookup migration to accy_v2")
    print("=" * 70)

    results = []
    results.append(("Import from accy_v2", test_import_from_accy_v2()))
    results.append(("Search function", test_search_function()))
    results.append(("Vocabulary loading", test_vocabulary_loading()))
    results.append(("CSV path", test_csv_path()))
    results.append(("Configs directory", test_configs_dir()))
    results.append(("Step 4.5 import", test_step4_5_import()))
    results.append(("Old model_lookup exists", test_old_model_lookup_still_exists()))

    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "[OK]" if result else "[FAIL]"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} passed")

    if passed == total:
        print("\n[SUCCESS] Migration successful! All tests passed.")
        sys.exit(0)
    else:
        print(f"\n[WARNING] {total - passed} test(s) failed. Review errors above.")
        sys.exit(1)
