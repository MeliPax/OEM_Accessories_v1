"""
Data standardization rules for OEM-specific trim names, model names, and descriptions.

Applies configuration-driven transformations at multiple pipeline points:
  - ADS data ingestion (mapper.py)
  - Incoming accessory data (orchestrator.py)
  - Search keyword normalization (manufacture_module.py)

Supports:
  - Trim level aliases (e.g., "N Line" → "N-Line")
  - Model name aliases (e.g., "IONIQ 5" variants)
  - Description text patterns (regex replacements)
"""

import re
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class DataStandardizer:
    """Apply OEM-specific standardization rules to vehicle data."""

    def __init__(self, config_dict: Dict, oem_name: str = "Unknown"):
        """
        Initialize standardizer with config rules.

        Args:
            config_dict: Loaded YAML config with standardization_rules section
            oem_name: OEM name for logging context (e.g., "Hyundai")

        Logs:
            - INFO: Standardizer initialized with rule count
            - DEBUG: Each rule type loaded
        """
        self.oem_name = oem_name
        self.rules = config_dict.get("standardization_rules", {})

        logger.info(
            f"standardizer | {oem_name} | Initialized with {len(self.rules)} rule categories"
        )

        # Log rule details at DEBUG level
        for category, items in self.rules.items():
            if isinstance(items, dict):
                logger.debug(
                    f"standardizer | {oem_name} | {category}: {len(items)} aliases"
                )
            elif isinstance(items, list):
                logger.debug(
                    f"standardizer | {oem_name} | {category}: {len(items)} patterns"
                )

    def standardize_trim_name(self, trim_name: Optional[str]) -> Optional[str]:
        """
        Apply trim level aliases to standardize trim names.

        E.g., "N Line" → "N-Line", "n-line" → "N-Line"

        Args:
            trim_name: Original trim name (e.g., "N Line", "Essential", "Preferred")

        Returns:
            Standardized trim name or original if no rule matches

        Logs:
            - DEBUG: Alias applied with before/after
            - DEBUG: No match found
        """
        if not trim_name or not isinstance(trim_name, str):
            return trim_name

        aliases = self.rules.get("trim_level_aliases", {})

        # Check aliases (case-insensitive matching, preserve standardized casing)
        for alias, standard in aliases.items():
            if trim_name.lower() == alias.lower():
                if trim_name != standard:  # Only log if actually changed
                    logger.debug(
                        f"standardizer | {self.oem_name} | "
                        f"Trim alias: '{trim_name}' → '{standard}'"
                    )
                return standard

        logger.debug(
            f"standardizer | {self.oem_name} | "
            f"No trim alias found for: '{trim_name}'"
        )
        return trim_name

    def standardize_model_name(self, model_name: Optional[str]) -> Optional[str]:
        """
        Apply model name aliases to standardize model names.

        E.g., "IONIQ5" → "IONIQ 5"

        Args:
            model_name: Original model name (e.g., "IONIQ5", "Elantra")

        Returns:
            Standardized model name or original if no rule matches

        Logs:
            - DEBUG: Alias applied
            - DEBUG: No match found
        """
        if not model_name or not isinstance(model_name, str):
            return model_name

        aliases = self.rules.get("model_name_aliases", {})

        # Check aliases (case-insensitive matching)
        for alias, standard in aliases.items():
            if model_name.lower() == alias.lower():
                if model_name != standard:
                    logger.debug(
                        f"standardizer | {self.oem_name} | "
                        f"Model alias: '{model_name}' → '{standard}'"
                    )
                return standard

        return model_name

    def standardize_description(self, description: Optional[str]) -> Optional[str]:
        """
        Apply regex patterns to fix formatting in description text.

        E.g., "N Line" → "N-Line", fix multiple spaces

        Args:
            description: Original description text (e.g., "N Line Ultimate DCT")

        Returns:
            Standardized description or original if no patterns apply

        Logs:
            - DEBUG: Pattern applied with before/after
            - DEBUG: Description unchanged
        """
        if not description or not isinstance(description, str):
            return description

        patterns = self.rules.get("description_patterns", [])

        if not patterns:
            logger.debug(
                f"standardizer | {self.oem_name} | No description patterns defined"
            )
            return description

        result = description
        changed = False

        for pattern_config in patterns:
            pattern = pattern_config.get("pattern")
            replacement = pattern_config.get("replacement")
            flags_str = pattern_config.get("flags", "")

            if not pattern or replacement is None:
                continue

            # Convert flags string to regex flags
            flags = 0
            if "IGNORECASE" in flags_str:
                flags |= re.IGNORECASE
            if "MULTILINE" in flags_str:
                flags |= re.MULTILINE

            # Apply pattern
            new_result = re.sub(pattern, replacement, result, flags=flags)

            if new_result != result:
                logger.debug(
                    f"standardizer | {self.oem_name} | "
                    f"Pattern '{pattern}': '{result}' → '{new_result}'"
                )
                result = new_result
                changed = True

        if not changed:
            logger.debug(
                f"standardizer | {self.oem_name} | "
                f"No description patterns matched: '{description}'"
            )

        return result

    def standardize_keywords(self, keywords: List[str]) -> List[str]:
        """
        Standardize a list of search keywords.

        Applies trim aliases to each keyword.

        Args:
            keywords: List of keywords (e.g., ["elantra", "n line"])

        Returns:
            List of standardized keywords

        Logs:
            - INFO: Keywords standardized (if any changed)
            - DEBUG: Each keyword's result
        """
        if not keywords:
            return keywords

        standardized = []
        changed_count = 0

        for kw in keywords:
            std_kw = self.standardize_trim_name(kw)
            standardized.append(std_kw)

            if std_kw != kw:
                changed_count += 1

        if changed_count > 0:
            logger.info(
                f"standardizer | {self.oem_name} | "
                f"Standardized {changed_count}/{len(keywords)} keywords"
            )

        return standardized

    def standardize_row(self, row: Dict, apply_to: List[str] = None) -> Dict:
        """
        Apply all standardization rules to a data row.

        Standardizes multiple fields: TrimName, Description, ModelName.

        Args:
            row: Data row dict (e.g., from ADS or accessory sheet)
            apply_to: List of fields to standardize (default: all)

        Returns:
            Row with standardized values

        Logs:
            - DEBUG: Fields standardized
            - ERROR: Exception during standardization
        """
        if not apply_to:
            apply_to = self.rules.get("applied_to", ["TrimName", "Description"])

        try:
            standardized_count = 0

            if "TrimName" in apply_to and "TrimName" in row:
                original = row["TrimName"]
                row["TrimName"] = self.standardize_trim_name(row["TrimName"])
                if row["TrimName"] != original:
                    standardized_count += 1

            if "Description" in apply_to and "Description" in row:
                original = row["Description"]
                row["Description"] = self.standardize_description(row["Description"])
                if row["Description"] != original:
                    standardized_count += 1

            if "ModelName" in apply_to and "ModelName" in row:
                original = row["ModelName"]
                row["ModelName"] = self.standardize_model_name(row["ModelName"])
                if row["ModelName"] != original:
                    standardized_count += 1

            if standardized_count > 0:
                logger.debug(
                    f"standardizer | {self.oem_name} | "
                    f"Standardized {standardized_count} fields in row"
                )

            return row

        except Exception as e:
            logger.error(
                f"standardizer | {self.oem_name} | "
                f"FAILED to standardize row | Error: {str(e)}"
            )
            return row
