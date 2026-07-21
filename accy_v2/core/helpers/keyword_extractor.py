from typing import List, Dict, Any
import re

from core.helpers.pipeline_logger import PipelineLogger


class KeywordExtractor:
    """
    Extract vehicle lookup keywords from sheet name and trim data.
    Handles model name, fuel type, and composite trim parsing.

    Examples:
        Sheet name: "2026_Outlander_ES_EN"
        Trim: "ES_GT-P"
        Result keywords: ["outlander", "es", "gt", "premium"]
    """

    def __init__(self, oem_config: Dict[str, Any], pipeline_logger: PipelineLogger):
        """
        Initialize with OEM-specific configuration.

        Args:
            oem_config: OEM-specific configuration with fuel_type_keywords,
                       trim_abbreviation_library, etc.
            pipeline_logger: Logger for debug and warning messages
        """
        self.oem_config = oem_config
        self.logger = pipeline_logger
        self.fuel_keywords = set(k.upper() for k in oem_config.get("fuel_type_keywords", []))
        self.abbreviation_lib = self._normalize_abbreviation_lib(
            oem_config.get("trim_abbreviation_library", {})
        )

    def extract_from_sheet_name(self, sheet_name: str) -> Dict[str, Any]:
        """
        Parse sheet name: YYYY_ModelName_Language or YYYY ModelName Language

        Args:
            sheet_name: Sheet name from Excel file (e.g., "2026_Outlander_ES_EN" or "2026 Outlander ES EN")

        Returns:
            {
                "model_keywords": [...],  # e.g., ["outlander", "es"]
                "fuel_type": "EV"|"PHEV"|None
            }

        Raises:
            ValueError: If sheet_name format is invalid or model keywords are empty
        """
        try:
            # Try underscore first, then space
            if "_" in sheet_name:
                parts = sheet_name.split("_")
            else:
                parts = sheet_name.split()

            # Expected format: YYYY_..._Language (minimum 3 parts)
            if len(parts) < 2:
                raise ValueError(
                    f"Sheet name '{sheet_name}' doesn't match expected format "
                    f"YYYY_ModelName_Language or YYYY ModelName (got {len(parts)} parts)"
                )

            # Validate first part is a 4-digit year
            year = parts[0]
            if not year.isdigit() or len(year) != 4:
                raise ValueError(
                    f"First segment '{year}' is not a valid 4-digit year"
                )

            # Check if last part is a language code (2 letters, typically EN/FR)
            last_part = parts[-1].upper()
            is_language_code = len(last_part) == 2 and last_part.isalpha()

            if is_language_code:
                # Format: YYYY_..._Language
                model_parts = parts[1:-1]
            else:
                # Format: YYYY_ModelName (no language suffix)
                model_parts = parts[1:]

            if not model_parts:
                raise ValueError(
                    f"No model name found in: {sheet_name}"
                )

            # Process model parts for fuel type and keywords
            result = self._process_model_parts(model_parts, sheet_name)

            # Note: model_keywords may be empty if all parts are fuel type keywords
            # For example: "2026 PHEV" has only fuel type, no model name
            # In this case, we return what we have and let the caller decide
            return result

        except ValueError as e:
            self.logger.warning(f"Sheet name parsing error: {str(e)}")
            raise
        except Exception as e:
            self.logger.warning(f"Unexpected error parsing sheet name '{sheet_name}': {str(e)}")
            raise

    def extract_from_trim(self, trim_value: str) -> List[str]:
        """
        Parse trim value: simple or composite (with _ or -)

        Args:
            trim_value: Trim value from DataFrame (e.g., "ES_GT-P")

        Returns:
            List of keywords in order (e.g., ["es", "gt", "premium"])

        Examples:
            "ES" → ["es"]
            "ES_FWD" → ["es", "fwd"]
            "ES_GT-P" → ["es", "gt", "premium"]
            "ES-P_AWC" → ["es", "premium", "awc"]
            "ES-XYZ" → ["es", "es-xyz"]  (xyz not in library, kept as-is with dash)
        """
        if not trim_value or not isinstance(trim_value, str):
            return []

        try:
            trim_value = trim_value.strip().rstrip("*").strip().lower()

            if not trim_value:
                return []

            # Step 1: Split by underscore (main delimiter)
            components = [c.strip() for c in trim_value.split("_")]
            components = [c for c in components if c]  # Remove empty strings

            # Step 2: Process each component for dash abbreviations
            keywords = []
            for component in components:
                processed = self._process_component(component)
                keywords.extend(processed)

            # Step 3: Deduplicate while preserving order (keep first occurrence)
            seen = set()
            deduplicated = []
            for kw in keywords:
                if kw not in seen:
                    deduplicated.append(kw)
                    seen.add(kw)

            return deduplicated

        except Exception as e:
            self.logger.warning(f"Error parsing trim '{trim_value}': {str(e)}")
            return []

    def combine_keywords(
        self, model_keywords: List[str], trim_keywords: List[str], fuel_type: str = None
    ) -> List[str]:
        """
        Combine model, trim, and fuel type keywords into final search list.

        Args:
            model_keywords: Keywords from sheet name model section
            trim_keywords: Keywords extracted from trim column
            fuel_type: Fuel type if detected (e.g., "EV", "PHEV")

        Returns:
            Combined and deduplicated keyword list

        Examples:
            model=["outlander"], trim=["es"], fuel=None
              → ["outlander", "es"]

            model=["outlander"], trim=["es", "gt", "premium"], fuel="PHEV"
              → ["outlander", "es", "gt", "premium", "phev"]
        """
        all_keywords = []

        # Add model keywords
        if model_keywords:
            all_keywords.extend(model_keywords)

        # Add trim keywords
        if trim_keywords:
            all_keywords.extend(trim_keywords)

        # Add fuel type if present
        if fuel_type:
            all_keywords.append(fuel_type.lower())

        # Final deduplication (keep first occurrence) and normalization
        seen = set()
        deduplicated = []
        for kw in all_keywords:
            kw_clean = kw.lower().strip() if kw else None
            if kw_clean and kw_clean not in seen:
                deduplicated.append(kw_clean)
                seen.add(kw_clean)

        return deduplicated

    def extract_keywords_for_model_lookup(self, sheet_name: str, trim_value: str) -> List[str]:
        """
        Extract combined keywords from sheet_name and trim for model number lookup.
        This is the convenience method used during batch model lookup.

        Args:
            sheet_name: Sheet name (e.g., "2026_Outlander_ES_EN")
            trim_value: Trim value from data (e.g., "ES", "ES_GT-P")

        Returns:
            Combined keyword list for model lookup

        Examples:
            sheet="2026_Outlander_ES_EN", trim="ES" → ["outlander", "es"]
            sheet="2026_Outlander_PHEV_EN", trim="Limited" → ["outlander", "limited", "phev"]
        """
        try:
            sheet_info = self.extract_from_sheet_name(sheet_name)
            model_keywords = sheet_info["model_keywords"]
            fuel_type = sheet_info["fuel_type"]

            trim_keywords = self.extract_from_trim(trim_value)

            return self.combine_keywords(model_keywords, trim_keywords, fuel_type)
        except Exception as e:
            self.logger.error(
                f"Error extracting keywords for lookup from sheet='{sheet_name}', "
                f"trim='{trim_value}': {str(e)}"
            )
            return []

    # -----------------------------------------------------------------------
    # Private Helpers
    # -----------------------------------------------------------------------

    def _normalize_abbreviation_lib(self, lib: Dict) -> Dict[str, str]:
        """Convert abbreviation library keys and values to lowercase."""
        return {k.lower(): v.lower() for k, v in lib.items()}

    def _process_model_parts(self, model_parts: List[str], sheet_name: str) -> Dict[str, Any]:
        """
        Extract model keywords and fuel type from sheet name parts.

        Detects fuel type keywords and separates them from model name.
        Fuel type keywords are defined in config: ["EV", "PHEV", "HEV", ...]

        Args:
            model_parts: Middle section of sheet_name split by "_"
            sheet_name: Original sheet name (for logging)

        Returns:
            {
                "model_keywords": ["outlander", "es"],
                "fuel_type": "PHEV" or None
            }
        """
        fuel_type = None
        model_keywords = []

        for part in model_parts:
            part_stripped = part.strip()
            part_upper = part_stripped.upper()

            # Check if this part is a fuel type keyword
            if part_upper in self.fuel_keywords:
                if fuel_type:
                    self.logger.warning(
                        f"Sheet '{sheet_name}': Multiple fuel type keywords found. "
                        f"Using first occurrence: '{fuel_type}', ignoring: '{part_upper}'"
                    )
                else:
                    fuel_type = part_upper
                    self.logger.debug(f"Detected fuel type: {fuel_type}")
            else:
                # It's a model keyword, normalize and add
                if part_stripped:
                    model_keywords.append(part_stripped.lower())

        return {"model_keywords": model_keywords, "fuel_type": fuel_type}

    def _process_component(self, component: str) -> List[str]:
        """
        Process single trim component for dash abbreviations.

        Rules:
        - If component has no dash: return as-is
        - If component has dash:
          - Only process if it's a single-letter abbreviation (e.g., "gt-p")
          - Multi-character hyphenated terms (e.g., "s-awc") stay as-is (one keyword)
          - For single-letter abbreviations:
            - Check abbreviation library
            - If match found: split into base + full word
            - If no match: keep entire component as-is

        Args:
            component: Single component after "_" split (e.g., "gt-p", "s-awc", "es")

        Returns:
            List of keywords from this component

        Examples:
            "es" → ["es"]
            "gt-p" → ["gt", "premium"]  (if "p": "premium" in library)
            "s-awc" → ["s-awc"]  (multi-char after dash, keep as hyphenated term)
            "gt-xyz" → ["gt-xyz"]  (multi-letter after dash, keep as-is)
        """
        keywords = []

        if "-" not in component:
            # No dash: simple component, return as-is
            keywords.append(component)
            return keywords

        # Contains dash: check if it's a single-letter abbreviation pattern
        parts = component.split("-")

        # Only process if last part is exactly 1 letter (abbreviation pattern)
        last_part = parts[-1].strip().lower()
        if len(last_part) == 1 and last_part in self.abbreviation_lib:
            # Single-letter abbreviation that's in the library
            # Split: keep base parts, expand last part
            base_parts = parts[:-1]
            for part in base_parts:
                part_clean = part.strip().lower()
                if part_clean:
                    keywords.append(part_clean)

            full_word = self.abbreviation_lib[last_part]
            keywords.append(full_word)
            self.logger.debug(f"Abbreviation matched: '-{last_part}' → '{full_word}'")
        else:
            # Not a single-letter abbreviation, or not in library
            # Keep entire component as-is (one keyword)
            keywords.append(component.lower())
            if len(last_part) == 1:
                self.logger.warning(
                    f"Abbreviation not found in library: '-{last_part}' in '{component}'. "
                    f"Keeping as-is. Available abbreviations: {list(self.abbreviation_lib.keys())}"
                )

        return keywords
