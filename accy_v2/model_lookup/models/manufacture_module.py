try:
    from db_queries.manufacturer import GET_BY_NAME
except ImportError:
    from model_lookup.db_queries.manufacturer import GET_BY_NAME

import pandas as pd
from sqlalchemy import text

"""

    Helpers

"""


import json
from typing import Union, Any
import os
from datetime import datetime
from pathlib import Path

MANUFACTURER_SEARCH_CONFIG = {
    "default": {
        "year_field": "ModelYear",
        "model_field": "ModelNumber",
        "trim_fields": ["Description"],
        "style_field": "Style_ID",
        "package_field": "Package",
    },
    "Hyundai": {
        "trim_fields": ["Description"],
    },
}

EV_KEYWORDS = ["EV", "PHEV"]


def get_manufacturer_config(make: str) -> dict:
    """
    Get the search config for a manufacturer.
    Merges default config with manufacturer-specific overrides.
    """
    config = MANUFACTURER_SEARCH_CONFIG.get("default", {}).copy()
    if make in MANUFACTURER_SEARCH_CONFIG:
        config.update(MANUFACTURER_SEARCH_CONFIG[make])
    return config


def is_valid_year(value: Any) -> bool:
    """
    Validate if a value is a valid year (1900-current year + 5).
    """
    if value is None or value == "":
        return False
    try:
        year = int(value)
        current_year = datetime.now().year
        return 1900 <= year <= current_year + 5
    except (ValueError, TypeError):
        return False


def strip_row_values(row: dict) -> dict:
    """
    Strip whitespace from all values and remove None/empty strings.
    Returns a cleaned dictionary.
    """
    cleaned = {}
    for key, value in row.items():
        if isinstance(value, str):
            value = value.strip()
        cleaned[key] = value if value not in (None, "") else None
    return cleaned


def validate_row_not_null(row: dict, required_fields: list[str] = None) -> bool:
    """
    Check if all required fields are not null.
    If required_fields not specified, checks all fields.
    """
    if required_fields is None:
        required_fields = list(row.keys())

    for field in required_fields:
        if field not in row or row[field] is None or row[field] == "":
            return False
    return True


def load_existing_csv(csv_path: str, expected_columns: list = None) -> pd.DataFrame:
    """
    Load existing CSV file and clean description punctuation.
    Returns empty DataFrame if file doesn't exist.

    If expected_columns provided and CSV has fewer columns, pads with empty columns.
    This handles schema evolution (e.g., reading a 7-column file when expecting 9).

    Applies description cleaning to normalize cosmetic info in all loaded data:
    - Removes parentheses/brackets that interfere with tokenization
    - Normalizes spacing patterns (e.g., "Two Tone" → "two-tone")
    """
    if os.path.exists(csv_path):
        try:
            df = pd.read_csv(csv_path)
            # Clean descriptions for all loaded data (not just search results)
            if not df.empty and "Description" in df.columns:
                df["Description"] = df["Description"].apply(_clean_description_punctuation)

            # Pad with expected columns if needed
            if expected_columns:
                for col in expected_columns:
                    if col not in df.columns:
                        df[col] = ""

            return df
        except Exception as e:
            print(f"Warning: Could not read existing CSV: {e}")
            # Return DataFrame with expected columns if parsing failed
            if expected_columns:
                return pd.DataFrame(columns=expected_columns)
            return pd.DataFrame()
    return pd.DataFrame()


def check_duplicate_record(
    df_new: pd.DataFrame, df_existing: pd.DataFrame, key_columns: list = None
) -> pd.DataFrame:
    """
    Filter out records that already exist in the database.
    Configurable unique key; defaults to Manufacturer, ModelYear, and ModelNumber.

    Args:
        df_new: New records to check
        df_existing: Existing records in the database
        key_columns: List of column names that define uniqueness.
                     Defaults to ["Manufacturer", "ModelYear", "ModelNumber"]

    Returns:
        DataFrame with only new records (not in df_existing)
    """
    if key_columns is None:
        key_columns = ["Manufacturer", "ModelYear", "ModelNumber"]

    if df_existing.empty:
        return df_new

    existing_cols = [col for col in key_columns if col in df_existing.columns]

    if not existing_cols:
        return df_new

    merge = df_new.merge(
        df_existing[existing_cols],
        on=existing_cols,
        how="left",
        indicator=True,
    )
    return df_new[merge["_merge"] == "left_only"].drop(
        columns=["_merge"], errors="ignore"
    )


def save_vehicle_models_to_csv(
    df: pd.DataFrame,
    csv_path: str = None,
    configs_dir: str = None,
    key_columns: list = None,
    dq_logger = None,
) -> dict:
    """
    Save vehicle models to CSV with validation, standardization, and deduplication.

    Standardizes descriptions at ingestion time (clean punctuation + translate OEM abbreviations)
    so the database file is always consistent and searches don't need to re-standardize every time.

    Args:
        df: DataFrame with vehicle model data
        csv_path: Path to CSV file (defaults to db/db_vehicle_models.csv)
        configs_dir: Directory for OEM configs (defaults to model_lookup/configs/)
        key_columns: List of column names that define uniqueness for deduplication.
                     Defaults to ["Manufacturer", "ModelYear", "ModelNumber"]
        dq_logger: Optional DQLogger for logging duplicates found

    Returns:
        dict with save status, records saved, duplicates skipped, etc.
    """
    if csv_path is None:
        csv_path = str(Path(__file__).parent.parent / "db" / "db_vehicle_models.csv")

    if configs_dir is None:
        configs_dir = str(Path(__file__).parent.parent / "configs")

    result = {
        "success": False,
        "total_records": len(df),
        "records_saved": 0,
        "records_skipped": 0,
        "duplicates": 0,
        "invalid_records": 0,
        "file_path": csv_path,
        "file_created": False,
    }

    if df.empty:
        result["message"] = "No data to save"
        return result

    os.makedirs(os.path.dirname(csv_path) or ".", exist_ok=True)

    df_filtered = df.copy()

    required_fields = ["ModelYear", "ModelNumber", "Description"]

    valid_records = []
    for _, row in df_filtered.iterrows():
        cleaned_row = strip_row_values(row.to_dict())

        if not is_valid_year(cleaned_row.get("ModelYear")):
            result["invalid_records"] += 1
            continue

        if not validate_row_not_null(cleaned_row, required_fields):
            result["invalid_records"] += 1
            continue

        valid_records.append(cleaned_row)

    if not valid_records:
        result["message"] = "No valid records to save"
        return result

    df_valid = pd.DataFrame(valid_records)

    # Format ModelNumber and Manufacturer columns for consistency
    if not df_valid.empty:
        if "ModelNumber" in df_valid.columns:
            df_valid["ModelNumber"] = df_valid["ModelNumber"].apply(_format_model_number)
        if "Manufacturer" in df_valid.columns:
            df_valid["Manufacturer"] = df_valid["Manufacturer"].apply(_format_manufacturer)

    # Standardize descriptions at ingestion: clean punctuation + translate OEM abbreviations
    try:
        try:
            from model_lookup.semantic.translator import load_oem_translator
        except ImportError:
            from semantic.translator import load_oem_translator

        for make in df_valid["Manufacturer"].unique():
            translator = load_oem_translator(make, configs_dir)
            if translator:
                mask = df_valid["Manufacturer"] == make
                df_valid.loc[mask, "Description"] = df_valid.loc[mask, "Description"].apply(
                    lambda d: _standardize_description(d, translator)
                )
    except Exception as e:
        # Log warning but don't fail the save if standardization has issues
        pass

    # Pre-harmonize columns: read existing header to determine full schema
    existing_cols = []
    if os.path.exists(csv_path):
        try:
            with open(csv_path, 'r') as f:
                existing_cols = f.readline().strip().split(',')
            # Ensure df_valid has all existing columns
            for col in existing_cols:
                if col not in df_valid.columns:
                    df_valid[col] = ""
        except Exception:
            pass

    # Determine the full write schema upfront
    write_columns = sorted(set(existing_cols + df_valid.columns.tolist()))
    df_existing = load_existing_csv(csv_path, expected_columns=write_columns)

    if not df_existing.empty:
        df_before_dedup = df_valid.copy()
        df_valid = check_duplicate_record(df_valid, df_existing, key_columns=key_columns)

        # Log duplicates found against existing CSV
        duplicates_found = len(df_before_dedup) - len(df_valid)
        if duplicates_found > 0 and dq_logger:
            dupes = df_before_dedup[~df_before_dedup.index.isin(df_valid.index)]
            for _, dupe_row in dupes.iterrows():
                key_values = key_columns if key_columns else ["Manufacturer", "ModelYear", "ModelNumber"]
                key_str = ", ".join([f"{col}={dupe_row.get(col, 'N/A')}" for col in key_values])
                dq_logger.log_warning(
                    sheet_name=dupe_row.get("Manufacturer", "UNKNOWN"),
                    model_name=dupe_row.get("ModelNumber", "UNKNOWN"),
                    record_index=None,
                    record_snapshot=dupe_row.to_dict(),
                    rule_violated="csv_uniqueness_rule",
                    issue_description=f"[CSV_DUPLICATE] Already exists in database: {key_str}",
                )

        result["duplicates"] = (
            result["total_records"] - result["invalid_records"] - len(df_valid)
        )

    if df_valid.empty:
        result["success"] = True
        result["message"] = "No new data to load — all records already exist"
        return result

    # Determine write mode: if schema changed (new columns), rewrite file instead of append
    # This prevents CSV corruption from column mismatch
    schema_changed = existing_cols and write_columns != existing_cols
    mode = "w" if (df_existing.empty or schema_changed) else "a"
    header = df_existing.empty or schema_changed

    # If schema changed and we're not starting fresh, include existing rows with new columns
    if schema_changed and not df_existing.empty:
        df_existing = df_existing.reindex(columns=write_columns, fill_value="")
        df_valid = pd.concat([df_existing, df_valid], ignore_index=True)

    # Reindex df_valid to write schema (ensures all columns present)
    df_valid = df_valid.reindex(columns=write_columns, fill_value="")

    try:
        df_valid.to_csv(csv_path, mode=mode, header=header, index=False, columns=write_columns)
        result["records_saved"] = len(df_valid)
        result["records_skipped"] = result["total_records"] - len(df_valid)
        result["success"] = True
        result["file_created"] = not os.path.exists(csv_path) or mode == "w"
        result["message"] = f"Successfully saved {len(df_valid)} records"

        # Rebuild vocab for any manufacturers in the saved data
        unique_makes = df_valid["Manufacturer"].unique().tolist()
        vocab_rebuilt = []
        classification_rebuilt = []
        configs_dir = str(Path(__file__).parent.parent / "configs")

        for make in unique_makes:
            try:
                vocab_result = build_manufacturer_keyword_vocab(make, csv_path, configs_dir)
                if vocab_result.get("saved", False):
                    vocab_rebuilt.append(make)
            except Exception:
                # Log vocab rebuild errors but don't fail the save
                pass

            # Rebuild classification config after vocab
            try:
                from model_lookup.classifier import build_classification_config

                class_result = build_classification_config(make, csv_path, configs_dir)
                if class_result.get("saved", False):
                    classification_rebuilt.append(make)
                # Log any unclassified tokens as warnings (non-fatal)
                unclassified = class_result.get("unclassified", [])
                if unclassified:
                    pass  # Unclassified tokens logged during build
            except Exception:
                # Don't fail the save if classification rebuild fails
                pass

        result["vocab_rebuilt"] = vocab_rebuilt
        result["classification_rebuilt"] = classification_rebuilt

    except Exception as e:
        result["message"] = f"Error saving to CSV: {str(e)}"

    return result


def parse_json_string(json_string: str) -> Union[dict, list]:
    """
    Parse a JSON string into a Python object (dict or list).

    Args:
        json_string (str): A valid JSON string.

    Returns:
        dict or list: Parsed JSON object.

    Raises:
        ValueError: If the input is not valid JSON.
        TypeError: If input is not a string.
    """
    if not isinstance(json_string, str):
        raise TypeError("Input must be a JSON string")

    try:
        return json.loads(json_string)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON string: {exc}") from exc


def get_manufacturer_df(engine, make: str) -> pd.DataFrame:
    query = text("""
        SELECT *
        FROM Manufacturer
        WHERE ManufacturerName = :make
            AND ManufacturerStatus = 0
    """)

    return pd.read_sql(query, engine, params={"make": make})


def get_manufacturer_bulletins_json(engine, make: str) -> pd.DataFrame:

    with engine.begin() as conn:
        result = conn.execute(
            text("""
                    SELECT 
                 top(1)       
                 B.BulletinDetails

                    FROM Bulletin B
                    WHERE B.BulletinManufacturer = (
                        SELECT ManufacturerId
                        FROM Manufacturer
                        WHERE ManufacturerName = :make
                            AND ManufacturerStatus = 0
                    )
                    AND B.BulletinStatus = 1
                    ORDER BY B.BulletinEnd DESC
                """),
            {"make": make},
        )
        return result.mappings().all()


def get_latest_bulletin_by_manufacturer_json(engine, make: str) -> pd.DataFrame:

    with engine.begin() as conn:
        result = conn.execute(
            text("""
                    SELECT 
                        top(1) B.BulletinDetails

                    FROM Bulletin B
                    WHERE B.BulletinManufacturer = (
                        SELECT ManufacturerId
                        FROM Manufacturer
                        WHERE ManufacturerName = :make
                            AND ManufacturerStatus = 0
                    )
                    AND B.BulletinStatus = 1
                    ORDER BY B.BulletinEnd DESC
                """),
            {"make": make},
        )
        return result.mappings().all()


def print_bulletin_details(bull):
    json_ = parse_json_string(bull[0]["BulletinDetails"])

    for idx, values in enumerate(json_):

        ModelYear = json_[idx].get("Year")
        ModelNumber = json_[idx].get("Model")
        Description = json_[idx].get("Description")
        TrimName = json_[idx].get("TrimName")
        Package = json_[idx].get("Package")
        Style_ID = json_[idx].get("Style")

        print(
            f"{ModelYear}, {ModelNumber}, { Description}, { TrimName}, { Package}, {Style_ID}"
        )


def convert_bulletin_to_df(
    bull: list[dict[str, Any]], make: str = None
) -> pd.DataFrame:
    """
    Convert bulletin JSON to DataFrame with validation.
    Only includes records with valid year and non-null required fields.
    Adds Manufacturer column with the provided make value.
    """
    json_ = parse_json_string(bull[0]["BulletinDetails"])

    records = []
    for item in json_:
        row = {
            "Manufacturer": make,
            "ModelYear": item.get("Year"),
            "ModelNumber": item.get("Model"),
            "Description": item.get("Description"),
            "TrimName": item.get("TrimName"),
            "Package": item.get("Package"),
            "Style_ID": item.get("Style"),
        }

        cleaned_row = strip_row_values(row)

        if not is_valid_year(cleaned_row.get("ModelYear")):
            continue

        if not validate_row_not_null(
            cleaned_row, ["ModelYear", "ModelNumber", "Description"]
        ):
            continue

        records.append(cleaned_row)

    if not records:
        return pd.DataFrame(
            columns=[
                "Manufacturer",
                "ModelYear",
                "ModelNumber",
                "Description",
                "TrimName",
                "Package",
                "Style_ID",
            ]
        )

    return pd.DataFrame(records)


def get_active_unique_manufacturers(engine) -> pd.DataFrame:
    query = text("""
        SELECT DISTINCT *
        FROM Manufacturer
        WHERE ManufacturerStatus = 0
                 AND ManufacturerName IS NOT NULL
                 AND ManufacturerName not like '%test%'
    """)

    return pd.read_sql(query, engine)


def build_word_boundary_pattern(keyword: str) -> str:
    """
    Build a regex pattern for exact word matching with word boundaries.

    Args:
        keyword: The keyword to match

    Returns:
        str: Regex pattern with word boundaries (e.g., r'\bSE\b')
    """
    import re as regex_module
    escaped_keyword = regex_module.escape(keyword)
    return rf"\b{escaped_keyword}\b"


def _extract_description_tokens(description: str) -> list[str]:
    """
    Whitespace-split description into lowercase tokens.
    Preserves hyphenated terms as single tokens (e.g., "S-AWC" stays as one token).

    Args:
        description: Description string from CSV

    Returns:
        List of lowercase tokens
    """
    if not description or not isinstance(description, str):
        return []
    return [t.lower() for t in description.split() if t]


def _clean_description_punctuation(description: str) -> str:
    """
    Clean database description by removing/normalizing problematic punctuation and spacing.
    Converts "(Two Tone Interior)" → "two-tone interior" so tokens classify properly.
    Normalizes common space-separated pairs to hyphenated form matching classifier vocab.

    Args:
        description: Description string from CSV

    Returns:
        Cleaned description with normalized punctuation and spacing
    """
    if not description or not isinstance(description, str):
        return description

    import re

    # Step 1: Remove parentheses, brackets that interfere with tokenization
    cleaned = re.sub(r'[()[\]{}]', '', description)

    # Step 2: Normalize common two-word patterns to hyphenated form
    # (must match classifier vocab like "two-tone" which is classified as INTERIOR)
    cleaned = re.sub(r'\btwo\s+tone\b', 'two-tone', cleaned, flags=re.IGNORECASE)

    # Step 3: Normalize whitespace
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    return cleaned


def _deduplicate_description_words(description: str) -> str:
    """
    Remove duplicate words from a description, case-insensitively, keeping first occurrence.

    Prevents artifacts like "Elantra HEV Hybrid Luxury" → "Elantra hybrid Luxury"
    after translation (HEV → hybrid) when the source already spelled out the translated term.
    Preserves order and first occurrence's casing.

    Args:
        description: Description string (already cleaned/translated)

    Returns:
        Description with duplicate words removed, preserving order and first occurrence's casing
    """
    if not description or not isinstance(description, str):
        return description

    seen = set()
    result = []
    for word in description.split():
        key = word.lower()
        if key not in seen:
            seen.add(key)
            result.append(word)

    return " ".join(result)


def _format_model_number(model_number: str) -> str:
    """
    Format model number to uppercase.

    Args:
        model_number: Model number string

    Returns:
        Model number in uppercase (e.g., "elcs4v2bes00" → "ELCS4V2BES00")
    """
    if not model_number or not isinstance(model_number, str):
        return model_number
    return model_number.upper().strip()


def _format_manufacturer(manufacturer: str) -> str:
    """
    Format manufacturer name to uppercase for consistency.

    Args:
        manufacturer: Manufacturer name string

    Returns:
        Manufacturer name in uppercase (e.g., "hyundai" → "HYUNDAI", "Genesis" → "GENESIS")
    """
    if not manufacturer or not isinstance(manufacturer, str):
        return manufacturer
    # Convert to uppercase (e.g., "hyundai" -> "HYUNDAI", "Genesis" -> "GENESIS")
    return manufacturer.strip().upper()


def _apply_title_case(description: str) -> str:
    """
    Apply title case formatting: capitalize first letter of each word, lowercase the rest.

    Examples:
        "elantra ultimate black" → "Elantra Ultimate Black"
        "kona EV preferred" → "Kona Ev Preferred"
        "two-tone interior" → "Two-Tone Interior" (hyphens preserved, each part capitalized)

    Args:
        description: Description string

    Returns:
        Description with title case applied to each whitespace-separated word
    """
    if not description or not isinstance(description, str):
        return description

    def capitalize_word(word: str) -> str:
        """Capitalize first letter, lowercase rest, handling hyphenated words."""
        if not word:
            return word
        # For hyphenated words (e.g., "two-tone"), capitalize each part
        if "-" in word:
            parts = word.split("-")
            return "-".join(part.capitalize() for part in parts if part)
        # Normal word: first letter uppercase, rest lowercase
        return word[0].upper() + word[1:].lower() if word else word

    words = description.split()
    return " ".join(capitalize_word(word) for word in words)


def _standardize_description(description: str, oem_translator: dict) -> str:
    """
    Standardize database description by:
    1. Cleaning punctuation that breaks tokenization
    2. Normalizing trim variant naming (e.g., "N Line" → "N-Line")
    3. Translating tokens using OEM translator while preserving original casing
    4. Removing duplicate words (case-insensitive) introduced by translation
    5. Applying title case (capitalize first letter of each word, lowercase the rest)

    Applies the same translation rules used for search keywords to ensure consistent
    vocabulary between search input and database (e.g., "ult" → "ultimate").
    Tokens not found in translator pass through unchanged, preserving their original case.

    Duplicate removal prevents artifacts like "Elantra HEV Hybrid Luxury" → "Elantra hybrid Luxury"
    when the translator maps HEV → hybrid and the source already contains "Hybrid".

    Title case ensures consistent formatting: "Elantra Ultimate Black" (not "elantra ultimate black").

    Args:
        description: Description string from CSV
        oem_translator: Translation dict from load_oem_translator()

    Returns:
        Standardized description with cleaned punctuation, translated tokens, deduplicated words,
        and title case formatting applied
    """
    if not description or not isinstance(description, str):
        return description

    # Step 1: Clean punctuation first (so "(Two Tone Interior)" becomes "Two Tone Interior")
    cleaned = _clean_description_punctuation(description)

    # Step 2: Normalize trim variant naming (e.g., "N Line" → "N-Line" for consistent DB storage)
    import re
    normalized = re.sub(r'\bN Line\b', 'N-Line', cleaned, flags=re.IGNORECASE)

    # Step 4: Translate tokens while preserving original casing for untranslated words
    if oem_translator:
        def _replace_token(match: "re.Match") -> str:
            word = match.group(0)
            # Look up lowercase version of word in translator, but return the translated version as-is
            # (untranslated words pass through with original case/hyphenation preserved)
            return oem_translator.get(word.lower(), word)

        # Replace each whitespace-separated token (already normalized to single spaces)
        translated = re.sub(r"\S+", _replace_token, normalized)
    else:
        translated = normalized

    # Step 5: Remove duplicate words introduced by translation (case-insensitive, first occurrence wins)
    deduplicated = _deduplicate_description_words(translated)

    # Step 6: Apply title case (capitalize first letter of each word, lowercase the rest)
    return _apply_title_case(deduplicated)


def build_manufacturer_keyword_vocab(
    make: str, csv_path: str = None, configs_dir: str = None
) -> dict:
    """
    Build and save a keyword vocabulary JSON for a manufacturer.

    Extracts all unique tokens from Description values for the given make,
    sorts them, and writes to {configs_dir}/{make.lower()}_keywords.json.

    Args:
        make: Manufacturer name
        csv_path: Path to CSV file (defaults to db/db_vehicle_models.csv)
        configs_dir: Directory for JSON files (defaults to model_lookup/configs/)

    Returns:
        dict with make, generated_at, keyword_count, keywords list
    """
    if csv_path is None:
        csv_path = str(Path(__file__).parent.parent / "db" / "db_vehicle_models.csv")

    if configs_dir is None:
        configs_dir = str(Path(__file__).parent.parent / "configs")

    df = load_existing_csv(csv_path)

    if df.empty:
        return {"make": make, "keywords": [], "keyword_count": 0, "message": "CSV is empty"}

    df_make = df[df["Manufacturer"] == make].copy()

    if df_make.empty:
        return {
            "make": make,
            "keywords": [],
            "keyword_count": 0,
            "message": f"No records found for manufacturer: {make}",
        }

    all_tokens = set()
    for desc in df_make["Description"].dropna():
        tokens = _extract_description_tokens(desc)
        all_tokens.update(tokens)

    sorted_keywords = sorted(list(all_tokens))

    os.makedirs(configs_dir, exist_ok=True)
    vocab_path = os.path.join(configs_dir, f"{make.lower()}_keywords.json")

    vocab_dict = {
        "make": make,
        "generated_at": datetime.now().isoformat(),
        "keyword_count": len(sorted_keywords),
        "keywords": sorted_keywords,
    }

    try:
        with open(vocab_path, "w") as f:
            json.dump(vocab_dict, f, indent=2)
        vocab_dict["file_path"] = vocab_path
        vocab_dict["saved"] = True
        return vocab_dict
    except Exception as e:
        vocab_dict["saved"] = False
        vocab_dict["error"] = str(e)
        return vocab_dict


def load_manufacturer_keyword_vocab(make: str, configs_dir: str = None) -> set[str]:
    """
    Load keyword vocabulary for a manufacturer from JSON.

    Returns empty set if file not found (graceful fallback — no extra filtering applied).

    Args:
        make: Manufacturer name
        configs_dir: Directory for JSON files (defaults to model_lookup/configs/)

    Returns:
        set of lowercase keywords
    """
    if configs_dir is None:
        configs_dir = str(Path(__file__).parent.parent / "configs")

    vocab_path = os.path.join(configs_dir, f"{make.lower()}_keywords.json")

    if not os.path.exists(vocab_path):
        return set()

    try:
        with open(vocab_path, "r") as f:
            vocab_dict = json.load(f)
        return set(vocab_dict.get("keywords", []))
    except Exception:
        return set()


def bootstrap_all_vocabs(csv_path: str = None, configs_dir: str = None) -> dict:
    """
    Bootstrap keyword vocabularies for all manufacturers in the CSV.

    Builds vocab JSON for each unique Manufacturer value.

    Args:
        csv_path: Path to CSV file (defaults to db/db_vehicle_models.csv)
        configs_dir: Directory for JSON files (defaults to model_lookup/configs/)

    Returns:
        dict with {make: result_dict} for each manufacturer
    """
    if csv_path is None:
        csv_path = str(Path(__file__).parent.parent / "db" / "db_vehicle_models.csv")

    if configs_dir is None:
        configs_dir = str(Path(__file__).parent.parent / "configs")

    df = load_existing_csv(csv_path)

    if df.empty:
        return {"status": "error", "message": "CSV is empty"}

    manufacturers = sorted(df["Manufacturer"].unique().tolist())

    results = {}
    for make in manufacturers:
        result = build_manufacturer_keyword_vocab(make, csv_path, configs_dir)
        results[make] = result

    return {"status": "success", "manufacturers": results}


def standardize_existing_database(csv_path: str = None, configs_dir: str = None) -> dict:
    """
    One-time migration: standardize all existing DB data in place.

    Applies complete standardization to every row in db_vehicle_models.csv:
    - Description: clean punctuation + translate OEM abbreviations + deduplicate + title case
    - ModelNumber: uppercase formatting (e.g., "elcs4v2bes00" → "ELCS4V2BES00")
    - Manufacturer: proper case formatting (e.g., "hyundai" → "Hyundai")

    Writes standardized rows back to the file.

    **IMPORTANT:** Back up db_vehicle_models.csv before running this function.

    Args:
        csv_path: Path to CSV file (defaults to db/db_vehicle_models.csv)
        configs_dir: Directory for OEM configs (defaults to model_lookup/configs/)

    Returns:
        dict with success status and count of standardized rows
    """
    if csv_path is None:
        csv_path = str(Path(__file__).parent.parent / "db" / "db_vehicle_models.csv")

    if configs_dir is None:
        configs_dir = str(Path(__file__).parent.parent / "configs")

    try:
        try:
            from model_lookup.semantic.translator import load_oem_translator
        except ImportError:
            from semantic.translator import load_oem_translator
    except ImportError:
        return {"success": False, "message": "Could not import translator"}

    df = load_existing_csv(csv_path)
    if df.empty:
        return {"success": False, "message": "CSV is empty"}

    standardized_count = 0

    for make in df["Manufacturer"].unique():
        translator = load_oem_translator(make, configs_dir)
        if translator:
            mask = df["Manufacturer"] == make
            df.loc[mask, "Description"] = df.loc[mask, "Description"].apply(
                lambda d: _standardize_description(d, translator)
            )
            standardized_count += mask.sum()

    # Format ModelNumber and Manufacturer columns for consistency
    if not df.empty:
        if "ModelNumber" in df.columns:
            df["ModelNumber"] = df["ModelNumber"].apply(_format_model_number)
        if "Manufacturer" in df.columns:
            df["Manufacturer"] = df["Manufacturer"].apply(_format_manufacturer)

    try:
        df.to_csv(csv_path, index=False)
        return {
            "success": True,
            "message": f"Standardized {standardized_count} rows",
            "rows_standardized": standardized_count,
            "total_rows": len(df),
            "file_path": csv_path,
        }
    except Exception as e:
        return {"success": False, "message": f"Error writing CSV: {str(e)}"}


def batch_save_manufacturer_models(
    engine,
    manufacturers: list[str],
    csv_path: str = None,
    configs_dir: str = None,
) -> dict:
    """
    Fetch and save vehicle models for multiple manufacturers.
    Standardizes descriptions at ingestion (clean + translate per OEM translator).

    Args:
        engine: SQLAlchemy engine for database connection
        manufacturers: List of manufacturer names
        csv_path: Path to CSV file (defaults to db/db_vehicle_models.csv)
        configs_dir: Directory for OEM configs (defaults to model_lookup/configs/)

    Returns:
        dict with results for each manufacturer and summary totals
    """
    if csv_path is None:
        csv_path = str(Path(__file__).parent.parent / "db" / "db_vehicle_models.csv")

    if configs_dir is None:
        configs_dir = str(Path(__file__).parent.parent / "configs")

    results = {
        "manufacturers": {},
        "summary": {
            "total_processed": 0,
            "total_saved": 0,
            "total_duplicates": 0,
            "total_invalid": 0,
            "errors": [],
        },
    }

    for make in manufacturers:
        try:
            bull = get_manufacturer_bulletins_json(engine, make)
            if not bull:
                results["manufacturers"][make] = {
                    "status": "no_data",
                    "message": "No bulletin data found",
                }
                continue

            df_models = convert_bulletin_to_df(bull, make=make)
            if df_models.empty:
                results["manufacturers"][make] = {
                    "status": "no_valid_records",
                    "message": "No valid records in bulletin",
                }
                continue

            save_result = save_vehicle_models_to_csv(df_models, csv_path, configs_dir)
            results["manufacturers"][make] = save_result

            results["summary"]["total_processed"] += save_result["total_records"]
            results["summary"]["total_saved"] += save_result["records_saved"]
            results["summary"]["total_duplicates"] += save_result["duplicates"]
            results["summary"]["total_invalid"] += save_result["invalid_records"]

        except Exception as e:
            error_msg = f"Error processing {make}: {str(e)}"
            results["manufacturers"][make] = {
                "status": "error",
                "message": error_msg,
            }
            results["summary"]["errors"].append(error_msg)

    return results


def _get_trim_discriminator_keywords(make: str = None, configs_dir: str = None) -> set[str]:
    """
    Return a set of keywords that discriminate between trim levels.
    These are actual trim variant names and TRIM_VARIANT tokens (like "N", "N-Line"),
    not fuel types (POWERTRAIN_TYPE) or transmission/drive specifications.

    Fuel types (POWERTRAIN_TYPE: hybrid, hev, phev, ev) are excluded because they are
    handled separately by the earlier EV-exclusion logic in search_models_by_description().
    Treating them as trim discriminators would incorrectly require users to specify trim
    names when searching by fuel type.

    Prefers to load from classification config if available, falls back to hardcoded set.

    Args:
        make: Manufacturer name (optional, enables config-driven lookup)
        configs_dir: Directory with classification configs (optional)

    Returns:
        set of known trim discriminator keywords (excluding POWERTRAIN_TYPE)
    """
    # Try to load from classification config
    if make:
        try:
            try:
                # Try relative import first (when called from accy_v2 package)
                from model_lookup.semantic.classifier import load_classification_config
            except ImportError:
                # Fall back to direct import (when called from model_lookup directory)
                from semantic.classifier import load_classification_config

            config = load_classification_config(make, configs_dir)
            # Include TRIM and TRIM_VARIANT, but NOT POWERTRAIN_TYPE (handled by EV-exclusion logic)
            trim_tokens = {
                token for token, category in config.get("token_map", {}).items() if category in ("TRIM", "TRIM_VARIANT")
            }
            if trim_tokens:
                return trim_tokens
        except Exception:
            pass  # Fall through to hardcoded set

    # Fallback to hardcoded set (backward compatibility)
    return {
        "premium", "noir", "se", "es", "gt", "le", "limited", "touring", "sel",
        "ex", "ex-l", "lx", "sx", "sport", "l", "s", "plus", "ta",
        "glx", "sport touring", "ex-l", "high line", "highline", "execline",
        "comfortline", "trendline", "gli", "jetta",
    }


def search_models_by_description(
    make: str, year: int, keywords: list[str], csv_path: str = None, exclude_ev: bool = True, configs_dir: str = None, oem_config: dict = None
) -> pd.DataFrame:
    """
    Search vehicle models by manufacturer, year, and description keywords.
    Keywords must match exactly as whole words (e.g., "SE" won't match "SEL").
    Filters out results that contain additional TRIM DISCRIMINATOR keywords not in the search list,
    while ignoring non-discriminating specification keywords (drive types, transmissions, packages).

    Automatically translates OEM-specific abbreviations (e.g., 'prem' → 'premium', 's-awc' → 'awd').

    Args:
        make: Manufacturer name
        year: Model year
        keywords: List of keywords to match in Description as exact words (all must be present)
                  OEM abbreviations are automatically translated (e.g., 'prem', 's-awc', 'p', 'n')
        csv_path: Path to CSV file (defaults to db/db_vehicle_models.csv)
        exclude_ev: If True and keywords don't contain EV keywords, filter out EV models
        configs_dir: Directory for keyword vocab JSONs (defaults to model_lookup/configs/)

    Returns:
        DataFrame with matching records
    """
    if csv_path is None:
        csv_path = str(Path(__file__).parent.parent / "db" / "db_vehicle_models.csv")

    if configs_dir is None:
        configs_dir = str(Path(__file__).parent.parent / "configs")

    # Translate OEM-specific abbreviations before searching
    try:
        try:
            # Try relative import first (when called from accy_v2 package)
            from model_lookup.semantic.translator import load_oem_translator, translate_keywords
        except ImportError:
            # Fall back to direct import (when called from model_lookup directory)
            from semantic.translator import load_oem_translator, translate_keywords

        translator = load_oem_translator(make, configs_dir)
        if translator:
            keywords = translate_keywords(keywords, translator)
    except Exception as e:
        # If translator not available, continue with original keywords
        translator = {}

    df = load_existing_csv(csv_path)

    if df.empty:
        return pd.DataFrame()

    df_filtered = df[df["Manufacturer"].str.lower() == make.lower()].copy()
    df_filtered = df_filtered[df_filtered["ModelYear"] == year]

    # DEBUG: Log the search parameters at entry
    import sys
    if make.lower() == 'hyundai' and 'pref' in [k.lower() for k in keywords]:
        print(f"\n[SEARCH_DEBUG] search_models_by_description() called:", file=sys.stderr)
        print(f"  make={make}, year={year}, keywords={keywords}", file=sys.stderr)
        print(f"  Initial candidates: {len(df_filtered)}", file=sys.stderr)

    # Parse OEM config to get search behavior flags
    oem_config = oem_config or {}
    if "model_lookup_rules" in oem_config:
        oem_rules = oem_config.get("model_lookup_rules", {}).get(make, {})
    else:
        oem_rules = oem_config

    use_single_char_token_matching = oem_rules.get("use_single_char_token_matching", False)

    for keyword in keywords:
        if use_single_char_token_matching and len(keyword) == 1:
            # For single-char keywords: strict token matching (exact word, not part of hyphenated term)
            df_filtered = df_filtered[
                df_filtered["Description"].apply(
                    lambda desc: keyword.lower() in _extract_description_tokens(desc)
                )
            ]
        else:
            # For multi-char keywords: use regex word boundary logic
            pattern = build_word_boundary_pattern(keyword)
            df_filtered = df_filtered[
                df_filtered["Description"].str.contains(pattern, case=False, na=False, regex=True)
            ]
        # DEBUG: Track how many records remain after each keyword filter
        import sys
        print(f"[SEARCH_DEBUG] After keyword '{keyword}': {len(df_filtered)} records", file=sys.stderr)

    # Get fuel type keywords from OEM config (already parsed above)

    raw_fuel_keywords = oem_rules.get("fuel_type_keywords", EV_KEYWORDS)

    # Translate fuel keywords through the same translator used for search keywords
    # (ensures we match against DB text that was ingested, not against config spellings)
    fuel_type_keywords = translate_keywords([kw.lower() for kw in raw_fuel_keywords], translator) if translator else [kw.lower() for kw in raw_fuel_keywords]

    # Check if user explicitly requested any fuel type
    search_kw_lower = [k.lower() for k in keywords]
    if exclude_ev and not any(kw in search_kw_lower for kw in fuel_type_keywords):
        # No fuel type keyword found in search — exclude all configured fuel types
        for fuel_keyword in fuel_type_keywords:
            pattern = build_word_boundary_pattern(fuel_keyword)
            df_filtered = df_filtered[
                ~df_filtered["Description"].str.contains(pattern, case=False, na=False, regex=True)
            ]

    # Post-filter: exclude results with TRIM DISCRIMINATOR keywords not in the search list
    # However: if any POWERTRAIN_TYPE keyword (fuel type) OR a TRIM keyword was explicitly requested,
    # skip discriminator filtering because the user is searching for a fuel type or trim
    # and should get all variants of that fuel type/trim (not just ones they explicitly named).
    vocab = load_manufacturer_keyword_vocab(make, configs_dir)
    if vocab:
        trim_discriminators = _get_trim_discriminator_keywords(make, configs_dir)
        search_kw_set = {kw.lower() for kw in keywords}

        # Check if any fuel-type keyword was in the search (before translation)
        user_requested_fuel_type = any(kw.lower() in fuel_type_keywords for kw in keywords)

        # Check if any trim keyword was in the search
        trim_kw_requested = bool(search_kw_set & trim_discriminators)

        # Only apply trim discriminator filtering if neither fuel type nor trim keyword was explicitly requested
        if not user_requested_fuel_type and not trim_kw_requested:
            def _has_extra_discriminator_keywords(desc: str) -> bool:
                tokens = set(_extract_description_tokens(desc))
                discriminator_tokens = tokens & trim_discriminators
                extra_discriminators = discriminator_tokens - search_kw_set
                return bool(extra_discriminators)

            df_filtered = df_filtered[~df_filtered["Description"].apply(_has_extra_discriminator_keywords)]

    # DEBUG: Log results at exit
    if make.lower() == 'hyundai' and 'pref' in [k.lower() for k in keywords]:
        print(f"  Final candidates: {len(df_filtered)}", file=sys.stderr)
        if len(df_filtered) > 0:
            for idx, row in df_filtered.iterrows():
                print(f"    - {row['Description'][:70]}", file=sys.stderr)
        print(f"[END_SEARCH_DEBUG]\n", file=sys.stderr)

    return df_filtered


def search_vehicle_models(
    year: int,
    model: str,
    make: str,
    trim: str = None,
    style_id: str = None,
    csv_path: str = None,
) -> pd.DataFrame:
    """
    Search vehicle models in CSV database by manufacturer-specific rules.

    Args:
        year: Model year (required, exact match)
        model: Model number (required, exact match, case-insensitive)
        make: Manufacturer name (required, exact match, case-insensitive)
        trim: Trim level (optional, contains match in configured trim fields)
        style_id: Style ID (optional, exact match, case-insensitive)
        csv_path: Path to CSV file (defaults to db/db_vehicle_models.csv)

    Returns:
        DataFrame with matching records (empty if no matches)
    """
    if csv_path is None:
        csv_path = str(Path(__file__).parent.parent / "db" / "db_vehicle_models.csv")

    df = load_existing_csv(csv_path)

    if df.empty:
        return pd.DataFrame()

    config = get_manufacturer_config(make)

    df_filtered = df[df["Manufacturer"].str.lower() == make.lower()].copy()

    df_filtered = df_filtered[df_filtered["ModelYear"] == year]

    df_filtered = df_filtered[df_filtered["ModelNumber"].str.lower() == model.lower()]

    if trim:
        trim_fields = config.get("trim_fields", ["Description"])
        trim_lower = trim.lower()

        mask = pd.Series([False] * len(df_filtered), index=df_filtered.index)
        for field in trim_fields:
            if field in df_filtered.columns:
                mask |= (
                    df_filtered[field].str.lower().str.contains(trim_lower, na=False)
                )
        df_filtered = df_filtered[mask]

    if style_id:
        style_field = config.get("style_field", "Style_ID")
        if style_field in df_filtered.columns:
            df_filtered = df_filtered[
                df_filtered[style_field].str.lower() == style_id.lower()
            ]

    return df_filtered
