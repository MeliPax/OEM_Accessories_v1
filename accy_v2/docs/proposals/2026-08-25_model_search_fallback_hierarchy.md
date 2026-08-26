# Proposal: Model Search Fallback Hierarchy with Persistent Fetch Activity Log

**Date:** 2026-08-25  
**Status:** PROPOSAL (Design only — no code changes in this document)  
**Next Phase:** Implementation + Integration (follows user approval of this design)

---

## Executive Summary

Today's model number lookup pipeline uses a 2-tier fallback (local CSV → online ADS if model line is missing), but has two critical gaps:
1. The ADS fallback gate is **in-memory and run-scoped**: it resets on every pipeline run, allowing the same model to be re-fetched from ADS multiple times per day. There's no record of "we already checked this within the last 30 days" across runs.
2. A **second data source exists but is unused**: `DB_VehConfig` (SQL Server on `pb_aristor_server`), which predates the ADS approach. It's not integrated into the pipeline, and its schema/code path predates the translator/standardization applied to ADS-sourced data.

This proposal introduces a **persistent, cross-run "Fetch Activity Log"** that becomes the single source of truth for database freshness, gates the ADS fallback with a 30-day staleness check, and prepares for VehConfig as a third fallback source (design-only for now, implementation deferred).

### Hierarchy (4 tiers)

```
1. Local CSV search (db_vehicle_models.csv)
   ├─ HIT → return model data
   └─ MISS → check tier 2

2. Fetch Activity Log + ADS fallback
   ├─ never fetched, OR completed fetch > 30 days ago, OR last attempt in_progress/failed
   │  ├─ call ADS to fetch (Manufacturer, ModelName, ModelYear)
   │  ├─ record in log: start → complete/fail
   │  └─ reload CSV and re-check tier 1
   ├─ last completed fetch <= 30 days ago
   │  └─ skip ADS ("still fresh") → go to tier 3
   └─ (HIT via reload or skip) → return model data
      (MISS) → check tier 3

3. Vehicle Config DB fallback (DESIGN ONLY, phase 2)
   ├─ call VehConfig.fetch_vehicle() [wrapper to be designed]
   ├─ record in log: start → complete/fail (Source=vehconfig)
   └─ reload CSV and re-check tier 1
      (HIT or MISS) → check tier 4

4. No model number
   └─ mark row with [NO_MODEL_NUMBER_ALL_SOURCES_EXHAUSTED] DQ tag
      keep row in output with empty Model column (row not dropped)
```

---

## Problem Statement

### Today's implementation

**File: `accy_v2/oems/hyundai/pipeline/step4_5_model_enrichment.py:90-130` (Mitsubishi identical at `:93-127`)**

```python
# Created once per pipeline run, stored in base_pipeline.py, passed to step4_5
ads_attempted = set()  

# Per-trim search:
if find_model_line(csv_df, make, year, model_name) is empty:
    if (make, model_name, year) not in ads_attempted:
        ads_attempted.add((make, model_name, year))
        result = ADSService(...).fetch_vehicle(make, model_name, year)
        if result:
            save_vehicle_models_to_csv(result)
            csv_df = load_existing_csv(csv_path)  # reload
            # re-check via search_models_by_description()
```

### Gaps

1. **No cross-run memory**: `ads_attempted` is created fresh in `base_pipeline.py::run()` every time a pipeline runs. An operator runs Hyundai at 9am, then Mitsubishi at 3pm — same day, 6 hours later. Both touch the same "2024 Elantra" model line. The 3pm run will re-fetch from ADS even though Hyundai already fetched it that morning, wasting ADS API quota and delaying the Mitsubishi run.

2. **No visibility into failures**: If ADS times out or returns 500 mid-run, the row gets a `[ADS_ERROR]` DQ tag and the set entry vanishes. The next run (or sheet in the same run) will retry ADS for the same model with no indication it's already failed once. No one sees "we tried 3 times for Elantra 2024, all timeouts — maybe investigate ADS availability or switch to fallback."

3. **No fallback to VehConfig**: The legacy `DB_VehConfig` database (Manufacturer/Bulletin tables) exists and has been used historically. It's currently dead code in production (`refresh_db.py` never runs), but it could fill gaps for models ADS doesn't know about yet. No path to use it without manual effort.

4. **Bulk CLI and inline inconsistent**: `refresh_db_ads.py` (the manual bulk-refresh script) and the inline per-pipeline ADS fallback are independent. An operator runs the bulk script to refresh everything for Hyundai 2025, then someone runs the pipeline 10 minutes later — the pipeline doesn't know the bulk script just updated the DB, so its `ads_attempted` gate doesn't defer to the fresh data; it re-fetches anyway (or at best, skips ADS only due to timing coincidence).

---

## Proposed Solution: Persistent Fetch Activity Log

### Core design

A **new CSV file** (`fetch_activity_log.csv`) that records **every attempt to fetch or refresh model data**, with explicit start/completion tracking and metadata to determine staleness.

#### File location and schema

**Path:** `accy_v2/model_lookup/db/fetch_activity_log.csv`

**Schema (9 columns, one row per unique `(Manufacturer, ModelName, ModelYear)`):**

| Column | Type | Notes |
|--------|------|-------|
| `Manufacturer` | string | OEM name (e.g., "Hyundai", "Genesis", "Mitsubishi") |
| `ModelName` | string | Vehicle model line (e.g., "Elantra", "Outlander") |
| `ModelYear` | int | Model year (e.g., 2024) |
| `FetchStartedAt` | ISO-8601 UTC timestamp | When the fetch began. Set when `start_fetch()` is called. |
| `FetchCompletedAt` | ISO-8601 UTC timestamp | When the fetch completed. Blank while in flight. Set by `complete_fetch()` or `fail_fetch()`. |
| `Status` | enum: `in_progress` / `completed` / `failed` | Did the fetch operation run to completion? `in_progress` = still running; `completed` = finished successfully or returned no data; `failed` = exception/timeout. **Distinct from whether data was found** — see Result column. |
| `Result` | enum: `found` / `not_found` / `error` | Did the fetch return model data? Only meaningful once Status ≠ `in_progress`. `error` only set if Status=`failed`. |
| `Source` | string | Which entry point triggered this fetch: `ads_inline` (per-pipeline fallback), `ads_bulk_cli` (manual bulk CLI), `vehconfig` (phase 2). |
| `RunID` | string | Unique identifier for the pipeline/CLI run that produced this record (tied to `PipelineLogger.run_id`). Allows tracing back to the original run log. |

**Example rows:**

```csv
Manufacturer,ModelName,ModelYear,FetchStartedAt,FetchCompletedAt,Status,Result,Source,RunID
Hyundai,Elantra,2024,2026-08-25T09:15:30Z,2026-08-25T09:15:45Z,completed,found,ads_inline,a1b2c3d4
Hyundai,Elantra,2024,2026-08-25T15:30:00Z,,in_progress,,ads_bulk_cli,x9y8z7w6
Mitsubishi,Outlander,2025,2026-08-23T14:22:10Z,2026-08-23T14:23:05Z,completed,not_found,ads_inline,p7q6r5s4
```

### Upsert semantics

**Not append-only**: each `(Manufacturer, ModelName, ModelYear)` key has at most one row. When a fetch is triggered:
1. **Read** the full CSV into memory.
2. Check if key exists; if not, create a new row.
3. Update the row (set `FetchStartedAt`, clear `FetchCompletedAt`/`Result`, set `Status=in_progress`).
4. **Write** the full CSV back (one complete file per update).
5. After fetch completes: **re-read**, update the same row with `FetchCompletedAt`, `Status`, `Result`, and **write** again.

**Why upsert instead of append?** Because `should_fetch()` needs to query the *latest* record to decide staleness (see below). An append-only log would require scanning the entire file for each `(Mfr, Model, Year)` to find the most recent row — expensive and fragile. Upsert keeps one row per key, always up-to-date.

**File size:** Bounded by the number of unique `(Mfr, Model, Year)` tuples touched by any pipeline/CLI run. Today's pipeline touches ~7–10 OEMs × ~5–10 model lines per OEM × ~3 years = ~200–300 rows. Full read-modify-write is negligible.

### Staleness check: 30-day rule + 5-minute timeout for stuck fetches

New method in the `FetchActivityLog` class:

```python
def should_fetch(self, manufacturer: str, model_name: str, model_year: int, 
                 staleness_days: int = 30, stalled_timeout_minutes: int = 5) -> bool:
    """
    Determine whether a fresh fetch is needed.
    
    Returns True if:
    - No row exists for this key (never fetched)
    - Status=in_progress AND elapsed time > stalled_timeout_minutes (process likely crashed; mark as failed, retry)
    - Status=failed (attempt errored; retry on next opportunity)
    - Status=completed, Result=found, but > staleness_days old (refresh data)
    - Status=completed, Result=not_found, but > staleness_days old (re-check, data might exist now)
    
    Returns False if:
    - Status=in_progress AND elapsed < stalled_timeout_minutes (attempt still actively running; don't stack fetches)
    - Status=completed, Result=found, and < staleness_days old (confirmed present and fresh; skip ADS)
    - Status=completed, Result=not_found, and < staleness_days old (confirmed absent; skip ADS, go to tier 3)
    """
```

**30-day staleness rule:**
- Both `found` and `not_found` count as "we checked this model"
- A model confirmed absent 5 days ago doesn't get re-fetched just because time passed
- Only after 30 days does staleness trigger a fresh ADS call (maybe model was added upstream, maybe a typo was fixed)

**5-minute timeout for stalled `in_progress` rows:**
- If a fetch is marked `in_progress` but has been stalled for > 5 minutes, the process likely crashed/hung
- Matches on-demand pipeline nature (not background jobs; if running for 5+ min, something is wrong)
- Automatic recovery: `should_fetch()` auto-marks the stale `in_progress` as `failed`, then returns `True` to retry
- Next pipeline run (or next sheet in same run) will see the marked-as-failed row and will retry ADS without waiting the full 30 days

**Failed attempts:**
- `Status=failed` rows don't wait for the 30-day clock — they're retried on the next opportunity
- This prevents a transient ADS timeout from blocking a model until staleness expires

### Implementation module: `accy_v2/model_lookup/fetch_activity_log.py`

New helper class with centralized factory initialization:

```python
from pathlib import Path
from datetime import datetime, timezone, timedelta
import pandas as pd

class FetchActivityLog:
    """
    Centralized interface for tracking model data fetch attempts across pipeline runs.
    Single source of truth for "when did we last check this model" and "did it work."
    """
    
    def __init__(self, csv_path: str):
        """Load existing log from CSV, or create empty log if file doesn't exist."""
        self.csv_path = Path(csv_path)
        self._load()
    
    def _load(self) -> None:
        """Read CSV into DataFrame, or initialize empty if file missing."""
        # Reads full CSV, stores in self.df
        # Handles missing file gracefully (returns empty DataFrame with correct schema)
    
    def _save(self) -> None:
        """Write DataFrame back to CSV (upsert pattern: full rewrite, atomic write via temp file)."""
        # Writes self.df to self.csv_path using atomic write pattern:
        # 1. Write to temporary file
        # 2. Atomic rename temp to final path
        # This prevents corruption if write is interrupted
    
    def should_fetch(self, manufacturer: str, model_name: str, model_year: int, 
                     staleness_days: int = 30, stalled_timeout_minutes: int = 5) -> bool:
        """
        Check if a fresh fetch is needed.
        
        Returns True if:
        - No row exists (never fetched)
        - Status=in_progress AND elapsed > stalled_timeout_minutes (process likely crashed)
        - Status=failed (retry failed attempts)
        - Status=completed AND (Result=found OR Result=not_found) AND elapsed > staleness_days
        
        Returns False if:
        - Status=in_progress AND elapsed < stalled_timeout_minutes (attempt still running, don't stack)
        - Status=completed AND elapsed < staleness_days (data is fresh)
        """
        # Finds row by key (Manufacturer, ModelName, ModelYear)
        # Handles in_progress timeout: if > 5 min, auto-fail and return True
    
    def start_fetch(self, manufacturer: str, model_name: str, model_year: int, 
                    source: str, run_id: str) -> None:
        """Record that a fetch is starting. Sets Status=in_progress, FetchStartedAt=now."""
        # Upserts row, calls self._save()
        # Emits: logger.info(f"[FETCH_START] {manufacturer} {model_name} {model_year} (source={source})")
    
    def complete_fetch(self, manufacturer: str, model_name: str, model_year: int, 
                       result: str, run_id: str) -> None:
        """
        Record a successful fetch. Sets Status=completed, Result=<found|not_found>, FetchCompletedAt=now.
        
        Args:
            result: "found" or "not_found" — must be one of these values (validates input)
        
        Raises:
            ValueError if result is not a valid enum value
        """
        # Validates result is "found" or "not_found"
        # Upserts row, calls self._save()
        # Emits: logger.info(f"[FETCH_COMPLETE_FOUND] ...") or logger.info(f"[FETCH_COMPLETE_NOT_FOUND] ...")
    
    def fail_fetch(self, manufacturer: str, model_name: str, model_year: int, 
                   error_message: str, run_id: str) -> None:
        """
        Record a failed fetch. Sets Status=failed, Result=error, FetchCompletedAt=now.
        
        Args:
            error_message: Description of the failure (e.g., "Connection timeout", "stalled for 312s")
        """
        # Upserts row (Result always "error"), calls self._save()
        # Emits: logger.warning(f"[FETCH_FAILED] {manufacturer} {model_name} {model_year}: {error_message}")


# ===== FACTORY FUNCTION: Single initialization point for both pipeline and CLI =====
def get_fetch_activity_log() -> FetchActivityLog:
    """
    Factory: Initialize FetchActivityLog with the standard production path.
    
    Both the pipeline and the bulk CLI use this function, ensuring:
    - Single source of truth for CSV location (encapsulated in model_lookup module)
    - Consistent initialization across all entry points
    - Easy to swap for test paths in unit tests
    
    Returns:
        Initialized FetchActivityLog instance
    """
    from pathlib import Path
    
    # CSV lives alongside db_vehicle_models.csv in the db/ folder
    csv_path = Path(__file__).parent / "db" / "fetch_activity_log.csv"
    return FetchActivityLog(str(csv_path))
```

**Design principle:** All model_lookup initialization logic lives in the model_lookup module. Pipeline and CLI code use the factory function, never hardcode paths.

---

## Architecture & Module Organization

### Design principle: Single source of truth for model_lookup initialization

The proposal centralizes all model_lookup initialization logic in the model_lookup module itself, avoiding scattered hardcoded paths across pipeline code. This achieves:

1. **Separation of concerns** — model_lookup is self-contained; pipeline code doesn't need to know CSV locations
2. **Consistency across entry points** — pipeline and bulk CLI use the same factory function
3. **Encapsulation** — CSV path is an implementation detail, not exposed to callers
4. **Testability** — easy to mock or inject test paths in unit tests
5. **Future-proofing** — if storage moves from CSV to database, only the factory needs to change

### Factory function pattern

```
get_fetch_activity_log() factory function
    ├─ Lives in: accy_v2/model_lookup/fetch_activity_log.py
    ├─ Called by: accy_v2/core/base_pipeline.py (pipeline initialization)
    ├─ Called by: accy_v2/model_lookup/refresh_db_ads.py (bulk CLI initialization)
    └─ Returns: Initialized FetchActivityLog instance (with CSV path resolved)
```

**Why factory over direct instantiation:**
- Direct: `FetchActivityLog(Path(__file__).parent / "db" / "fetch_activity_log.csv")` — path logic scattered
- Factory: `get_fetch_activity_log()` — all path logic in one place, both callers use it identically

---

## Integration Points

### Point 1: Inline per-pipeline ADS fallback (`step4_5_model_enrichment.py`)

**Files affected:**
- `accy_v2/oems/hyundai/pipeline/step4_5_model_enrichment.py`
- `accy_v2/oems/mitsubishi/pipeline/step4_5_model_enrichment.py`
- `accy_v2/core/base_pipeline.py` (delete `ads_attempted` initialization)

**Changes:**

1. **Initialize `FetchActivityLog` once per pipeline run** (in `base_pipeline.py::run()`, where `ads_attempted` is currently created):
   ```python
   # Replace:
   #   ads_attempted = set()
   # With:
   from accy_v2.model_lookup.fetch_activity_log import get_fetch_activity_log
   
   fetch_log = get_fetch_activity_log()  # Factory handles path, initialization
   ```
   Pass `fetch_log` down to `run_step4_5_model_enrichment()` instead of `ads_attempted`.
   
   **Why factory function:** All model_lookup initialization logic lives in the model_lookup module (not scattered across pipeline code). Both pipeline and CLI use the same factory, ensuring consistent path and initialization.

2. **Replace the model-line gate in `step4_5_model_enrichment.py`** (currently lines ~90–130 in both files):
   ```python
   # OLD:
   if find_model_line(csv_df, make, year, model_name) is None:
       if (make, model_name, year) not in ads_attempted:
           ads_attempted.add((make, model_name, year))
           result = ADSService(...).fetch_vehicle(make, model_name, year)
           if result:
               save_vehicle_models_to_csv(result)
               csv_df = load_existing_csv(csv_path)
   
   # NEW:
   if find_model_line(csv_df, make, year, model_name) is None:
       if fetch_log.should_fetch(make, model_name, year, staleness_days=30):
           fetch_log.start_fetch(make, model_name, year, source="ads_inline", 
                                 run_id=run_id)
           try:
               result = ADSService(...).fetch_vehicle(make, model_name, year)
               if result:
                   save_vehicle_models_to_csv(result)
                   csv_df = load_existing_csv(csv_path)
                   fetch_log.complete_fetch(make, model_name, year, 
                                           result="found", run_id=run_id)
               else:
                   fetch_log.complete_fetch(make, model_name, year, 
                                           result="not_found", run_id=run_id)
           except Exception as e:
               fetch_log.fail_fetch(make, model_name, year, 
                                    error_message=str(e), run_id=run_id)
               logger.warning(f"[ADS_FETCH_ERROR] {make} {model_name} {year}: {e}")
   ```

3. **Extend `_categorize_search_failure()`** (currently line ~455–488 in `step4_5_model_enrichment.py`) to add a new terminal categorization tag:
   - New tag: `[NO_MODEL_NUMBER_ALL_SOURCES_EXHAUSTED]` (used when tiers 1–3 all miss)
   - Keep existing tags for intermediate tiers (`[MODEL_LINE_NOT_FOUND]`, `[DATABASE_NO_MATCH]`, `[ADS_ERROR]`) for detail in DQ logging

4. **Delete `ads_attempted` from `base_pipeline.py`** entirely — no longer needed, the persistent log now tracks this.

**Benefit:** The persistent log naturally subsumes the in-memory set's function *within* a run too. If two sheets in the same Hyundai run both reference "Elantra 2024," the first triggers a fetch and writes `FetchStartedAt/Status=in_progress` to the log. The second checks `should_fetch()`, sees `Status=in_progress` (< 30 days, attempt not finished yet), and skips ADS. By the time the first completes, the log is updated, and both sheets benefit from the same fresh data.

### Point 2: Bulk refresh CLI (`refresh_db_ads.py`)

**File:** `accy_v2/model_lookup/refresh_db_ads.py`

**Changes:**

The existing `refresh_from_ads()` flow (lines 34–232) already iterates per make × year, then fetches trims per model within that make/year. Initialize the log at the start of the function, then wrap each per-model fetch with tracking:

```python
# At start of refresh_from_ads():
from accy_v2.model_lookup.fetch_activity_log import get_fetch_activity_log
from uuid import uuid4

fetch_log = get_fetch_activity_log()  # Factory initialization (same as pipeline)
run_id = str(uuid4())[:8]            # Unique run ID for this bulk refresh

# Inside the loop where models are being fetched:
for model in models_for_make_year:
    manufacturer = make  # (or use canonical name mapping)
    model_name = model["name"]
    model_year = year
    
    # NEW: Record fetch start
    fetch_log.start_fetch(manufacturer, model_name, model_year, 
                          source="ads_bulk_cli", run_id=run_id)
    try:
        # EXISTING: fetch via ADS
        trims = service.get_trims(model)
        
        if trims:
            # EXISTING: save to CSV
            save_vehicle_models_to_csv(...)
            # NEW: Record success
            fetch_log.complete_fetch(manufacturer, model_name, model_year, 
                                     result="found", run_id=run_id)
        else:
            # NEW: Record "no data found"
            fetch_log.complete_fetch(manufacturer, model_name, model_year, 
                                     result="not_found", run_id=run_id)
    except Exception as e:
        # NEW: Record failure
        fetch_log.fail_fetch(manufacturer, model_name, model_year, 
                             error_message=str(e), run_id=run_id)
        dq_logger.log_warning(...)  # existing DQ pattern
        logger.warning(f"[ADS_BULK_FETCH_ERROR] {manufacturer} {model_name} {year}: {e}")
        # Continue to next model (don't crash on partial failures)
```

**Benefit:** A manual bulk refresh (e.g., `python refresh_db_ads.py --makes Hyundai --years 2024 2025`) correctly resets the 30-day staleness clock for every model it touches. The next inline pipeline run sees the fresh data and won't redundantly re-fetch. This coordinated state (single source of truth in the fetch-activity log) prevents the old problem where bulk CLI and inline pipeline were independent.

### Point 3: Vehicle Config DB fallback (DESIGN ONLY, phase 2)

**Defer implementation**, but document the integration point:

```python
# In step4_5_model_enrichment.py, after ADS fallback (tier 2):

if find_model_line(csv_df, make, year, model_name) is None:
    # TODO(vehconfig-phase2): Implement VehConfig fallback
    # fetch_log.start_fetch(make, model_name, year, source="vehconfig", run_id=run_id)
    # try:
    #     result = VehConfigService(...).fetch_vehicle(make, model_name, year)
    #     if result:
    #         save_vehicle_models_to_csv(result)  # same path, so standardized/deduped
    #         csv_df = load_existing_csv(csv_path)
    #         fetch_log.complete_fetch(make, model_name, year, result="found", run_id=run_id)
    #     else:
    #         fetch_log.complete_fetch(make, model_name, year, result="not_found", run_id=run_id)
    # except Exception as e:
    #     fetch_log.fail_fetch(make, model_name, year, error_message=str(e), run_id=run_id)
    # 
    # if find_model_line(csv_df, make, year, model_name) is None:
    #     # Mark terminal: all sources exhausted
    #     categorize as [NO_MODEL_NUMBER_ALL_SOURCES_EXHAUSTED]
```

(Placeholder for phase 2 implementation; the structure is already there, just not yet active.)

---

## Vehicle Config DB Revival (Design Only — Phase 2)

### Current state

`DB_VehConfig` exists as a SQL Server database (`pb_aristor_server`) with `Manufacturer` and `Bulletin` tables containing historical vehicle accessory data. It's accessed via:
- `accy_v2/model_lookup/engine.py` — creates SQLAlchemy connection from env vars (`pb_aristor_server`, `DB_VehConfig`, `USER_NAME`, `PASSWORD`, `ODBC_DRIVER`)
- `accy_v2/model_lookup/db_queries/manufacturer.py` — raw SQL queries
- `accy_v2/model_lookup/refresh_db.py` — bulk refresh script (currently unmaintained, not in any pipeline)

### Why not ready yet

1. **Schema mismatch**: `refresh_db.py` writes a 19-column header (`VehicleID,Manufacturer,ModelNumber,...`) that doesn't match the current 10-column schema (`Description, Drivetrain, Manufacturer, ModelName, ModelNumber, ModelYear, Package, PassDoors, TrimName, engine_type`). There's also a typo (`Drivetrrain`).

2. **Dedup key mismatch**: ADS ingestion uses a 4-column uniqueness invariant (`Manufacturer, ModelYear, ModelNumber, Description`). VehConfig's `batch_save_manufacturer_models()` doesn't align; dedup keys would conflict.

3. **Missing translator/standardization**: ADS-sourced rows go through OEM translator and standardization (abbreviations expanded, case normalized) before writing to CSV. VehConfig rows would bypass this, introducing inconsistency.

4. **No single-model query**: Existing queries are make-level or bulletin-based. We need a `fetch_vehicle(make, model, year)` interface matching ADS's signature.

5. **Credentials not verified**: `model_lookup/creds/.env` (gitignored) is required but can't be verified from the repo. Need confirmation that `pb_aristor_server` is still reachable and credentials are current.

### What phase 2 must do

1. **Fix `refresh_db.py` CSV writer** to emit the correct 10-column schema and no typos.
2. **Align dedup key** with the 4-column invariant used by ADS.
3. **Wire VehConfig rows through translator/standardization** (same path ADS uses before write).
4. **Implement `fetch_vehicle(make, model, year)`** query wrapper around existing Manufacturer/Bulletin tables, filtering `BulletinDetails` JSON by Year/Model.
5. **Verify `pb_aristor_server` and `DB_VehConfig` credentials** are current and reachable.
6. **Interface parity**: Ensure the VehConfig call site in step4_5_model_enrichment.py looks identical to the ADS call (same inputs, same save path, same reload-and-recheck pattern).

---

## Out of Scope

- **`refresh_db.py` (legacy VehConfig CLI)** is not instrumented in this phase. Once phase 2 revives VehConfig, `refresh_db.py` will be updated to wrap its fetches in the same `start_fetch()`/`complete_fetch()` pattern, tagged `Source=vehconfig`. Until then, `refresh_db.py` remains dead code.

- **No changes to `search_models_by_description()`, `VehicleSearchEngine`, translator/classifier logic, or the `db_vehicle_models.csv` schema itself.** This proposal is purely about when to fetch and from where, not how to search or standardize once fetched.

- **No code changes in this document.** This is an architecture/design document for review and approval. The follow-up implementation pass will have no ambiguity — the module interface, call sites, and integration points are fully specified here.

---

## Known Limitations & Future Considerations

### Single-process assumption
**Current design:** Assumes pipelines run one at a time (sequential execution, no multiprocessing). CSV read-modify-write is not atomic; concurrent writes would cause data loss.

**Current state:** ✅ All pipeline runs are on-demand and sequential. No scheduling or parallelization yet. Low risk.

**If adding parallelization later:** Upgrade path exists:
- Use atomic write via temp-file-then-rename (simple fix, included in `_save()` spec)
- Optional: add file locking (advisory lock via `fcntl`/`msvcrt`)
- Optional: upgrade to SQLite for native atomicity

### Stalled `in_progress` timeout
**Current design:** Treats `in_progress` rows older than 5 minutes as failed. On-demand pipelines that run for 5+ minutes without updating the log indicate a crash.

**Edge case:** If ADS takes longer than 5 minutes to respond (unusual, but possible with slow networks), a concurrent run might mark the first attempt as failed. However, the first run's data is still saved to `db_vehicle_models.csv`, so the end result is correct (data is available, log reflects "timeout" — a bit misleading but not wrong).

**Acceptable for current use case:** Yes. On-demand pipelines typically complete in < 5 min. If slow ADS becomes common, increase timeout to 10 minutes.

### VehConfig credential validity
**Risk:** `model_lookup/creds/.env` is gitignored and not in the repo. If `pb_aristor_server` / `DB_VehConfig` credentials are stale or the server is decommissioned, phase 2 will be blocked.

**Mitigation:** Before phase 2 starts, verify with the infrastructure/data team that the credentials are current and the database is still live.

### Future: Honda and parallel OEMs
**Question:** When Honda's pipeline is built, should it use this same hierarchy and log from day one?

**Recommendation:** Yes — the log is OEM-agnostic (keyed by Manufacturer, which is already part of the pipeline's metadata). Reusing it ensures consistency across all OEMs and enables future parallelization/scheduling without redesign.

---

## Files to be created/modified (Phase 1 implementation)

### New files (in model_lookup module)

**`accy_v2/model_lookup/fetch_activity_log.py`** (200–250 lines)
- `FetchActivityLog` class (all methods as specified in Implementation section)
- `get_fetch_activity_log()` factory function (centralized initialization)
- Encapsulates: CSV path resolution, file I/O, staleness logic, 5-minute timeout logic

**`accy_v2/model_lookup/db/fetch_activity_log.csv`** (data file)
- Created empty on first run
- Grows as fetches are recorded (one row per unique Manufacturer/ModelName/ModelYear key)
- Expected size: ~200–300 rows (bounded by distinct model/year combos across all OEMs)

### Modified files (integration points)

**`accy_v2/core/base_pipeline.py`** (~10 lines changed)
- Replace: `ads_attempted = set()` initialization
- With: `fetch_log = get_fetch_activity_log()`
- Pass `fetch_log` to `run_step4_5_model_enrichment()` in place of `ads_attempted`
- Delete entire `ads_attempted` threading logic

**`accy_v2/oems/hyundai/pipeline/step4_5_model_enrichment.py`** (~40–50 lines changed)
- Replace: `if (make, model_name, year) not in ads_attempted` gate
- With: `if fetch_log.should_fetch(make, model_name, year)` check
- Wrap ADS call: `fetch_log.start_fetch()` → try ADS → `fetch_log.complete_fetch()` / `fail_fetch()`
- Update: `_categorize_search_failure()` to add `[NO_MODEL_NUMBER_ALL_SOURCES_EXHAUSTED]` tag

**`accy_v2/oems/mitsubishi/pipeline/step4_5_model_enrichment.py`** (~40–50 lines changed)
- Identical changes to Hyundai (same gate + wrap pattern)

**`accy_v2/model_lookup/refresh_db_ads.py`** (~60–80 lines changed)
- Add initialization: `fetch_log = get_fetch_activity_log()` + `run_id = uuid4().hex[:8]`
- Wrap per-model fetch loop: `fetch_log.start_fetch()` → fetch → `complete_fetch()` / `fail_fetch()`
- Source tag: `"ads_bulk_cli"` (not `"ads_inline"`)

### Module organization principle
**All model_lookup initialization logic lives in `accy_v2/model_lookup/`** — not scattered across pipeline code. Both pipeline and CLI import and use the same factory function, ensuring consistent initialization and encapsulation of CSV paths.

---

## Phase 2 Implementation (NOT in this proposal)

**`accy_v2/model_lookup/refresh_db.py`** — update schema, align dedup, wire through translator
**`accy_v2/model_lookup/engine.py`** — possible enhancements to query interface
**`accy_v2/oems/{hyundai,mitsubishi}/pipeline/step4_5_model_enrichment.py`** — add VehConfig fallback (after ADS tier 2)

---

## Next Steps

1. **Review this proposal** — feedback, corrections, or approval before implementation
2. **(Approved)** Implement Phase 1 (FetchActivityLog class, inline + bulk CLI integration, delete ads_attempted)
3. **Test Phase 1** — verify 30-day gate works, cross-run memory holds, no regressions in existing pipeline behavior
4. **Design Phase 2** — VehConfig revival (separate proposal, after phase 1 is stable)

---

## References

- `accy_v2/docs/SYSTEM_ARCHITECTURE.md` — existing architecture doc (sections 3g2 "ADS Fallback", 3i "Duplicate Model-Number Handling")
- `accy_v2/oems/hyundai/pipeline/step4_5_model_enrichment.py` — Hyundai model enrichment (primary reference for integration)
- `accy_v2/model_lookup/refresh_db_ads.py` — ADS bulk refresh CLI (secondary integration point)
- `accy_v2/core/helpers/pipeline_logger.py`, `dq_logger.py` — existing logging infrastructure (patterns to reuse)
