"""Honda Pipeline Orchestrator

Modular pipeline for processing Honda accessory Excel files with section-based processing,
EN/FR reconciliation, and packages/kits rollup.

Inherits from BasePipeline to integrate with accy_v2's standardized pipeline architecture.
Supports batch processing (all files) or single file mode via run_pipeline.py.

Architecture:
  - Layer 1: Data Ingestion (Step 1: Validation & metadata extraction)
  - Layer 2: Data Transformation (Steps 2-4: normalization, standardization, transformation)
  - Layer 3: Model Lookup (Step 4.5: VehicleSearchEngine integration)
  - Layer 4: Output Filtering (Step 5: Excel generation + DQ reports)
  - Layer 5: Support Systems (Config, translators, loggers)

Key Features:
  - Section-based processing (6 sections per file)
  - EN/FR reconciliation with composite part number normalization
  - Packages/Kits rollup (parent-child aggregation)
  - Batch processing (multi-file directory orchestration)
  - Config-driven (YAML) settings
"""

from typing import Dict, Any, Set, List, Tuple
from pathlib import Path
import re

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
    step2_header_normalization,
    step3_standardization,
    step3_5_extract_vehicle_year,
    step4_transformation,
    step4_5_model_enrichment,
    step5_output,
)


class HondaPipeline(BasePipeline):
    """Honda Accessory Pipeline Orchestrator

    Processes Honda Excel files from landing_zone/ and produces standardized outputs
    with model enrichment, data quality reporting, and audit trails.

    Follows the same pattern as Mitsubishi/Mazda/Hyundai pipelines.
    Integrates sections 1-6 of Honda data processing.
    """

    OEM_NAME = "honda"

    def run(self, file_path: str, config_root: str) -> Dict[str, Any]:
        """Override run() to store file path for metadata extraction in Step 1."""
        self._current_file_path = file_path
        return super().run(file_path, config_root)

    def load_file(self, file_path: str) -> Dict[str, pd.DataFrame]:
        """Load Excel file and return {sheet_name: raw_df} for each sheet.

        Honda files have complex header structures with metadata rows before actual headers.
        Only process LoadFile sheets (flat EN/FR data) and Master sheets (wide format).
        Skip Template, SELL, and other non-data sheets.

        Args:
            file_path: Path to Honda Excel file

        Returns:
            Dictionary mapping sheet names to raw DataFrames (with row=0 as first data row)
        """
        excel = pd.ExcelFile(file_path)
        dfs = {}
        for name in excel.sheet_names:
            name_upper = name.upper()

            # EN data sheets to include:
            # New format: _DATA (flat), _APP_EN (applicability)
            # Legacy format: LoadFile sheets (flat), Master sheets (wide)
            include = (
                "_DATA" in name_upper or
                "_APP_EN" in name_upper or
                ("loadfile" in name_upper and "master" not in name_upper)
            )

            # Exclude FR, SELL, SELECT PROVINCE, and other non-data sheets
            exclude = (
                "_APP_FR" in name_upper or
                "SELL" in name_upper or
                "SELECT" in name_upper or
                "PROVINCE" in name_upper or
                "TEMPLATE" in name_upper
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

        Honda files have complex multi-level headers with metadata rows.
        This step extracts model name, year, identifies sections, and finds trim columns.
        """
        sheet_name = meta_data.get("sheet_name", "unknown")

        try:
            # Extract metadata from filename
            if hasattr(self, "_current_file_path"):
                file_path = Path(self._current_file_path)

                # Extract year from filename pattern
                year_match = re.search(r'(\d{4})', file_path.parent.name)
                if year_match:
                    try:
                        year = int(year_match.group(1))
                        if 2000 <= year <= 2050:
                            meta_data["vehicle_year"] = year
                    except ValueError:
                        pass

                # Extract model from filename
                filename_no_ext = file_path.stem
                model_parts = filename_no_ext.split()
                if model_parts:
                    meta_data["model_name"] = model_parts[0].capitalize()

            # Extract metadata from sheet rows
            if len(df) > 3:
                for idx in range(min(5, len(df))):
                    row = df.iloc[idx]
                    row_str = " ".join(str(v) for v in row.values if pd.notna(v)).lower()

                    if "model name" in row_str and len(row) > 2:
                        for col_idx in range(1, len(row)):
                            val = row.iloc[col_idx]
                            if pd.notna(val) and isinstance(val, str) and len(val) > 0 and "nan" not in str(val).lower():
                                meta_data["model_name"] = str(val).strip()
                                break
                    elif "model year" in row_str and len(row) > 2:
                        for col_idx in range(1, len(row)):
                            val = row.iloc[col_idx]
                            if pd.notna(val):
                                try:
                                    year_val = int(val)
                                    if 2000 <= year_val <= 2050:
                                        meta_data["vehicle_year"] = year_val
                                except (ValueError, TypeError):
                                    pass
                                break

            # Identify the actual header row
            header_row_idx = None
            if "DATA" in sheet_name.upper() and len(df) > 6:
                header_row_idx = 6  # Row 6 has headers for DATA sheet
            elif "APP" in sheet_name.upper():
                for idx in range(8, min(15, len(df))):
                    row = df.iloc[idx]
                    non_null_count = sum(1 for v in row if pd.notna(v))
                    if non_null_count > 3:
                        header_row_idx = idx
                        break

            meta_data["header_row_index"] = header_row_idx

            # For APP sheets: detect sections and trim columns
            if "APP" in sheet_name.upper():
                section_structure = step1_validation.identify_section_boundaries(df)
                if section_structure:
                    meta_data["section_structure"] = section_structure
                    trim_columns_per_section = step1_validation.extract_trim_columns(df, section_structure)
                    meta_data["trim_columns_per_section"] = trim_columns_per_section
                    pipeline_logger.info(f"Step 1: {len(section_structure)} sections detected")

            pipeline_logger.info(f"Step 1: Metadata extracted - {meta_data.get('model_name')} {meta_data.get('vehicle_year')}")

        except Exception as e:
            pipeline_logger.debug(f"Step 1 detail: {e}")
            import traceback
            pipeline_logger.debug(traceback.format_exc())

        return df

    def run_step2_header_normalization(
        self,
        working_df: pd.DataFrame,
        config: Dict,
        meta_data: Dict,
        dq_logger: DQLogger,
        pipeline_logger: PipelineLogger,
    ) -> Dict[str, Any]:
        """Step 2: Header normalization.

        Extracts proper column names from the identified header row and applies them.
        Drops all metadata rows that come before the actual data.
        """
        try:
            from accy_v2.oems.honda.pipeline.step2_header_normalization import normalize_headers

            normalized_df, meta_updated = normalize_headers(working_df, meta_data, config)
            meta_data.update(meta_updated)

            pipeline_logger.info(f"Step 2: Headers normalized - {len(normalized_df.columns)} columns, {len(normalized_df)} rows")
            pipeline_logger.debug(f"Step 2: Column names: {normalized_df.columns.tolist()[:10]}")

            return {"normalized_df": normalized_df, "sections": {}}
        except Exception as e:
            pipeline_logger.warning(f"Step 2 failed: {e}")
            return {"normalized_df": working_df, "sections": {}}

    def run_step3_standardization(
        self,
        working_df: pd.DataFrame,
        step2_result: Dict,
        config: Dict,
        meta_data: Dict,
        dq_logger: DQLogger,
        pipeline_logger: PipelineLogger,
    ) -> pd.DataFrame:
        """Step 3: Data standardization.

        Cleans data types, strips whitespace, converts numeric columns.
        Prepares data for transformation in Step 4.
        """
        try:
            from accy_v2.oems.honda.pipeline.step3_standardization import standardize

            standardized_df, meta_updated, warnings = standardize(working_df, meta_data, config)
            meta_data.update(meta_updated)

            for warning in warnings:
                dq_logger.log_warning(
                    sheet_name=meta_data.get("sheet_name", ""),
                    model_name=meta_data.get("model_name", ""),
                    record_index=0,
                    record_snapshot={},
                    rule_violated=warning.get("rule", "standardization_rule"),
                    issue_description=warning.get("message", ""),
                )

            pipeline_logger.info(f"Step 3: Data standardized - {len(standardized_df)} rows, {len(standardized_df.columns)} columns")

            return standardized_df
        except Exception as e:
            pipeline_logger.warning(f"Step 3 failed: {e}")
            return working_df

    def run_step3_5_extract_vehicle_year(
        self,
        standardized_df: pd.DataFrame,
        meta_data: Dict,
        config: Dict,
        pipeline_logger: PipelineLogger,
    ) -> pd.DataFrame:
        """Step 3.5: Extract and validate vehicle year from metadata.

        Converts year string to int, validates against configured range.
        ✅ IMPLEMENTED
        """
        try:
            meta_data = step3_5_extract_vehicle_year.extract_vehicle_year(meta_data, config)
            pipeline_logger.info(f"Step 3.5: Vehicle year extracted: {meta_data.get('vehicle_year')}")
        except Exception as e:
            pipeline_logger.warning(f"Step 3.5 failed: {e}")
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
        """Step 4: Long-format transformation.

        Melts trim columns from wide to long format and creates trim_level column.
        """
        try:
            from accy_v2.oems.honda.pipeline.step4_transformation import transform

            transformed_dict, meta_updated, warnings = transform(standardized_df, meta_data, config)
            meta_data.update(meta_updated)

            for warning in warnings:
                dq_logger.log_warning(
                    sheet_name=meta_data.get("sheet_name", ""),
                    model_name=meta_data.get("model_name", ""),
                    record_index=0,
                    record_snapshot={},
                    rule_violated=warning.get("rule", "transformation_rule"),
                    issue_description=warning.get("message", ""),
                )

            en_df = transformed_dict.get("EN", pd.DataFrame())
            pipeline_logger.info(f"Step 4: Transformation complete - {len(en_df)} rows after melting")

            return transformed_dict
        except Exception as e:
            pipeline_logger.warning(f"Step 4 failed: {e}")
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
        """Step 4.5: Model enrichment via VehicleSearchEngine.

        Tokenizes and normalizes trims, performs batch model lookup,
        scores matches, adds model_number and model_status columns.
        ✅ IMPLEMENTED
        """
        try:
            enriched, meta_updated, warnings = step4_5_model_enrichment.enrich_with_model_numbers(
                transformed, {}, meta_data, config
            )
            meta_data.update(meta_updated)
            for warning in warnings:
                dq_logger.log_warning(
                    sheet_name=meta_data.get("sheet_name", ""),
                    model_name=meta_data.get("model_name", ""),
                    record_index=0,
                    record_snapshot={},
                    rule_violated=warning.get("rule_type", "model_enrichment_warning"),
                    issue_description=warning.get("message", ""),
                )
            pipeline_logger.info(f"Step 4.5: Model enrichment complete")
            return enriched
        except Exception as e:
            pipeline_logger.warning(f"Step 4.5 failed: {e}")
            return transformed

    def run_step5_output(
        self,
        transformed: Dict[str, pd.DataFrame],
        meta_data: Dict,
        config: Dict,
        pipeline_logger: PipelineLogger,
    ) -> Dict[str, pd.DataFrame]:
        """Step 5: Output generation with flat data sheets for batch traceability.

        Saves melted standardized data (flat format) with source_file column for batch processing.
        ✅ IMPLEMENTED
        """
        try:
            from pathlib import Path

            # Extract filename from source_file path for batch mode traceability
            source_file_path = meta_data.get("source_file", "")
            file_name = Path(source_file_path).name if source_file_path else "unknown"

            frames = {}
            for lang in ["EN", "FR"]:
                df = transformed.get(lang)
                if df is not None and not df.empty:
                    df_output = df.copy()
                    # Add source_file column at the beginning for batch traceability
                    df_output.insert(0, "source_file", file_name)
                    # Use Accessories_EN/FR names for flat data sheets
                    frames[f"Accessories_{lang}"] = df_output

            pipeline_logger.info(f"Step 5: Output frames prepared (flat data with source_file tracking for batch mode)")
            return frames
        except Exception as e:
            pipeline_logger.warning(f"Step 5 failed: {e}")
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
        """Write combined output using standard output writer."""
        write_combined_output(
            all_frames, run_stats, dq_logger, config, run_id,
            pipeline_logger, profile_col="Trim"
        )

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML files (stub for Phase 3+)."""
        # Phase 3+: Load 6-file YAML structure
        # - pipeline.yaml
        # - section_patterns.yaml
        # - reconciliation.yaml
        # - trim_config.yaml
        # - Plus schema files from ModularConfigLoader
        pass

    def _scan_input_files(self) -> list:
        """Scan input directory for Excel files (stub for Phase 3+)."""
        # Phase 3+: Scan input_dir for *.xlsx files
        # Return list of file paths
        pass

    def _process_file(self, filepath: Path) -> Tuple[bool, Dict[str, Any]]:
        """Process single Honda Excel file through 7-step pipeline (stub for Phase 3+).

        Args:
            filepath: Path to Excel file

        Returns:
            Tuple of (success, metrics)
        """
        # Phase 3+: Implement 7-step pipeline
        # 1. Load & validate
        # 2. Normalize headers (section-aware)
        # 3. Standardize & rollup
        # 4. Transform EN/FR + reconciliation
        # 5. Model lookup enrichment
        # 6. Output generation
        # 7. DQ reporting
        pass

    def _aggregate_results(self) -> Dict[str, Any]:
        """Aggregate batch results and metrics (stub for Phase 3+)."""
        # Phase 3+: Aggregate across all files
        # Write batch_summary_dq.json
        pass


if __name__ == "__main__":
    pipeline = HondaPipeline()
    results = pipeline.run()
    print(results)
