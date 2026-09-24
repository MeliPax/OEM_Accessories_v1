"""Trim Generalization & Family Extraction Utility (Phase 2 Stub)

Placeholder for trim family matching logic. Full implementation in Phase 5.

Phase 2: Design document created (design_docs/trim_generalization_algorithm.md)
         Function stubs only (deferred to Phase 5 for VehicleSearchEngine integration)
Phase 5: Full implementation with database lookups
"""

from typing import List, Dict, Optional, Any


def extract_trim_family(
    trim_name: str,
    model_name: str,
    model_year: int,
    db: Optional[Any] = None,
    config: Optional[Dict] = None
) -> List[str]:
    """Extract all database trim variants matching a general trim name.
    
    Example:
      extract_trim_family("Sport", "CR-V", 2026)
      -> ["Sport", "Sport AWD", "Sport FWD", "Sport Hybrid"]
         (or just exact match if exists)
    
    Args:
        trim_name: General trim name (may be prefix)
        model_name: Model name (e.g., "CR-V", "Accord")
        model_year: Vehicle year
        db: Optional database connection/service
        config: Optional config with matching rules
    
    Returns:
        List of database trim names matching the family
        (empty list if no matches)
    
    Note:
        Phase 2 stub: returns empty list
        Phase 5 implementation: actual database queries
    """
    # Phase 2: Stub returns empty list
    # Phase 5: Implement exact match -> prefix match logic
    # See design_docs/trim_generalization_algorithm.md for algorithm
    return []


def normalize_trim(
    trim_name: str,
    language: str = "EN"
) -> str:
    """Normalize trim name for matching (e.g., lowercase, strip whitespace).
    
    Args:
        trim_name: Raw trim name
        language: "EN" or "FR" (for language-specific normalization)
    
    Returns:
        Normalized trim name
    
    Note:
        Phase 5: Implement based on trim_config.yaml rules
    """
    # Phase 2 stub: basic normalization
    return trim_name.strip().lower() if trim_name else ""


def extract_trim_keywords(
    trim_name: str,
    tokenization_config: Optional[Dict] = None
) -> List[str]:
    """Extract keywords from trim name (tokenization).
    
    Splits on space/hyphen, respects compound keywords (e.g., "EX-L").
    
    Args:
        trim_name: Raw trim name (e.g., "Sport AWD", "EX-L")
        tokenization_config: Config with split_on, compound_keywords
    
    Returns:
        List of keyword tokens
    
    Note:
        Phase 5: Implement per trim_config.yaml rules
    """
    # Phase 2 stub: basic tokenization
    if not trim_name:
        return []
    
    # Simple split on whitespace only
    return trim_name.lower().split()
