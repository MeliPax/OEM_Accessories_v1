# Safety Process: Code Changes & Deployment

**Purpose:** Ensure code changes are safe, tested, and well-documented  
**Audience:** All developers and AI agents  
**Effective:** June 23, 2026

---

## Overview

This document defines a safe, seamless process for making code changes to the OEM Accessory Pipeline while preventing common issues:

- **Broken code** → Caught by tests
- **Lost work** → Protected by git workflow
- **Regressions** → Caught by test suite
- **Poor documentation** → Enforced by checklist
- **Bad deployments** → Prevented by staged review

---

## Core Principles

### 1. Test First, Deploy Second

✅ **Always:**
- Write or update tests before committing
- Run full test suite before PR
- Perform manual acceptance testing
- Verify no regressions

❌ **Never:**
- Deploy untested code
- Skip testing because "it's just a docs change"
- Trust that "it will work because it looks right"

### 2. Document As You Code

✅ **Always:**
- Update docstrings when you modify functions
- Update CHANGELOG before committing
- Update README if structure changes
- Explain decisions in code comments

❌ **Never:**
- Leave code without docstrings
- Commit without CHANGELOG entry
- Write code you can't explain

### 3. Review Before Merging

✅ **Always:**
- Create PR before merging to main
- Have tests pass before asking for review
- Provide clear summary for reviewer
- Wait for approval before merging

❌ **Never:**
- Force-push to main
- Bypass review process
- Merge failing tests
- Merge without documentation

### 4. Keep Main Branch Safe

✅ **Always:**
- Feature branches for all work
- PR review before merge
- Tests must pass
- Only fast-forward merges

❌ **Never:**
- Commit directly to main
- Push broken code to main
- Deploy from feature branches
- Rewrite main branch history

---

## Step-by-Step Safety Process

### PHASE 1: Planning (Before Coding)

#### Step 1: Assess the Scope
```
[ ] Is this change small (1-2 files)?
[ ] Medium (3-5 files)?
[ ] Large (6+ files or major restructuring)?

[ ] Does it affect core logic or only output?
[ ] Does it change interfaces (function signatures)?
[ ] Does it affect performance?
[ ] Are there breaking changes?
```

#### Step 2: Read the Docs

**Required reading (5-10 min):**
```
[ ] README.md - Understand project structure
[ ] DECISIONS.md - Understand WHY things are designed this way
[ ] CHANGELOG.md - See recent changes and current state
[ ] Related docs - docs/config_schema.md, etc.
[ ] Test files - See how similar code is tested
```

#### Step 3: Identify Impact

```
Questions to answer:

1. What will break if I make this change?
   - List all affected modules
   - List all affected functions/classes
   - List all affected tests

2. Who depends on this code?
   - What calls this function?
   - What imports this module?
   - What tests validate this?

3. How will I know if something breaks?
   - What tests should still pass?
   - What manual tests should I run?
   - What outputs should I verify?

4. How will I revert if needed?
   - Can I git revert this?
   - Will old data still work?
   - Are there migration steps needed?
```

**Output:** Fill in PLAN_feature.md with answers

#### Step 4: Design Your Solution

**Before coding, document:**
```
What is the minimal change needed?
- Don't over-engineer
- Don't refactor things that don't need refactoring
- Don't "while I'm at it" fix unrelated bugs

What are potential side effects?
- Performance impact?
- Compatibility issues?
- Data structure changes?

How will I test this?
- Unit tests (specific functions)
- Integration tests (across modules)
- Manual tests (real data, real workflow)
- Regression tests (existing functionality)
```

---

### PHASE 2: Development (While Coding)

#### Step 1: Create Feature Branch

```bash
# Get latest main
git checkout main
git pull origin main

# Create feature branch
git checkout -b feature/descriptive-name

# Verify you're on the right branch
git branch  # Should show *feature/descriptive-name
```

**Branch naming rules:**
- `feature/add-vocabulary-filtering` — New feature
- `feature/fix-model-ambiguity` — Bug fix
- `feature/refactor-column-mapper` — Refactoring
- `feature/update-docs-only` — Documentation

#### Step 2: Code & Test Together

**Development loop (repeat):**
```
1. Write a small chunk of code (~50 lines)
2. Write tests for that chunk
3. Run tests (should pass)
4. Commit with clear message
5. Repeat until feature complete
```

**Never:**
- Write all code, then tests
- Commit untested code
- Work for hours without commits
- Skip tests for "simple" changes

#### Step 3: Commit Frequently

```bash
# After each logical chunk
git add file1.py file2.py
git commit -m "Add vocabulary filtering to search_models

Prevents false positives when searching for trim-level keywords.
Searching for ['outlander', 'phev', 'gt'] now returns only GT
variant, not GT-Premium.

Tests: test_exact_matching.py - all 5 cases pass
"

# More commits as you continue
git add docs/CHANGELOG.md
git commit -m "Update CHANGELOG for vocabulary filtering"

git add accy_v2/DEVELOPER_GUIDE.md
git commit -m "Update developer guide with testing requirements"
```

**Good commit practices:**
- One logical change per commit
- Clear, descriptive message
- Small enough to revert if needed
- Tests pass after each commit

#### Step 4: Update Docs As You Go

**Don't leave it for the end.**

```bash
# As you add functions
# → Add docstrings immediately

# As you make changes
# → Update CHANGELOG immediately

# As you finish
# → Update README.md if needed
# → Update DECISIONS.md if architectural
# → Update related docs
```

---

### PHASE 3: Testing (Before PR)

#### Step 1: Run Unit Tests

```bash
# Test your new/modified module
python -m pytest accy_v2/module_you_changed/test_*.py -v

# Or run specific test
python -m pytest accy_v2/module/test_file.py::test_function -v
```

**Expected:** All tests pass ✓

#### Step 2: Run Integration Tests

```bash
# Run all tests in affected areas
python -m pytest accy_v2/oems/mitsubishi/ -v

# Run full test suite
python -m pytest accy_v2/ -v
```

**Expected:** All tests pass ✓

#### Step 3: Manual Testing (Acceptance)

**With real data:**

```bash
# 1. Place sample Excel in data/landing_zone/mitsubishi/
# 2. Run pipeline
python accy_v2/oems/mitsubishi/run_mitsubishi.py

# 3. Check outputs created
ls accy_v2/output/ready_to_upload/
ls accy_v2/output/dq_reports/
ls accy_v2/output/pipeline_logs/

# 4. Verify Excel file
# - Open in Excel/Sheets
# - Check sheets (model_name_EN, model_name_FR, _Report)
# - Check columns (correct columns present?)
# - Check data (looks reasonable?)
# - Check no errors in data

# 5. Verify DQ Report
cat accy_v2/output/dq_reports/*.json | python -m json.tool
# - Valid JSON?
# - Expected warnings/errors?
# - No false warnings?

# 6. Verify Pipeline Log
tail -50 accy_v2/output/pipeline_logs/*.txt
# - No ERROR lines?
# - Expected steps completed?
# - Timing reasonable?
```

**Checklist:**
```
[ ] Excel file created
[ ] All expected sheets present
[ ] Correct columns (no extra, no missing)
[ ] Data looks reasonable (not all NULL, reasonable values)
[ ] DQ report is valid JSON
[ ] DQ report has expected warnings (not new false warnings)
[ ] Pipeline log shows successful completion
[ ] No ERROR lines in pipeline log
[ ] Performance acceptable (didn't 10x the runtime)
```

#### Step 4: Regression Testing

**Verify you didn't break anything:**

```bash
# Test other OEMs still work
python accy_v2/oems/mazda/run_mazda.py

# Run existing tests that might be affected
python -m pytest accy_v2/core/ -v
python -m pytest accy_v2/model_lookup/ -v
```

**Checklist:**
```
[ ] All existing tests still pass
[ ] Other OEMs still work
[ ] No new warnings in logs
[ ] Performance unchanged
```

---

### PHASE 4: Code Review (Before Merge)

#### Step 1: Prepare Your PR

**Before pushing:**

```bash
# Update main with latest changes
git fetch origin
git rebase origin/main

# Resolve any conflicts
# (If conflicts, ask for help)

# Run tests one more time
python -m pytest accy_v2/ -v

# Push to remote
git push origin feature/your-feature-name
```

#### Step 2: Create PR

```bash
# Using GitHub CLI
gh pr create --title "Fix model lookup ambiguity" --body "
## Description

When searching for model numbers, results included false positives.
For example, searching for ['outlander', 'phev', 'gt'] returned both
'Outlander PHEV GT S-AWC' and 'Outlander PHEV GT Premium S-AWC'.

Fixed by filtering results based on trim discriminators vs specs.

## Testing

- [x] Unit tests: 5/5 pass
- [x] Integration tests: 3/3 pass
- [x] Manual testing: Verified with real data
- [x] Regression testing: All existing tests pass
- [x] No performance regression

## Documentation

- [x] Docstrings added
- [x] CHANGELOG.md updated
- [x] Code comments explain WHY
- [x] No TODO/FIXME left

## Files Changed

- accy_v2/model_lookup/models/manufacture_module.py (new functions)
- accy_v2/oems/*/pipeline/step4_5_model_enrichment.py (updated calls)

## Related

Closes #123 (if applicable)
See IMPLEMENTATION_2026-06-23.md for technical details
"
```

**PR checklist:**
```
[ ] Title is clear and concise
[ ] Description explains the problem and solution
[ ] Testing section complete and honest
[ ] Documentation section shows what was updated
[ ] Files list is accurate
[ ] No draft/WIP (unless explicitly labeled)
```

#### Step 3: User Review

**User will check:**
- [ ] Tests pass (CI/CD status)
- [ ] Documentation updated
- [ ] Code quality acceptable
- [ ] No obvious bugs or issues
- [ ] No breaking changes (or documented)

**Agent provides summary:**
```
Test Results:
✓ Unit tests: 12/12 pass
✓ Integration: 5/5 pass
✓ Manual: Verified with real data
✓ Regression: No new failures

Documentation:
✓ CHANGELOG updated
✓ Docstrings present
✓ Code comments clear
✓ No TODOs left

Ready for review.
```

#### Step 4: Address Feedback

If user requests changes:

```bash
# Make requested changes
# (Edit files, fix issues)

git add modified_files.py
git commit -m "Address review feedback

- Fixed: X
- Added: Y
- Clarified: Z

See: [PR comment link if applicable]
"

# Push updated commits
git push origin feature/your-feature-name

# Comment on PR: "Updates pushed, ready for re-review"
```

---

### PHASE 5: Merge (Final Gate)

#### Step 1: Final Verification

Before merge, final checks:

```bash
# Latest main
git fetch origin
git rebase origin/main

# All tests pass
python -m pytest accy_v2/ -v

# Manual test one more time
python accy_v2/oems/mitsubishi/run_mitsubishi.py
# (Quick verify outputs created)

# Commit log is clean
git log origin/main..HEAD --oneline
# (Make sure commits are logical)
```

#### Step 2: Merge

**User action:** Approve and merge via GitHub

```bash
# OR merge locally (if no conflicts)
git checkout main
git pull origin main
git merge --no-ff feature/your-feature-name
git push origin main
```

**Merge strategy:**
- **Squash merge:** All feature commits → 1 commit on main (recommended)
- **Merge commit:** Preserve feature branch history

**Never use:**
- Fast-forward merge (loses feature branch history)
- Force push

#### Step 3: Cleanup

```bash
# Delete feature branch locally
git branch -d feature/your-feature-name

# Delete feature branch on remote
git push origin -d feature/your-feature-name

# Verify main is merged
git log main | head -5
# (Should show your changes)
```

---

## Safety Guardrails

### Automated Checks (What to Expect)

These checks run automatically:

```
[ ] Branch is up to date with main
[ ] All tests pass (CI/CD)
[ ] No merge conflicts
[ ] Commits are squashed (if using squash merge)
[ ] Commit message is clear
```

### Manual Checks (What to Verify)

Before clicking "Merge":

```
[ ] Tests pass (status shows green checkmark)
[ ] Documentation updated (CHANGELOG visible in PR)
[ ] No obvious bugs (code review passed)
[ ] No breaking changes (or documented)
[ ] Meaningful test coverage (not just "add" then "remove")
```

### What Can Go Wrong (& How to Fix)

| Problem | Cause | Fix |
|---------|-------|-----|
| Tests fail | Code bug or missing test | Fix code, re-run tests |
| Merge conflict | Changes to same lines | Rebase, resolve conflicts |
| Performance degradation | Inefficient code | Profile, optimize |
| Regression | Broke existing feature | Run regression tests, fix |
| Documentation out of sync | Forgot to update docs | Add docs, re-commit |

---

## Incident Response

### If Something Goes Wrong

#### During Development

**Tests fail:**
```bash
# Read error message carefully
python -m pytest test_file.py::test_function -v

# Fix code
# Re-run test
# Repeat
```

**Merge conflict:**
```bash
# Understand both versions
git status  # See conflicts

# Resolve conflicts in file
# Test both versions still work
git add resolved_file
git commit -m "Resolve merge conflict with main"
```

**Broke something accidentally:**
```bash
# If not committed yet
git diff file.py  # See what changed
git checkout file.py  # Undo changes

# If committed but not pushed
git reset --soft HEAD~1  # Undo commit, keep changes
# (Or git revert if already pushed)
```

#### After Merge to Main

**Discovered bug after merge:**

1. **Create hotfix branch:**
   ```bash
   git checkout main
   git pull origin main
   git checkout -b hotfix/fix-bug-description
   ```

2. **Fix and test:**
   ```bash
   # Fix the bug
   # Run tests
   # Manual testing
   ```

3. **Merge quickly:**
   ```bash
   git push origin hotfix/fix-bug-description
   gh pr create --title "Hotfix: [description]"
   # Fast-track review and merge
   ```

**Regression noticed in tests:**

1. **Don't panic** — This is what tests are for!
2. **Roll back if critical:** `git revert <commit>`
3. **Create issue:** Document the problem
4. **Fix properly:** Use feature branch approach
5. **Prevent repeat:** Add test case

---

## Checklist: Am I Ready to Push?

Print this out and check before pushing to PR:

```
BEFORE PUSHING PR
================

Code Quality
[ ] Code follows PEP 8
[ ] Docstrings on all public functions
[ ] Comments explain WHY (not WHAT)
[ ] No TODO/FIXME comments
[ ] No debug print() statements

Testing
[ ] Unit tests written
[ ] All unit tests pass
[ ] Integration tests pass
[ ] Manual testing completed
[ ] Regression tests pass
[ ] No new warnings in logs

Documentation
[ ] CHANGELOG.md updated
[ ] Docstrings complete
[ ] README.md updated (if needed)
[ ] DECISIONS.md updated (if needed)
[ ] Code comments clear

Git
[ ] Branch name follows convention
[ ] Commits have clear messages
[ ] Commits are logical chunks
[ ] No merge conflicts
[ ] Up to date with main

Verification
[ ] Output files created
[ ] Output format correct
[ ] DQ report valid
[ ] Pipeline log shows success
[ ] Performance acceptable

Safety
[ ] No hardcoded paths
[ ] No secrets in code
[ ] Error handling in place
[ ] No breaking changes (or documented)
[ ] Graceful fallbacks if needed

READY TO PUSH: YES / NO
```

---

## What Success Looks Like

✅ **Feature implemented:**
- Code works correctly
- Tests pass
- Documentation updated
- No regressions

✅ **PR reviewed:**
- User approved changes
- Feedback addressed
- Tests still pass
- Ready to merge

✅ **Merged to main:**
- Feature branch deleted
- Main updated
- CI/CD passes
- No issues reported

✅ **In production:**
- Working as intended
- No regressions
- Users happy
- Properly documented

---

## Quick Reference

### For AI Agents

Follow this flow:

```
1. Read docs (README, DECISIONS, CHANGELOG)
2. Create feature branch
3. Write tests FIRST
4. Write code to pass tests
5. Update docstrings & comments
6. Update CHANGELOG.md
7. Run all tests
8. Manual testing with real data
9. Push to PR with summary
10. Wait for user approval
11. Merge to main
12. Delete feature branch
```

### For Code Review

Ask these questions:

```
[ ] Do I understand what this changes?
[ ] Are there tests? Are they comprehensive?
[ ] Does it break anything else?
[ ] Is documentation updated?
[ ] Is the approach sensible?
[ ] Would I maintain this code?
```

### For Deployment

Verify:

```
[ ] Main branch
[ ] All tests pass
[ ] Documentation updated
[ ] No regressions observed
[ ] Safe to deploy to production
```

---

**Last Updated:** June 23, 2026  
**Maintained By:** Development Team  
**Questions?** See DEVELOPER_GUIDE.md or ask for clarification

