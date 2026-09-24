# Project Requirements: Honda Pipeline Modernization
**Version:** 2.0  
**Date:** 2026-09-24  
**Status:** Step 1 Complete, Step 2+ Requirements Formalized

---

## Executive Summary

The Honda pipeline modernization project is implementing a **production-grade OEM data accessory processing pipeline** integrated with the accy_v2 system. Step 1 (validation) is complete; Step 2-6 proceeding with formalized architecture principles.

**Key Principle:** Config-driven, modular, observable, testable, resilient.

---

## Part 1: Core Requirements

### 1.1 Functional Requirements

#### Step 1: Validation (COMPLETE)
| Req | Description | Status | Test |
|-----|-----------|--------|------|
| 1.1.1 | Load EN (_APP_EN) and FR (_APP_FR) sheets from Excel | ✅ | PASS |
| 1.1.2 | Extract model name and year using two-level fallback (L1: quick scan, L2: regex) | ✅ | PASS |
| 1.1.3 | Detect all 6 sections in order; FATAL if missing; WARNING if out-of-order | ✅ | PASS |
| 1.1.4 | Validate column headers per section; extract trim columns after "Installed Price" | ✅ | PASS |
| 1.1.5 | Consolidate warnings with severity sorting (FATAL → ERROR → WARNING) | ✅ | PASS |
| 1.1.6 | Return tuple: ((en_df, fr_df), metadata_dict, dq_warnings_list) | ✅ | PASS |

#### Step 2-6: Future Steps (PLANNED)
| Req | Description | Status | Timeline |
|-----|-----------|--------|----------|
| 1.2.1 | Header normalization and section extraction | ⏳ | Week 2 |
| 1.2.2 | Data standardization and packages/kits rollup | ⏳ | Week 3 |
| 1.2.3 | EN/FR reconciliation with divergence tracking | ⏳ | Week 3-4 |
| 1.2.4 | Model lookup enrichment via VehicleSearchEngine | ⏳ | Week 4-5 |
| 1.2.5 | Output generation and DQ reporting | ⏳ | Week 5-6 |

---

### 1.2 Non-Functional Requirements

#### Configuration Management
- **Req 1.2.1:** All domain-specific values MUST be config-driven, not hardcoded
  - Column names, mappings, markers → section_patterns.yaml
  - Trim extraction settings → trim_config.yaml
  - Metadata keywords → pipeline.yaml
  - Code accepts no hardcoded Honda-specific strings
  
- **Req 1.2.2:** Config MUST be validated on load
  - JSONSchema validation
  - Type checking (string, int, bool, enum)
  - Semantic validation (year ranges, numeric bounds)
  - Detailed error messages on validation failure

- **Req 1.2.3:** Config MUST be versioned
  - Each config file includes `metadata.config_version`
  - Semantic versioning (major.minor.patch)
  - Compatibility tracking (`compatible_with: ">=1.0,<2.0"`)
  - Migration path for major version changes

#### Error Handling & Resilience
- **Req 1.2.4:** Transient errors MUST be retried
  - I/O errors: file locked, disk full → retry up to 3 times
  - Exponential backoff (1s, 2s, 4s)
  - Validation errors: NOT retried (fail immediately)

- **Req 1.2.5:** Partial success MUST be tracked
  - Record which parts succeeded, which failed
  - Allow downstream systems to use partial results where safe
  - Never silently drop successful work due to one failure

- **Req 1.2.6:** Severity levels MUST be enforced
  - FATAL: Stop processing immediately, return error
  - ERROR: Log error, continue processing, mark in DQ
  - WARNING: Log warning, continue processing, note in output

#### Observability & Instrumentation
- **Req 1.2.7:** All logs MUST be structured
  - JSON format with consistent schema
  - Always include: timestamp, correlation_id, step, severity, message
  - No free-text logging (unstructured)

- **Req 1.2.8:** Processing MUST be traceable with correlation ID
  - Unique ID assigned per file (or per batch)
  - Passed through all functions and logged
  - Enables: grep logs → see full file journey

- **Req 1.2.9:** Performance MUST be measured
  - Every major step timed (load, metadata, sections, columns, DQ)
  - Duration logged as structured event
  - Baseline established: load < 1s, total < 5s per file

#### Testability & Data Contracts
- **Req 1.2.10:** Input MUST be validated against schema
  - Check before processing: sheets exist, data present, structure valid
  - Reject invalid files immediately (don't process)
  - Provide specific error for each validation failure

- **Req 1.2.11:** Output MUST match contract
  - All output fields guaranteed present
  - Types guaranteed (dict, list, string, int)
  - Validation_status always present and valid

- **Req 1.2.12:** Regressions MUST be preventable
  - Regression test suite for each bug fix
  - Real Honda data used in tests (not just synthetic)
  - Tests run on every build

#### Modularity & Extensibility
- **Req 1.2.13:** Code MUST NOT be Honda-specific in core paths
  - Generic validation logic applicable to other OEMs
  - Honda-specific rules isolated in config or Honda-specific modules
  - No "if oem == 'honda'" in shared code

- **Req 1.2.14:** Adding new OEM SHOULD NOT require code changes
  - Provide config files following same schema
  - Use existing orchestrator and validators
  - Test with sample data

#### Deployment & Operations
- **Req 1.2.15:** Deployment MUST be documented
  - Step-by-step guide for dev, staging, prod
  - Configuration loading process explicit
  - Rollback procedure defined

- **Req 1.2.16:** Operational support MUST be provided
  - On-call runbook for common errors
  - Alerting thresholds documented
  - Escalation procedure defined

---

## Part 2: Architecture Principles

### 2.1 Config-Driven Design
**Principle:** Domain knowledge lives in config files, not code.

**Rationale:** 
- Enables non-engineers to adjust OEM-specific rules
- Supports multiple OEMs without code duplication
- Allows runtime configuration changes

**Application:**
- Column names, mappings → config/section_patterns.yaml
- Trim extraction rules → config/trim_config.yaml
- Error handling strategy → config/pipeline.yaml
- All code paths accept config as parameter

**Enforcement:**
- Code review: Reject hardcoded values (will fail linter)
- No string literals matching column names, section names, etc.
- ConfigError raised if required config missing at startup

### 2.2 Progressive Validation
**Principle:** Validate early and often; fail fast on fatal errors.

**Rationale:**
- Catch problems at boundary before deep processing
- Don't waste resources on invalid data
- Provide clear feedback on what's wrong

**Application:**
- Validate input at ingestion (schema)
- Validate metadata early (model name, year)
- Validate sections before processing columns
- Check invariants after each step

**Enforcement:**
- ValidationError raised before processing starts if schema invalid
- FATAL errors stop processing immediately
- DQ report generated even on failures (not lost)

### 2.3 Structured Observability
**Principle:** All logs are structured, machine-readable, and traceable.

**Rationale:**
- Production debugging requires structured context
- Correlation IDs enable end-to-end tracing
- Metrics enable alerting and dashboards

**Application:**
- JSON logging format (not text)
- Correlation ID on every event
- Step and duration on every major operation
- Metrics exported for monitoring

**Enforcement:**
- Code review: Reject print() and unstructured logging
- Logging tests verify JSON format
- CI builds fail if correlation ID missing in logs

### 2.4 Testability First
**Principle:** Code is designed to be testable; contracts are explicit.

**Rationale:**
- Makes regressions detectable
- Enables confidence in changes
- Reduces need for manual testing

**Application:**
- Input/output schemas defined and validated
- Unit tests for each part
- Integration tests for full pipeline
- Regression tests for each bug

**Enforcement:**
- Coverage target: > 80%
- New code requires tests before merge
- Regressions trigger test addition

### 2.5 OEM-Agnostic Core
**Principle:** Shared code works for any OEM; OEM-specific logic isolated.

**Rationale:**
- Reduces maintenance burden
- Enables faster OEM onboarding
- Promotes code reuse

**Application:**
- Validation framework: generic, config-driven
- Parts 1-6 work for Honda, Hyundai, Mazda, etc.
- OEM-specific validators inherit from base class
- Config files define OEM differences

**Enforcement:**
- No "if oem == 'honda'" in shared code paths
- New validators must extend base class
- Linter checks for OEM-specific strings

---

## Part 3: Quality Gates

### 3.1 Code Quality
| Check | Standard | Enforcement |
|-------|----------|------------|
| Coverage | > 80% | CI blocks merge if < 80% |
| Linting | PEP8 + custom rules | Pre-commit hook |
| Type Hints | 100% for public functions | Mypy on CI |
| Hardcoded Values | Zero | Linter rule |
| Docstrings | All public functions | Linter rule |

### 3.2 Testing
| Test Type | Coverage | When |
|-----------|----------|------|
| Unit | All parts (1-6) | Every commit |
| Integration | Full pipeline | Every commit |
| Regression | All past bugs | Every commit |
| Real Data | Sample Honda files | Before release |
| Performance | < 5s per file | Weekly |

### 3.3 Configuration
| Check | Standard | When |
|-------|----------|------|
| Schema Validation | Must pass JSONSchema | On load |
| Required Keys | All present | On load |
| Type Checking | Correct types | On load |
| Value Ranges | Min/max validated | On load |
| Semantic Check | Domain rules valid | On load |

### 3.4 Documentation
| Deliverable | When | Reviewed By |
|------------|------|------------|
| API Contract | With feature | Tech lead |
| Architecture Decision | Before implementation | Architect |
| Completion Report | After phase | Project lead |
| On-Call Runbook | Before prod | Operations |

---

## Part 4: Acceptance Criteria

### 4.1 Step 1 (Validation) - COMPLETE ✅

**Acceptance Criteria:**
- [x] All 6 parts implemented and tested
- [x] Handles sparse Excel files correctly
- [x] Two-level metadata extraction working
- [x] All sections detected with order validation
- [x] Column headers validated per section
- [x] Trim columns extracted and deduplicated
- [x] Warnings consolidated with severity sorting
- [x] End-to-end test PASSING with realistic data
- [x] Code review APPROVED
- [x] Config-driven (no hardcoded values)
- [x] Structured logging implemented
- [x] Error handling strategy clear
- [x] Correlation IDs on all events
- [x] Input/output schemas defined
- [x] Completion report created

**Status:** ✅ READY FOR STEP 2

---

### 4.2 Step 2 (Standardization) - IN PROGRESS

**Acceptance Criteria:**
- [ ] Header normalization implemented (extract section headers)
- [ ] Data cleanup (trim, type coercion, null handling)
- [ ] Packages/kits parent-child detection
- [ ] Rollup aggregation logic (children → parent)
- [ ] EN/FR divergence tracking
- [ ] Tests: Unit, integration, real data
- [ ] Code review: APPROVED
- [ ] Config-driven: All rules in config
- [ ] Observability: Structured logging, timing
- [ ] Performance: < 3s per file
- [ ] Completion report created

**Expected Timeline:** Week 2-3

---

### 4.3 Steps 3-6 (Future) - PLANNED

*See HONDA_PIPELINE_MODERNIZATION.md for detailed breakdown*

---

## Part 5: Success Metrics

### 5.1 Quality Metrics
- Test coverage: > 80%
- Critical bugs in prod: 0 per month
- Configuration errors: 0 (caught at load)
- Regressions: 0 (regression tests prevent)

### 5.2 Performance Metrics
- Step 1 latency: < 5 seconds per file
- Step 2 latency: < 10 seconds per file
- Batch throughput: 100 files / minute
- Memory per file: < 500 MB

### 5.3 Reliability Metrics
- Availability: 99.9%
- Error rate: < 1% (recoverable + fatal)
- Mean time to detect (MTTR): < 5 minutes
- Mean time to recover (MTTR): < 15 minutes

### 5.4 Operational Metrics
- Time to onboard new OEM: 2-3 days (config only)
- Time to fix bug: 2-4 hours (config) or 4-8 hours (code)
- Time to deploy: < 30 minutes

---

## Part 6: Constraints & Assumptions

### 6.1 Constraints
- Must integrate with existing accy_v2 system
- Must use VehicleSearchEngine for model lookup
- Must output Excel format (for downstream)
- Must run on Windows PowerShell and Linux bash

### 6.2 Assumptions
- Excel files are valid (checked at boundary)
- Metadata always present (Section 1)
- All 6 sections present (EN sheet)
- Column headers present (immediately after section)
- Trim columns follow after "Installed Price"

### 6.3 Out of Scope
- Historical data migration
- Real-time processing (batch only)
- Machine learning model inference
- Multi-language support beyond EN/FR

---

## Part 7: Approval & Sign-Off

**Document Owner:** Data Engineering  
**Last Approved:** 2026-09-24  
**Next Review:** After Step 2 completion

| Role | Name | Approval | Date |
|------|------|----------|------|
| Project Lead | TBD | [ ] | |
| Tech Lead | TBD | [ ] | |
| Architect | Claude Code | [x] | 2026-09-24 |
| Operations | TBD | [ ] | |

---

## Appendix A: Configuration Files Reference

### section_patterns.yaml
Defines Honda section structure: 6 sections, column headers, expected columns, trim extraction settings.

### trim_config.yaml
Defines trim applicability markers, extraction rules, tokenization, validation rules.

### pipeline.yaml
Defines error handling strategy, metadata extraction, batch settings, output format, logging.

### reconciliation.yaml
Defines EN/FR sheet matching, composite part number handling, cost tolerance.

---

## Appendix B: Links to Related Documents

- Architecture Review: `accy_v2/planning/ARCHITECTURE_REVIEW.md`
- Step 1 Completion: `accy_v2/planning/oem_pipeline/honda_pipeline_modernization/deliverables/STEP1_COMPLETION_REPORT.md`
- Phase 2 Plan: `accy_v2/planning/oem_pipeline/honda_pipeline_modernization/PLAN.md` (TBD)
- API Reference: `accy_v2/planning/API_REFERENCE.md` (TBD)
- On-Call Runbook: `accy_v2/planning/RUNBOOK.md` (TBD)
