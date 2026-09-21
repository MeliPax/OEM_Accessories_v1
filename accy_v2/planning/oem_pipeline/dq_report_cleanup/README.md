# DQ Report Cleanup: csv_uniqueness_rule Noise Filtering

## Overview

This planning folder addresses the issue of `csv_uniqueness_rule` warnings cluttering DQ export documents. These warnings are operational noise (duplicate detection from ADS refresh cycles) and should be filtered out of stakeholder-facing reports while remaining in pipeline logs for debugging.

## Current Issue

- **Genesis 2026-09-08 example:** 39 total warnings, of which 30 are `csv_uniqueness_rule` (noise)
- Only 9 warnings are actionable (model lookup failures, data gaps)
- Noise obscures real issues in reports

## Solution

Filter `csv_uniqueness_rule` from DQ export documents at report generation time, while keeping it in pipeline logs.

- **Scope:** Minimal code change (DQLogger.write_dq_report())
- **Impact:** DQ reports show only actionable issues
- **Backward Compatible:** New metadata field, same JSON structure

## Files in This Folder

- **PLAN_CSV_UNIQUENESS_NOISE_FILTERING.md** — Full plan with implementation options, verification steps, and questions for review

## Status

⏳ **PLANNING** — Awaiting approval before implementation

## Next Steps

1. Review plan and decide on Option A (Filter at Report Generation) vs Option B (Tag at Log Time)
2. Implement chosen approach
3. Run full pipeline verification across all 4 OEMs
4. Update documentation
5. Merge to dev/main

