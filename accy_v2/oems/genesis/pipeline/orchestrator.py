from typing import Any, Dict, List
from pathlib import Path

import pandas as pd

from core.base_pipeline import BasePipeline
from core.config_loader_v2 import ModularConfigLoader, get_output_paths
from core.helpers.dq_logger import DQLogger
from core.helpers.header_helpers import clean_column_name, promote_header_row
from core.helpers.output_writer import write_combined_output
from core.helpers.pipeline_logger import PipelineLogger

from oems.hyundai_genesis.pipeline import (
    step1_validation,
    step2_header_normalization,
    step3_standardization,
    step3_5_extract_vehicle_year,
    step4_transformation,
    step4_5_model_enrichment,
    step5_output,
)


class GenesisPipeline(BasePipeline):
    """
    Genesis OEM pipeline.

    Reads Genesis sheet from source workbook (sheet name configured in pipeline.yaml).
    Groups rows by (year, model) before feeding to the step pipeline.
    Each group is header-promoted before grouping since groupby() requires clean column names.

    Manufacturer is fixed as "Genesis" for all rows (no per-row routing).
    """

    OEM_NAME = "genesis"
    BRAND_NAME = "Genesis"

    def _resolve_sheet(self, excel: pd.ExcelFile, wanted: str) -> str:
        """Resolve sheet name case-insensitively, raise clear error if not found."""
        match = next(
            (s for s in excel.sheet_names if s.strip().lower() == wanted.strip().lower()),
            None
        )
        if match is None:
            raise ValueError(
                f"Required sheet '{wanted}' not found in workbook. Found sheets: {excel.sheet_names}."
            )
        return match

    def load_file(self, file_path: str) -> Dict[str, pd.DataFrame]:
        """
        Load Genesis sheet and group rows by (year, model).

        Returns {f"{year}_{model_slug}": group_df} where each group_df is
        header-promoted and ready for step1.

        Genesis's load_file() pre-promotes headers because groupby() needs
        clean column names.

        Step1 is responsible for setting group_key, year_from, model_name, manufacturer
        in meta_data based on the sheet_name (which becomes the group key here).
        """
        excel = pd.ExcelFile(file_path)
        config_root = Path(__file__).parent.parent / "config"
        loader = ModularConfigLoader(self.OEM_NAME, config_root)
        pipeline_config = loader.load_pipeline_config()

        # Resolve sheet name from config with validation
        sheet_name = self._resolve_sheet(excel, pipeline_config.get("source_sheet", "Genesis"))

        # Read the resolved sheet
        raw = excel.parse(sheet_name=sheet_name, header=None)

        # Promote header: row 0 = banner, row 1 becomes header
        working = promote_header_row(raw)

        # Sanitize column names (lowercase, spaces→underscores, etc.)
        working.columns = [clean_column_name(str(c)) for c in working.columns]

        # Find the actual year and model columns
        col_lower = {c.lower(): c for c in working.columns}
        year_col = next((c for c in col_lower.keys() if "year" in c and "from" in c), None)
        model_col = next((c for c in col_lower.keys() if c == "model"), None)

        if not year_col or not model_col:
            raise ValueError(
                f"Required columns not found. Looking for 'year_from' and 'model'. "
                f"Found columns: {working.columns.tolist()}"
            )

        year_col = col_lower[year_col]
        model_col = col_lower[model_col]

        # Group by (year, model) using actual column names
        groups = {}
        for (year, model), group_df in working.groupby([year_col, model_col]):
            model_slug = str(model).strip().replace(" ", "_").lower()
            key = f"{int(year)}_{model_slug}"

            # Add metadata columns to dataframe so step1 can extract them
            # Store as special columns that step1 will read and put into meta_data
            group_df = group_df.copy()
            group_df["__group_key__"] = key
            group_df["__year_from__"] = int(year)
            group_df["__model_name__"] = model_slug
            group_df["__manufacturer__"] = self.BRAND_NAME

            groups[key] = group_df.reset_index(drop=True)

        return groups

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
        return step4_transformation.run(
            standardized_df, step2_result, config, meta_data, dq_logger, pipeline_logger
        )

    def run_step4_5_model_enrichment(
        self,
        transformed: Dict[str, pd.DataFrame],
        meta_data: Dict,
        config: Dict,
        dq_logger: DQLogger,
        pipeline_logger: PipelineLogger,
        ads_attempted: set = None,
    ) -> Dict[str, pd.DataFrame]:
        return step4_5_model_enrichment.run(transformed, meta_data, config, dq_logger, pipeline_logger, ads_attempted)

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
        write_combined_output(all_frames, run_stats, dq_logger, config, run_id, pipeline_logger, profile_col="Trim")
