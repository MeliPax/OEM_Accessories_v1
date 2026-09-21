from typing import Any, Dict, List

import pandas as pd

from core.base_pipeline import BasePipeline
from core.helpers.dq_logger import DQLogger
from core.helpers.output_writer import write_combined_output
from core.helpers.pipeline_logger import PipelineLogger

from oems.mazda.pipeline import (
    step1_validation,
    step2_header_normalization,
    step3_standardization,
    step3_5_extract_vehicle_year,
    step4_transformation,
    step4_5_model_enrichment,
    step5_output,
)


class MazdaPipeline(BasePipeline):
    """
    Mazda OEM pipeline.
    Processes flat CSV files grouped by CarLineCode (model).
    Each step delegates to its module.
    """

    OEM_NAME = "mazda"

    def load_file(self, file_path: str) -> Dict[str, pd.DataFrame]:
        """Load CSV or Excel file, group by CarLineCode, and return {model: raw_df} for each model."""
        file_lower = file_path.lower()

        if file_lower.endswith('.xlsx') or file_lower.endswith('.xls'):
            df = pd.read_excel(file_path)
        elif file_lower.endswith('.csv'):
            # Try UTF-8 first, fall back to Windows-1252 if that fails
            try:
                df = pd.read_csv(file_path, encoding='utf-8')
            except UnicodeDecodeError:
                df = pd.read_csv(file_path, encoding='windows-1252')
        else:
            raise ValueError(f"Unsupported file format: {file_path}. Expected .csv, .xlsx, or .xls")

        return {model: group.reset_index(drop=True) for model, group in df.groupby("CarLineCode")}

    def run_step1_validation(
        self,
        df: pd.DataFrame,
        config: Dict,
        meta_data: Dict,
        dq_logger: DQLogger,
        pipeline_logger: PipelineLogger,
    ) -> pd.DataFrame:
        return step1_validation.run(df, config, meta_data, dq_logger, pipeline_logger)

    def run_step2_header_normalization(
        self,
        working_df: pd.DataFrame,
        config: Dict,
        meta_data: Dict,
        dq_logger: DQLogger,
        pipeline_logger: PipelineLogger,
    ) -> Dict[str, Any]:
        return step2_header_normalization.run(working_df, config, meta_data, dq_logger, pipeline_logger)

    def run_step3_standardization(
        self,
        working_df: pd.DataFrame,
        step2_result: Dict,
        config: Dict,
        meta_data: Dict,
        dq_logger: DQLogger,
        pipeline_logger: PipelineLogger,
    ) -> pd.DataFrame:
        return step3_standardization.run(working_df, step2_result, config, meta_data, dq_logger, pipeline_logger)

    def run_step3_5_extract_vehicle_year(
        self,
        standardized_df: pd.DataFrame,
        meta_data: Dict,
        config: Dict,
        pipeline_logger: PipelineLogger,
    ) -> pd.DataFrame:
        return step3_5_extract_vehicle_year.run(standardized_df, meta_data, config, pipeline_logger)

    def run_step4_transformation(
        self,
        standardized_df: pd.DataFrame,
        step2_result: Dict,
        config: Dict,
        meta_data: Dict,
        dq_logger: DQLogger,
        pipeline_logger: PipelineLogger,
    ) -> Dict[str, pd.DataFrame]:
        return step4_transformation.run(standardized_df, step2_result, config, meta_data, dq_logger, pipeline_logger)

    def run_step4_5_model_enrichment(
        self,
        transformed: Dict[str, pd.DataFrame],
        meta_data: Dict,
        config: Dict,
        dq_logger: DQLogger,
        pipeline_logger: PipelineLogger,
    ) -> Dict[str, pd.DataFrame]:
        return step4_5_model_enrichment.run(transformed, meta_data, config, dq_logger, pipeline_logger)

    def run_step5_output(
        self,
        transformed: Dict[str, pd.DataFrame],
        meta_data: Dict,
        config: Dict,
        pipeline_logger: PipelineLogger,
    ) -> Dict[str, pd.DataFrame]:
        return step5_output.prepare_frames(transformed, meta_data, config)

    def run_write_combined_output(
        self,
        all_frames: Dict[str, pd.DataFrame],
        run_stats: List[Dict],
        dq_logger: DQLogger,
        run_id: str,
        config: Dict,
        pipeline_logger: PipelineLogger,
    ) -> None:
        write_combined_output(all_frames, run_stats, dq_logger, config, run_id, pipeline_logger, profile_col="Package")
