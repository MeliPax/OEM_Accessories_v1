#!/usr/bin/env python3
"""
Shorthand database commands (delegates to accy_v2/model_lookup/refresh_db_ads.py).

Usage - APPEND (add data without archiving):
    python run_db.py append mitsubishi                    # Add Mitsubishi (2024-2026)
    python run_db.py append mitsubishi --years 2023 2024  # Specific years

Usage - REFRESH (archive then replace):
    python run_db.py refresh hyundai                      # Full refresh (with archive)
    python run_db.py refresh hyundai --years 2024 2025    # Specific years (with archive)

These are shortcuts to refresh_db_ads.py:
    append  = refresh_db_ads.py --no-archive
    refresh = refresh_db_ads.py (no flag)
"""

import sys
import subprocess
from pathlib import Path

project_root = Path(__file__).parent

# Valid make names (for case-insensitive lookup)
VALID_MAKES = {
    "hyundai": "Hyundai",
    "honda": "Honda",
    "kia": "Kia",
    "genesis": "Genesis",
    "mazda": "Mazda",
    "mitsubishi": "Mitsubishi",
    "volkswagen": "Volkswagen",
}


def normalize_make(make_str: str) -> str:
    """
    Normalize make name to correct capitalization.

    Args:
        make_str: Make name (any case)

    Returns:
        Properly capitalized make name

    Raises:
        ValueError: If make name is not valid
    """
    normalized = VALID_MAKES.get(make_str.lower())
    if not normalized:
        valid = ", ".join(sorted(VALID_MAKES.values()))
        raise ValueError(
            f"Unknown make: '{make_str}'\nValid makes: {valid}"
        )
    return normalized


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "append":
        if len(sys.argv) < 3:
            print("Usage: python run_db.py append MAKE [--years YEAR1 YEAR2 ...]")
            print("Example: python run_db.py append mitsubishi")
            print("         python run_db.py append mitsubishi --years 2023 2024 2025")
            print("\nValid makes (case-insensitive):")
            for make in sorted(VALID_MAKES.values()):
                print(f"  - {make}")
            sys.exit(1)

        try:
            make = normalize_make(sys.argv[2])
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)

        # Build command: refresh_db_ads.py --makes MAKE --no-archive [--years ...]
        cmd = [
            sys.executable,
            str(project_root / "accy_v2" / "model_lookup" / "refresh_db_ads.py"),
            "--makes", make,
            "--no-archive"
        ]

        # Add years if specified
        if "--years" in sys.argv:
            years_idx = sys.argv.index("--years") + 1
            cmd.extend(["--years"] + sys.argv[years_idx:])

        # Run as subprocess
        result = subprocess.run(cmd, cwd=str(project_root))
        sys.exit(result.returncode)

    elif command == "refresh":
        if len(sys.argv) < 3:
            print("Usage: python run_db.py refresh MAKE [--years YEAR1 YEAR2 ...]")
            print("Example: python run_db.py refresh hyundai")
            print("         python run_db.py refresh hyundai --years 2024 2025 2026")
            print("\nValid makes (case-insensitive):")
            for make in sorted(VALID_MAKES.values()):
                print(f"  - {make}")
            sys.exit(1)

        try:
            make = normalize_make(sys.argv[2])
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)

        # Build command: refresh_db_ads.py --makes MAKE [--years ...]
        cmd = [
            sys.executable,
            str(project_root / "accy_v2" / "model_lookup" / "refresh_db_ads.py"),
            "--makes", make
        ]

        # Add years if specified
        if "--years" in sys.argv:
            years_idx = sys.argv.index("--years") + 1
            cmd.extend(["--years"] + sys.argv[years_idx:])

        # Run as subprocess
        result = subprocess.run(cmd, cwd=str(project_root))
        sys.exit(result.returncode)

    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
