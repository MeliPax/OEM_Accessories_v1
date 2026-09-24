# Batch Reporting JSON Schema

**Status:** Design Document (Phase 2)  
**Used By:** Phase 6 (Output & DQ Reporting, Step 5)  
**Output File:** `batch_summary_dq.json`

---

## Overview

The `batch_summary_dq.json` file aggregates metrics and issues across all files in a Honda batch run. It provides a high-level summary for stakeholders and a detailed issue list for triage.

**File Location:** `output/dq_reports/honda/{batch_id}/batch_summary_dq.json`

**Example Batch ID:** `2026-09-23_honda_2026-09`

---

## JSON Schema

### Root Level

```json
{
  "batch_id": "2026-09-23_honda_2026-09",
  "batch_folder": "landing_zone/honda/2026/2026-09/",
  "processing_timestamp": "2026-09-23T14:30:45.123456Z",
  "status": "COMPLETED_WITH_WARNINGS",
  "files_processed": 3,
  "files_failed": 0,
  "files_with_warnings": 2,
  
  "reconciliation_metrics": {...},
  "summary_warnings": {...},
  "files_with_issues": [...],
  
  "metadata": {...}
}
```

---

## Field Definitions

### Batch Metadata

```json
{
  "batch_id": "2026-09-23_honda_2026-09",
  // Unique batch identifier (timestamp + folder name)
  // Format: YYYY-MM-DD_hh-mm-ss_honda_{folder_name}
  
  "batch_folder": "landing_zone/honda/2026/2026-09/",
  // Full path to input folder processed
  
  "processing_timestamp": "2026-09-23T14:30:45.123456Z",
  // ISO 8601 UTC timestamp of batch completion
  
  "status": "COMPLETED_WITH_WARNINGS",
  // One of: COMPLETED_SUCCESS, COMPLETED_WITH_WARNINGS, COMPLETED_WITH_ERRORS, FAILED
  // Rules:
  //   - SUCCESS: All files processed, zero warnings
  //   - WITH_WARNINGS: All files processed, some warnings (no ERRORS/CRITICAL)
  //   - WITH_ERRORS: Some files processed, some warnings/errors
  //   - FAILED: Batch failed (CRITICAL error or >N% failure rate)
  
  "files_processed": 3,
  // Total input files found in batch_folder
  
  "files_failed": 0,
  // Files that failed to process (CRITICAL error)
  
  "files_with_warnings": 2,
  // Files with warnings (but processed successfully)
  
  "processing_duration_seconds": 45.67,
  // Total time to process entire batch
}
```

### Reconciliation Metrics

```json
{
  "reconciliation_metrics": {
    "total_parts": 4500,
    // Total parts across all files
    
    "parts_successfully_mapped": 4450,
    // EN parts that found FR equivalents (successful reconciliation)
    
    "reconciliation_success_rate": 0.9889,
    // Percentage: parts_successfully_mapped / total_parts
    
    "en_only_parts": 30,
    // EN parts with no FR equivalent (not necessarily bad)
    
    "fr_only_parts": 20,
    // FR parts with no EN equivalent (anomaly - should be rare)
    
    "cost_divergence_detected": 12,
    // Parts with EN/FR cost variance >15%
    
    "part_number_divergences": 5,
    // Parts where EN and FR part numbers differ after normalization
    
    "en_fr_record_pairs": 4470,
    // EN/FR pairs successfully created (before filtering by model lookup)
    
    "model_lookup_success_rate": 0.92,
    // Percentage of parts with model_number found
  }
}
```

### Summary Warnings (Rule Aggregation)

```json
{
  "summary_warnings": {
    "rollup_verification_rule": 2,
    // Count of this rule fired across all files
    
    "en_fr_divergence_rule": 5,
    "composite_part_number_normalization_rule": 15,
    "part_mapping_confidence_rule": 0,
    "en_only_part_rule": 30,
    "fr_only_part_rule": 20,
    "trim_parsing_error_rule": 0,
    "cost_mismatch_rule": 8,
    "model_lookup_not_found_rule": 18,
    "model_lookup_low_confidence_rule": 3,
    "trim_normalization_rule": 10,
    // ... (one entry per rule)
    
    "total_warnings": 92
    // Sum of all rule counts
  }
}
```

### Files With Issues (Detail)

```json
{
  "files_with_issues": [
    {
      "filename": "Accord_2027.xlsx",
      // Original input filename
      
      "model": "Accord",
      "year": 2027,
      // Extracted model and year
      
      "status": "PROCESSED_WITH_WARNINGS",
      // One of: SUCCESS, PROCESSED_WITH_WARNINGS, FAILED
      
      "warning_count": 8,
      // Total warnings for this file
      
      "error_count": 0,
      // Total errors (non-blocking)
      
      "critical_count": 0,
      // Total critical errors (would block processing if found)
      
      "rows_processed": 450,
      // Rows input to pipeline
      
      "rows_output": 440,
      // Rows in final output (filtered by model_lookup_success)
      
      "processing_time_seconds": 12.5,
      // Time to process this file
      
      "reconciliation_metrics": {
        "en_fr_mapping_success": 0.98,
        "model_lookup_success": 0.95,
        // File-level metrics (subset of batch metrics)
      },
      
      "top_issues": [
        {
          "rule": "en_fr_divergence_rule",
          "count": 3,
          "example": "Part '50977-565-45BH': EN/FR cost diverges (EN: $29.99, FR: $34.99)"
        },
        {
          "rule": "model_lookup_not_found_rule",
          "count": 2,
          "example": "Model lookup failed: Accord 2027 Sport not found"
        }
      ],
      
      "recommended_action": "Review EN/FR cost mismatches; confirm pricing with partner"
      // Actionable suggestion for stakeholder
    },
    
    {
      "filename": "CR-V_2027.xlsx",
      "model": "CR-V",
      "year": 2027,
      "status": "PROCESSED_WITH_WARNINGS",
      "warning_count": 4,
      // ... (similar structure)
    }
  ]
}
```

### Metadata

```json
{
  "metadata": {
    "pipeline_version": "2.7.0",
    // Honda pipeline version
    
    "accy_v2_version": "2.5.1",
    // Core accy_v2 version
    
    "processor": "claude-code",
    // Who/what processed the batch
    
    "configuration": {
      "quarantine_threshold": 0.10,
      "section_count": 6,
      "enable_en_fr_reconciliation": true
      // Relevant config settings
    },
    
    "known_limitations": [
      "EN/FR sheet encoding assumed UTF-8",
      "Model lookup failures flagged but not blocking"
    ]
  }
}
```

---

## Complete Example

```json
{
  "batch_id": "2026-09-23_093045_honda_2026-09",
  "batch_folder": "landing_zone/honda/2026/2026-09/",
  "processing_timestamp": "2026-09-23T14:30:45.123456Z",
  "status": "COMPLETED_WITH_WARNINGS",
  "files_processed": 3,
  "files_failed": 0,
  "files_with_warnings": 2,
  "processing_duration_seconds": 45.67,
  
  "reconciliation_metrics": {
    "total_parts": 4500,
    "parts_successfully_mapped": 4450,
    "reconciliation_success_rate": 0.9889,
    "en_only_parts": 30,
    "fr_only_parts": 20,
    "cost_divergence_detected": 12,
    "part_number_divergences": 5,
    "model_lookup_success_rate": 0.92
  },
  
  "summary_warnings": {
    "rollup_verification_rule": 2,
    "en_fr_divergence_rule": 12,
    "composite_part_number_normalization_rule": 15,
    "part_mapping_confidence_rule": 0,
    "en_only_part_rule": 30,
    "fr_only_part_rule": 20,
    "trim_parsing_error_rule": 0,
    "cost_mismatch_rule": 8,
    "model_lookup_not_found_rule": 18,
    "model_lookup_low_confidence_rule": 3,
    "trim_normalization_rule": 10,
    "total_warnings": 118
  },
  
  "files_with_issues": [
    {
      "filename": "Accord_2027.xlsx",
      "model": "Accord",
      "year": 2027,
      "status": "PROCESSED_WITH_WARNINGS",
      "warning_count": 8,
      "error_count": 0,
      "critical_count": 0,
      "rows_processed": 450,
      "rows_output": 440,
      "processing_time_seconds": 12.5,
      "reconciliation_metrics": {
        "en_fr_mapping_success": 0.98,
        "model_lookup_success": 0.95
      },
      "top_issues": [
        {
          "rule": "en_fr_divergence_rule",
          "count": 3,
          "example": "Part '50977-565-45BH': EN/FR cost diverges (EN: $29.99, FR: $34.99)"
        },
        {
          "rule": "model_lookup_not_found_rule",
          "count": 2,
          "example": "Model lookup failed: Accord 2027 Sport not found"
        },
        {
          "rule": "cost_mismatch_rule",
          "count": 3,
          "example": "Part 'ABC-123': EN/FR cost variance 22% (EN: $29.99, FR: $36.99)"
        }
      ],
      "recommended_action": "Review EN/FR cost mismatches; confirm part availability with partner"
    },
    {
      "filename": "CR-V_2027.xlsx",
      "model": "CR-V",
      "year": 2027,
      "status": "PROCESSED_WITH_WARNINGS",
      "warning_count": 4,
      "error_count": 0,
      "critical_count": 0,
      "rows_processed": 500,
      "rows_output": 495,
      "processing_time_seconds": 14.2,
      "reconciliation_metrics": {
        "en_fr_mapping_success": 0.99,
        "model_lookup_success": 0.90
      },
      "top_issues": [
        {
          "rule": "model_lookup_not_found_rule",
          "count": 4,
          "example": "Model lookup failed: CR-V 2027 Sport not found in database"
        }
      ],
      "recommended_action": "Verify CR-V 2027 Sport trim in database; may require ADS refresh"
    }
  ],
  
  "metadata": {
    "pipeline_version": "2.7.0",
    "accy_v2_version": "2.5.1",
    "processor": "claude-code",
    "configuration": {
      "quarantine_threshold": 0.10,
      "section_count": 6,
      "enable_en_fr_reconciliation": true
    },
    "known_limitations": [
      "EN/FR sheet encoding assumed UTF-8",
      "Model lookup failures flagged but not blocking; use ADS refresh for missing years"
    ]
  }
}
```

---

## JSON Schema Validation

**JSON Schema (Draft 7):**

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Honda Batch DQ Report",
  "type": "object",
  "required": [
    "batch_id",
    "batch_folder",
    "processing_timestamp",
    "status",
    "files_processed",
    "reconciliation_metrics",
    "summary_warnings"
  ],
  "properties": {
    "batch_id": { "type": "string" },
    "batch_folder": { "type": "string" },
    "processing_timestamp": { "type": "string", "format": "date-time" },
    "status": { "enum": ["COMPLETED_SUCCESS", "COMPLETED_WITH_WARNINGS", "COMPLETED_WITH_ERRORS", "FAILED"] },
    "files_processed": { "type": "integer", "minimum": 0 },
    "files_failed": { "type": "integer", "minimum": 0 },
    "files_with_warnings": { "type": "integer", "minimum": 0 },
    "processing_duration_seconds": { "type": "number", "minimum": 0 }
  }
}
```

---

## Usage

### For Stakeholders (Partners)

- Review `status` and `summary_warnings` at a glance
- Check `files_with_issues[].recommended_action` for next steps
- Drill into specific file's `top_issues` if needed

### For Operations/CI/CD

- Alert if `status` = "FAILED" or files_failed > 0
- Archive JSON with output Excel files for audit trail
- Feed metrics to dashboards/alerts

### For Debugging

- Use `files_with_issues[].processing_time_seconds` to identify slow files
- Check `reconciliation_metrics.model_lookup_success_rate` to gauge database coverage
- Correlate specific rules in `summary_warnings` with pattern of failures

---

**Status:** Design document (Phase 2)  
**Implementation:** Phase 6 (Output & DQ Reporting, Step 5)  
**File Format:** JSON (machine-readable, human-readable, easily parsed)
