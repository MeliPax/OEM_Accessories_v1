# DEVELOPMENT_GUIDE.md — Step-by-Step for Agents

**Status:** 📋 PLANNING (Actionable guide for agents starting development work)  
**Date Created:** 2026-09-09  
**Audience:** Agents (Claude instances) responsible for implementing features or fixes

---

## Quick Start: From Issue to Merged PR

### Phase 1: Identify & Plan (5 min)

1. **Read the Issue/Request**
   - What is the problem? (user report, proposal, research finding)
   - Where is it documented? (PROPOSAL.md, issue tracker, conversation context)
   - What's the scope? (one file vs. multi-OEM vs. architectural change?)

2. **Locate Related Planning Docs**
   ```bash
   find accy_v2/planning -name "*{topic}*" -type f
   # Examples: trim_hierarchy_orphan_safety_net/PROPOSAL.md, csv_uniqueness_filtering/
   ```
   - Read the PROPOSAL.md if it exists (outlines design + open questions)
   - Check if similar work is already done elsewhere (search for keywords in commits)

3. **Confirm Understanding**
   - Summarize the problem in 1-2 sentences
   - List affected files (search via `grep -r` or `git log --name-only`)
   - Identify test cases needed

### Phase 2: Create Feature Branch (2 min)

```bash
# Always start from clean dev
git checkout dev
git pull origin dev

# Create feature branch with clear name
git checkout -b feature/my-feature-name

# Example:
# git checkout -b feature/trim-hierarchy-orphan-safety-net
```

**Never:** Develop on `dev` or `main` directly.

---

### Phase 3: Implement (varies)

#### 3a — Understand Current Code

```bash
# Find related files
grep -r "SearchResult" accy_v2/model_lookup/  # Example: search-related code

# Read the file where you'll make changes
cat accy_v2/model_lookup/search_engine.py | head -100

# Check recent commits (understand what changed)
git log --oneline -20 -- accy_v2/model_lookup/search_engine.py
```

#### 3b — Make Changes

- **One concern per file** — Don't mix unrelated changes
- **Follow existing patterns** — If other OEMs have a mechanism, use it for all
- **Test as you go** — Don't write 500 lines then try to test

```bash
# Edit a file
# (Your editor or IDE)

# Verify syntax (Python)
python -m py_compile accy_v2/model_lookup/search_engine.py

# Run tests
pytest accy_v2/tests/test_search_engine.py -v
```

#### 3c — Commit Frequently

```bash
# Stage specific changes (not everything)
git add accy_v2/model_lookup/search_engine.py

# Commit with clear message
git commit -m "Implement: Add implied_trim_variant field to SearchResult"

# Repeat as you complete logical steps
git add accy_v2/oems/hyundai/config/enrichment.yaml
git commit -m "Config: Add implied_trim_variant_trims template to all OEMs"
```

**Good commit = one logical change you can explain in a sentence.**

---

### Phase 4: Test Locally (15-30 min)

#### 4a — Unit Tests

```bash
# Run all tests for the modified module
pytest accy_v2/tests/test_model_lookup/ -v

# Run specific test
pytest accy_v2/tests/test_search_engine.py::TestImpliedTrimVariant -v

# If no tests exist, create them
# (See Phase 5 for guidance)
```

**Success criteria:** All tests pass, coverage for edge cases (null, empty, boundary).

#### 4b — Integration Tests

```bash
# Run full pipeline for one OEM (quickest)
cd accy_v2 && python -m run_pipeline.py \
  --source ~/data/hyundai_test.xlsx \
  --oem hyundai \
  --output ~/output_test/

# Check DQ report (if model lookup touched)
cat ~/output_test/dq_reports/hyundai/*.json | python -m json.tool | grep orphaned_record_rule
```

**Success criteria:** 
- Pipeline completes without errors
- Output workbook has all expected sheets
- New DQ rules (if added) appear correctly
- No new unexpected warnings

#### 4c — Spot-Check Output

```bash
# Open output workbook
open ~/output_test/hyundai_2026-09-09_output.xlsx

# Verify:
# - All columns present (Model, TrimName, etc.)
# - No truncated data
# - No extra/missing sheets
```

---

### Phase 5: Add Tests (If Needed)

#### 5a — Identify Test Cases

```python
# Example: Testing implied_trim_variant_trims

test_cases = [
    {
        "name": "Elantra TCR matches Elantra N rule",
        "make": "Hyundai",
        "year": 2026,
        "keywords": ["elantra", "tcr"],
        "expected_implied_variant": "n",
    },
    {
        "name": "Non-matching trim ignores rule",
        "make": "Hyundai",
        "year": 2026,
        "keywords": ["elantra", "sport"],
        "expected_implied_variant": None,
    },
    {
        "name": "Wrong year skips rule",
        "make": "Hyundai",
        "year": 2025,  # Rule is years: [2026]
        "keywords": ["elantra", "tcr"],
        "expected_implied_variant": None,
    },
]
```

#### 5b — Write Test

```python
# accy_v2/tests/test_search_engine.py

def test_implied_trim_variant_injection():
    """Verify implied_trim_variant_trims config rule fires correctly."""
    engine = VehicleSearchEngine(csv_path, configs_dir, oem_config)
    
    result = engine.search("Hyundai", 2026, ["elantra", "tcr"])
    assert result is not None
    assert result.implied_trim_variant == "n"  # Expected injection
```

#### 5c — Run & Verify

```bash
pytest accy_v2/tests/test_search_engine.py::test_implied_trim_variant_injection -v
```

---

### Phase 6: Update Documentation (10 min)

#### 6a — Update PROPOSAL.md

```markdown
# Mark status as IMPLEMENTED (if this was planned work)
**Status:** ✅ IMPLEMENTED (2026-09-09)

# Add implementation summary at bottom
## Implementation Summary (2026-09-09)
- ✅ Added field X
- ✅ Updated file Y
- ✅ Config added to Z
```

#### 6b — Update Commit Message

```bash
# If final commit is complex, rewrite message to be clear
git commit --amend -m "Implement: Trim hierarchy orphan safety net

Part 1 — implied_trim_variant mechanism:
- Add SearchResult.implied_trim_variant field
- Add step 3.6 in search_engine.py
- Add config template to all OEMs

Part 2 — orphaned_record_rule safety net:
- Create orphan_record_validator.py
- Wire dq_logger through pipelines
- Integrate into all step5_output.py files

Impact: Elantra TCR now finds N-line model..."
```

#### 6c — Update CHANGELOG (if user-visible change)

```yaml
# accy_v2/docs/CHANGELOG.md
# Add at top under "Unreleased" section

## [Unreleased]

### Added
- **Trim hierarchy safety net:** Config-driven implied_trim_variant mechanism for sub-line fallback (e.g., Elantra N)
- **Orphaned record detection:** Cross-OEM DQ check flags any row with missing model number at output stage
- **Elantra TCR rule:** 2026 Elantra TCR now resolves to Elantra N-line model via config

### Fixed
- Silent orphan records no longer reach output (flagged with orphaned_record_rule)
```

---

### Phase 7: Push & Create PR (5 min)

#### 7a — Push to Remote

```bash
# Push your feature branch
git push origin feature/my-feature-name

# Verify it's there
git branch -vv
# Should show: feature/my-feature-name      a3c9381 [origin/feature/...] Docs: Mark as IMPLEMENTED
```

#### 7b — Create PR

**Via CLI:**
```bash
gh pr create \
  --title "Implement: Trim hierarchy orphan safety net" \
  --body "## Summary
- Adds implied_trim_variant_trims config mechanism
- Adds orphaned_record_rule DQ safety net
- Wires dq_logger through all pipelines

## Testing
- ✅ Unit tests for SearchResult field
- ✅ Pipeline runs end-to-end (Hyundai)
- ✅ DQ report shows orphaned_record_rule
- ✅ No regressions on existing searches

Closes #XX (if applicable)"
```

**Via GitHub UI:**
1. Visit `https://github.com/MeliPax/OEM_Accessories_v1/compare/dev...feature/my-feature-name`
2. Click "Create Pull Request"
3. Fill in title + description
4. Click "Create"

#### 7c — Link Related Work

In PR description, link to:
- Planning doc: `accy_v2/planning/oem_pipeline/trim_hierarchy_orphan_safety_net/PROPOSAL.md`
- Related commits: `Ref: 0df7f8b`
- Related issues/conversations

---

### Phase 8: Address Feedback (varies)

1. **Read review comments** (on GitHub or via `gh pr view`)
2. **Make fixes** — Commit with new message (don't amend unless requested)
   ```bash
   git add accy_v2/path/to/file.py
   git commit -m "Review: Address feedback on orphan_record_validator"
   git push origin feature/my-feature-name
   ```
3. **Respond to each comment** — Explain your fix
4. **Request re-review** (GitHub button: "Re-request review")

---

### Phase 9: Merge & Cleanup (2 min)

**After approval:**

```bash
# Merge via GitHub UI (preferred, keeps history)
# Or via CLI:
gh pr merge feature/my-feature-name --merge

# Verify merge
git checkout dev && git pull origin dev

# Clean up local branch
git branch -d feature/my-feature-name
```

✅ **Done!** Your work is now in `dev`, ready for integration testing.

---

## Troubleshooting

### "Tests are failing"

```bash
# Check what changed since last working commit
git diff HEAD~1

# Run test with verbose output
pytest accy_v2/tests/test_xyz.py -v -s

# Check if it's an import error
python -c "from accy_v2.model_lookup.search_engine import SearchResult"

# If import fails, check syntax
python -m py_compile accy_v2/model_lookup/search_engine.py
```

### "Pipeline won't run"

```bash
# Check if config is valid YAML
python -c "import yaml; yaml.safe_load(open('accy_v2/oems/hyundai/config/enrichment.yaml'))"

# Check if a required function was added
grep -r "orphan_record_validator" accy_v2/

# Try running a smaller test first
python -c "from accy_v2.core.helpers.orphan_record_validator import flag_orphaned_records; print('Import OK')"
```

### "Git merge conflict"

```bash
# If dev has changed since branch creation, rebase:
git checkout feature/my-feature
git rebase dev

# Resolve conflicts (editor will show them)
# Then:
git add accy_v2/file_with_conflict.py
git rebase --continue
git push origin feature/my-feature --force-with-lease  # Safe force push
```

---

## Quick Reference: Common Commands

| Task | Command |
|------|---------|
| Start new work | `git checkout -b feature/name` |
| Stage a file | `git add accy_v2/path/file.py` |
| Commit | `git commit -m "Type: Message"` |
| Push branch | `git push origin feature/name` |
| Run tests | `pytest accy_v2/tests/ -v` |
| Run pipeline | `python -m run_pipeline.py --oem hyundai` |
| Create PR | `gh pr create --title "..." --body "..."` |
| View PR status | `gh pr view` |
| Merge PR | `gh pr merge --merge` |
| Clean up | `git branch -d feature/name` |

---

## Checklist Before PR

- [ ] Code compiles/imports without errors
- [ ] Unit tests pass (if added new functions)
- [ ] Pipeline runs without errors (at least one OEM)
- [ ] DQ report is valid (if model lookup touched)
- [ ] Commit messages are clear
- [ ] PROPOSAL.md or related docs updated
- [ ] Branch has no merge conflicts with `dev`
- [ ] All changes are related to the feature (no unrelated cleanup)

---

**Next Step:** When ready to implement a feature, follow this guide section-by-section. Ask for clarification in comments if any step is unclear.
