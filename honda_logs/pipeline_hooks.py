"""
Pipeline Hooks - Integration points for logging
Add these logging calls to the notebook at each key step
"""

import pandas as pd
from pathlib import Path
from typing import Dict, Any, Tuple
from .pipeline_logger import get_logger


def log_pipeline_start(input_dir: str, output_dir: str, make: str):
    """Call this at the start of run_pipeline()"""
    logger = get_logger()
    logger.info("\n" + "="*100)
    logger.info("HONDA PIPELINE EXECUTION START")
    logger.info("="*100)
    logger.log_step("pipeline_start", "STARTED", {
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "make": make,
    })


def log_excel_loading(file_count: int, excel_dict: Dict):
    """Call this after loading Excel files"""
    logger = get_logger()
    logger.log_step("load_excel_files", "COMPLETED", {
        "files_loaded": file_count,
        "models": list(excel_dict.keys()),
    })
    logger.debug(f"Excel files loaded: {list(excel_dict.keys())}")


def log_models_database_loading(honda_models_df: pd.DataFrame):
    """Call this after loading honda_models.csv"""
    logger = get_logger()
    total_records = len(honda_models_df)
    valid_records = (honda_models_df["ModelName"].notna()).sum()

    logger.log_step("load_models_database", "COMPLETED", {
        "total_records": total_records,
        "valid_records": valid_records,
        "null_records": total_records - valid_records,
    })
    logger.info(f"Honda models database: {valid_records}/{total_records} records valid")


def log_data_extraction_start():
    """Call this before data extraction"""
    logger = get_logger()
    logger.log_step("data_extraction", "STARTED", {})


def log_data_extraction_complete(extracted_results: Dict, failures: Dict):
    """Call this after data extraction"""
    logger = get_logger()
    logger.log_step("data_extraction", "COMPLETED", {
        "successful_models": len(extracted_results),
        "failed_models": len(failures),
        "models_extracted": list(extracted_results.keys()),
    })

    if failures:
        logger.warning(f"Failed models: {list(failures.keys())}")
        for model_key, err in failures.items():
            logger.error(f"  {model_key}: {err}")


def log_ready_to_load_start(extracted_count: int):
    """Call this before create_ready_to_load_data()"""
    logger = get_logger()
    logger.log_step("build_ready_to_load", "STARTED", {
        "models_to_process": extracted_count,
    })


def log_trim_templates_built(model_key: str, trim_dfs: Dict):
    """Call this after building trim-level templates"""
    logger = get_logger()
    logger.debug(f"[{model_key}] Trim templates built: {list(trim_dfs.keys())}")


def log_model_attachment_start(model_key: str, honda_models_db: pd.DataFrame):
    """Call this before attaching model numbers"""
    logger = get_logger()
    logger.debug(f"[{model_key}] Starting model number attachment...")
    logger.debug(f"[{model_key}] Database has {len(honda_models_db)} records")


def log_model_attachment_complete(model_key: str, df_before: pd.DataFrame, df_after: pd.DataFrame):
    """Call this after attaching model numbers"""
    logger = get_logger()

    if "model_number" in df_after.columns:
        non_null = df_after["model_number"].notna().sum()
        total = len(df_after)
        pct = (non_null / total * 100) if total > 0 else 0

        logger.log_model_number_attachment(model_key, df_before, df_after)

        # Log sample model numbers
        samples = df_after[df_after["model_number"].notna()]["model_number"].unique()[:5]
        logger.debug(f"[{model_key}] Sample model numbers: {list(samples)}")

        # Check for trim names in model_number (indicator of failure)
        if any("trim" in str(v).lower() or any(c in str(v) for c in ["LX", "EX", "SPORT", "TOURING"])
               for v in df_after["model_number"].dropna()):
            logger.warning(f"[{model_key}] WARNING: model_number contains trim names instead of model codes!")
    else:
        logger.error(f"[{model_key}] CRITICAL: model_number column missing after attachment!")


def log_model_status(model_key: str, status: str, issues: str):
    """Call this when logging model QA status"""
    logger = get_logger()
    logger.debug(f"[{model_key}] Status: {status} | Issues: {issues}")


def log_ready_to_load_complete(final_model_dfs: Dict, report_rows: list):
    """Call this after all models are processed"""
    logger = get_logger()
    logger.log_step("build_ready_to_load", "COMPLETED", {
        "models_with_data": len(final_model_dfs),
        "report_rows": len(report_rows),
    })


def log_excel_export_start(output_path: str):
    """Call this before exporting to Excel"""
    logger = get_logger()
    logger.log_step("export_excel", "STARTED", {
        "output_path": str(output_path),
    })


def log_excel_export_complete(file_path: str, sheet_name: str, df: pd.DataFrame):
    """Call this after exporting a sheet"""
    logger = get_logger()
    logger.log_output_file(file_path, sheet_name, df)

    if "Model" in df.columns:
        model_col_sample = df["Model"].head(10).tolist()
        logger.debug(f"[Export] Sheet '{sheet_name}' Model column sample: {model_col_sample}")


def log_pipeline_complete():
    """Call this at the end of run_pipeline()"""
    logger = get_logger()
    logger.log_step("pipeline_complete", "SUCCESS", {})
    logger.save_logs()
    logger.print_summary()


def log_error(message: str, exception: Exception = None):
    """Log an error during execution"""
    logger = get_logger()
    logger.error(message, exception)
