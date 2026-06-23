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


def load_existing_csv(csv_path: str) -> pd.DataFrame:
    """
    Load existing CSV file. Returns empty DataFrame if file doesn't exist.
    """
    if os.path.exists(csv_path):
        try:
            return pd.read_csv(csv_path)
        except Exception as e:
            print(f"Warning: Could not read existing CSV: {e}")
            return pd.DataFrame()
    return pd.DataFrame()


def check_duplicate_record(
    df_new: pd.DataFrame, df_existing: pd.DataFrame
) -> pd.DataFrame:
    """
    Filter out records that already exist in the database.
    Uses Manufacturer, ModelYear, and ModelNumber as the unique key.
    """
    if df_existing.empty:
        return df_new

    required_cols = ["Manufacturer", "ModelYear", "ModelNumber"]
    existing_cols = [col for col in required_cols if col in df_existing.columns]

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


def save_vehicle_models_to_csv(df: pd.DataFrame, csv_path: str = None) -> dict:
    """
    Save vehicle models to CSV with validation and deduplication.

    Args:
        df: DataFrame with vehicle model data
        csv_path: Path to CSV file (defaults to db/db_vehicle_models.csv)

    Returns:
        dict with save status, records saved, duplicates skipped, etc.
    """
    if csv_path is None:
        csv_path = str(Path(__file__).parent.parent / "db" / "db_vehicle_models.csv")

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

    df_existing = load_existing_csv(csv_path)

    if not df_existing.empty:
        df_valid = check_duplicate_record(df_valid, df_existing)
        result["duplicates"] = (
            result["total_records"] - result["invalid_records"] - len(df_valid)
        )

    if df_valid.empty:
        result["success"] = True
        result["message"] = "No new data to load — all records already exist"
        return result

    mode = "w" if df_existing.empty else "a"
    header = df_existing.empty

    try:
        df_valid.to_csv(csv_path, mode=mode, header=header, index=False)
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
        Description2 = json_[idx].get("Description2")
        Package = json_[idx].get("Package")
        Style_ID = json_[idx].get("Style")

        print(
            f"{ModelYear}, {ModelNumber}, { Description}, { Description2}, { Package}, {Style_ID}"
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
            "Description2": item.get("Description2"),
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
                "Description2",
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
    return rf"\b{keyword}\b"


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


def batch_save_manufacturer_models(
    engine,
    manufacturers: list[str],
    csv_path: str = None,
) -> dict:
    """
    Fetch and save vehicle models for multiple manufacturers.

    Args:
        engine: SQLAlchemy engine for database connection
        manufacturers: List of manufacturer names
        csv_path: Path to CSV file (defaults to db/db_vehicle_models.csv)

    Returns:
        dict with results for each manufacturer and summary totals
    """
    if csv_path is None:
        csv_path = str(Path(__file__).parent.parent / "db" / "db_vehicle_models.csv")

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

            save_result = save_vehicle_models_to_csv(df_models, csv_path)
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
    These are actual trim variant names, not transmission/drive specifications.

    Prefers to load from classification config if available, falls back to hardcoded set.

    Args:
        make: Manufacturer name (optional, enables config-driven lookup)
        configs_dir: Directory with classification configs (optional)

    Returns:
        set of known trim discriminator keywords
    """
    # Try to load from classification config
    if make:
        try:
            from model_lookup.classifier import load_classification_config

            config = load_classification_config(make, configs_dir)
            trim_tokens = {
                token for token, category in config.get("token_map", {}).items() if category == "TRIM"
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
    make: str, year: int, keywords: list[str], csv_path: str = None, exclude_ev: bool = True, configs_dir: str = None
) -> pd.DataFrame:
    """
    Search vehicle models by manufacturer, year, and description keywords.
    Keywords must match exactly as whole words (e.g., "SE" won't match "SEL").
    Filters out results that contain additional TRIM DISCRIMINATOR keywords not in the search list,
    while ignoring non-discriminating specification keywords (drive types, transmissions, packages).

    Args:
        make: Manufacturer name
        year: Model year
        keywords: List of keywords to match in Description as exact words (all must be present)
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

    df = load_existing_csv(csv_path)

    if df.empty:
        return pd.DataFrame()

    df_filtered = df[df["Manufacturer"] == make].copy()
    df_filtered = df_filtered[df_filtered["ModelYear"] == year]

    for keyword in keywords:
        pattern = build_word_boundary_pattern(keyword)
        df_filtered = df_filtered[
            df_filtered["Description"].str.contains(pattern, case=False, na=False, regex=True)
        ]

    if exclude_ev and not any(kw.upper() in [k.upper() for k in keywords] for kw in EV_KEYWORDS):
        for ev_keyword in EV_KEYWORDS:
            pattern = build_word_boundary_pattern(ev_keyword)
            df_filtered = df_filtered[
                ~df_filtered["Description"].str.contains(pattern, case=False, na=False, regex=True)
            ]

    # Post-filter: exclude results with TRIM DISCRIMINATOR keywords not in the search list
    vocab = load_manufacturer_keyword_vocab(make, configs_dir)
    if vocab:
        trim_discriminators = _get_trim_discriminator_keywords(make, configs_dir)
        search_kw_set = {kw.lower() for kw in keywords}

        def _has_extra_discriminator_keywords(desc: str) -> bool:
            tokens = set(_extract_description_tokens(desc))
            discriminator_tokens = tokens & trim_discriminators
            extra_discriminators = discriminator_tokens - search_kw_set
            return bool(extra_discriminators)

        df_filtered = df_filtered[~df_filtered["Description"].apply(_has_extra_discriminator_keywords)]

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
