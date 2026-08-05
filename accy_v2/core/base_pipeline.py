from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from core.config_loader_v2 import ModularConfigLoader, get_output_paths
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
        dq_logger: DQLogger,
        pipeline_logger: PipelineLogger,
    ) -> pd.DataFrame:
        """Apply column mapping, enforce data types, standardize trim values."""
        ...

    @abstractmethod
    def run_step3_5_extract_vehicle_year(
        self,
        standardized_df: pd.DataFrame,
        meta_data: Dict,
        config: Dict,
        pipeline_logger: PipelineLogger,
    ) -> pd.DataFrame:
        """Extract vehicle_year from sheet_name and store in meta_data.
        Uses valid_year_range from config for validation.
        Returns: standardized_df (unchanged)."""
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
    def run_step4_5_model_enrichment(
        self,
        transformed: Dict[str, pd.DataFrame],
        meta_data: Dict,
        config: Dict,
        dq_logger: DQLogger,
        pipeline_logger: PipelineLogger,
        ads_attempted: set = None,
    ) -> Dict[str, pd.DataFrame]:
        """Enrich with model numbers via lookup and validate.
        Returns: {language: enriched_DataFrame} with model_number and vehicle_year columns.

        Args:
            ads_attempted: Run-scoped set of (make, model_name, year) tuples already checked in ADS,
                          to avoid redundant per-trim ADS calls for the same model/year.
        """
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

    def run(self, file_path: str, config_root: str) -> None:
        """
        Execute the pipeline with modular config structure.

        DECISION [015/020]: Use ModularConfigLoader for config loading.

        Args:
            file_path: Path to input file
            config_root: Path to config directory (accy_v2/oems/{oem}/config/)
        """
        # Load modular config (DECISION [015]: Modular 5-file structure)
        loader = ModularConfigLoader(self.OEM_NAME, Path(config_root))
        pipeline_config = loader.load_pipeline_config()
        enrichment_config = loader.load_enrichment()
        transformations_config = loader.load_transformations()
        upstream_schema = loader.load_upstream_schema()
        intermediate_schema = loader.load_intermediate_schema()

        # Build config dict with backward compatibility for existing step methods
        # Maps modular structure back to legacy structure to minimize code changes
        config = self._build_legacy_config(
            pipeline_config, enrichment_config, transformations_config, upstream_schema, intermediate_schema
        )

        # Derive output paths from OEM name (DECISION [018])
        output_paths = get_output_paths(self.OEM_NAME)
        config["output"] = {
            "ready_to_upload_path": str(output_paths["ready_to_upload"]),
            "dq_report_path": str(output_paths["dq_reports"]),
            "pipeline_log_path": str(output_paths["pipeline_logs"]),
        }

        run_id = uuid.uuid4().hex[:8]

        dq_logger = DQLogger(run_id=run_id, source_file=file_path)
        pipeline_logger = PipelineLogger(
            run_id=run_id,
            log_path=config["output"]["pipeline_log_path"],
        )

        # Run-scoped cache: track ADS lookups already attempted in this run to avoid redundant calls
        # Key: (make, model_name, year) tuples (once per model/year, not per-trim)
        ads_attempted = set()

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
                standardized_df = self.run_step3_standardization(working_df, step2_result, config, meta_data, dq_logger, pipeline_logger)
                standardized_df = self.run_step3_5_extract_vehicle_year(standardized_df, meta_data, config, pipeline_logger)
                
                transformed = self.run_step4_transformation(standardized_df, step2_result, config, meta_data, dq_logger, pipeline_logger)

                if config.get("use_model_lookup", True):
                    pipeline_logger.info(f"Step 4.5: model_lookup enrichment | sheet='{sheet_name}'")
                    enriched = self.run_step4_5_model_enrichment(transformed, meta_data, config, dq_logger, pipeline_logger, ads_attempted)
                else:
                    pipeline_logger.info(f"Step 4.5: SKIPPED (use_model_lookup=false) | sheet='{sheet_name}'")
                    enriched = transformed

                sheet_frames = self.run_step5_output(enriched, meta_data, config, pipeline_logger)

                # Merge frames: if a sheet key exists from prior groups (e.g., different years of same model),
                # concatenate instead of overwriting. This allows consolidating multi-year data into single sheets.
                for key, df in sheet_frames.items():
                    if key in all_output_frames:
                        all_output_frames[key] = pd.concat([all_output_frames[key], df], ignore_index=True)
                    else:
                        all_output_frames[key] = df

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
                dq_logger.log_warning(
                    sheet_name=sheet_name,
                    model_name=meta_data.get("model_name", "unknown"),
                    record_index=-1,
                    record_snapshot={},
                    rule_violated="structural_validation_failure",
                    issue_description=f"Sheet structural validation failed and was skipped: {str(exc)}",
                )
                sheets_skipped += 1

        self.run_write_combined_output(all_output_frames, model_run_stats, dq_logger, run_id, config, pipeline_logger)
        dq_logger.write_dq_report(config["output"]["dq_report_path"])
        pipeline_logger.log_run_complete(sheets_processed, sheets_skipped)

    @staticmethod
    def _build_legacy_config(
        pipeline_config: Dict, enrichment_config: Dict, transformations_config: Dict,
        upstream_schema: Dict, intermediate_schema: Dict = None
    ) -> Dict:
        """
        Build config dict with backward compatibility for existing step methods.

        Maps modular 5-file structure back to legacy flat structure.
        This allows gradual migration: steps don't change immediately.

        DECISION [015]: Modular config → Legacy config mapping.
        """
        if intermediate_schema is None:
            intermediate_schema = {}
        # Map upstream schema columns to legacy column_definition format
        column_definition = {}
        for col_name, col_def in upstream_schema.get("columns", {}).items():
            column_definition[col_name] = {
                "key_words": col_def.get("detect_by_keyword", {}),
                "data_type": col_def.get("expected_data_type"),
                "required": col_def.get("required", False),
            }

        # Extract lists for backward compatibility
        required_columns = [
            name
            for name, col_def in upstream_schema.get("columns", {}).items()
            if col_def.get("required", False)
        ]
        non_null_columns = required_columns.copy()

        # Build col_data_type_dict from transformations: identify which columns need float conversion
        col_data_type_dict = {"to_float": [], "to_string": []}
        for canonical_col, col_transforms in transformations_config.get("columns", {}).items():
            operations = col_transforms.get("operations", [])
            has_float_op = any(op.get("name") == "convert_to_float" for op in operations)
            if has_float_op:
                col_data_type_dict["to_float"].append(canonical_col)
            else:
                col_data_type_dict["to_string"].append(canonical_col)

        # Extract language-specific columns for step4_transformation._split_by_language()
        language_columns = intermediate_schema.get("language_specific_columns", {})

        # Extract trim column pattern from sheet_validation.trim_table
        trim_column_pattern = (
            upstream_schema.get("sheet_validation", {})
            .get("trim_table", {})
            .get("column_pattern")
        )

        # Build legacy config structure
        return {
            "column_definition": column_definition,
            "required_columns": required_columns,
            "non_null_columns": non_null_columns,
            "non_null_threshold": pipeline_config.get("non_null_threshold", 0.5),
            "use_model_lookup": pipeline_config.get("use_model_lookup", True),
            "trim_column_patterns": trim_column_pattern,
            "model_lookup_rules": enrichment_config.get("model_lookup", {}).get("brands", {}),
            "col_data_type_dict": col_data_type_dict,
            "language_columns": language_columns,
            "output": {},  # Will be filled by run() with derived paths
        }
