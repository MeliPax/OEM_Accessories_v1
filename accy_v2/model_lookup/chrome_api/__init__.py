"""
AutoData Solutions (ADS) API integration.

This module provides a clean, senior-level API client and service for consuming
the ADS Year/Make/Model/Trim vehicle taxonomy data and populating the
pipeline's db_vehicle_models.csv.

Exports:
  - refresh_from_ads(makes, years) — Main orchestrator to fetch and save ADS data
  - config module — Environment and credential management
  - client module — HTTP client with retry/backoff/timeout
  - mapper module — Transform ADS trim JSON to pipeline row schema
"""

__version__ = "0.1.0"
