# Vehicle Database Update Commands

## 🚀 Simple Commands

### Update Single Manufacturer
```bash
python populate_vehicle_database.py Mitsubishi
python populate_vehicle_database.py Mazda
python populate_vehicle_database.py Honda
```

### Update Multiple Manufacturers
```bash
python populate_vehicle_database.py Mitsubishi Mazda Honda
python populate_vehicle_database.py Mitsubishi Honda Kia Toyota
```

### List Available Manufacturers
```bash
python populate_vehicle_database.py --list
```

### Get Help
```bash
python populate_vehicle_database.py --help
python populate_vehicle_database.py -h
```

---

## 📊 Output Example

```
================================================================================
VEHICLE DATABASE POPULATION
================================================================================
Timestamp: 2026-06-22 15:45:30
CSV Path: model_lookup/db/db_vehicle_models.csv
Manufacturers: Mitsubishi, Mazda
================================================================================

Fetching Mitsubishi models...
Processing Mitsubishi...
Fetching Mazda models...
Processing Mazda...

================================================================================
POPULATION SUMMARY
================================================================================

Total records processed: 287
Records saved to CSV: 275
Duplicates (skipped): 10
Invalid records: 2

Per-manufacturer results:
  ✓ Mitsubishi: 156 saved, 5 duplicates
  ✓ Mazda: 119 saved, 5 duplicates

================================================================================
✓ DATABASE POPULATION SUCCESSFUL
✓ CSV file ready: model_lookup/db/db_vehicle_models.csv
================================================================================
```

---

## 📝 Examples

### First Time Setup
```bash
# Populate with all manufacturers
python populate_vehicle_database.py Mitsubishi Mazda Honda Toyota Kia Subaru Volkswagen
```

### Update Existing
```bash
# Just update Mitsubishi (adds new, skips duplicates)
python populate_vehicle_database.py Mitsubishi
```

### Add New OEM
```bash
# Add a new manufacturer to existing database
python populate_vehicle_database.py Nissan
```

### Verify What's Supported
```bash
# See what manufacturers are available
python populate_vehicle_database.py --list
```

---

## ✅ What It Does

1. ✓ Connects to database
2. ✓ Fetches latest bulletins for each manufacturer
3. ✓ Converts to structured data
4. ✓ Saves to CSV (`model_lookup/db/db_vehicle_models.csv`)
5. ✓ Skips duplicates automatically
6. ✓ Reports results with counts

---

## ⚡ Quick Start

```bash
# 1. Setup test environment
python setup_test_data.py

# 2. Populate database (instead of long command!)
python populate_vehicle_database.py Mitsubishi

# 3. Run pipeline test
python test_model_lookup_pipeline.py mitsubishi
```

Much simpler! 🎉

---

## 🆘 Troubleshooting

### "Could not connect to database"
- Make sure `.env` file exists with credentials
- Check database server is running
- Verify credentials are correct

### "No bulletin data found"
- Manufacturer may not have data in the source database
- Try: `python populate_vehicle_database.py --list` to see available

### "All records are duplicates"
- Database already has this manufacturer's data
- Re-running will skip all duplicates (expected behavior)

---

## 📁 Database Location

The populated data is saved to:
```
model_lookup/db/db_vehicle_models.csv
```

This is used by the pipeline when looking up model numbers.
