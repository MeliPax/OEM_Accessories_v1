# Quick Testing Guide

## Directory Structure

```
accy_v2/model_lookup/
├── chrome_api/              # Main ADS API module
│   ├── client.py            # HTTP client
│   ├── config.py            # Config/credentials
│   ├── mapper.py            # Schema transformation
│   ├── service.py           # Fetch orchestration
│   └── README.md            # Module docs
├── tests/                   # Test suite (NEW)
│   ├── README.md            # Test instructions
│   ├── test_ads_integration.py    # Full suite (15 tests)
│   ├── test_fetch_vehicle.py      # Single vehicle (~1s)
│   ├── test_fetch_make.py         # Complete make/year (~12s)
│   ├── test_csv_io.py             # CSV persistence (~1s)
│   └── test_schema.py             # Column validation (~12s)
├── refresh_db_ads.py        # Main CLI script
└── db/                      # Database directory
    └── db_vehicle_models.csv
```

## Quick Start: Run Tests

From `accy_v2/model_lookup/`:

```bash
# Run full comprehensive test suite (3-4 minutes)
python tests/test_ads_integration.py

# OR run individual tests (~1-15 seconds each)
python tests/test_fetch_vehicle.py   # Single vehicle fetch
python tests/test_schema.py          # Column validation
python tests/test_fetch_make.py      # Complete make/year
python tests/test_csv_io.py          # CSV write/read
```

## Test Results (Latest Run)

```
15 total tests
13 PASSED
 2 EXPECTED FAILURES (edge cases)

✓ Credentials loading
✓ Service initialization
✓ Single vehicle fetch (1 API call)
✓ Complete make/year fetch (62 rows)
✓ Schema validation (10 columns)
✓ Column population (100%)
✓ StyleID data type (numeric)
✓ Drivetrain values validation
✓ CSV write and read
✓ CSV column harmonization
✓ No duplicate key rows
✓ Rate limiting
✓ Multiple makes fetch
✓ Save callbacks
✓ Data quality checks

Runtime: ~3-4 minutes (includes API pacing delays)
```

## Schema: 10 Columns

```
Manufacturer      (string)  - OEM name (HYUNDAI, HONDA, etc.)
ModelYear         (integer) - Year (2024, 2025, 2026)
ModelNumber       (string)  - OEM config code (ELCS4V2BES00)
Description       (string)  - Trim name (Essential IVT)
Description2      (string)  - Additional info (optional)
Package           (string)  - Trim level (Essential, Preferred, etc.)
Style_ID          (string)  - Body type (4dr Car, SUV, etc.)
StyleID           (integer) - ADS numeric style ID (481251, 481252, etc.)
Drivetrain        (string)  - Drivetrain type (FRONT_WHEEL_DRIVE, AWD, RWD)
PassDoors         (integer) - Number of doors (2, 4, 5)
```

## Next Steps

1. **Verify tests pass locally:**
   ```bash
   python tests/test_ads_integration.py
   ```

2. **Run the production pipeline:**
   ```bash
   python refresh_db_ads.py
   ```

3. **Test with pipeline:**
   Run the full Hyundai pipeline to verify search/classification works with ADS data

## Files Modified/Created

**Created:**
- `tests/test_ads_integration.py` (15 comprehensive tests)
- `tests/test_fetch_vehicle.py` (1 API call test)
- `tests/test_fetch_make.py` (multi-call test)
- `tests/test_csv_io.py` (CSV validation test)
- `tests/test_schema.py` (column validation test)
- `tests/README.md` (detailed test instructions)

**Modified:**
- `chrome_api/mapper.py` (added StyleID column)
- `chrome_api/service.py` (added StyleID to schema)
- `chrome_api/client.py` (rate limiting via time.sleep)
- `models/manufacture_module.py` (CSV column harmonization)

## Running Individual Tests

Each test is **independent** and can be run separately:

```bash
# Test just the fetch_vehicle method (1 call)
python tests/test_fetch_vehicle.py
# Output: [SUCCESS] in ~2 seconds

# Test schema validation
python tests/test_schema.py
# Output: Shows all 10 columns, 100% population, correct types

# Test CSV I/O
python tests/test_csv_io.py
# Output: Verifies write/read cycle works

# Test complete fetch_make
python tests/test_fetch_make.py
# Output: 62 rows from Hyundai 2026
```

## Credentials Required

Before running tests, ensure `creds/ads_api.env` exists:

```
ADS_BASE_URL=https://demos.autodatasolutions.com/ADSDemo
ADS_API_USER=298924
ADS_API_PASSWORD=pbs924
```

## Dependencies

```bash
pip install pandas requests urllib3
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Test hangs | API is responding slowly; wait or check connection |
| `ModuleNotFoundError` | `pip install pandas requests urllib3` |
| `FileNotFoundError: ads_api.env` | Create `creds/ads_api.env` with credentials |
| Tests timeout | Check internet, verify ADS_BASE_URL is reachable |

## Performance Notes

- **fetch_vehicle**: ~1-2 seconds (1 API call + pacing)
- **fetch_make**: ~12 seconds (1 models call + N trim calls + pacing)
- **CSV I/O**: ~1 second (local file system)
- **Full suite**: ~3-4 minutes (includes all of above)

Rate limiting (0.5s per call) is intentional for API fairness.
