# Automated Checks Specification

**Document:** Planning  
**Created:** June 26, 2026  
**Status:** Draft - For Review  
**Related:** `01_CI_CD_STRATEGY.md`

---

## Overview

This document specifies each automated check that runs during CI/CD pipeline, including the tool, configuration, and expected behavior.

**Key Principle:** Checks run locally (developer can run same checks before push) and in CI (before merge).

---

## Check Groups

All checks are organized by category and run **on every push** to any branch.

---

## 1. Code Style & Format Checks

### 1.1 Linting (flake8)

**Tool:** `flake8` (linter for PEP 8 style violations)

**Config File:** `.flakeo8`

**What it checks:**
- PEP 8 style violations (line length, indentation, spacing)
- Unused imports
- Undefined names
- Syntax errors

**Triggers failure:** Any violation (unless specifically ignored)

**Local run:**
```bash
flake8 accy_v2/
```

**CI run:** Automatic on push

**Estimated time:** <5 seconds

**Ignore patterns:**
- `E501` (line too long) — handled by Black
- `W503` (line break before binary operator) — modern style

---

### 1.2 Code Formatting (black)

**Tool:** `black` (opinionated code formatter)

**Config File:** `pyproject.toml` (under `[tool.black]`)

**What it checks:**
- Consistent indentation (4 spaces)
- Quote style (double quotes)
- Line length (88 chars)
- Trailing commas in multi-line constructs

**Triggers failure:** File not formatted per Black style

**Local run:**
```bash
black --check accy_v2/
```

**Auto-fix locally:**
```bash
black accy_v2/
```

**CI run:** Automatic on push (fails if not formatted)

**Estimated time:** <5 seconds

**Config target:**
```toml
[tool.black]
line-length = 88
target-version = ['py39']
include = '\.pyi?$'
extend-exclude = '''
^/tests/fixtures/
'''
```

---

### 1.3 Import Sorting (isort)

**Tool:** `isort` (sorts and organizes imports)

**Config File:** `pyproject.toml` (under `[tool.isort]`)

**What it checks:**
- Imports organized in standard order: stdlib → third-party → local
- No duplicate imports
- Consistent import formatting

**Triggers failure:** Imports not sorted correctly

**Local run:**
```bash
isort --check-only accy_v2/
```

**Auto-fix locally:**
```bash
isort accy_v2/
```

**CI run:** Automatic on push (fails if not sorted)

**Estimated time:** <5 seconds

**Config target:**
```toml
[tool.isort]
profile = "black"
multi_line_mode = 3
include_trailing_comma = true
line_length = 88
```

---

## 2. Type Checking

### 2.1 Type Hints (mypy)

**Tool:** `mypy` (static type checker)

**Config File:** `mypy.ini`

**What it checks:**
- Functions have proper type hints
- Type mismatches detected
- Missing optional[] for nullable values
- Incompatible assignments

**Triggers failure:** Type errors or missing type hints

**Local run:**
```bash
mypy accy_v2/
```

**CI run:** Automatic on push

**Estimated time:** 10-15 seconds

**Config target:**
```ini
[mypy]
python_version = 3.9
warn_return_any = True
warn_unused_configs = True
ignore_missing_imports = True
strict_optional = True
warn_redundant_casts = True
warn_no_return = True
```

**Exemptions:** Third-party libraries with no type stubs can be ignored

---

## 3. Unit Tests

### 3.1 Test Execution (pytest)

**Tool:** `pytest` (unit test framework)

**Config File:** `pytest.ini`

**What it checks:**
- All unit tests pass
- Code coverage meets threshold (>80%)
- No test collection errors
- Assertions pass

**Triggers failure:**
- Any test fails
- Coverage < 80%
- Collection errors

**Local run:**
```bash
pytest accy_v2/tests/unit/ -v --cov=accy_v2 --cov-report=term
```

**CI run:** Automatic on push

**Estimated time:** 15-20 seconds

**Test structure:**
```
accy_v2/tests/
├── unit/
│   ├── test_column_mapper.py
│   ├── test_dq_logger.py
│   ├── test_mitsubishi_step1.py
│   ├── test_mitsubishi_step2.py
│   ├── test_mitsubishi_step3.py
│   ├── test_mitsubishi_step4.py
│   ├── test_mitsubishi_step5.py
│   └── test_mazda_*.py
└── fixtures/
    ├── sample_data.xlsx
    ├── sample_config.json
    └── expected_output.json
```

**Config target:**
```ini
[pytest]
testpaths = accy_v2/tests/unit
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --strict-markers --tb=short
```

---

## 4. Integration Tests

### 4.1 End-to-End Pipeline Tests

**Tool:** `pytest` (integration test suite)

**Trigger:** Only on merge to staging (not on every push)

**What it checks:**
- Mitsubishi pipeline with sample data succeeds
- Mazda pipeline with sample data succeeds
- Output files have correct schema
- DQ report structure correct
- No unexpected regressions

**Local run:**
```bash
pytest accy_v2/tests/integration/ -v --timeout=60
```

**CI run:** On merge to staging only (takes longer)

**Estimated time:** 30-45 seconds

**Test data:** Small sample files (20-30 rows, fake pricing data)

---

## 5. Security Scanning

### 5.1 Secret Detection (detect-secrets)

**Tool:** `detect-secrets` (finds hardcoded secrets)

**Config File:** `.secretsignore`

**What it checks:**
- No AWS keys, API tokens, passwords
- No database connection strings
- No private keys

**Triggers failure:** Secret detected

**Local run:**
```bash
detect-secrets scan --baseline .secrets.baseline
```

**CI run:** Automatic on push

**Estimated time:** <5 seconds

---

### 5.2 Dependency Vulnerabilities (Safety)

**Tool:** `safety` (checks for known vulnerabilities in dependencies)

**What it checks:**
- All pip packages checked against security database
- Known CVEs detected
- Outdated package versions flagged

**Triggers failure:** Medium+ severity vulnerability found

**Local run:**
```bash
safety check --json
```

**CI run:** Automatic on push (weekly update of security DB)

**Estimated time:** 5-10 seconds

---

### 5.3 Code Security Analysis (bandit)

**Tool:** `bandit` (scans for common security issues)

**Config File:** `.bandit`

**What it checks:**
- Hardcoded passwords/secrets
- SQL injection vectors
- Insecure deserialization
- Use of exec/eval
- Weak random generation

**Triggers failure:** High severity issue found

**Local run:**
```bash
bandit -r accy_v2/ -f json
```

**CI run:** Automatic on push

**Estimated time:** <5 seconds

**Config target:**
```yaml
# .bandit
exclude_dirs:
  - /tests/
  - /fixtures/
skips: []
```

---

## 6. Documentation Checks

### 6.1 Docstring Validation (pydocstyle)

**Tool:** `pydocstyle` (checks docstring format)

**What it checks:**
- Functions have docstrings
- Docstrings follow PEP 257 convention
- Docstrings are not empty

**Triggers failure:** Missing or malformed docstrings

**Local run:**
```bash
pydocstyle accy_v2/ --ignore=D100,D101,D102
```

**CI run:** Automatic on push (warnings only, not failures)

**Estimated time:** <5 seconds

**Ignore rules:**
- `D100` — Missing module docstring (optional for __init__.py)
- `D101` — Missing class docstring (okay for simple classes)

---

### 6.2 README & CHANGELOG Validation

**Tool:** Custom Python script

**What it checks:**
- CHANGELOG.md mentions changes made in this PR
- README.md links to relevant documentation
- No broken links in documentation

**Triggers failure:** If PR adds code but doesn't update docs

**Local run:**
```bash
python scripts/validate_docs.py
```

**CI run:** Automatic on PR to staging/main (not on every push)

**Estimated time:** <5 seconds

---

## 7. Data Quality Validation

### 7.1 Pipeline Smoke Test

**Tool:** Custom Python script

**Trigger:** On merge to staging

**What it checks:**
- Pipeline runs without FATAL errors on sample data
- Output file generated with correct sheet names
- DQ report generated in valid JSON format
- No new DQ warning categories introduced

**Local run:**
```bash
python scripts/smoke_test.py
```

**CI run:** On merge to staging

**Estimated time:** 20-30 seconds

---

## Run Time Summary

| Check | Time | Trigger |
|-------|------|---------|
| flake8 | <5s | Every push |
| black | <5s | Every push |
| isort | <5s | Every push |
| mypy | 10-15s | Every push |
| pytest (unit) | 15-20s | Every push |
| pytest (integration) | 30-45s | Merge to staging |
| detect-secrets | <5s | Every push |
| safety | 5-10s | Every push |
| bandit | <5s | Every push |
| pydocstyle | <5s | Every push |
| smoke test | 20-30s | Merge to staging |

**Total time (every push):** ~60 seconds  
**Total time (merge to staging):** ~150 seconds (2.5 minutes)

---

## Local Developer Workflow

**Before pushing, run:**

```bash
# Format code
black accy_v2/
isort accy_v2/

# Run checks
flake8 accy_v2/
mypy accy_v2/
pytest accy_v2/tests/unit/ -v --cov=accy_v2

# Run security checks
detect-secrets scan
safety check
bandit -r accy_v2/
```

Or use a pre-commit hook (see `04_DEVELOPER_SETUP.md`).

---

## Questions for Team

- [ ] Are these tools the preferred choices, or do we want alternatives?
- [ ] Should coverage threshold be 80% or higher?
- [ ] Should type hints be required or just "encouraged" (warnings)?
- [ ] Should documentation check block merge or just warn?
- [ ] Do we want pre-commit hooks installed for all developers?

---

**Next Document:** `03_GITHUB_ACTIONS_SETUP.md` — Concrete workflow files  
**Related:** `01_CI_CD_STRATEGY.md`, `05_TEST_STRATEGY.md`
