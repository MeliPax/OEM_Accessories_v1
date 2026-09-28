"""Honda OEM Pipeline Module

Implements the 5-step pipeline for processing Honda accessory data:
- Step 1: Data loading & validation (section-based)
- Step 2: Header normalization
- Step 3: Data standardization
- Step 4: Transformation to long format
- Step 4.5: Model enrichment via VehicleSearchEngine
- Step 5: Output generation

Architecture:
- Section-based processing (6 sections per sheet)
- EN/FR dual sheets processed independently
- Source tracking for batch processing
"""

__version__ = "0.1.0"
__all__ = ["HondaPipeline"]

from accy_v2.oems.honda.pipeline.orchestrator import HondaPipeline
