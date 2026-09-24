"""Composite Part Number Normalization Utility

Normalizes composite part numbers (with "or"/"ou" alternatives) to single canonical value.

Example:
  "50977-565-45BH or 50977-565-45SH" → "50977-565-45BH" (left-priority)
  "50977-565-45BH ou 50977-565-45SH" → "50977-565-45BH" (FR, same logic)
"""

from typing import Optional


def normalize_composite_part_number(
    part_num: Optional[str],
    language: str = "EN"
) -> Optional[str]:
    """Normalize composite part numbers with left-priority strategy.

    Converts "part1 or part2" → "part1" (left side preferred)
    Works for both EN ("or") and FR ("ou") variants.

    Args:
        part_num: Raw part number (may contain "or"/"ou" separator).
                 Can be None or empty string.
        language: "EN" (default) or "FR". Case-insensitive validation.

    Returns:
        Normalized part number (single value), or None if input is None/empty.

    Raises:
        ValueError: If language is not "EN" or "FR" (case-insensitive)

    Examples:
        >>> normalize_composite_part_number("50977-565-45BH or 50977-565-45SH", "EN")
        '50977-565-45BH'

        >>> normalize_composite_part_number("50977-565-45BH ou 50977-565-45SH", "FR")
        '50977-565-45BH'

        >>> normalize_composite_part_number("50977-565-45BH", "EN")
        '50977-565-45BH'

        >>> normalize_composite_part_number(None, "EN")
        None

        >>> normalize_composite_part_number(" or 50977-565-45SH", "EN")
        '50977-565-45SH'
    """
    # Validate language parameter
    language_upper = language.upper()
    if language_upper not in ("EN", "FR"):
        raise ValueError(
            f"Invalid language '{language}': must be 'EN' or 'FR'"
        )

    # Handle None input
    if part_num is None:
        return None

    # Handle empty string
    if not part_num:
        return None if part_num != "" else ""

    # Determine separator based on language
    separator = "or" if language_upper == "EN" else "ou"

    # Split on separator (case-insensitive, max 2 parts)
    # Use case-insensitive search
    part_num_lower = part_num.lower()
    separator_lower = separator.lower()

    if separator_lower not in part_num_lower:
        # No separator found → return as-is
        return part_num.strip() if part_num.strip() else None

    # Find separator position (case-insensitive)
    separator_pos = part_num_lower.find(separator_lower)
    left_part = part_num[:separator_pos].strip()
    right_part = part_num[separator_pos + len(separator):].strip()

    # Left-priority logic: left if not empty, else right, else None
    if left_part:
        return left_part
    elif right_part:
        return right_part
    else:
        return None
