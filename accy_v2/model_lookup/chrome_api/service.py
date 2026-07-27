"""
Service to orchestrate ADS API data collection.

Coordinates years → makes → models → trims batch collection and transforms
responses into pipeline schema using mapper.py.
"""

import pandas as pd
from typing import List, Optional, Any
from .config import load_ads_env, get_make_name_map
from .client import ADSClient
from .mapper import ads_response_to_rows
from .validators import validate_unique_keys


class ADSService:
    """Orchestrator for ADS API calls and data transformation."""

    def __init__(self, pipeline_logger: Optional[Any] = None, dq_logger: Optional[Any] = None):
        """Initialize ADS service with credentials and client.

        Args:
            pipeline_logger: Optional PipelineLogger for dev/ops logs (defaults to print)
            dq_logger: Optional DQLogger for data quality warnings (defaults to print)
        """
        config = load_ads_env()
        self.client = ADSClient(
            config["base_url"],
            config["api_user"],
            config["api_password"],
        )
        self.make_map = get_make_name_map()
        self.pipeline_logger = pipeline_logger
        self.dq_logger = dq_logger

    def _log_info(self, msg: str) -> None:
        """Log info message to pipeline logger or print."""
        if self.pipeline_logger:
            self.pipeline_logger.info(msg)
        else:
            print(msg)

    def _log_warning(self, msg: str) -> None:
        """Log warning message to pipeline logger or print."""
        if self.pipeline_logger:
            self.pipeline_logger.warning(msg)
        else:
            print(f"WARNING: {msg}")

    def _log_dq_warning(self, make: str, model_number: str, issue: str) -> None:
        """Log data quality warning."""
        if self.dq_logger:
            self.dq_logger.log_warning(
                sheet_name=make,
                model_name=model_number,
                record_index=None,
                record_snapshot={"ModelNumber": model_number},
                rule_violated="ads_style_uniqueness_rule",
                issue_description=issue,
            )
        else:
            print(f"DQ WARNING [{make}] {model_number}: {issue}")

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
            pandas DataFrame with 9-column schema ready for save_vehicle_models_to_csv()
        """
        all_rows = []

        for make in makes:
            self._log_info(f"\nFetching {make}...")

            # Verify make is known
            if make not in self.make_map:
                self._log_warning(f"Unknown make {make}, skipping")
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
                            self._log_warning(f"Error fetching {year} {make} {model}: {model_err}")
                            continue

                    print("OK", end=" ")

                except Exception as year_err:
                    self._log_warning(f"Error fetching {year}: {year_err}")
                    continue

            print()

        # Convert to DataFrame
        if not all_rows:
            self._log_warning("No rows fetched from ADS")
            return pd.DataFrame(
                columns=[
                    "Manufacturer",
                    "ModelYear",
                    "ModelNumber",
                    "Description",
                    "TrimName",
                    "Package",
                    "Style_ID",
                    "Drivetrain",
                    "PassDoors",
                ]
            )

        df = pd.DataFrame(all_rows)

        # Validate uniqueness: check for in-batch duplicates on 4-column key
        unique_key = ["Manufacturer", "ModelYear", "ModelNumber", "Package"]
        df_deduped, df_dupes = validate_unique_keys(df, unique_key)

        if not df_dupes.empty:
            self._log_warning(f"Found {len(df_dupes)} in-batch duplicate(s) on unique key {unique_key}")
            for _, dupe_row in df_dupes.iterrows():
                issue = (
                    f"[ADS_DUPLICATE_STYLE] Duplicate configuration: "
                    f"{dupe_row['Manufacturer']} {dupe_row['ModelYear']} "
                    f"{dupe_row['ModelNumber']} (Package={dupe_row['Package']})"
                )
                self._log_dq_warning(
                    dupe_row["Manufacturer"],
                    dupe_row["ModelNumber"],
                    issue,
                )
            df = df_deduped

        self._log_info(f"\nFetched {len(df)} vehicle configurations from ADS (after dedup)")
        self._log_info(f"Manufacturers: {df['Manufacturer'].unique().tolist()}")
        self._log_info(f"Years: {sorted(df['ModelYear'].unique().tolist())}")

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
                rows = [r for r in rows if r.get("TrimName") == trim]

            if not rows:
                return pd.DataFrame(
                    columns=[
                        "Manufacturer",
                        "ModelYear",
                        "ModelNumber",
                        "Description",
                        "TrimName",
                        "Package",
                        "Style_ID",
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
                        self._log_warning(f"Error fetching {year} {make} {model}: {model_err}")
                        continue

            except Exception as year_err:
                self._log_warning(f"Error fetching {year} for {make}: {year_err}")
                continue

        if not all_rows:
            return pd.DataFrame(
                columns=[
                    "Manufacturer",
                    "ModelYear",
                    "ModelNumber",
                    "Description",
                    "TrimName",
                    "Package",
                    "Style_ID",
                    "Drivetrain",
                    "PassDoors",
                ]
            )

        df = pd.DataFrame(all_rows)

        # Validate uniqueness within this batch
        unique_key = ["Manufacturer", "ModelYear", "ModelNumber", "Package"]
        df_deduped, df_dupes = validate_unique_keys(df, unique_key)

        if not df_dupes.empty:
            self._log_warning(f"Found {len(df_dupes)} in-batch duplicate(s) on unique key {unique_key}")
            for _, dupe_row in df_dupes.iterrows():
                issue = (
                    f"[ADS_DUPLICATE_STYLE] Duplicate configuration: "
                    f"{dupe_row['Manufacturer']} {dupe_row['ModelYear']} "
                    f"{dupe_row['ModelNumber']} (Package={dupe_row['Package']})"
                )
                self._log_dq_warning(dupe_row["Manufacturer"], dupe_row["ModelNumber"], issue)
            df = df_deduped

        return df

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
            self._log_info(f"Auto-discovered makes: {makes}")

        # Auto-discover years if not provided
        if years is None:
            try:
                years = self.client.get_years(country, language, "DESC")
                self._log_info(f"Auto-discovered years: {years}")
            except Exception as e:
                self._log_warning(f"Could not auto-discover years: {e}")
                years = [2024, 2025, 2026]
                self._log_info(f"Falling back to default years: {years}")

        all_rows = []

        for make in makes:
            self._log_info(f"\nDumping {make}...")

            if make not in self.make_map:
                self._log_warning(f"Unknown make {make}, skipping")
                continue

            make_df = self.fetch_make(make, years, country, language, language_locale)

            if not make_df.empty:
                all_rows.append(make_df)
                self._log_info(f"  {len(make_df)} records for {make}")

                # Incremental save if callback provided
                if save_callback:
                    try:
                        save_callback(make, make_df)
                    except Exception as save_err:
                        self._log_warning(f"Save callback failed for {make}: {save_err}")

        # Concatenate all makes
        if not all_rows:
            self._log_warning("No rows fetched from ADS")
            return pd.DataFrame(
                columns=[
                    "Manufacturer",
                    "ModelYear",
                    "ModelNumber",
                    "Description",
                    "TrimName",
                    "Package",
                    "Style_ID",
                    "Drivetrain",
                    "PassDoors",
                ]
            )

        result_df = pd.concat(all_rows, ignore_index=True)
        self._log_info(f"\nTotal fetched: {len(result_df)} configurations")

        return result_df
