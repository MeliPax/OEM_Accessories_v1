# Developer Guide: OEM Accessory Pipeline

**Audience:** AI agents, developers, and contributors  
**Purpose:** Provide clear instructions for making code changes while maintaining quality, consistency, and documentation  
**Last Updated:** June 26, 2026

---

## Table of Contents

1. [Before You Start](#before-you-start)
2. [Development Workflow](#development-workflow)
3. [Code Standards](#code-standards)
4. [Documentation Requirements](#documentation-requirements)
5. [Testing & Acceptance](#testing--acceptance)
6. [Git Workflow](#git-workflow)
7. [Quality Checklist](#quality-checklist)

---

## Before You Start

### 1. Understand the Context

Before making any code changes, **read the relevant documentation:**

**Always read:**
- [README.md](README.md) — Project overview and structure
- [DECISIONS.md](DECISIONS.md) — Architectural decisions (understand the WHY)
- [CHANGELOG.md](CHANGELOG.md) — Recent changes and current state

**For specific areas:**
- **Model lookup changes:** → Read [model_lookup/README_VOCABULARY_FILTERING.md](model_lookup/README_VOCABULARY_FILTERING.md)
- **Config changes:** → Read [docs/config_schema.md](docs/config_schema.md)
- **Output/DQ changes:** → Read [docs/dq_report_guide.md](docs/dq_report_guide.md)
- **Adding new OEM:** → Read [docs/adding_new_oem.md](docs/adding_new_oem.md) (if exists)
- **Recent updates:** → Read [UPDATES_YYYY-MM-DD.md](UPDATES_2026-06-26.md) (or [UPDATES_2026-06-23.md](UPDATES_2026-06-23.md))

**Why?** Documentation gives you:
- **Context:** Why this code exists and what problem it solves
- **Constraints:** Assumptions baked into the design
- **Precedent:** How similar changes were done before
- **Tradeoffs:** Why certain approaches were chosen over others

### 2. Clarify Your Task

Before coding, answer:
- [ ] **What problem are you solving?** (e.g., "fix ambiguous model matches")
- [ ] **Why does it matter?** (e.g., "DQ reports show false warnings")
- [ ] **What files will you touch?** (e.g., "step4_5_model_enrichment.py, search_models_by_description()")
- [ ] **What tests exist?** (e.g., "test_exact_matching.py")
- [ ] **Who depends on this?** (e.g., "step4_5 uses search_models_by_description()")

---

## Development Workflow

### Phase 1: Plan Your Changes

#### Step 1.1: Create a Feature Branch

```bash
# From project root
git checkout main
git pull origin main
git checkout -b feature/your-feature-name
```

**Naming convention:**
- `feature/fix-model-ambiguity` — Bug fix
- `feature/add-vocabulary-filtering` — New feature
- `feature/refactor-column-mapper` — Refactoring
- `feature/update-docs` — Documentation only

#### Step 1.2: Document Your Plan

Before you write code, document what you're going to do in a comment at the top of your feature branch:

Create or update a planning doc (e.g., `PLAN_your_feature.md`):

```markdown
# Plan: [Feature Name]

## Problem
[What problem are you solving?]

## Solution
[What's your approach?]

## Files to Change
- file1.py (lines X-Y)
- file2.py (new feature)
- docs/...md (update)

## Tests
- Existing tests: test_X.py
- New tests: test_Y.py
- Manual testing: [steps to verify]

## Documentation Updates
- CHANGELOG.md (Added section)
- README.md (if structure changed)
- docs/... (new guide?)
```

**Why?** Gives you a chance to think through the change before coding.

### Phase 2: Write Code

#### Step 2.1: Follow Code Standards

See [Code Standards](#code-standards) section.

#### Step 2.2: Keep Changes Focused

- **One feature per branch** — Don't mix unrelated changes
- **Make small commits** — "Added vocabulary loading" not "Added vocab + fixed imports + cleaned up"
- **Test as you go** — Don't wait until the end

#### Step 2.3: Update Code As You Go

As you write code:

1. **Add docstrings** to all new functions:
   ```python
   def search_models_by_description(make, year, keywords):
       """
       Search vehicle models by manufacturer, year, and keywords.
       
       Args:
           make: Manufacturer name (e.g., "Mitsubishi")
           year: Model year (int)
           keywords: List of search keywords
           
       Returns:
           DataFrame with matching records
       """
   ```

2. **Comment WHY, not WHAT:**
   ```python
   # Good
   # Excluded EV models unless explicitly searched (user intent)
   if exclude_ev and not any(...):
   
   # Bad
   # Filter EV models
   if exclude_ev and not any(...):
   ```

3. **Use meaningful names:**
   ```python
   # Good
   trim_discriminators = {"premium", "noir", "se", "gt"}
   
   # Bad
   td = {"premium", "noir", "se", "gt"}
   ```

### Phase 3: Test Your Changes

#### Step 3.1: Unit Tests

For new functions, write unit tests:

```python
def test_extract_description_tokens():
    """Test tokenization of vehicle descriptions."""
    result = _extract_description_tokens("Outlander PHEV GT S-AWC")
    assert result == ["outlander", "phev", "gt", "s-awc"]
    
    # Test edge cases
    assert _extract_description_tokens(None) == []
    assert _extract_description_tokens("") == []
```

**Where to put tests:**
- New module → `test_module_name.py` in same directory
- Modified module → Add tests to existing `test_*.py` file
- Integration → Add to existing integration test

#### Step 3.2: Integration Tests

Run tests in context:

```bash
# Test a specific file
python accy_v2/model_lookup/test_exact_matching.py

# Test a specific OEM pipeline
python -c "from accy_v2.oems.mitsubishi.orchestrator import run; run()"

# Test output formatting
python -c "from accy_v2.core.helpers.output_writer import write_combined_output; ..."
```

#### Step 3.3: Manual Testing (Acceptance)

Before finalizing:

1. **Run with real data** (if possible):
   ```bash
   # Place test Excel in data/landing_zone/mitsubishi/
   python accy_v2/oems/mitsubishi/run_mitsubishi.py
   
   # Check outputs
   ls accy_v2/output/ready_to_upload/
   ls accy_v2/output/dq_reports/
   ```

2. **Verify outputs:**
   - [ ] Excel file created
   - [ ] Correct sheets present (model_name_EN, model_name_FR, _Report)
   - [ ] Columns correct (no unwanted columns)
   - [ ] DQ report valid JSON
   - [ ] Pipeline log has no ERRORs

3. **Check side effects:**
   - [ ] Other OEMs still work
   - [ ] Performance acceptable
   - [ ] No new warnings in logs

---

## Code Standards

### File Organization

```
module/
  __init__.py              # Package marker
  module.py               # Main logic
  test_module.py          # Tests
  helpers/
    __init__.py
    helper1.py
    helper2.py
    test_helpers.py
```

### Python Style

**General:**
- Python 3.9+ syntax
- PEP 8 style (use `black` or `autopep8` if available)
- Type hints for function signatures
- Docstrings for all public functions and classes

**Imports:**
- Group: standard library, third-party, local (in that order)
- Sort alphabetically within groups
- One import per line (except: `from X import a, b`)

```python
import json
import os
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
from sqlalchemy import text

from core.helpers.dq_logger import DQLogger
from model_lookup.models.manufacture_module import search_models_by_description
```

**Comments:**
- No docstrings for obvious code
- Comment complex logic and non-obvious decisions
- Update comments when you change code (rotting comments are worse than no comments)

**Error handling:**
- Validate at system boundaries (user input, file I/O, database)
- Trust internal code (don't over-validate between functions)
- Use descriptive error messages

```python
# Good
if not csv_path.exists():
    raise FileNotFoundError(f"Vehicle model database not found: {csv_path}")

# Bad
if not csv_path.exists():
    raise Exception("File not found")
```

### Naming Conventions

| Type | Example | Notes |
|------|---------|-------|
| Functions | `extract_keywords()`, `_private_helper()` | snake_case, underscore prefix for private |
| Classes | `KeywordExtractor`, `PipelineLogger` | PascalCase |
| Constants | `EV_KEYWORDS`, `BATCH_SIZE` | UPPER_SNAKE_CASE |
| Variables | `model_mapping`, `df_filtered` | snake_case, descriptive |
| DataFrame cols | `model_number`, `trim_level` | snake_case |

### Path Handling

**Always use relative paths from script location:**

```python
# Good
csv_path = Path(__file__).parent.parent / "db" / "db_vehicle_models.csv"

# Bad
csv_path = "../../db/db_vehicle_models.csv"  # Breaks if run from different dir
csv_path = "/absolute/path/..."  # Not portable
```

### Logging

Use the pipeline logger for output (not `print()`):

```python
from core.helpers.pipeline_logger import PipelineLogger

logger = PipelineLogger(...)

# Info level
logger.info("Processing sheet: 2026_Outlander_EN")

# Debug level (for developers)
logger.debug(f"Found {len(results)} matching models with keywords={keywords}")

# Warning level (something unexpected but not fatal)
logger.warning(f"No model found for trim {trim}, skipping")

# Error level (fatal)
logger.error(f"Could not load config: {e}")
```

---

## Documentation Requirements

### For Every Change

Update documentation BEFORE committing:

#### 1. Docstrings (In Code)

For new/modified functions:
```python
def search_models_by_description(make, year, keywords):
    """
    Search vehicle models by description keywords with exact trim matching.
    
    Args:
        make: Manufacturer name (e.g., "Mitsubishi")
        year: Model year
        keywords: List of keywords (combined from model name, fuel type, trim)
        
    Returns:
        pd.DataFrame: Matching model records
        
    Raises:
        FileNotFoundError: If CSV database not found
        
    Example:
        >>> results = search_models_by_description("Mitsubishi", 2026, ["outlander", "phev", "gt"])
        >>> len(results)
        1
    """
```

#### 2. README (Project Overview)

Update if:
- [ ] New module/package added
- [ ] Project structure changed
- [ ] Setup/installation changed
- [ ] Running instructions changed

Template:
```markdown
# New Feature Name

Brief description of what it does.

## How to Use

```python
from module import function
result = function(args)
```

## Files
- `file1.py` — What it does
- `file2.py` — What it does
```

#### 3. CHANGELOG.md (Change History)

**Every commit requires a CHANGELOG entry:**

```markdown
### Added
- **New feature name:** Description
  - Subfeature 1: Details
  - Subfeature 2: Details

### Changed
- **Modified feature:** What changed and why

### Fixed
- **Bug name:** What was wrong and how it was fixed
```

**Format:**
- Use present tense: "Added X", "Fixed Y", "Removed Z"
- Be specific: what file(s), what behavior changed
- Include context: why this matters

#### 4. DECISIONS.md (Architectural Decisions)

For significant changes, add a decision record:

```markdown
### [XXX] Feature Name

**Status:** Accepted | Proposed | Deprecated

**Context:**
Why did we face this decision?

**Decision:**
What did we choose?

**Rationale:**
Why this over alternatives?

**Consequences:**
What are the trade-offs?

**Example:**
```python
# Code showing the decision
```
```

#### 5. Specialized Docs

If you add a major subsystem:
- Create `docs/new_system.md`
- Include: Purpose, how to use, examples, troubleshooting
- Link from README.md

Example: [docs/config_schema.md](docs/config_schema.md)

### Commit Messages

**Format:**
```
One-line summary (60 chars)

Detailed explanation if needed (wrap at 80 chars).
Multiple paragraphs OK.

Fixes: [issue number if applicable]
See: [related doc or commit]
```

**Examples:**

```
Fix model lookup ambiguity with vocabulary filtering

When searching for ["outlander", "phev", "gt"], results included
both "Outlander PHEV GT S-AWC" and "Outlander PHEV GT Premium S-AWC".
The second is wrong — "premium" wasn't searched.

Solution: Post-filter results to exclude extra trim discriminators
(premium, noir, se, es, gt) while allowing specification keywords
(fwd, awc, s-awc, manual, cvt) that don't change trim level.

See: IMPLEMENTATION_2026-06-23.md
```

```
Relocate model_lookup into accy_v2

Move model_lookup/ from project root to accy_v2/model_lookup/ for
better code organization. All paths use relative navigation from
script location, so no code changes needed in callers.

Verified: 7 migration tests pass, imports work both ways.
```

---

## Testing & Acceptance

### Test Pyramid

```
           Integration Tests (end-to-end)
          /        |         \
      Unit Tests (functions)
     /    |    \
  Linting
```

### Unit Test Checklist

For new/modified functions:

```
[ ] Happy path (normal input → expected output)
[ ] Edge cases (None, empty, single item)
[ ] Error cases (invalid input → clear error)
[ ] Integration (called from actual code path)
[ ] Performance (acceptable for real data)
```

Example:

```python
def test_search_models_by_description():
    """Test exact keyword matching."""
    
    # Happy path
    results = search_models_by_description("Mitsubishi", 2026, ["outlander", "phev", "gt"])
    assert len(results) == 1
    assert results.iloc[0]["Description"] == "Outlander PHEV GT S-AWC"
    
    # Edge case: missing keyword
    results = search_models_by_description("Mitsubishi", 2026, ["outlander", "phev"])
    assert len(results) > 1  # Multiple GT variants
    
    # Edge case: extra keyword
    results = search_models_by_description("Mitsubishi", 2026, ["outlander", "phev", "gt", "premium"])
    assert len(results) == 1
    assert "Premium" in results.iloc[0]["Description"]
    
    # Error case: no matches
    results = search_models_by_description("Mitsubishi", 2026, ["nonexistent"])
    assert len(results) == 0
```

### Acceptance Testing

Run before submitting PR:

```bash
# 1. Run all tests
python -m pytest accy_v2/

# 2. Run with real data
python accy_v2/oems/mitsubishi/run_mitsubishi.py

# 3. Verify outputs
# - Check Excel files (sheets, columns, data)
# - Check DQ report (valid JSON, correct warnings)
# - Check pipeline log (no errors, expected steps)

# 4. Verify side effects
# - Other OEMs still work
# - Performance acceptable
# - No new warnings/errors in logs
```

### Acceptance Criteria Template

Before submitting PR, verify:

```markdown
## Acceptance Criteria

- [ ] Code follows style guide (docstrings, comments, naming)
- [ ] Unit tests added/updated
- [ ] All tests pass (unit + integration)
- [ ] Manual testing completed with real data
- [ ] No regressions in other modules
- [ ] CHANGELOG.md updated
- [ ] README.md updated (if structure/setup changed)
- [ ] DECISIONS.md updated (if architectural change)
- [ ] Commit messages clear and complete
- [ ] No TODO/FIXME comments left
- [ ] Performance acceptable
```

---

## Git Workflow

### Step 1: Create Feature Branch

```bash
git checkout main
git pull origin main
git checkout -b feature/your-feature-name
```

### Step 2: Make Commits

**As you work:**
```bash
# After each logical chunk of work
git add accy_v2/module1.py accy_v2/docs/feature.md
git commit -m "Add feature X to module1

Detailed explanation of what changed and why.

See: CHANGELOG.md
"
```

**Good commit practices:**
- Commit frequently (not at the end)
- One logical change per commit
- Message explains the WHY
- All tests pass after each commit

### Step 3: Push and Create PR

```bash
# Push your branch
git push origin feature/your-feature-name

# Create PR (using gh CLI)
gh pr create --title "Brief title" --body "$(cat <<'EOF'
## Description
What does this PR do?

## Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing completed

## Checklist
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] No breaking changes
- [ ] Code follows standards

## Screenshots/Examples
[If applicable]
EOF
)"
```

### Step 4: User Review & Approval

**Agent:** Runs tests, shows summary:
```
Test Results:
  ✓ Unit tests: 12/12 pass
  ✓ Integration tests: 3/3 pass
  ✓ Manual testing: Verified with real data
  
Documentation:
  ✓ CHANGELOG.md updated
  ✓ Docstrings added
  ✓ README.md updated

Ready for review.
```

**User:** Reviews PR and approves or requests changes.

### Step 5: Merge to Main

Once approved:

```bash
# On the feature branch
git pull origin main  # Sync with any new main commits
git push origin feature/your-feature-name

# GitHub: Merge via PR UI (Squash or Create merge commit)
# Or locally:
git checkout main
git pull origin main
git merge --no-ff feature/your-feature-name
git push origin main

# Cleanup
git branch -d feature/your-feature-name
git push origin -d feature/your-feature-name
```

### Merge Strategy

**Recommended:** Squash merge (all feature commits → 1 commit on main)

```bash
# Via gh CLI
gh pr merge <PR#> --squash
```

**Or:** Create merge commit (preserves feature branch history)

```bash
git merge --no-ff feature/your-feature-name
```

**Avoid:** Fast-forward merge (loses feature branch history)

---

## Data & Push Safety

### What Belongs in Git

| Category | In Git? | Notes |
|----------|---------|-------|
| Python source (`.py`) | ✓ Yes | All application code, modules, helpers |
| Config JSON (`.json`) | ✓ Yes | Translator configs, classification configs, pipeline configs |
| Reference Data (CSV) | ✓ Yes | `accy_v2/model_lookup/db/db_vehicle_models.csv` — this is static reference data |
| Jupyter notebooks (`.ipynb`) | ✓ Yes | But **clear outputs before committing** (see below) |
| OEM input Excel files | ✓ Yes | Landing zone files are tracked — they are small, single inputs |
| **Markdown docs** (`.md`) | ✓ Yes | All documentation |
| **Python bytecode** | ✗ **No** | `__pycache__/`, `*.pyc`, `*.pyo` — auto-excluded |
| **Jupyter checkpoints** | ✗ **No** | `.ipynb_checkpoints/` — auto-excluded |
| **Output files** | ✗ **No** | `accy_v2/output/ready_to_upload/` — auto-excluded |
| **Secrets/credentials** | ✗ **No** | `.env`, `*.pem`, `*secret*`, `*.key` — auto-excluded |
| **OS junk** | ✗ **No** | `.DS_Store`, `Thumbs.db` — auto-excluded |

**Rationale:** Git stores bytecode, checkpoints, and secrets *forever*. History rewriting is hard. Instead, we exclude at the source with `.gitignore` and `.gitattributes`.

### Pre-Push Checklist

**Before every `git push origin <branch>`:**

```
[ ] Code changes are intentional (git diff --stat looks right)
[ ] No secrets staged (git status: no .env, *.pem, *secret* files)
[ ] No bytecode staged (git status: no __pycache__, *.pyc)
[ ] Notebook outputs cleared (see below)
[ ] All tests pass locally
[ ] Branch is up to date with main (git rebase or merge origin/main)
[ ] Commit messages clear and reference docs/issues
```

### Clearing Notebook Outputs Before Committing

Jupyter notebooks embed cell outputs (large DataFrames, print results, plots) directly in the `.ipynb` JSON. These can:
- Bloat the repository
- Leak sensitive data from intermediate calculations
- Make diffs unreadable (full notebook re-serializes)

**Solution: Clear outputs before adding `.ipynb` to git**

#### Option 1: Using Jupyter CLI

```bash
# Clear outputs from a single notebook
jupyter nbconvert --ClearOutputPreprocessor.enabled=True --inplace accy_v2/model_lookup/veh_model_service.ipynb
```

#### Option 2: Using Jupyter Lab / Jupyter Notebook UI

1. Open notebook in Jupyter
2. Menu: **Edit** → **Clear All Outputs**
3. **File** → **Save Notebook**

#### Option 3: Before Staging (Shell Alias)

Add to your `.bashrc` or PowerShell profile for convenience:

```bash
# Bash
clear-nb() { jupyter nbconvert --ClearOutputPreprocessor.enabled=True --inplace "$1"; }

# PowerShell
function Clear-Notebook { jupyter nbconvert --ClearOutputPreprocessor.enabled=True --inplace $args[0] }
```

Then:
```bash
clear-nb accy_v2/model_lookup/veh_model_service.ipynb
git add accy_v2/model_lookup/veh_model_service.ipynb
```

### Line Ending Safety

This project includes `.gitattributes` to handle line ending normalization:

- **Python, JSON, Markdown, shell scripts:** Always stored as LF (`\n`) in Git, checked out as system-default on your machine
- **Binary files (`.xlsx`, `.pdf`, `.png`):** No line ending conversion; marked `binary` to prevent noisy diffs

**Why?** Windows/Mac users can both work on the same branch without accidental line-ending noise. Read: [git-scm.com/book/.../gitattributes](https://git-scm.com/book/en/v2/Customizing-Git-Git-Attributes)

---

## Quality Checklist

### Before Pushing PR

- [ ] **Code**
  - [ ] Follows PEP 8 style
  - [ ] Type hints present
  - [ ] Docstrings for all public functions
  - [ ] Comments explain WHY, not WHAT
  - [ ] No TODO/FIXME comments
  - [ ] Imports organized and sorted

- [ ] **Testing**
  - [ ] Unit tests written
  - [ ] All tests pass
  - [ ] Edge cases covered
  - [ ] Integration testing done
  - [ ] Manual testing with real data

- [ ] **Documentation**
  - [ ] CHANGELOG.md updated
  - [ ] README.md updated (if needed)
  - [ ] DECISIONS.md updated (if architectural)
  - [ ] Docstrings complete
  - [ ] Comments clear

- [ ] **Git**
  - [ ] Commits have clear messages
  - [ ] No unrelated changes mixed in
  - [ ] Branch up to date with main
  - [ ] No merge conflicts

- [ ] **Verification**
  - [ ] No regressions
  - [ ] Performance acceptable
  - [ ] All relevant tests pass
  - [ ] Outputs correct

### After Merge to Main

- [ ] Pull main locally to verify
- [ ] Run full test suite
- [ ] Try running pipeline end-to-end
- [ ] Monitor logs for any issues
- [ ] Delete feature branch

---

## Examples

### Example 1: Adding New OEM Support

**Files to create:**
- `oems/newoem/config/newoem_config.json`
- `oems/newoem/pipeline/step1_validation.py`
- `oems/newoem/pipeline/step2_header_normalization.py`
- `oems/newoem/pipeline/step3_standardization.py`
- `oems/newoem/pipeline/step4_transformation.py`
- `oems/newoem/pipeline/step4_5_model_enrichment.py`
- `oems/newoem/pipeline/step5_output.py`
- `oems/newoem/pipeline/orchestrator.py`
- `oems/newoem/run_newoem.py`

**Files to update:**
- `README.md` — Add new OEM to project structure
- `CHANGELOG.md` — "Added NewOEM pipeline support"
- `DECISIONS.md` — Reasoning for NewOEM implementation
- `docs/adding_new_oem.md` — Steps to add another OEM

**Testing:**
- Create test Excel files for NewOEM
- Run `python oems/newoem/run_newoem.py`
- Verify output structure and content

**Documentation:**
- Add "NewOEM Configuration" section to README
- Create `docs/newoem_business_rules.md` if OEM-specific

### Example 2: Fixing a Bug

**Reproduce:**
1. Understand the bug (read docs, look at logs)
2. Write test that demonstrates the bug
3. Verify test fails

**Fix:**
1. Make minimal code change to fix bug
2. Verify test now passes
3. Run all existing tests (no regressions)

**Document:**
1. Update CHANGELOG: `### Fixed - [Bug name]: [What was wrong and how fixed]`
2. Add comment in code explaining the fix
3. Link to issue/bug report if applicable

**Example commit:**
```
Fix model lookup returning ambiguous results

Searching for ["outlander", "phev", "gt"] returned both GT and
GT-Premium variants. Root cause: search didn't filter by extra
trim discriminators.

Solution: Post-filter results using per-manufacturer vocab to
exclude extra trim-level keywords (premium, noir, se, etc.) while
allowing specification keywords (fwd, awc, etc.).

Fixes: [issue#123]
Test: test_exact_matching.py - all 5 cases pass
```

### Example 3: Refactoring

**Before refactoring:**
1. [ ] Have good test coverage
2. [ ] All tests pass
3. [ ] Behavior is correct

**During refactoring:**
1. [ ] Run tests after each significant change
2. [ ] Never change behavior, only structure
3. [ ] Keep commits small

**After refactoring:**
1. [ ] All tests pass
2. [ ] Manual testing confirms same behavior
3. [ ] Code is cleaner/faster/more maintainable

**Document:**
```
Refactor: Simplify keyword extraction logic

- Extracted _extract_description_tokens() for reuse
- Combined model + trim + fuel keywords in single function
- No behavior changes, tests still pass
- Improves readability and reduces code duplication
```

---

## FAQ

### Q: When should I create a new test file vs. add to existing?

**A:** 
- **New file:** New module, >5 new test cases, or testing a major subsystem
- **Existing file:** Small change, 1-2 test cases, modifying existing module

### Q: How detailed should commit messages be?

**A:** 
- **Subject line:** <60 chars, present tense, specific
- **Body:** Explain WHAT changed and WHY (not HOW)
- **References:** Link to related docs/issues/decisions

### Q: Should I write tests before or after code?

**A:** 
- Prefer **TDD (test-first):** Write test, code fails, write code, test passes
- Acceptable: Write code then tests immediately
- Avoid: Write code, tests later (they often don't happen)

### Q: How do I handle breaking changes?

**A:**
1. Document in CHANGELOG under "BREAKING CHANGES"
2. Update all affected code (don't leave broken code)
3. Add migration guide in docs/
4. Increase version number if using semver

### Q: What if I find a bug in someone else's code while working on my feature?

**A:**
1. Don't fix it in your feature branch (separate concerns)
2. Note it in DECISIONS.md or comment with TODO
3. File an issue or create separate PR to fix it
4. Reference your feature PR in the issue

### Q: How do I review someone else's PR?

**A:**
1. [ ] Code follows standards
2. [ ] Tests are comprehensive
3. [ ] Documentation updated
4. [ ] No obvious bugs
5. [ ] Asks clarifying questions if needed
6. [ ] Tests pass
7. [ ] Approves or requests changes

---

## Resources

**Within this project:**
- [README.md](README.md) — Project overview
- [DECISIONS.md](DECISIONS.md) — Why things are the way they are
- [CHANGELOG.md](CHANGELOG.md) — What changed and when
- [docs/](docs/) — Specialized documentation

**External:**
- [PEP 8](https://www.python.org/dev/peps/pep-0008/) — Python style guide
- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html) — Docstring standards
- [Git Best Practices](https://git-scm.com/book/en/v2) — Git documentation
- [Keep a Changelog](https://keepachangelog.com/) — Changelog format

---

## Getting Help

If you're stuck:

1. [ ] Check [README.md](README.md) and [DECISIONS.md](DECISIONS.md)
2. [ ] Look for similar code (grep the codebase)
3. [ ] Check existing tests for examples
4. [ ] Read the docstring of related functions
5. [ ] Ask for clarification before making assumptions

---

**Last Updated:** June 23, 2026  
**Maintained By:** Development Team  
**Next Review:** [When next major change happens]
