from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from typing import Any, Dict, List

import pandas as pd

from core.config_loader import load_config
from core.helpers.dq_logger import DQLogger
from core.helpers.pipeline_logger import PipelineLogger


class PipelineFatalError(Exception):
    """Raised within a step to signal a FATAL error — the sheet must be skipped."""


class BasePipeline(ABC):
    """
    Abstract base for all OEM pipelines.
    Defines the 5-step contract and owns the run() loop.

    Each OEM subclass implements the five abstract step methods.
    The run() method is shared and never overridden.
    """

    OEM_NAME: str = "base"

    @abstractmethod
    def load_file(self, file_path: str) -> Dict[str, pd.DataFrame]:
        """Load source file and return {identifier: raw_df} for each processing unit.
        For Excel: {sheet_name: raw_df}. For CSV: {model: raw_df} grouped by model."""
        ...

    @abstractmethod
    def run_step1_validation(
        self,
        df: pd.DataFrame,
        config: Dict,
        meta_data: Dict,
        dq_logger: DQLogger,
        pipeline_logger: PipelineLogger,
    ) -> pd.DataFrame:
        """Validate raw sheet structure. Populates meta_data in-place. Returns promoted working_df."""
        ...

    @abstractmethod
    def run_step2_header_normalization(
        self,
        working_df: pd.DataFrame,
        config: Dict,
        meta_data: Dict,
        dq_logger: DQLogger,
        pipeline_logger: PipelineLogger,
    ) -> Dict[str, Any]:
        """Map columns to standard names and identify valid trim columns.
        Returns: {col_mapping, valid_trim_cols, trim_validation_log}"""
        ...

    @abstractmethod
    def run_step3_standardization(
        self,
        working_df: pd.DataFrame,
        step2_result: Dict,
        config: Dict,
        meta_data: Dict,
        pipeline_logger: PipelineLogger,
    ) -> pd.DataFrame:
        """Apply column mapping, enforce data types, standardize trim values."""
        ...

    @abstractmethod
    def run_step4_transformation(
        self,
        standardized_df: pd.DataFrame,
        step2_result: Dict,
        config: Dict,
        meta_data: Dict,
        dq_logger: DQLogger,
        pipeline_logger: PipelineLogger,
    ) -> Dict[str, pd.DataFrame]:
        """Validate applicability, melt trim columns, return dict of output DataFrames."""
        ...

    @abstractmethod
    def run_step5_output(
        self,
        transformed: Dict[str, pd.DataFrame],
        meta_data: Dict,
        config: Dict,
        pipeline_logger: PipelineLogger,
    ) -> Dict[str, pd.DataFrame]:
        """Prepare output frames (enrich, rename, filter). Returns {sheet_key: df}. Does NOT write."""
        ...

    @abstractmethod
    def run_write_combined_output(
        self,
        all_frames: Dict[str, pd.DataFrame],
        run_stats: List[Dict],
        dq_logger: DQLogger,
        run_id: str,
        config: Dict,
        pipeline_logger: PipelineLogger,
    ) -> None:
        """Write all accumulated model frames + Report sheet to one Excel file."""
        ...

    def run(self, file_path: str, config_path: str) -> None:
        config = load_config(config_path)
        run_id = uuid.uuid4().hex[:8]

        dq_logger = DQLogger(run_id=run_id, source_file=file_path)
        pipeline_logger = PipelineLogger(
            run_id=run_id,
            log_path=config["output"]["pipeline_log_path"],
        )

        pipeline_logger.log_run_start(oem=self.OEM_NAME, file_path=file_path)

        sheets_processed = 0
        sheets_skipped = 0
        all_output_frames: Dict[str, pd.DataFrame] = {}
        model_run_stats: List[Dict] = []

        try:
            data_units = self.load_file(file_path)
        except Exception as exc:
            pipeline_logger.log_fatal("N/A", "file_load", str(exc))
            raise

        for sheet_name, df_raw in data_units.items():
            pipeline_logger.log_sheet_start(sheet_name)
            meta_data: Dict[str, Any] = {"sheet_name": sheet_name, "source_file": file_path}
            warnings_before = dq_logger.warning_count

            try:

                working_df = self.run_step1_validation(df_raw, config, meta_data, dq_logger, pipeline_logger)
                records_in = len(working_df)

                step2_result = self.run_step2_header_normalization(working_df, config, meta_data, dq_logger, pipeline_logger)
                standardized_df = self.run_step3_standardization(working_df, step2_result, config, meta_data, pipeline_logger)
                transformed = self.run_step4_transformation(standardized_df, step2_result, config, meta_data, dq_logger, pipeline_logger)
                sheet_frames = self.run_step5_output(transformed, meta_data, config, pipeline_logger)

                all_output_frames.update(sheet_frames)
                records_out = sum(len(df) for df in sheet_frames.values())

                model_run_stats.append({
                    "model_name": meta_data.get("model_name", "unknown"),
                    "sheet_name": sheet_name,
                    "records_in": records_in,
                    "records_out": records_out,
                    "dq_warnings": dq_logger.warning_count - warnings_before,
                    "source_file": file_path,
                })
                pipeline_logger.log_sheet_complete(sheet_name, records_in, records_out)
                sheets_processed += 1

            except PipelineFatalError as exc:
                pipeline_logger.log_fatal(sheet_name, step="pipeline", reason=str(exc))
                sheets_skipped += 1

        self.run_write_combined_output(all_output_frames, model_run_stats, dq_logger, run_id, config, pipeline_logger)
        dq_logger.write_dq_report(config["output"]["dq_report_path"])
        pipeline_logger.log_run_complete(sheets_processed, sheets_skipped)
