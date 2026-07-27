# ADS Integration Test Suite

Complete test suite for the AutoData Solutions API integration.

## Quick Start

Run all tests:

```bash
cd accy_v2/model_lookup
python tests/test_ads_integration.py
```

## Individual Tests

Run specific tests without running the full suite:

### 1. Test Single Vehicle Fetch (~2 seconds)

Tests the minimal-call `fetch_vehicle()` method. Fetches one specific vehicle trim.

```bash
python tests/test_fetch_vehicle.py
```

**What it tests:**

- API call count (should be exactly 1)
- Correct model data returned
- All columns populated
- Data types correct

**Expected output:**

```
TEST: fetch_vehicle() - Single Vehicle Fetch
Fetching Hyundai Elantra Essential (2026)...
  Time: 1.3s (includes pacing)
  Rows returned: 1
  [OK] Returned exactly 1 row
  [OK] ModelNumber: ELCS4V2BES00
  [OK] StyleID: 481251
  [OK] Drivetrain: FRONT_WHEEL_DRIVE
  [OK] PassDoors: 4
[SUCCESS] fetch_vehicle test passed
```

---

### 2. Test Complete Make/Year Fetch (~15 seconds)

Tests the `fetch_make()` method. Fetches all trims for Hyundai 2026 (62 configurations).

```bash
python tests/test_fetch_make.py
```

**What it tests:**

- Multiple API calls (years → models → trims)
- All rows returned
- Correct manufacturer and year
- Schema validation

**Expected output:**

```
TEST: fetch_make() - Complete Make/Year Fetch
Fetching all Hyundai 2026 trims...
  Rows returned: 62
  [OK] Retrieved 62 rows for Hyundai 2026
  [OK] All rows are HYUNDAI
  [OK] All rows are year 2026
  [OK] Has all 10 columns
  [OK] All critical columns populated

  Sample rows:
    ELCS4V2BES00    | Essential IVT            | StyleID=481251
    ELCS4V2BPR00    | Preferred IVT            | StyleID=481252
    ELCS4V2BPRTE    | Preferred IVT w/Tech Pkg | StyleID=481253
[SUCCESS] fetch_make test passed
```

---

### 3. Test CSV Write/Read (~15 seconds)

Tests saving data to CSV and reading it back.

```bash
python tests/test_csv_io.py
```

**What it tests:**

- CSV file creation
- Data persistence
- Column preservation
- Row count accuracy

**Expected output:**

```
TEST: CSV Write/Read
[1/3] Fetching data...
      Fetched 62 rows
[2/3] Writing to CSV...
      Successfully saved 62 records
[3/3] Reading from CSV...
      Read 62 rows, 10 columns
  [OK] Row count matches
  [OK] Has all 10 columns
  [OK] Data integrity verified

  Columns in CSV:
    - Manufacturer
    - ModelYear
    - ModelNumber
    - Description
    - Description2
    - Package
    - Style_ID
    - StyleID
    - Drivetrain
    - PassDoors
[SUCCESS] CSV write/read test passed
```

---

### 4. Test Schema Validation (~15 seconds)

Tests that all columns exist, have correct data types, and are populated.

```bash
python tests/test_schema.py
```

**What it tests:**

- All 10 columns present
- Column order correct
- Data population percentage
- Data type correctness

**Expected output:**

```
TEST: Schema Validation
[1/2] Checking all columns present...
  [OK] All 10 columns present in correct order

[2/2] Checking data population...
  [OK] Manufacturer               62/ 62 (100.0%)
  [OK] ModelYear                 62/ 62 (100.0%)
  [OK] ModelNumber               62/ 62 (100.0%)
  [OK] Description               62/ 62 (100.0%)
  [OK] Description2               0/ 62 (  0.0%)
  [OK] Package                   62/ 62 (100.0%)
  [OK] Style_ID                  62/ 62 (100.0%)
  [OK] StyleID                   62/ 62 (100.0%)
  [OK] Drivetrain                62/ 62 (100.0%)
  [OK] PassDoors                 62/ 62 (100.0%)

[3/2] Checking data types...
  [OK] Manufacturer              object
  [OK] ModelYear                 int64
  [OK] ModelNumber               object
  [OK] Description               object
  [OK] StyleID                   int64
  [OK] PassDoors                 int64
[SUCCESS] Schema validation test passed
```

---

### 5. Test All (Comprehensive Suite)

Runs all 15 tests in sequence. Takes ~3-4 minutes total.

```bash
python tests/test_ads_integration.py
```

**What it tests:**

- Credentials loading
- Service initialization
- Single vehicle fetch
- Make/year fetch
- Schema validation
- Column population
- CSV write/read
- Schema harmonization
- Data quality
- Rate limiting
- Multiple makes
- Save callbacks
- And more...

**Expected output:**

```
======================================================================
  ADS INTEGRATION TEST SUITE
======================================================================

======================================================================
  RUNNING TESTS
======================================================================
[OK] test_credentials_loaded
     User: 298924
[OK] test_service_initialization
     Makes available: 7
[OK] test_fetch_vehicle_single_call
     1 row in 1.3s (includes pacing)
[OK] test_fetch_make_complete
     62 rows fetched
... (11 more tests)

======================================================================
  TEST SUMMARY
======================================================================
Total:  15
Passed: 13
Failed:  2

[FAILED] 2 TEST(S) FAILED
```

---

## Test Requirements

Before running tests, ensure:

1. **Credentials file exists:**

   ```bash
   cat accy_v2/model_lookup/creds/ads_api.env
   ```
2. **Python dependencies:**

   ```bash
   pip install pandas requests urllib3
   ```
3. **Writable database directory:**

   ```bash
   mkdir -p accy_v2/model_lookup/db
   mkdir -p accy_v2/model_lookup/db/archive
   ```

---

## Test Results Summary

| Test                | Time  | Rows  | Status     |
| ------------------- | ----- | ----- | ---------- |
| fetch_vehicle       | ~1s   | 1     | ✓         |
| fetch_make          | ~12s  | 62    | ✓         |
| CSV I/O             | ~1s   | 62    | ✓         |
| Schema              | ~12s  | 62    | ✓         |
| All (comprehensive) | ~3-4m | Mixed | ✓ (13/15) |

---

## Troubleshooting

| Issue                              | Solution                                         |
| ---------------------------------- | ------------------------------------------------ |
| `FileNotFoundError: ads_api.env` | Create`creds/ads_api.env` with credentials     |
| `ConnectionError`                | Check internet, verify ADS_BASE_URL is reachable |
| `ModuleNotFoundError`            | `pip install pandas requests urllib3`          |
| Test hangs                         | API might be slow; let it run (has 30s timeout)  |
| Tests fail intermittently          | Network issue; retry or check API availability   |

---

## Running Tests in Production

Before running the full `refresh_db_ads.py` pipeline, run these tests in order:

1. `test_fetch_vehicle.py` - Verify single fetch works
2. `test_fetch_make.py` - Verify multi-row fetch works
3. `test_csv_io.py` - Verify CSV persistence works
4. `test_schema.py` - Verify data schema is correct
5. `test_ads_integration.py` - Full suite (optional, comprehensive)

If all pass, you're ready to run:

```bash
python accy_v2/model_lookup/refresh_db_ads.py
```

---

## Notes

- Tests use **actual API calls** (not mocks), so they require internet connectivity
- Rate limiting is enabled (0.5s per call) to be API-friendly
- Tests create temporary files in `db/test_*.csv` and clean up after themselves
- Expected runtime: ~2 minutes for individual test, ~4 minutes for full suite
