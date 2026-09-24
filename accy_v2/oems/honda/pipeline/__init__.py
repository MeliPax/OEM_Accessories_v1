"""Honda Pipeline Steps

Modular processing steps for Honda accessory pipeline:
- Step 1: Validation & Metadata Extraction
- Step 2: Header Normalization (section-aware)
- Step 3: Standardization & Rollup Logic
- Step 3.5: Vehicle Year Extraction
- Step 4: Transformation & EN/FR Reconciliation
- Step 4.5: Model Lookup Enrichment
- Step 5: Output & DQ Reporting
"""

__all__ = [
    "step1_validation",
    "step2_header_normalization",
    "step3_standardization",
    "step3_5_extract_vehicle_year",
    "step4_transformation",
    "step4_5_model_enrichment",
    "step5_output",
]
