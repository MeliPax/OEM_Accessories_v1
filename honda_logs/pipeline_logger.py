"""
Honda Pipeline Logging System
Comprehensive logging for debugging pipeline execution
"""

import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, List
import pandas as pd


class PipelineLogger:
    """Centralized logging for the Honda pipeline"""

    def __init__(self, log_dir: str = "honda_logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Timestamp for this run
        self.run_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.run_dir = self.log_dir / self.run_timestamp
        self.run_dir.mkdir(parents=True, exist_ok=True)

        # Log files
        self.log_file = self.run_dir / "pipeline.log"
        self.steps_file = self.run_dir / "steps.json"
        self.data_checks_file = self.run_dir / "data_checks.json"
        self.errors_file = self.run_dir / "errors.json"

        # Initialize file structures
        self.steps = []
        self.data_checks = []
        self.errors = []

        # Setup Python logging
        self.py_logger = self._setup_python_logger()

        # Print startup
        self.info(f"Pipeline logging initialized - Run: {self.run_timestamp}")
        self.info(f"Log directory: {self.run_dir}")

    def _setup_python_logger(self) -> logging.Logger:
        """Setup Python logging to both file and console"""
        logger = logging.getLogger("honda_pipeline")
        logger.setLevel(logging.DEBUG)

        # File handler
        fh = logging.FileHandler(self.log_file)
        fh.setLevel(logging.DEBUG)

        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)

        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)

        logger.addHandler(fh)
        logger.addHandler(ch)

        return logger

    def info(self, message: str):
        """Log info message"""
        self.py_logger.info(message)

    def debug(self, message: str):
        """Log debug message"""
        self.py_logger.debug(message)

    def warning(self, message: str):
        """Log warning message"""
        self.py_logger.warning(message)

    def error(self, message: str, exception: Optional[Exception] = None):
        """Log error message"""
        self.py_logger.error(message)
        if exception:
            self.py_logger.error(f"Exception: {str(exception)}")
        self.errors.append({
            "timestamp": datetime.now().isoformat(),
            "message": message,
            "exception": str(exception) if exception else None
        })

    def log_step(self, step_name: str, status: str, details: Optional[Dict[str, Any]] = None):
        """Log a pipeline step completion"""
        step_record = {
            "timestamp": datetime.now().isoformat(),
            "step": step_name,
            "status": status,
            "details": details or {}
        }
        self.steps.append(step_record)

        detail_str = f" | {json.dumps(details)}" if details else ""
        self.info(f"[STEP] {step_name} - {status}{detail_str}")

    def log_data_check(self, check_name: str, result: Dict[str, Any]):
        """Log a data quality check"""
        check_record = {
            "timestamp": datetime.now().isoformat(),
            "check": check_name,
            "result": result
        }
        self.data_checks.append(check_record)

        status = "PASS" if result.get("passed", False) else "FAIL"
        self.debug(f"[DATA CHECK] {check_name} - {status} | {json.dumps(result)}")

    def log_dataframe(self, df: pd.DataFrame, name: str, max_rows: int = 10):
        """Log DataFrame structure and sample data"""
        self.debug(f"\n[DATAFRAME] {name}")
        self.debug(f"  Shape: {df.shape}")
        self.debug(f"  Columns: {list(df.columns)}")
        self.debug(f"  Dtypes:\n{df.dtypes}")
        self.debug(f"  First {max_rows} rows:\n{df.head(max_rows)}")

    def log_model_number_attachment(self, model_key: str, df_before: pd.DataFrame, df_after: pd.DataFrame):
        """Log model number attachment process"""
        check = {
            "model": model_key,
            "rows_before": len(df_before),
            "rows_after": len(df_after),
            "has_model_number_col": "model_number" in df_after.columns,
            "non_null_model_numbers": df_after["model_number"].notna().sum() if "model_number" in df_after.columns else 0,
            "sample_model_numbers": df_after["model_number"].dropna().head(5).tolist() if "model_number" in df_after.columns else [],
            "unique_model_numbers": df_after["model_number"].nunique() if "model_number" in df_after.columns else 0,
        }
        self.log_data_check(f"attach_model_number_with_matcher({model_key})", check)

        if "model_number" in df_after.columns:
            non_null = df_after["model_number"].notna().sum()
            total = len(df_after)
            pct = (non_null / total * 100) if total > 0 else 0
            self.info(f"Model numbers attached: {non_null}/{total} ({pct:.1f}%)")

    def log_vehicle_match(self, model_year: int, model_name: str, result: Dict[str, Any]):
        """Log a single vehicle match result"""
        check = {
            "model_year": model_year,
            "model_name": model_name,
            "matched": result.get("matched", False),
            "certainty": result.get("certainty", "UNMATCHED"),
            "match_score": result.get("match_score", 0.0),
            "model_number": result.get("model_number"),
        }
        self.debug(f"[VEHICLE MATCH] {model_name} ({model_year}): {check}")

    def log_output_file(self, file_path: str, sheet_name: str, df: pd.DataFrame):
        """Log output file details"""
        check = {
            "file": file_path,
            "sheet": sheet_name,
            "rows": len(df),
            "columns": list(df.columns),
            "has_model_col": "Model" in df.columns or "model" in df.columns,
            "has_model_name_col": "model_name" in df.columns,
        }

        # Check for model numbers in output
        if "Model" in df.columns:
            sample_values = df["Model"].head(10).tolist()
            check["sample_Model_values"] = sample_values
            check["non_null_Model"] = df["Model"].notna().sum()

        if "model" in df.columns:
            sample_values = df["model"].head(10).tolist()
            check["sample_model_values"] = sample_values
            check["non_null_model"] = df["model"].notna().sum()

        self.log_data_check(f"output_file({sheet_name})", check)

    def save_logs(self):
        """Save all logs to JSON files"""
        # Save steps
        with open(self.steps_file, 'w') as f:
            json.dump(self.steps, f, indent=2)

        # Save data checks
        with open(self.data_checks_file, 'w') as f:
            json.dump(self.data_checks, f, indent=2)

        # Save errors
        with open(self.errors_file, 'w') as f:
            json.dump(self.errors, f, indent=2)

        self.info(f"Logs saved to {self.run_dir}")

    def print_summary(self):
        """Print execution summary"""
        self.info("\n" + "="*100)
        self.info("EXECUTION SUMMARY")
        self.info("="*100)
        self.info(f"Run timestamp: {self.run_timestamp}")
        self.info(f"Total steps logged: {len(self.steps)}")
        self.info(f"Data checks performed: {len(self.data_checks)}")
        self.info(f"Errors encountered: {len(self.errors)}")

        if self.errors:
            self.info("\nErrors:")
            for err in self.errors:
                self.info(f"  - {err['message']}")

        self.info("="*100 + "\n")


# Global logger instance
_logger = None


def get_logger() -> PipelineLogger:
    """Get or create the global logger instance"""
    global _logger
    if _logger is None:
        _logger = PipelineLogger()
    return _logger


def log_step(step_name: str, status: str, details: Optional[Dict[str, Any]] = None):
    """Convenience function to log a step"""
    get_logger().log_step(step_name, status, details)


def log_dataframe(df: pd.DataFrame, name: str):
    """Convenience function to log a dataframe"""
    get_logger().log_dataframe(df, name)
