"""Honda Pipeline Steps

Modular step implementations for the Honda accessory pipeline.

Imports:
  - step1_validation: Data loading and section-based validation
  - (Future) step2_header_normalization: Header extraction and column mapping
  - (Future) step3_standardization: Data cleaning and standardization
  - (Future) step4_transformation: Melt to long format
  - (Future) step4_5_model_enrichment: Model number lookup
  - (Future) step5_output: Output generation and DQ reporting
"""

from accy_v2.oems.honda.pipeline import step1_validation

__all__ = ["step1_validation"]
