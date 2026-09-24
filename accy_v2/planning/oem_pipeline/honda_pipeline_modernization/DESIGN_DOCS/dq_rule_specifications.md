# DQ Rule Specifications Catalog

**Status:** Design Document (Phase 2)  
**Used By:** Step 1–7 (all steps log DQ warnings)  
**Integration:** `accy_v2/core/helpers/dq_logger.py`

---

## Overview

This document defines all Data Quality (DQ) rules for the Honda pipeline. Each rule specifies:
- **Rule Name** — Unique identifier (snake_case)
- **Severity** — INFO, WARNING, ERROR, CRITICAL
- **When It Fires** — Condition triggering the rule
- **What It Means** — User-friendly explanation
- **How to Fix** — Recommended action
- **Message Template** — DQ report format

---

## Validation Rules (Steps 1–2)

### section_missing_rule

| Field | Value |
|-------|-------|
| **Severity** | ERROR |
| **Fires** | When expected section (e.g., "Packages") not found in file |
| **Meaning** | File structure incomplete or corrupted; section identifiers don't match config |
| **Fix** | Verify file section headers match `section_patterns.yaml`; confirm file format |
| **Message Template** | `"Section '{section_name}' (expected '{expected_pattern}') not found in file"` |
| **Example** | `"Section 'Electronics' (expected '2.0 Electronics') not found"` |

### section_count_mismatch_rule

| Field | Value |
|-------|-------|
| **Severity** | WARNING |
| **Fires** | When section count ≠ expected count (default 6) |
| **Meaning** | File has extra or missing sections |
| **Fix** | Review file structure; confirm all 6 sections are present and in order |
| **Message Template** | `"Expected {expected_count} sections, found {actual_count}"` |
| **Example** | `"Expected 6 sections, found 5"` |

### section_order_divergence_rule

| Field | Value |
|-------|-------|
| **Severity** | WARNING |
| **Fires** | When sections appear out of expected order |
| **Meaning** | Sections present but in wrong sequence |
| **Fix** | Reorder sections to match expected order (Packages → Electronics → Interior → Exterior → Cargo → General) |
| **Message Template** | `"Sections out of order: found {actual_order} but expected {expected_order}"` |
| **Example** | `"Sections out of order: found [Packages, Interior, Electronics, ...] but expected [Packages, Electronics, Interior, ...]"` |

### header_not_found_rule

| Field | Value |
|-------|-------|
| **Severity** | ERROR |
| **Fires** | When required column headers not found in section |
| **Meaning** | Section has wrong structure; expected columns missing |
| **Fix** | Verify column names in file match config; check for misspellings or extra columns |
| **Message Template** | `"Section '{section}': Required columns {missing_columns} not found"` |
| **Example** | `"Section 'Packages': Required columns ['Part Number', 'Description'] not found"` |

### orphan_record_rule

| Field | Value |
|-------|-------|
| **Severity** | WARNING |
| **Fires** | When part has no trims marked (all trim columns empty/blank) |
| **Meaning** | Part is not applicable to any trim level; may be incomplete data |
| **Fix** | Add trim applicability markers (•, T, E) for at least one trim; or remove part if not applicable |
| **Message Template** | `"Part '{part_number}' ('{description}') has no trim applicability markers"` |
| **Example** | `"Part '50977-565-45BH' ('Roof Rack') has no trim applicability markers"` |

### invalid_trim_marker_rule

| Field | Value |
|-------|-------|
| **Severity** | WARNING |
| **Fires** | When trim column has unexpected marker (not in applicability_markers or not_applicable_markers) |
| **Meaning** | Data quality issue; unexpected value in applicability column |
| **Fix** | Replace marker with valid value from config (• for applies, blank for not applicable) |
| **Message Template** | `"Part '{part_number}': Trim '{trim}' has invalid marker '{marker}' (expected one of {valid_markers})"` |
| **Example** | `"Part '50977-565-45BH': Trim 'EX-L' has invalid marker 'X' (expected one of ['•', 'T', 'E', ' ', '', 'N/A'])"` |

---

## Rollup Rules (Step 3)

### rollup_verification_rule

| Field | Value |
|-------|-------|
| **Severity** | WARNING |
| **Fires** | When parent rollup child count doesn't match aggregated parts |
| **Meaning** | Package rollup may have lost or duplicated parts |
| **Fix** | Review parent-child relationships in source file; verify all children were captured |
| **Message Template** | `"Package '{parent_desc}': Expected {expected_child_count} child parts, rolled up {actual_child_count}"` |
| **Example** | `"Package 'All-Weather Mats': Expected 4 child parts, rolled up 3"` |

### parent_child_trim_mismatch_rule

| Field | Value |
|-------|-------|
| **Severity** | WARNING |
| **Fires** | When any child part has different trim applicability than parent |
| **Meaning** | Child trim coverage differs from parent; may indicate data inconsistency |
| **Fix** | Review child trims; either align with parent or separate into different package |
| **Message Template** | `"Package '{parent_desc}': Parent has trims {parent_trims}, but child '{child_desc}' has {child_trims}"` |
| **Example** | `"Package 'Weather Mats': Parent has trims [EX-L, Touring], but child 'Front Mats' has [EX-L]"` |

### parent_missing_numeric_rule

| Field | Value |
|-------|-------|
| **Severity** | WARNING |
| **Fires** | When parent row has missing numeric value (price, labor hours, etc.) but children have values |
| **Meaning** | Package cost/labor may be incomplete |
| **Fix** | Fill in parent numeric values; or verify children's values are correct and complete |
| **Message Template** | `"Package '{parent_desc}': Parent {field} is empty, but children have values"` |
| **Example** | `"Package 'Wheel & Tire Package': Parent price is empty, but children have prices"` |

---

## Reconciliation Rules (Step 4)

### en_fr_divergence_rule

| Field | Value |
|-------|-------|
| **Severity** | WARNING |
| **Fires** | When EN and FR records have different cost or part count |
| **Meaning** | EN and FR data don't align; may indicate pricing or availability differences |
| **Fix** | Confirm with partner; verify pricing and part lists are identical EN/FR |
| **Message Template** | `"Part '{part_number}': EN/FR {field} diverges (EN: {en_value}, FR: {fr_value})"` |
| **Example** | `"Part '50977-565-45BH': EN/FR cost diverges (EN: $29.99, FR: $34.99)"` |

### composite_part_number_normalization_rule

| Field | Value |
|-------|-------|
| **Severity** | INFO |
| **Fires** | When composite part number is normalized (e.g., "A or B" → "A") |
| **Meaning** | Part number had alternatives; left-priority variant was used |
| **Fix** | No action required (FYI only); verify left-priority part is correct if concerned |
| **Message Template** | `"Part normalized: '{original}' → '{normalized}'"` |
| **Example** | `"Part normalized: '50977-565-45BH or 50977-565-45SH' → '50977-565-45BH'"` |

### part_mapping_confidence_rule

| Field | Value |
|-------|-------|
| **Severity** | WARNING |
| **Fires** | When EN/FR part mapping confidence is low (<85%) |
| **Meaning** | EN and FR records matched, but with low confidence; may not be same part |
| **Fix** | Manually verify EN/FR pair is correct; if not, mark for correction |
| **Message Template** | `"Part '{part_number}': EN/FR mapping confidence {confidence}% (threshold: 85%)"` |
| **Example** | `"Part 'ABC-123': EN/FR mapping confidence 72% (threshold: 85%)"` |

### en_only_part_rule

| Field | Value |
|-------|-------|
| **Severity** | INFO |
| **Fires** | When EN part has no FR equivalent |
| **Meaning** | Part available only in English data (common for English-market parts) |
| **Fix** | No action required; verify this is expected (US-only part) |
| **Message Template** | `"Part '{part_number}' ('{description}') found only in EN, no FR equivalent"` |
| **Example** | `"Part '50977-565-45BH' ('Premium Floor Mats') found only in EN"` |

### fr_only_part_rule

| Field | Value |
|-------|-------|
| **Severity** | WARNING |
| **Fires** | When FR part has no EN equivalent |
| **Meaning** | Anomaly; typically all FR parts should have EN equivalents |
| **Fix** | Verify FR data doesn't have extra parts; check for part number typos EN/FR |
| **Message Template** | `"Part '{part_number}' found only in FR, no EN equivalent (anomaly)"` |
| **Example** | `"Part '50977-565-45BH' found only in FR, no EN equivalent"` |

---

## Transformation Rules (Steps 3–4)

### trim_parsing_error_rule

| Field | Value |
|-------|-------|
| **Severity** | WARNING |
| **Fires** | When trim column parsing fails or produces unexpected result |
| **Meaning** | Trim value could not be parsed correctly |
| **Fix** | Verify trim value; check for special characters or encoding issues |
| **Message Template** | `"Trim parsing error for part '{part_number}': {error_message}"` |
| **Example** | `"Trim parsing error for part '50977-565-45BH': Unexpected character 'ü' in trim 'Tñring'"` |

### cost_mismatch_rule

| Field | Value |
|-------|-------|
| **Severity** | WARNING |
| **Fires** | When EN/FR cost variance >15% |
| **Meaning** | Significant price difference between EN and FR versions |
| **Fix** | Confirm pricing is intentional (currency difference?) or correct data error |
| **Message Template** | `"Part '{part_number}': EN/FR cost variance {variance}% (EN: ${en_cost}, FR: ${fr_cost})"` |
| **Example** | `"Part 'ABC-123': EN/FR cost variance 22% (EN: $29.99, FR: $36.99)"` |

### part_count_mismatch_rule

| Field | Value |
|-------|-------|
| **Severity** | WARNING |
| **Fires** | When part availability diverges EN/FR (e.g., EN has 5 parts, FR has 3) |
| **Meaning** | Different number of component parts in EN vs. FR package |
| **Fix** | Verify part lists are complete EN/FR; check for missing parts in one version |
| **Message Template** | `"Package '{description}': EN has {en_count} parts, FR has {fr_count} parts"` |
| **Example** | `"Package 'Weather Mats': EN has 4 parts (front+rear), FR has 2 parts"` |

---

## Model Lookup Rules (Step 4.5)

### model_lookup_not_found_rule

| Field | Value |
|-------|-------|
| **Severity** | ERROR |
| **Fires** | When VehicleSearchEngine returns 0 candidates for trim |
| **Meaning** | Trim/model combination not found in database |
| **Fix** | Verify model and trim are correct; check database for missing model/year entry |
| **Message Template** | `"Model lookup failed: {model_name} {year} {trim} not found in database"` |
| **Example** | `"Model lookup failed: CR-V 2026 Sport not found in database"` |

### model_lookup_low_confidence_rule

| Field | Value |
|-------|-------|
| **Severity** | WARNING |
| **Fires** | When model lookup confidence < 70% |
| **Meaning** | Match found but low confidence; may be wrong vehicle |
| **Fix** | Manually verify model number is correct for trim; check trim spelling |
| **Message Template** | `"Model lookup low confidence: {model_name} {trim} → {model_number} ({confidence}%)"` |
| **Example** | `"Model lookup low confidence: CR-V Sport → CR-V-001 (65%)"` |

### trim_normalization_rule

| Field | Value |
|-------|-------|
| **Severity** | INFO |
| **Fires** | When trim is normalized during lookup (e.g., "CR-V" → "crv") |
| **Meaning** | Trim value transformed for matching |
| **Fix** | No action required; for reference only |
| **Message Template** | `"Trim normalized: '{original}' → '{normalized}'"` |
| **Example** | `"Trim normalized: 'CR-V SE' → 'cr-v se'"` |

---

## Severity Levels

| Severity | Meaning | Action |
|----------|---------|--------|
| **INFO** | Informational only (e.g., normalization happened) | Document; no action needed |
| **WARNING** | Data quality issue; may affect output | Review and verify; fix if possible |
| **ERROR** | Significant issue; part/section may not process | Fix before processing continues |
| **CRITICAL** | File-level failure; entire file may be unusable | Investigate and reprocess |

---

## DQ Report Integration

All rules are logged and aggregated in:
1. **DQ Sheet** in output Excel (per-file, all warnings)
2. **batch_summary_dq.json** (batch-level metrics by rule)
3. **Pipeline logs** (detailed context for each warning)

---

**Status:** Design document (Phase 2)  
**Implementation:** Integrated into pipeline steps (Steps 1–7)  
**Configuration:** Rules enabled/disabled via config (future enhancement)
