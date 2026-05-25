# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.1
#   kernelspec:
#     display_name: base
#     language: python
#     name: python3
# ---

# %%
import pandas as pd
import pathlib as pl


import os


from __future__ import annotations

from typing import Dict, Any, Union
import math



# %%
# Directories

RAW_DATA_DIR = pl.Path("../landing_zone/")
READY_TO_UPLOAD_FILES_DIR = pl.Path("../ready_to_upload/")

RAW_DATA_DIR = RAW_DATA_DIR / "2026" / "Mitsubishi"
SAMPLE_DATA_FILE_PATH = RAW_DATA_DIR / "Accessory Guide - February26.xlsx"
READY_TO_UPLOAD_DIR = READY_TO_UPLOAD_FILES_DIR / "2026" / "Mitsubishi"

# %%
ESSENTIAL_COLUMNS = ['Part Number', 'English Description', 'French Description', 'Remarks',
       'MSRP $', 'Install Time','Labour Rate']


ESSENTIAL_COLUMNS_AFTER_CLEANUP = ['Part_Number', 'English_Description', 'French_Description', 'Remarks',
       'MSRP_$', 'Install_Time', 'Labour_Rate']



NON_TRIM_COLUMNS = ['Image', 'Install_Sheet', 'Category', 'Install_Sheet', "DNP_$"]

NON_ESSENTIAL_COLUMNS = ['Category', 'Photo', "Image", 'DNP_$', 'Installed_Price', 'IMC', 'OH+OH', 'Install_Sheet']

BOUNDARY_COLUMNS_FOR_TRIM_COLUMNS = {
       "left":["Remarks"], 
       "right":["Photo", "image"]
}

# LANG specific cols

LANG_SPECIFIC_COLUMNS = {
       "English": ["English_Description"],
       "French": ["French_Description"]
}


MODEL_COL_NAME = "Model_Name"
TRIM_COL_NAME = "Trim"


# Define a mapping of original column names to new column names
RATE_IMPORT_COLUMN_MAPPING = {
       'part_number': 'Part',
       'english_description': 'Description',
       'french_description': 'Description',
       'remarks': 'Comments',
       'msrp_$': 'Price',
       'install_time': 'Hours',
       'Trim': 'Trim'
    }


COLS_ESSENTIAL_FOR_RATE_IMPORT = ['Part', 'Description', 'Comments', 'Price', 'Hours', 'Trim']

'''

Data Quality check:


'''


NON_NULLABLE_COLUMNS = ['Part_Number', 'English_Description', 'MSRP_$', 'Install_Time']



# %%
# Sheet name keywords that indicate NON-DATA sheets
# Case-insensitive, substring match

NON_MODEL_KEYWORDS = [
    "meta_data", "Luxwood"
]


# %%
import re

def to_lowercase(strings: List[str]) -> List[str]:
    """
    Convert all strings in a list to lowercase.

    Args:
        strings (List[str]): A list of strings to normalize.

    Returns:
        List[str]: A new list where each string is lowercased.

    Raises:
        TypeError: If any element in the list is not a string.
    """
    if not all(isinstance(s, str) for s in strings):
        raise TypeError("All elements must be strings")

    return [s.lower() for s in strings]
def clean_column_headers(columnName: str) -> str:
    """
    Cleans up a columns name by:
    1. Reducing multiple spaces to a single space
    2. Normalizing hyphen spacing:
       - "- ", " -", and " - " are all replaced with "-"
    
    Args:
        columnName (str): Raw column name string

    Returns:
        str: Cleaned column name
    """

    if not isinstance(columnName, str):
        raise TypeError("columnName must be a string")

    # Normalize hyphen spacing:
    # Any amount of whitespace around a hyphen becomes a single hyphen
    cleaned = re.sub(r"\s*-\s*", "-", columnName)

    # Replace multiple spaces with a single space
    cleaned = re.sub(r"\s{2,}", " ", cleaned)

    
    # Trim leading/trailing whitespace
    cleaned = cleaned.strip()

    # replace remaining spaces with underscores for consistent formatting
    cleaned = cleaned.replace(" ", "_")


    # Trim leading/trailing whitespace
    return cleaned

def clean_model_name(model_name: str) -> str:
    """
    Cleans up a model name by:
    1. Reducing multiple spaces to a single space
    2. Normalizing hyphen spacing:
       - "- ", " -", and " - " are all replaced with "-"
    
    Args:
        model_name (str): Raw model name string

    Returns:
        str: Cleaned model name
    """

    if not isinstance(model_name, str):
        raise TypeError("model_name must be a string")

    # Normalize hyphen spacing:
    # Any amount of whitespace around a hyphen becomes a single hyphen
    cleaned = re.sub(r"\s*-\s*", "-", model_name)

    # Replace multiple spaces with a single space
    cleaned = re.sub(r"\s{2,}", " ", cleaned)

    
    # Trim leading/trailing whitespace
    cleaned = cleaned.strip()

    # replace remaining spaces with underscores for consistent formatting
    cleaned = cleaned.replace(" ", "_")


    # Trim leading/trailing whitespace
    return cleaned


def lowercase_list(values):
    """
    Converts all string elements in a list to lowercase.
    Non-string values are left unchanged.
    """
    return [
        value.lower() if isinstance(value, str) else value
        for value in values
    ]


def is_valid_data_sheet(sheet_name: str) -> bool:
    """
    Determine whether a sheet name represents an actual data sheet.

    Returns False if the sheet name contains any excluded keyword.
    """
    normalized = sheet_name.lower()

    return not any(
        keyword in normalized
        for keyword in lowercase_list(NON_MODEL_KEYWORDS)
    )

def header_promotion_successful(df: pd.DataFrame) -> list:
    """
    Returns a list of missing essential columns
    exists in df.columns.
    
    Extra columns in the DataFrame are allowed.
    Order does not matter.
    """
    return list(set(ESSENTIAL_COLUMNS) - set(df.columns))


def drop_fully_empty_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Drop columns that are entirely empty (all values NaN).

    Parameters
    ----------
    df : pandas.DataFrame
        DataFrame AFTER header promotion.

    Returns
    -------
    pandas.DataFrame
        Cleaned DataFrame with fully empty columns removed.

    Raises
    ------
    ValueError
        If df is None or empty.
    """

    if df is None or df.empty:
        raise ValueError("Cannot clean DataFrame: DataFrame is empty or None")

    # Drop columns where ALL values are NaN
    cleaned_df = df.dropna(axis=1, how="all")

    return cleaned_df

import pandas as pd
from typing import List


def filter_for_essential_columns_only(
    df: pd.DataFrame,
    columns_to_filter_out: List[str]
) -> pd.DataFrame:
    """
    Returns a DataFrame with specified columns removed (case-insensitive),
    while preserving the original column names in the output.

    Args:
        df (pd.DataFrame): Input DataFrame
        columns_to_filter_out (List[str]): List of column names to exclude

    Returns:
        pd.DataFrame: DataFrame containing only the remaining columns
    """

    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame")

    if not isinstance(columns_to_filter_out, list):
        raise TypeError("columns_to_filter_out must be a list of column names")

    # Normalize columns_to_filter_out to lowercase for comparison
    columns_to_filter_out_lower = {
        col.lower() for col in columns_to_filter_out
    }

    # Identify actual columns to drop (preserve original casing)
    columns_to_drop = [
        col for col in df.columns
        if str(col).lower() in columns_to_filter_out_lower
    ]
    # Drop only matching columns, ignore non-existent ones safely
    df = df.drop(columns=columns_to_drop)

    df.columns = lowercase_list(df.columns)

    return df


def strip_dataframe_values(df: pd.DataFrame) -> pd.DataFrame:
    """
    Strips leading and trailing whitespace from all string values
    in a pandas DataFrame.

    Non-string values are left unchanged.
    """

    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame")

    df = df.copy()

    for col in df.select_dtypes(include=["object", "string"]):
        df[col] = df[col].apply(
            lambda value: value.strip() if isinstance(value, str) else value
        )

    return df




# %%

# %%


def extract_sheet_meta_data_from_columns(
    df: pd.DataFrame,
    sheet_name: str,
) -> Dict[str, Any]:
    """
    Extract metadata from sheet columns.

    IMPORTANT:
    - This function REFUSES to run on ignored sheets.
    """

    # ---- hard guard: ignored sheets are forbidden
    if not is_valid_data_sheet(sheet_name):
        raise ValueError(
            f"Metadata extraction attempted on ignored sheet: '{sheet_name}'"
        )

    if df.empty:
        raise ValueError(f"Sheet '{sheet_name}' is empty")

    # -----------------------------
    # Filter usable columns
    # -----------------------------
    valid_columns = [
        col for col in df.columns
        if "unnamed" not in str(col).lower()
    ]

    if not valid_columns:
        raise ValueError(
            f"Sheet '{sheet_name}' has no usable columns after filtering 'Unnamed'"
        )

    # -----------------------------
    # 1) Model name from column 0
    # -----------------------------
    model_name = str(valid_columns[0]).strip()

    # Clean up the model name to ensure consistent formatting
    model_name = clean_model_name(model_name)

    # -----------------------------
    # 2) Extract L_rate from column values
    # -----------------------------
    L_rate = "not found"

    for col in valid_columns:
        value = col

        if value is None or (isinstance(value, float) and math.isnan(value)):
            continue

        if isinstance(value, (int, float)):
            L_rate = value
            break

        if isinstance(value, str):
            try:
                L_rate = float(value.strip())
                break
            except ValueError:
                continue
            
    return {
        "model_name": model_name.lower(),
        "L_rate": L_rate,
    }


# %%



def check_l_rate_consistency(meta_data: Dict[str, Dict[str, Any]]) -> bool:
    """
    Check whether all L_rate values are the same across all models.

    Parameters
    ----------
    meta_data : dict
        Dictionary of per-sheet metadata in the form:
        {
            "SheetName": {
                "model_name": str,
                "L_rate": float | int | "not found"
            },
            ...
        }

    Returns
    -------
    bool
        True if all L_rate values are identical.

    Raises
    ------
    ValueError
        If meta_data is empty, malformed, contains missing L_rate values,
        or if L_rate values differ across models.
    """

    if not isinstance(meta_data, dict) or not meta_data:
        raise ValueError("meta_data must be a non-empty dictionary")

    l_rates = {}
    for sheet_name, data in meta_data.items():
        if not isinstance(data, dict):
            raise ValueError(f"Metadata for '{sheet_name}' is not a dictionary")

        if "L_rate" not in data:
            raise ValueError(f"Missing L_rate for sheet '{sheet_name}'")

        l_rate = data["L_rate"]

        if l_rate == "not found":
            raise ValueError(f"L_rate not found for sheet '{sheet_name}'")

        if not isinstance(l_rate, (int, float)):
            raise ValueError(
                f"Invalid L_rate type for sheet '{sheet_name}': {type(l_rate).__name__}"
            )

        l_rates[sheet_name] = l_rate

    unique_rates = set(l_rates.values())

    if len(unique_rates) > 1:
        raise ValueError(
            "L_rate values are not consistent across models: "
            f"{l_rates}"
        )

    return True


# %%
def change_and_filter_cols_for_rate_importer(df: pd.DataFrame) -> pd.DataFrame:
    """
    Changes column names to match the expected format for the rate importer.
    For example, it may rename 'Labour Rate' to 'Labour_Rate' and ensure all columns are lowercase with underscores.

    Args:
        df (pd.DataFrame): The input DataFrame with original column names.
    Returns:
        pd.DataFrame: The DataFrame with renamed columns suitable for the rate importer.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("Input must be a pandas DataFrame")
    
    # Rename columns based on the mapping
    df = df.rename(columns = RATE_IMPORT_COLUMN_MAPPING)

    
    # Filter columns to only include those in essential for rate importing
    df = df[[col for col in df.columns if col in COLS_ESSENTIAL_FOR_RATE_IMPORT]]

    return df


# %%
def promote_first_row_to_header(df: pd.DataFrame, sheet_name: str) -> pd.DataFrame:
    """
    Promote row 0 to become column headers and drop it from the data.

    Raises
    ------
    ValueError if the DataFrame has fewer than 2 rows
    """

    if df.shape[0] < 2:
        raise ValueError("Cannot promote first row to header: insufficient rows")

    new_header = df.iloc[0].astype(str).str.strip()
    df = df.iloc[1:].reset_index(drop=True)
    df.columns = new_header


    missing_columns = header_promotion_successful(df)
    
    # Clean column headers after promotion to ensure consistent formatting
    df.columns = [clean_column_headers(col) for col in df.columns]

    if missing_columns:
        raise ValueError(
            f"Header promotion failed: essential columns are missing after promotion: {missing_columns} in sheet '{sheet_name}'"
        )
    
    
    # df.columns = {
    #     col.lower() for col in df.columns
    # }


    return df

   

# %%

# %%
from pathlib import Path
# from typing import Dict, Union

def load_excel_sheets_to_dict(
    excel_file_path: Union[str, Path]
) -> Dict[str, object]:
    """
    Load ONLY valid data sheets from an Excel file.
    Ignored sheets are excluded from BOTH data and metadata.
    Applies header promotion and column cleanup.
    """

    path = Path(excel_file_path).expanduser().resolve()

    if not path.exists():
        raise FileNotFoundError(f"Excel file not found: {path}")

    if not path.is_file():
        raise ValueError(f"Path is not a file: {path}")

    valid_extensions = {".xls", ".xlsx", ".xlsm", ".xlsb", ".ods"}
    if path.suffix.lower() not in valid_extensions:
        raise ValueError(f"Unsupported Excel file type: {path.suffix}")

    try:
        excel = pd.ExcelFile(path)
    except Exception as exc:
        raise RuntimeError(f"Failed to open Excel file: {path}") from exc

    result: Dict[str, object] = {}
    meta_data: Dict[str, Dict[str, object]] = {}

    for raw_sheet_name in excel.sheet_names:
        clean_sheet_name = raw_sheet_name.strip().lower()

        # ---- skip ignored sheets
        if not is_valid_data_sheet(clean_sheet_name):
            continue

        if clean_sheet_name in result:
            raise ValueError(
                f"Duplicate sheet name after stripping: '{clean_sheet_name}'"
            )

        try:
            df_raw = excel.parse(sheet_name=raw_sheet_name)
        except Exception as exc:
            raise RuntimeError(
                f"Failed to parse sheet '{raw_sheet_name}' from {path}"
            ) from exc

        # ---- extract metadata BEFORE header promotion
        sheet_meta = extract_sheet_meta_data_from_columns(
            df=df_raw,
            sheet_name=clean_sheet_name,
        )


        # ---- promote first row to headers
        df_promoted = promote_first_row_to_header(df_raw, clean_sheet_name)

        # print(f"Successfully promoted headers for sheet '{df_promoted.columns}'")

        # ---- drop fully empty columns
        df_clean = drop_fully_empty_columns(df_promoted)
       
        # Strip all string values in the DataFrame to clean up any leading/trailing whitespace
        df_clean = strip_dataframe_values(df_clean)

        # print(f"Successfully dropped fully empty columns for sheet '{df_clean.columns}'")

        # ---- filter for essential columns only
        df_filtered = filter_for_essential_columns_only(df_clean, columns_to_filter_out = NON_ESSENTIAL_COLUMNS)
        
        # print(f"Successfully filtered essential columns for sheet '{df_filtered.columns}'")

        meta_data[clean_sheet_name] = sheet_meta

        # set the long/standard model name as the key in the result dictionary to ensure consistency across sheets, instead of using the raw sheet name which may have variations.
        actual_model_name = sheet_meta.get("model_name", f"unknown_model_{clean_sheet_name}")
        result[actual_model_name] = df_filtered
        
    
    if not result:
        raise ValueError(
            f"No valid data sheets found in {path}. "
            f"Excluded keywords: {NON_MODEL_KEYWORDS}"
        )

    result["meta_data"] = meta_data
    return result


# %% [markdown]
# Data Exploratory Analysis

# %%

def validate_non_null_columns(
    df: pd.DataFrame,
    non_null_columns: list[str]
) -> tuple[bool, pd.DataFrame]:
    """
    Check that specified columns contain no empty values.

    Empty is defined as:
    - NaN / None
    - Empty string ""
    - Whitespace-only strings

    Args:
        df (pd.DataFrame): Input DataFrame
        non_null_columns (list[str]): Columns that must not be empty

    Returns:
        tuple:
            - bool: True if no empty values found, False otherwise
            - pd.DataFrame: Subset of rows where at least one specified column is empty
    """
    # Defensive copy is NOT needed; we do not mutate df
    
    # Build a boolean mask for "empty" values per column
    empty_mask = (
        df[non_null_columns]
        .isna() |
        df[non_null_columns].apply(
            lambda col: col.astype(str).str.strip().eq("")
        )
    )

    # Rows where ANY of the specified columns are empty
    failing_rows = df[empty_mask.any(axis=1)]

    # Validation result
    is_valid = failing_rows.empty

    return is_valid, failing_rows


# %%
def check_if_is_inboundary_for_trim_columns(df: pd.DataFrame, column_name: str) -> bool:
    """
    Check if a column is within the defined boundary columns for trim columns.

    Parameters
    ----------
    df : pd.DataFrame
        The DataFrame containing the columns.
    column_name : str
        The name of the column to check.

    Returns
    -------
    bool
        True if the column is within the boundaries, False otherwise.
    """

    columns = list(df.columns)
    column_name_lower = str(column_name).lower()

    left_boundaries = lowercase_list(BOUNDARY_COLUMNS_FOR_TRIM_COLUMNS["left"])
    right_boundaries = lowercase_list(BOUNDARY_COLUMNS_FOR_TRIM_COLUMNS["right"])

    left_index = max(
        (i for i, col in enumerate(columns) if str(col).lower() in left_boundaries),
        default=-1
    )
    
    right_index = min(
        (i for i, col in enumerate(columns) if str(col).lower() in right_boundaries),
        default=len(columns)
    )

    column_index = next(
        (i for i, col in enumerate(columns) if str(col).lower() == column_name_lower),
        None
    )

    if column_index is None:
        raise ValueError(f"Column '{column_name}' not found in DataFrame")

    return left_index < column_index < right_index

# %%


def get_valid_trim_column_names(df: pd.DataFrame) -> list:
    """
    Returns a list of trim level column names.
    Comparison against global exclusion lists is case-insensitive,
    while original column names (stripped) are preserved in output.
    """

    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame")

    # Normalize global exclusion lists for case-insensitive comparison
    essential_lower = {str(c).lower() for c in ESSENTIAL_COLUMNS_AFTER_CLEANUP}
    non_trim_lower = {str(c).lower() for c in NON_TRIM_COLUMNS}
    non_essential_lower = {str(c).lower() for c in NON_ESSENTIAL_COLUMNS}

    trim_column_names = [
        str(col).strip()
        for col in df.columns
        if str(col).lower() not in essential_lower
        and str(col).lower() not in non_trim_lower
        and str(col).lower() not in non_essential_lower
        and check_if_is_inboundary_for_trim_columns(df, col)
    ]
    
    return trim_column_names

 

# %%

# %%


def get_trim_specific_dataframes(df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """
    Given a DataFrame and a list of trim column names, returns a dictionary of DataFrames filtered for each trim.

    Each key in the output dictionary corresponds to a trim column name, and its value is a DataFrame containing only the rows where that trim column has an "X" (indicating applicability for that trim).

    The returned DataFrames include only the essential columns plus the specific trim column for context.
    """
    # get trim column names
    trim_column_names = get_valid_trim_column_names(df)

    lang_and_trim_specific_df_dict = {}
    for trim in trim_column_names:
        filter_for_trim = df[trim].str.upper() == "X" # "X" indicates applicability for the trim; adjust as needed based on actual data
        sliced_df = df[lowercase_list(ESSENTIAL_COLUMNS_AFTER_CLEANUP) + [trim]].loc[filter_for_trim]

        sliced_df.rename(columns={trim: TRIM_COL_NAME}, inplace=True)  # Rename the trim column to a standard name for consistency
        sliced_df[TRIM_COL_NAME] = trim  # Set the value of the trim column to the trim name for context
        
        lang_and_trim_specific_df_dict[trim] = sliced_df      # Keep only essential columns + the specific trim column for context

        
    return lang_and_trim_specific_df_dict    



# %%
def merge_language_specific_dfs_by_trim(lang_trim_spec_dfs: Dict[str, Dict[str, pd.DataFrame]]) -> Dict[str, pd.DataFrame]:
    """
    Merges language-specific DataFrames by trim level into single DataFrames for each language.

    Parameters
    ----------
    lang_trim_spec_dfs : dict
        A nested dictionary of DataFrames in the format:
        {
            "TrimName": {
                "Language": DataFrame,
                ...
            },
            ...
        }

    Returns
    -------
    dict
        A dictionary containing the merged DataFrames for each language.
    """
    
    merged_EN_df = pd.DataFrame()
    merged_FR_df = pd.DataFrame()

    for trim in lang_trim_spec_dfs:
        for lang, df in lang_trim_spec_dfs[trim].items():
            if lang == "EN":
                merged_EN_df = pd.concat([merged_EN_df, df], ignore_index=True)
            elif lang == "FR":
                merged_FR_df = pd.concat([merged_FR_df, df], ignore_index=True)

    
    merged_EN_df = change_and_filter_cols_for_rate_importer(merged_EN_df)
    
    merged_FR_df = change_and_filter_cols_for_rate_importer(merged_FR_df)

    return {"EN": merged_EN_df, "FR": merged_FR_df}


# %%

def get_trim_and_language_specific_dataframes(trim_specific_df_dict: Dict[str, pd.DataFrame]) -> Dict[str, Dict[str, pd.DataFrame]]:
    """
    Given a dictionary of trim-specific DataFrames and a mapping of language-specific columns, returns a nested dictionary of DataFrames filtered for each trim and language.

    The output dictionary has the format:
    {
        "TrimName": {
            "Language": DataFrame,
            ...
        },
        ...
    }
    Each innermost DataFrame contains only the rows where the specific trim column has an "X" (indicating applicability for that trim) and includes only the essential columns plus the language-specific description column for context.
    """

    lang_and_trim_specific_df_dict = {}

    for trim, df in trim_specific_df_dict.items():
        lang_and_trim_specific_df_dict[trim] = {}
        
        # Create a new DataFrame with only essential columns + existing language-specific columns
        EN_specific_columns = lowercase_list(LANG_SPECIFIC_COLUMNS["English"])
        FR_specific_columns = lowercase_list(LANG_SPECIFIC_COLUMNS["French"])

    
        lang_and_trim_specific_df_dict[trim]["EN"] = df.drop(columns=FR_specific_columns)
        lang_and_trim_specific_df_dict[trim]["FR"] = df.drop(columns=EN_specific_columns)

    return lang_and_trim_specific_df_dict


# %%

def save_merged_dfs_to_excel(all_merged_dfs_by_language: Dict[str, Dict[str, pd.DataFrame]], output_path: Union[str, Path]):
    """
    Saves merged DataFrames to an Excel file with separate sheets for each language.

    Parameters
    ----------
    all_merged_dfs_by_language : dict
        A dictionary containing merged DataFrames for each language in the format:
        {
            "ModelName": {
                "Language": DataFrame,
                ...
            },
            ...
        }
    output_path : str or Path
        The file path where the Excel file will be saved.   
    Raises
    ------  
    ValueError
        If the output path is invalid or if any of the DataFrames are not valid for saving.
    IOError
        If there is an error during the file writing process, such as permission issues.
    """
    output_path = Path(output_path).expanduser().resolve()

    # Ensure the output directory exists
    output_dir = output_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"{output_path.stem}_{timestamp}{output_path.suffix}"

    try:
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            for model_name, lang_dfs in all_merged_dfs_by_language.items():
                for lang, df in lang_dfs.items():
                    if not isinstance(df, pd.DataFrame):
                        raise ValueError(
                            f"Data for {model_name} in {lang} is not a valid DataFrame"
                        )

                    sheet_name = f"{model_name}_{lang}"
                    df.to_excel(writer, sheet_name=sheet_name, index=False)

    except Exception as exc:
        raise IOError(f"Failed to save Excel file to {output_path}") from exc



# %%
def extract_raw_data_dic(data_dict : Dict[str, object])-> Dict[ str, Dict[str, pd.DataFrame]]:

    all_merged_dfs_by_language = {}
    
    # loop through each model and process its DataFrame
    for model, model_df in data_dict.items():
        if model in NON_MODEL_KEYWORDS:
            continue

        if model_df is None or not isinstance(model_df, pd.DataFrame):
            
            raise ValueError(f"Model {model} data not found for model - Process_data()")

        # Step 2: Extract trim-specific DataFrames
        trim_specific_dict = get_trim_specific_dataframes(model_df)

        # Step 3: Split trim-specific DataFrames into language-specific DataFrames
        lang_trim_spec_dfs = get_trim_and_language_specific_dataframes(trim_specific_dict)
        
        # Step 4: Merge all language-specific DataFrames by language
        merged_model_df_dict = merge_language_specific_dfs_by_trim(lang_trim_spec_dfs)
        
        all_merged_dfs_by_language[model] = merged_model_df_dict
    
    return all_merged_dfs_by_language


# %%
def process_data(excel_file_path: Union[str, Path]):
    """
    Main function to process the data from raw Excel sheets to merged DataFrames by language.

    Steps:
    1. Load Excel sheets into a dictionary of DataFrames.
    2. For each model's DataFrame, extract trim-specific DataFrames.
    3. For each trim-specific DataFrame, further split into language-specific DataFrames.
    4. Merge all language-specific DataFrames by language.

    Returns
    -------
    dict
        A dictionary containing the merged DataFrames for each language.
    """

    # Step 1: Load Excel sheets into a dictionary of DataFrames
    data_dict = load_excel_sheets_to_dict(excel_file_path)

    merged_model_df_dict = extract_raw_data_dic(data_dict)

    
    # Step 5: Save merged DataFrames to Excel
    output_file_path = READY_TO_UPLOAD_DIR / "mitsubishi_Accy.xlsx"
    # save_merged_dfs_to_excel(all_merged_dfs_by_language, output_file_path)

    return merged_model_df_dict


# %%

# %%

# Loaded data 
SAMPLE_DATA_FILE_PATH = RAW_DATA_DIR / "Accessory Guide - February26.xlsx"

merged = process_data(SAMPLE_DATA_FILE_PATH)
 

# %%

merged["2020_rvr"]["EN"]


# %%
