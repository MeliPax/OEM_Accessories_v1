#!/usr/bin/env python3
"""
Phase 1 Discovery Script: Inspect real ADS API responses.

This is a small, development-only tool to fetch sample data from the ADS API
and inspect the raw response structure. Use this to:

1. Confirm the API is reachable with your credentials
2. Inspect the actual JSON field names and data types
3. Identify which fields map to our pipeline's ModelNumber, Description, etc.
4. Save sample responses for reference during mapper development

Usage:
    python inspect_sample.py

The script will:
- Load credentials from ads_api.env
- Fetch years from the API
- Pick one year, make, model, and fetch trims
- Pretty-print the response
- Save the raw JSON to sample_responses/ for reference
"""

import json
import sys
import traceback
from pathlib import Path
from datetime import datetime

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from chrome_api.config import load_ads_env, get_make_name_map
from chrome_api.client import ADSClient


def inspect_ads_api():
    """Main discovery workflow."""
    print("\n" + "=" * 70)
    print("ADS API Discovery — Phase 1")
    print("=" * 70)

    # Load credentials
    print("\n[1/5] Loading ADS credentials...")
    try:
        config = load_ads_env()
        print(f"      OK Base URL: {config['base_url']}")
        print(f"      OK API User: {config['api_user']}")
    except (FileNotFoundError, RuntimeError) as e:
        print(f"      ✗ Error: {e}")
        return 1

    # Initialize client
    print("\n[2/5] Initializing ADS client...")
    client = ADSClient(config["base_url"], config["api_user"], config["api_password"])
    print("      OK Client initialized")

    # Configuration
    sample_make = "Hyundai"
    language_locale = "CA_en"  # Format: country_language
    country = "CA"
    language = "en"

    # First, verify we can fetch models at all
    sample_year = 2026
    print(f"\n[3/5] Fetching models for {sample_year} {sample_make}...")
    try:
        models = client.get_models(sample_year, sample_make, country, language, "ASC")
        print(f"      Response type: {type(models)}")
        print(f"      Found {len(models)} models: {models[:10]}")
        if not models:
            print("      FAIL: No models returned - API may not be working")
            return 1
        sample_model = models[0]
        print(f"      Using model: {sample_model}")
    except Exception as e:
        print(f"      ERROR fetching models: {e}")
        traceback.print_exc()
        return 1

    # Fetch trims (now using POST method)
    print(f"\n[4/5] Fetching trims for {sample_year} {sample_make} {sample_model}...")
    try:
        trims_response = client.get_trims(sample_year, sample_make, sample_model, language_locale)
        print(f"      Received response (type: {type(trims_response).__name__})")

        if isinstance(trims_response, dict):
            print(f"      Response keys: {list(trims_response.keys())}")
            # Pretty-print the structure
            print("\n" + "=" * 70)
            print("RAW RESPONSE STRUCTURE")
            print("=" * 70)
            print(json.dumps(trims_response, indent=2)[:2000] + "...")

            # Save full response for reference
            sample_dir = Path(__file__).parent / "sample_responses"
            sample_dir.mkdir(exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            sample_file = sample_dir / f"ads_sample_{sample_year}_{sample_make}_{sample_model}_{timestamp}.json"
            with open(sample_file, "w") as f:
                json.dump(trims_response, f, indent=2)
            print(f"\nFull response saved to: {sample_file.relative_to(Path.cwd())}")

            # Ask follow-up questions for Phase 2
            print("\n" + "=" * 70)
            print("NEXT STEPS")
            print("=" * 70)
            print("""
1. Review the JSON structure above and the full file saved to sample_responses/
2. Identify which fields contain:
   - OEM order/configuration code (equivalent to our current ModelNumber)
   - Trim/configuration name (for Description)
   - Style/body type
   - Any other relevant data
3. Provide the field mapping to the developer
4. The mapper.py and service.py will be built based on this mapping
            """)
        else:
            print(f"      Unexpected response type: {type(trims_response)}")
            print(json.dumps(trims_response, indent=2))

    except Exception as e:
        print(f"      ERROR fetching trims: {e}")
        traceback.print_exc()
        return 1

    print("\n[5/5] Discovery complete!")

    print("\n" + "=" * 70)
    print("Discovery complete!")
    print("=" * 70 + "\n")
    return 0


if __name__ == "__main__":
    exit(inspect_ads_api())
