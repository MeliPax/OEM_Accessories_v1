# Branch Protection Rules

**Document:** Planning  
**Created:** June 26, 2026  
**Status:** Draft - For Review  
**Related:** `01_CI_CD_STRATEGY.md`, `02_AUTOMATED_CHECKS.md`

---

## Overview

This document specifies GitHub branch protection rules to enforce on `staging` and `main` branches. These rules prevent merging code that doesn't meet quality standards.

---

## Staging Branch Rules

**Target Branch:** `staging`

Branch protection rules enforce the development workflow:

```
feature/* → PR → [Checks] ✓ [Review] ✓ → Merge to staging
```

### Rule 1: Require Status Checks

**Status checks that must pass:**
- ✅ lint (flake8, black, isort)
- ✅ type-check (mypy)
- ✅ unit-tests (pytest)
- ✅ security-scan (bandit, detect-secrets, safety)
- ✅ docs-check (docstring validation)

**Configuration:**
```
Require status checks to pass before merging: ON
Require branches to be up to date before merging: ON
```

**Effect:** PR cannot be merged until all checks pass

---

### Rule 2: Require Code Review

**Configuration:**
```
Require pull request reviews before merging: ON
Number of approving reviews required: 1
Require review from code owners: OFF (optional)
Dismiss stale pull request approvals when new commits are pushed: ON
Require approval of the most recent reviewable push: ON
```

**Effect:**
- ✅ 1 human must approve the PR
- ✅ If PR author pushes new commits, approval is cleared (must re-approve)
- ❌ PR author cannot approve their own PR

**Exceptions:** None (all PRs need review)

---

### Rule 3: Merge Options

**Configuration:**
```
Allow merge commits: ON
Allow squash merging: ON
Allow rebase merging: ON
Require commit message to match pattern: OFF
Require merge to be up to date before merging: OFF (already required in Rule 1)
Automatically delete head branches: ON
```

**Rationale:**
- Multiple merge strategies available (developer chooses)
- Auto-delete keeps branch list clean
- Linear history not required (can rebase locally before PR if desired)

---

### Rule 4: Dismiss Stale Reviews

**When enabled:**
- Any push to the PR automatically clears existing approvals
- Reviewers see new changes and must re-approve

**Configuration:**
```
Dismiss stale pull request approvals when new commits are pushed: ON
Require review from code owners: OFF
```

---

### Rule 5: Restrict Force Pushes

**Configuration:**
```
Restrict who can push to matching branches: OFF (anyone can push)
Allow force pushes: NOBODY (force push blocked)
Allow deletions: OFF (branch cannot be deleted)
```

**Effect:**
- ❌ Nobody can force-push to staging (prevents accidental rewrites)
- ❌ Staging branch cannot be deleted
- ✅ Normal commits can be pushed

---

## Main Branch Rules

**Target Branch:** `main`

Branch protection rules enforce production safety:

```
staging → PR → [Checks] ✓ [2 Reviews] ✓ [Staging QA] ✓ → Merge to main
```

### Rule 1: Require Status Checks

**Status checks that must pass (same as staging):**
- ✅ lint (flake8, black, isort)
- ✅ type-check (mypy)
- ✅ unit-tests (pytest)
- ✅ integration-tests (staged data)
- ✅ security-scan (bandit, detect-secrets, safety)
- ✅ docs-check (docstring validation)

**Configuration:**
```
Require status checks to pass before merging: ON
Require branches to be up to date before merging: ON
Strict policy (cannot merge if any change since approval): ON
```

**Effect:** PR cannot merge if any new commits pushed (must re-review)

---

### Rule 2: Require Code Review

**Configuration (stricter than staging):**
```
Require pull request reviews before merging: ON
Number of approving reviews required: 2
Require review from code owners: ON (if code owners file exists)
Dismiss stale pull request approvals when new commits are pushed: ON
Require approval of the most recent reviewable push: ON
```

**Effect:**
- ✅ 2 different humans must approve
- ✅ Code owner must approve (if applicable)
- ✅ Stale approvals dismissed on new commits
- ❌ PR author cannot approve their own PR

**Why stricter?** Production safety requires multiple eyes

---

### Rule 3: Merge Options

**Configuration:**
```
Allow merge commits: OFF (cleaner history)
Allow squash merging: ON
Allow rebase merging: ON
Require commit message to match pattern: OFF
Require merge to be up to date before merging: ON (already in Rule 1)
Automatically delete head branches: ON
```

**Rationale:**
- Linear history: merge commits create confusing histories
- Squash/rebase keep history clean
- Auto-delete keeps branch list clean

---

### Rule 4: Restrict Force Pushes

**Configuration (strictest):**
```
Restrict who can push to matching branches: ON (only admins)
Allow force pushes: NOBODY (force push blocked)
Allow deletions: OFF (cannot delete main)
```

**Effect:**
- ❌ Nobody (not even admins by default) can force-push
- ❌ Main branch cannot be deleted
- ✅ Normal commits via PR merges only

---

## Comparison: Staging vs. Main

| Rule | Staging | Main |
|------|---------|------|
| Status checks | ✅ Required | ✅ Required |
| Code reviews | 1 approval | 2 approvals |
| Code owner approval | Not required | Required |
| Merge strategies | Merge / Squash / Rebase | Squash / Rebase only |
| Force push | Blocked | Blocked strictly |
| Auto-delete head | ✅ Yes | ✅ Yes |

---

## Implementation Steps

### Step 1: Enable Branch Protection on Staging

1. Go to GitHub repository settings
2. Navigate to `Branches` → `Branch protection rules`
3. Click `Add rule`
4. Enter branch name pattern: `staging`
5. Enable all rules listed above
6. Save

### Step 2: Enable Branch Protection on Main

1. Same as step 1, but pattern: `main`
2. Use stricter settings listed above

### Step 3: Add Code Owners (Optional)

Create `.github/CODEOWNERS` file:

```
# Entire repo
* @user1 @user2

# Core pipeline
/accy_v2/core/ @dev1
/accy_v2/oems/mitsubishi/ @dev2
/accy_v2/oems/mazda/ @dev3

# Tests
/accy_v2/tests/ @dev1 @dev2
```

---

## GitHub Settings Summary

### For Staging:
```json
{
  "required_status_checks": {
    "strict": true,
    "checks": ["lint", "type-check", "unit-tests", "security-scan", "docs"]
  },
  "required_pull_request_reviews": {
    "dismissal_restrictions": {},
    "require_code_owner_reviews": false,
    "required_approving_review_count": 1,
    "dismiss_stale_reviews": true,
    "require_last_push_approval": true
  },
  "enforce_admins": false,
  "require_linear_history": false,
  "required_conversation_resolution": false,
  "allow_force_pushes": false,
  "allow_deletions": false
}
```

### For Main:
```json
{
  "required_status_checks": {
    "strict": true,
    "checks": ["lint", "type-check", "unit-tests", "integration-tests", "security-scan", "docs"]
  },
  "required_pull_request_reviews": {
    "dismissal_restrictions": {},
    "require_code_owner_reviews": true,
    "required_approving_review_count": 2,
    "dismiss_stale_reviews": true,
    "require_last_push_approval": true
  },
  "enforce_admins": true,
  "require_linear_history": true,
  "required_conversation_resolution": false,
  "allow_force_pushes": false,
  "allow_deletions": false
}
```

---

## Rationale

### Why Status Checks?
→ Prevents merging code that doesn't meet quality standards

### Why Code Review?
→ Catches logic errors, architecture issues, security holes

### Why 2 Reviews on Main?
→ Production safety: redundant check reduces risk

### Why Dismiss Stale Reviews?
→ Ensures reviewers see final code before merge

### Why Block Force Push?
→ Prevents accidental rewriting of history

### Why Auto-Delete Head?
→ Keeps branch list clean, easier repository navigation

---

## Questions for Team

- [ ] Should we require Code Owners file? Which developers own which areas?
- [ ] Should require_last_push_approval be strict (yes for production safety)?
- [ ] Should we allow administrators to bypass protections? (recommend: no)
- [ ] Should PR title/commit message follow a pattern? (e.g., "feat: ...", "fix: ...")

---

**Next Document:** `04_GITHUB_ACTIONS.md` — CI/CD workflow files  
**Related:** `01_CI_CD_STRATEGY.md`, `02_AUTOMATED_CHECKS.md`
