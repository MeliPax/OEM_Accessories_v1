"""
Service to orchestrate ADS API data collection.

Coordinates years → makes → models → trims batch collection and transforms
responses into pipeline schema using mapper.py.
"""

import pandas as pd
from typing import List, Optional
from .config import load_ads_env, get_make_name_map
from .client import ADSClient
from .mapper import ads_response_to_rows


class ADSService:
    """Orchestrator for ADS API calls and data transformation."""

    def __init__(self):
        """Initialize ADS service with credentials and client."""
        config = load_ads_env()
        self.client = ADSClient(
            config["base_url"],
            config["api_user"],
            config["api_password"],
        )
        self.make_map = get_make_name_map()

    def refresh_from_ads(
        self,
        makes: List[str],
        years: List[int],
        country: str = "CA",
        language: str = "en",
        language_locale: str = "CA_en",
    ) -> pd.DataFrame:
        """
        Fetch vehicle data from ADS and transform to pipeline schema.

        Args:
            makes: List of ADS make names (e.g., ["Hyundai", "Genesis"])
            years: List of model years (e.g., [2024, 2025, 2026])
            country: Country code for years/makes fetch (e.g., "CA")
            language: Language code for years/makes fetch (e.g., "en")
            language_locale: Locale for trims fetch (e.g., "CA_en")

        Returns:
            pandas DataFrame with 7-column schema ready for save_vehicle_models_to_csv()
        """
        all_rows = []

        for make in makes:
            print(f"\nFetching {make}...")

            # Verify make is known
            if make not in self.make_map:
                print(f"  WARNING: Unknown make {make}, skipping")
                continue

            for year in years:
                print(f"  {year}...", end=" ", flush=True)

                try:
                    # Fetch models for this year/make
                    models = self.client.get_models(year, make, country, language, "ASC")

                    for model in models:
                        try:
                            # Fetch trims for this year/make/model
                            trims_response = self.client.get_trims(
                                year, make, model, language_locale
                            )

                            # Transform to rows
                            rows = ads_response_to_rows(trims_response, make)
                            all_rows.extend(rows)

                        except Exception as model_err:
                            print(f"\n    Error fetching {year} {make} {model}: {model_err}")
                            continue

                    print("OK", end=" ")

                except Exception as year_err:
                    print(f"\n  Error fetching {year}: {year_err}")
                    continue

            print()

        # Convert to DataFrame
        if not all_rows:
            print("WARNING: No rows fetched from ADS")
            return pd.DataFrame(
                columns=[
                    "Manufacturer",
                    "ModelYear",
                    "ModelNumber",
                    "Description",
                    "Description2",
                    "Package",
                    "Style_ID",
                    "StyleID",
                    "Drivetrain",
                    "PassDoors",
                ]
            )

        df = pd.DataFrame(all_rows)

        print(f"\nFetched {len(df)} vehicle configurations from ADS")
        print(f"Manufacturers: {df['Manufacturer'].unique().tolist()}")
        print(f"Years: {sorted(df['ModelYear'].unique().tolist())}")

        return df

    def fetch_vehicle(
        self,
        make: str,
        model: str,
        year: int,
        trim: Optional[str] = None,
        country: str = "CA",
        language: str = "en",
        language_locale: str = "CA_en",
    ) -> pd.DataFrame:
        """
        Fetch data for a single vehicle (minimal API calls).

        Calls only get_trims() — no get_models() needed since model name is provided.
        Optionally filters to a specific trim by Package.

        Args:
            make: ADS make name (e.g., "Hyundai")
            model: Model name (e.g., "Elantra")
            year: Model year
            trim: Optional trim/package name to filter results (e.g., "Essential")
            country: Country code for trims fetch
            language: Language code
            language_locale: Locale for trims fetch (e.g., "CA_en")

        Returns:
            DataFrame with matching rows (likely 1 row if trim specified, multiple if not)
        """
        if make not in self.make_map:
            raise ValueError(f"Unknown make: {make}")

        try:
            trims_response = self.client.get_trims(year, make, model, language_locale)
            rows = ads_response_to_rows(trims_response, make)

            # Filter by trim if specified
            if trim and rows:
                rows = [r for r in rows if r.get("Package") == trim]

            if not rows:
                return pd.DataFrame(
                    columns=[
                        "Manufacturer",
                        "ModelYear",
                        "ModelNumber",
                        "Description",
                        "Description2",
                        "Package",
                        "Style_ID",
                        "StyleID",
                        "Drivetrain",
                        "PassDoors",
                    ]
                )

            return pd.DataFrame(rows)
        except Exception as e:
            print(f"Error fetching {year} {make} {model}: {e}")
            raise

    def fetch_make(
        self,
        make: str,
        years: List[int],
        country: str = "CA",
        language: str = "en",
        language_locale: str = "CA_en",
    ) -> pd.DataFrame:
        """
        Fetch all vehicles for one make across multiple years.

        For each year: calls get_models() once, then get_trims() per model.
        Used for targeted OEM/year refreshes.

        Args:
            make: ADS make name (e.g., "Hyundai")
            years: List of model years
            country: Country code
            language: Language code
            language_locale: Locale for trims fetch

        Returns:
            DataFrame with all trims for the make/years combination
        """
        if make not in self.make_map:
            raise ValueError(f"Unknown make: {make}")

        all_rows = []

        for year in years:
            try:
                models = self.client.get_models(year, make, country, language, "ASC")

                for model in models:
                    try:
                        trims_response = self.client.get_trims(
                            year, make, model, language_locale
                        )
                        rows = ads_response_to_rows(trims_response, make)
                        all_rows.extend(rows)
                    except Exception as model_err:
                        print(f"  Error fetching {year} {make} {model}: {model_err}")
                        continue

            except Exception as year_err:
                print(f"Error fetching {year} for {make}: {year_err}")
                continue

        if not all_rows:
            return pd.DataFrame(
                columns=[
                    "Manufacturer",
                    "ModelYear",
                    "ModelNumber",
                    "Description",
                    "Description2",
                    "Package",
                    "Style_ID",
                    "Drivetrain",
                    "PassDoors",
                ]
            )

        return pd.DataFrame(all_rows)

    def dump_all(
        self,
        makes: Optional[List[str]] = None,
        years: Optional[List[int]] = None,
        country: str = "CA",
        language: str = "en",
        language_locale: str = "CA_en",
        save_callback=None,
    ) -> pd.DataFrame:
        """
        One-time full data dump from ADS.

        Fetches all vehicles for specified makes/years. Auto-discovers makes and years
        if not provided. Optionally calls save_callback after each make for incremental
        saves (recommended to bound memory and prevent loss from late failures).

        Args:
            makes: List of ADS make names. If None, uses all known makes.
            years: List of model years. If None, fetches from API.
            country: Country code
            language: Language code
            language_locale: Locale for trims fetch
            save_callback: Optional callable(make, df) for incremental saves after each make

        Returns:
            Concatenated DataFrame for all makes/years
        """
        # Auto-discover makes if not provided
        if makes is None:
            makes = list(self.make_map.keys())
            print(f"Auto-discovered makes: {makes}")

        # Auto-discover years if not provided
        if years is None:
            try:
                years = self.client.get_years(country, language, "DESC")
                print(f"Auto-discovered years: {years}")
            except Exception as e:
                print(f"Warning: Could not auto-discover years: {e}")
                years = [2024, 2025, 2026]
                print(f"Falling back to default years: {years}")

        all_rows = []

        for make in makes:
            print(f"\nDumping {make}...")

            if make not in self.make_map:
                print(f"  WARNING: Unknown make {make}, skipping")
                continue

            make_df = self.fetch_make(make, years, country, language, language_locale)

            if not make_df.empty:
                all_rows.append(make_df)
                print(f"  {len(make_df)} records for {make}")

                # Incremental save if callback provided
                if save_callback:
                    try:
                        save_callback(make, make_df)
                    except Exception as save_err:
                        print(f"  Warning: Save callback failed for {make}: {save_err}")

        # Concatenate all makes
        if not all_rows:
            print("WARNING: No rows fetched from ADS")
            return pd.DataFrame(
                columns=[
                    "Manufacturer",
                    "ModelYear",
                    "ModelNumber",
                    "Description",
                    "Description2",
                    "Package",
                    "Style_ID",
                    "Drivetrain",
                    "PassDoors",
                ]
            )

        result_df = pd.concat(all_rows, ignore_index=True)
        print(f"\nTotal fetched: {len(result_df)} configurations")

        return result_df
