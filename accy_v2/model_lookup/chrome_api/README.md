# AutoData Solutions (ADS) YMMT API Integration

Clean, production-grade API client and service for consuming AutoData Solutions vehicle taxonomy data and populating the pipeline's `db_vehicle_models.csv`.

## Folder Structure

```
chrome_api/
├── __init__.py              Package exports
├── config.py                Environment loading (base URL only for Phase 1)
├── client.py                HTTP client: User-Agent rotation + header spoofing (no auth for demo)
├── mapper.py                [PHASE 2] Transform ADS trim JSON to pipeline row schema
├── service.py               [PHASE 2] Orchestrator: years → makes → models → trims
├── refresh_db_ads.py        [PHASE 2] CLI entrypoint (like refresh_db.py but for ADS)
├── inspect_sample.py        [PHASE 1] Discovery script — fetch and inspect raw ADS responses
├── sample_responses/        [PHASE 1] Saved raw JSON samples (gitignored, dev reference only)
└── README.md                This file
```

## Phase 1: Discovery (Current)

### Setup

**Phase 1 uses header spoofing (no authentication required for demo endpoints)**

1. **Configure the ADS base URL in `accy_v2/model_lookup/creds/ads_api.env`:**

   ```
   # Just need the base URL for the demo
   ADS_BASE_URL=https://demos.autodatasolutions.com/ADSDemo
   ```
2. **Run the discovery script:**

   ```bash
   cd accy_v2/model_lookup
   python chrome_api/inspect_sample.py
   ```
3. **Review the output:**

   - Script will fetch 1 sample year/make/model combination
   - Uses rotating User-Agent + spoofed Origin/Referer headers (mimics real browser)
   - Pretty-prints the JSON structure to console
   - Saves full response to `chrome_api/sample_responses/` for reference
   - **You** then inspect and identify the ADS field mapping

### What You're Looking For

The script will show the real ADS response structure. Identify which fields correspond to:

- **OEM Model Number** (equivalent to our pipeline's `ModelNumber` — e.g., `ELCS4V2BES00`)
- **Trim/Configuration Name** (for the `Description` field)
- **Style/Body Type** (SUV, Sedan, etc.)
- **Any other relevant data** for the pipeline

## Phase 2: Implementation (Blocked on Phase 1)

Once Phase 1 identifies the field mapping:

1. **`mapper.py`** — Transform ADS trim response to pipeline 7-column schema

   - Maps ADS fields → `Manufacturer, ModelYear, ModelNumber, Description, Description2, Package, Style_ID`
   - Handles any data normalization needed
2. **`service.py`** — Orchestrate the full refresh

   - Years → Makes → Models → Trims
   - Batch collection into DataFrames
   - Call existing `save_vehicle_models_to_csv()` (no reimplementation needed)
3. **`refresh_db_ads.py`** — CLI entrypoint

   - Same shape as existing `refresh_db.py`
   - Archives current CSV to `db/archive/` before refresh
   - Calls `service.refresh_from_ads(makes, years)`

## Architecture Principles

### Reuse, Don't Reinvent

- ✅ Reuse existing `save_vehicle_models_to_csv()` for write/validation/dedup/standardization
- ✅ Reuse existing `{make}_translator.json` for description normalization
- ✅ Reuse existing `{make}_classification.json` and keywords rebuild
- ✅ Archive pattern already in `refresh_db.py`

### Robustness (even with spoofing)

- ✅ Retry/backoff via `urllib3.Retry` (handles transient failures)
- ✅ Explicit timeout on every HTTP request (no hangs)
- ✅ User-Agent rotation (mimics real browser traffic)
- ✅ Clean separation of concerns: config, client, mapper, service

### Parallel, Not Replacement

- The existing SQL-based `refresh_db.py` is **untouched**
- New `refresh_db_ads.py` is an **alternative** path
- Both write to the same `db/db_vehicle_models.csv` via the same safe-write function
- **ADS is the primary/default path going forward** (per your direction)

## Running Phase 1

1. Set `ADS_BASE_URL` in `ads_api.env`
2. Run: `python chrome_api/inspect_sample.py`
3. Review output and the saved JSON file
4. Tell the developer which ADS fields map to which pipeline columns
5. Developer builds Phase 2 (mapper + service)

## Next Steps

- [ ] Set `ADS_BASE_URL` in `ads_api.env`
- [ ] Run `inspect_sample.py` to fetch sample data
- [ ] Review the raw JSON and identify field mappings
- [ ] Provide field mapping to developer for Phase 2 implementation
