"""
Service to orchestrate ADS API data collection.

Coordinates years → makes → models → trims batch collection and transforms
responses into pipeline schema using mapper.py.

Features:
  - Configuration-driven engine_type extraction (ENGINE_TYPE keywords + translator)
  - Dynamic loading of OEM-specific classification and translator configs
  - Comprehensive logging via structured logging module
"""

import json
import yaml
import logging
import pandas as pd
from typing import List, Optional, Any, Dict
from pathlib import Path
from .config import load_ads_env, get_make_name_map
from .client import ADSClient
from .mapper import ads_response_to_rows
from .validators import validate_unique_keys
from ..semantic.standardizer import DataStandardizer
from ..semantic.translator import load_oem_translator

logger = logging.getLogger(__name__)


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
        self._config_cache = {}  # Cache for loaded configs (classification/translator)

    def _load_config_for_make(self, make: str) -> tuple:
        """
        Load classification, translator, and standardizer configs for an OEM.

        Caches loaded configs to avoid repeated file I/O.

        Args:
            make: OEM name (e.g., "Hyundai")

        Returns:
            Tuple of (classification_dict, translator_dict, standardizer_obj)
            Returns None for missing configs

        Logs:
            - DEBUG: Config loading attempt, cached retrieve
            - INFO: Config loaded successfully
            - WARNING: Config file not found
            - ERROR: Config loading failure
        """
        # Return from cache if already loaded
        if make in self._config_cache:
            logger.debug(f"service | {make} | Config retrieved from cache")
            return self._config_cache[make]

        try:
            configs_dir = Path(__file__).parent.parent / "configs"
            # New paths: configs/{make}/{file}.yaml instead of {make}_{file}.json
            make_lower = make.lower()
            classification_file = configs_dir / make_lower / "classification.yaml"
            standardization_file = configs_dir / make_lower / "standardization.yaml"

            logger.debug(
                f"service | {make} | Loading configs from: {configs_dir}"
            )

            # Load classification
            classification = None
            if classification_file.exists():
                with open(classification_file, 'r') as f:
                    classification = yaml.safe_load(f)
                logger.debug(
                    f"service | {make} | Loaded classification.yaml "
                    f"({len(classification.get('token_map', {}))} keywords)"
                )
            else:
                logger.warning(
                    f"service | {make} | Classification file not found: {classification_file}"
                )

            # Load translator (use load_oem_translator to get flattened dict)
            translator = load_oem_translator(make, str(configs_dir))
            if translator:
                logger.debug(
                    f"service | {make} | Loaded translator.yaml "
                    f"({len(translator)} flattened keywords)"
                )
            else:
                logger.warning(
                    f"service | {make} | Translator file not found"
                )

            # Load standardizer
            standardizer = None
            if standardization_file.exists():
                with open(standardization_file, 'r') as f:
                    config = yaml.safe_load(f)
                standardizer = DataStandardizer(config, make)
                logger.debug(
                    f"service | {make} | Loaded standardization.yaml with "
                    f"{len(config.get('standardization_rules', {}))} rule categories"
                )
            else:
                logger.debug(
                    f"service | {make} | Standardization file not found: {standardization_file}"
                )

            config_status = []
            if classification:
                config_status.append("classification")
            if translator:
                config_status.append("translator")
            if standardizer:
                config_status.append("standardizer")

            if config_status:
                logger.info(
                    f"service | {make} | Configs loaded | components: {', '.join(config_status)}"
                )
            else:
                logger.warning(
                    f"service | {make} | No configs found (engine_type extraction and standardization disabled)"
                )

            # Cache the result
            self._config_cache[make] = (classification, translator, standardizer)
            return classification, translator, standardizer

        except Exception as e:
            logger.error(
                f"service | {make} | FAILED to load config files | Error: {str(e)}"
            )
            self._config_cache[make] = (None, None, None)
            return None, None, None

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

        Features:
          - Loads OEM-specific classification and translator configs
          - Extracts engine_type from ModelName/Description using ENGINE_TYPE keywords
          - Deduplicates on 4-column uniqueness key (Manufacturer+Year+ModelNumber+Package)
          - Logs progress with engine_type extraction details

        Args:
            makes: List of ADS make names (e.g., ["Hyundai", "Genesis"])
            years: List of model years (e.g., [2024, 2025, 2026])
            country: Country code for years/makes fetch (e.g., "CA")
            language: Language code for years/makes fetch (e.g., "en")
            language_locale: Locale for trims fetch (e.g., "CA_en")

        Returns:
            pandas DataFrame with 10-column schema ready for save_vehicle_models_to_csv():
            Manufacturer, ModelYear, ModelNumber, Description, TrimName,
            Package, Drivetrain, PassDoors, ModelName, engine_type
        """
        all_rows = []

        for make in makes:
            self._log_info(f"\nFetching {make}...")
            logger.info(f"refresh_from_ads | {make} | Starting fetch")

            # Verify make is known
            if make not in self.make_map:
                self._log_warning(f"Unknown make {make}, skipping")
                logger.warning(f"refresh_from_ads | {make} | Unknown make, skipping")
                continue

            # Load configuration for this make (classification, translator, standardizer)
            classification, translator, standardizer = self._load_config_for_make(make)

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

                            # Transform to rows (with engine_type extraction and standardization)
                            rows = ads_response_to_rows(
                                trims_response, make, classification, translator, standardizer
                            )
                            all_rows.extend(rows)
                            logger.debug(
                                f"refresh_from_ads | {make} {year} {model} | "
                                f"Converted {len(rows)} trims to rows"
                            )

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
            logger.error(f"fetch_vehicle | {make} | Unknown make")
            raise ValueError(f"Unknown make: {make}")

        try:
            logger.debug(f"fetch_vehicle | {make} {year} {model} | Fetching trims")

            # Load configuration for this make
            classification, translator, standardizer = self._load_config_for_make(make)

            trims_response = self.client.get_trims(year, make, model, language_locale)
            rows = ads_response_to_rows(trims_response, make, classification, translator, standardizer)
            logger.debug(f"fetch_vehicle | {make} {year} {model} | Converted {len(rows)} trims")

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
            logger.error(f"fetch_make | {make} | Unknown make")
            raise ValueError(f"Unknown make: {make}")

        logger.info(f"fetch_make | {make} | Fetching for years: {years}")

        # Load configuration for this make (once, reuse for all years)
        classification, translator, standardizer = self._load_config_for_make(make)

        all_rows = []

        for year in years:
            try:
                logger.debug(f"fetch_make | {make} {year} | Fetching models")
                models = self.client.get_models(year, make, country, language, "ASC")

                for model in models:
                    try:
                        trims_response = self.client.get_trims(
                            year, make, model, language_locale
                        )
                        rows = ads_response_to_rows(
                            trims_response, make, classification, translator, standardizer
                        )
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
