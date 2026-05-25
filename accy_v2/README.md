# OEM Accessory Pipeline (`v1`)

A scalable, config-driven data processing pipeline for importing and validating OEM accessory price files. Each OEM has its own pipeline configuration, allowing flexible business rules while sharing common core logic.

---

## What This Is

The pipeline transforms raw OEM accessory Excel files into standardized, validated output:

- **Input:** Multi-sheet Excel workbook with parts, descriptions, pricing, and trim applicability
- **Output:**
  - Single combined Excel file (one per run) with all models split EN/FR, plus a `_Report` sheet summarizing quality issues and model statistics
  - DQ report (JSON) listing data quality issues for stakeholder review
  - Pipeline execution log (text) for debugging and operations

---

## Project Structure

```
OEMAccessories/
├── core/                          # Shared pipeline logic
│   ├── base_pipeline.py           # Abstract pipeline orchestrator
│   ├── config_loader.py           # Config validation
│   └── helpers/                   # Shared utilities
│       ├── column_mapper.py       # Column keyword matching
│       ├── dq_logger.py           # Data quality report generation
│       ├── header_helpers.py      # Column cleaning, header promotion
│       ├── pipeline_logger.py     # Execution logging
│       └── trim_helpers.py        # Trim column detection and validation
│
├── data/                          # Raw OEM source files
│   └── landing_zone/
│       ├── mitsubishi/            # Mitsubishi source Excel files
│       ├── honda/                 # Future OEMs
│       └── mazda/
│
├── oems/                          # OEM-specific implementations
│   ├── mitsubishi/                # Example: Mitsubishi pipeline
│   │   ├── config/
│   │   │   └── mitsubishi_config.json   # Business rules
│   │   └── pipeline/
│   │       ├── orchestrator.py    # Calls base pipeline with OEM overrides
│   │       └── step*.py           # Pipeline steps (1-5)
│   │
│   └── [future OEMs follow same pattern]
│
├── output/                        # Generated artifacts (created at runtime)
│   ├── dq_reports/
│   ├── pipeline_logs/
│   └── ready_to_upload/
│
├── run_mitsubishi.py              # Entry point for Mitsubishi
├── README.md                       # This file
├── DECISIONS.md                    # Design decision log
├── CHANGELOG.md                    # Change history
└── docs/
    ├── config_schema.md           # How to author a config file
    └── dq_report_guide.md         # How to read DQ reports
```

---

## Setup

### Requirements

- Python 3.9+
- pandas, openpyxl (see dependencies)

### Installation

```bash
# Clone or navigate to the repository
cd OEMAccessories

# Install dependencies
pip install pandas openpyxl

# Optional: verify the setup by checking structure
python -c "import sys; print(f'Python {sys.version}')"
```

---

## Running a Pipeline

### Setup: Place source file

1. Obtain the OEM source Excel file (e.g., `Accessory Guide - February26.xlsx`)
2. Place it in the appropriate folder:
   ```
   OEMAccessories/data/landing_zone/mitsubishi/Accessory Guide - February26.xlsx
   ```

### Mitsubishi example

```bash
cd OEMAccessories

# Auto-discover and use the most recent .xlsx in data/landing_zone/mitsubishi/
python run_mitsubishi.py

# Or specify an explicit path (optional)
python run_mitsubishi.py "data/landing_zone/mitsubishi/Accessory Guide - February26.xlsx"
```

**Output:**

- Combined Excel file in `output/ready_to_upload/mitsubishi/mitsubishi_<run_id>_<timestamp>.xlsx`
  - Contains `_Report` sheet (summary and issues) + model sheets (`{model}_{lang}`)
- DQ report in `output/dq_reports/mitsubishi/dq_report_<run_id>_<timestamp>.json`
- Pipeline log in `output/pipeline_logs/mitsubishi/pipeline_<run_id>_<timestamp>.log`

### What success looks like

```
[INFO] RUN START | oem=mitsubishi | file=... | run_id=a1b2c3d4
[INFO] SHEET START | sheet=2026 Outlander
[INFO] SHEET COMPLETE | sheet=2026 Outlander | records_in=131 | records_out=1488
...
[INFO] Combined output saved: output/ready_to_upload/mitsubishi/mitsubishi_a1b2c3d4_20260519_150225.xlsx
[INFO] RUN COMPLETE | sheets_processed=11 | sheets_skipped=2
```

---

## Understanding the Output

### 1. Combined output Excel file

- **Location:** `output/ready_to_upload/mitsubishi/mitsubishi_<run_id>_<timestamp>.xlsx`
- **Sheets:**
  - `_Report` (first tab) — Run summary, model profile, and all flagged data quality records
  - `{model}_{lang}` sheets — One sheet per model/language (e.g., `2026_outlander_EN`, `2026_outlander_FR`)
- **Model sheet columns:** `Part`, `Description`, `Comments`, `Price`, `Hours`, `Trim`
- **Model sheet rows:** Only records that passed non-null column validation (null records logged to DQ report)
- **Report sheet sections:**
  - **Run Summary:** run_id, source file, timestamp, sheets processed/skipped, total DQ warnings
  - **Model Profile:** one row per model with record counts and DQ warning count
  - **DQ Records:** all flagged issues with part numbers and descriptions for quick review

### 2. DQ Report (JSON)

- **Location:** `output/dq_reports/mitsubishi/dq_report_<run_id>_<timestamp>.json`
- **Audience:** Data stewards, stakeholders
- **Content:** All data quality issues found (null values, profitability problems, trim issues)
- **Interpretation:** See [dq_report_guide.md](docs/dq_report_guide.md)

### 3. Pipeline Log (text)

- **Location:** `output/pipeline_logs/mitsubishi/pipeline_<run_id>_<timestamp>.log`
- **Audience:** Developers, operations
- **Content:** Execution events, sheet start/stop, record counts, FATAL errors
- **Use:** Debugging why a sheet was skipped, audit trail

---

## Adding a New OEM

The pipeline is designed for multiple OEMs. Each new OEM requires:

1. **Config file:** Define business rules for column matching, data validation, output mapping

   - See [config_schema.md](docs/config_schema.md) for the full reference
   - Example: `oems/mitsubishi/config/mitsubishi_config.json`
2. **Orchestrator:** Minimal file that calls the base pipeline

   - Example: `oems/mitsubishi/pipeline/orchestrator.py`
3. **Entry point:** Simple script that instantiates the orchestrator

   - Example: `run_mitsubishi.py`

**Typical effort:** 1-2 hours (write the config, reuse all core logic).

See `DECISIONS.md` for the architectural reasoning.

---

## Key Files for Different Roles

| Role                                      | Start here                                  |
| ----------------------------------------- | ------------------------------------------- |
| **Developer adding a new OEM**      | `docs/config_schema.md`                   |
| **Reviewing output**                | `docs/dq_report_guide.md`                 |
| **Maintaining core logic**          | `DECISIONS.md`, then the `core/` folder |
| **Operations running the pipeline** | "Running a Pipeline" section above          |

---

## Documentation

- **[DECISIONS.md](DECISIONS.md)** — Why things were built the way they are
- **[CHANGELOG.md](CHANGELOG.md)** — What changed between versions
- **[docs/config_schema.md](docs/config_schema.md)** — Reference for the OEM config JSON
- **[docs/dq_report_guide.md](docs/dq_report_guide.md)** — How to interpret DQ reports
