"""Honda Pipeline Orchestrator

Modular pipeline for processing Honda accessory Excel files with section-based processing,
EN/FR reconciliation, and model enrichment.

Inherits from BasePipeline to integrate with accy_v2's standardized pipeline architecture.
Follows the same pattern as Mitsubishi/Mazda/Hyundai/Genesis pipelines.

Architecture:
  - Layer 1: Data Ingestion (Step 1: Validation & metadata extraction)
  - Layer 2: Data Transformation (Steps 2-4: header norm, standardization, transformation)
  - Layer 3: Model Lookup (Step 4.5: VehicleSearchEngine integration)
  - Layer 4: Output Filtering (Step 5: Excel generation + DQ reports)
  - Layer 5: Support Systems (Config, translators, loggers)

Key Features:
  - Section-based processing (6 sections per file)
  - EN/FR processing with independent validation
  - Batch processing (multi-file directory orchestration)
  - Config-driven (YAML) settings
"""

from typing import Dict, Any, List, Set
from pathlib import Path

import pandas as pd

# Import BasePipeline for inheritance
try:
    from accy_v2.core.base_pipeline import BasePipeline
except ImportError:
    # Fallback if absolute imports fail
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
    from accy_v2.core.base_pipeline import BasePipeline

from accy_v2.core.helpers.dq_logger import DQLogger
from accy_v2.core.helpers.output_writer import write_combined_output
from accy_v2.core.helpers.pipeline_logger import PipelineLogger

# Import Honda-specific step modules
from accy_v2.oems.honda.pipeline import (
    step1_validation,
)


class HondaPipeline(BasePipeline):
    """Honda Accessory Pipeline Orchestrator

    Processes Honda Excel files from landing_zone/ and produces standardized outputs
    with model enrichment, data quality reporting, and audit trails.

    Follows the same pattern as Mitsubishi/Mazda/Hyundai/Genesis pipelines.
    Integrates sections 1-5 of Honda data processing.
    """

    OEM_NAME = "honda"

    def run(self, file_path: str, config_root: str) -> Dict[str, Any]:
        """Override run() to store file path for metadata extraction in Step 1."""
        self._current_file_path = file_path
        return super().run(file_path, config_root)

    def load_file(self, file_path: str) -> Dict[str, pd.DataFrame]:
        """Load Excel file and return {sheet_name: raw_df} for each sheet.

        Honda files have complex header structures with metadata rows before actual headers.
        Only process _APP_EN and _APP_FR sheets (product data).
        Skip _DATA (metadata only), SELL (summary), SELECT PROVINCE, and other non-data sheets.

        Args:
            file_path: Path to Honda Excel file

        Returns:
            Dictionary mapping sheet names to raw DataFrames (with header=None, all rows as data)
        """
        excel = pd.ExcelFile(file_path)
        dfs = {}

        for name in excel.sheet_names:
            name_upper = name.upper()

            # Data sheets to include:
            # EN sheets: _APP_EN (section-based)
            # FR sheets: _APP_FR (section-based)
            include = "_APP_EN" in name_upper or "_APP_FR" in name_upper

            # Explicitly exclude all non-product sheets
            exclude = (
                "_DATA" in name_upper or  # Metadata only, not product data
                "SELL" in name_upper or  # Summary view
                "SELECT" in name_upper or  # Province selector
                "PROVINCE" in name_upper or  # Province names
                "TEMPLATE" in name_upper  # Template sheet
            )

            if include and not exclude:
                df = excel.parse(sheet_name=name, header=None)
                dfs[name] = df

        return dfs

    def run_step1_validation(
        self,
        df: pd.DataFrame,
        config: Dict,
        meta_data: Dict,
        dq_logger: DQLogger,
        pipeline_logger: PipelineLogger,
    ) -> pd.DataFrame:
        """Step 1: File validation and metadata extraction.

        Honda files have complex multi-level structure with metadata rows,
        section markers, and section-specific headers.
        This step validates structure, identifies sections, and extracts metadata.
        """
        try:
            # Store the sheet name in metadata for reference
            if "sheet_name" not in meta_data:
                meta_data["sheet_name"] = "unknown"

            # Call Step 1 validation
            working_df, meta_updated = step1_validation.run(df, config, meta_data, dq_logger, pipeline_logger)
            meta_data.update(meta_updated)

            pipeline_logger.info(
                f"Step 1: Validation complete - "
                f"{len(working_df)} rows, "
                f"{meta_data.get('sections_detected', 0)} sections detected"
            )

            return working_df

        except Exception as e:
            pipeline_logger.warning(f"Step 1 failed: {e}")
            import traceback
            pipeline_logger.debug(traceback.format_exc())
            raise

    def run_step2_header_normalization(
        self,
        working_df: pd.DataFrame,
        config: Dict,
        meta_data: Dict,
        dq_logger: DQLogger,
        pipeline_logger: PipelineLogger,
    ) -> Dict[str, Any]:
        """Step 2: Header normalization (stub for Phase 2)."""
        pipeline_logger.info("Step 2: Header normalization (not yet implemented)")
        return {}

    def run_step3_standardization(
        self,
        working_df: pd.DataFrame,
        step2_result: Dict,
        config: Dict,
        meta_data: Dict,
        dq_logger: DQLogger,
        pipeline_logger: PipelineLogger,
    ) -> pd.DataFrame:
        """Step 3: Data standardization (stub for Phase 2)."""
        pipeline_logger.info("Step 3: Data standardization (not yet implemented)")
        return working_df

    def run_step3_5_extract_vehicle_year(
        self,
        standardized_df: pd.DataFrame,
        meta_data: Dict,
        config: Dict,
        pipeline_logger: PipelineLogger,
    ) -> pd.DataFrame:
        """Step 3.5: Extract and validate vehicle year (stub for Phase 2)."""
        pipeline_logger.info("Step 3.5: Vehicle year extraction (not yet implemented)")
        return standardized_df

    def run_step4_transformation(
        self,
        standardized_df: pd.DataFrame,
        step2_result: Dict,
        config: Dict,
        meta_data: Dict,
        dq_logger: DQLogger,
        pipeline_logger: PipelineLogger,
    ) -> Dict[str, pd.DataFrame]:
        """Step 4: Long-format transformation (stub for Phase 2)."""
        pipeline_logger.info("Step 4: Transformation (not yet implemented)")
        return {"EN": standardized_df, "FR": standardized_df}

    def run_step4_5_model_enrichment(
        self,
        transformed: Dict[str, pd.DataFrame],
        meta_data: Dict,
        config: Dict,
        dq_logger: DQLogger,
        pipeline_logger: PipelineLogger,
        ads_attempted: Set = None,
    ) -> Dict[str, pd.DataFrame]:
        """Step 4.5: Model enrichment via VehicleSearchEngine (stub for Phase 2)."""
        pipeline_logger.info("Step 4.5: Model enrichment (not yet implemented)")
        return transformed

    def run_step5_output(
        self,
        transformed: Dict[str, pd.DataFrame],
        meta_data: Dict,
        config: Dict,
        pipeline_logger: PipelineLogger,
    ) -> Dict[str, pd.DataFrame]:
        """Step 5: Output generation (stub for Phase 2)."""
        pipeline_logger.info("Step 5: Output generation (not yet implemented)")
        return transformed

    def run_write_combined_output(
        self,
        all_frames: Dict[str, pd.DataFrame],
        run_stats: List[Dict],
        dq_logger: DQLogger,
        run_id: str,
        config: Dict,
        pipeline_logger: PipelineLogger,
    ) -> None:
        """Write combined output using standard output writer (stub for Phase 2)."""
        pipeline_logger.info("Write output (not yet implemented)")


if __name__ == "__main__":
    pipeline = HondaPipeline()
    print(f"Honda Pipeline: {pipeline.OEM_NAME}")
