# CLAUDE.md — Development Workflow & Standards

**Status:** 📋 PLANNING (Template for project-wide development guidelines)  
**Date Created:** 2026-09-09  
**Purpose:** Central guide for all agents on code development, branching, commits, and testing

---

## Overview

This document defines the workflow and standards for all development in this project. It ensures consistency across work items, reduces context-switching overhead, and provides clear checkpoints for quality and testing.

---

## Branch Naming & Strategy

### Branch Categories

| Category | Prefix | Purpose | Lifespan |
|----------|--------|---------|----------|
| Feature | `feature/` | New feature or mechanism | Until merged to dev |
| Bugfix | `fix/` | Bug fix with root cause analysis | Until merged to dev |
| Research | `research/` | Investigation / exploration (no code changes) | Until merged to docs/planning |
| Docs | `docs/` | Documentation only | Until merged to dev |
| Refactor | `refactor/` | Code cleanup, no behavior change | Until merged to dev |

### Naming Convention

```
{category}/{short-description}

Examples:
  feature/trim-hierarchy-orphan-safety-net
  fix/gv70-electrified-fuel-type-gate
  research/package-differentiator-cross-oem
  docs/dq-report-architecture
  refactor/search-engine-step-simplification
```

### Branch Lifecycle

1. **Create** — Branch from `dev`, never from `main`
2. **Develop** — Commit frequently, write clear messages
3. **Test** — All local tests + pipeline verification pass
4. **PR** — Request review, address feedback
5. **Merge** — Squash or keep commit history (per review)
6. **Delete** — Remove branch after merge

**Never:**
- Develop directly on `dev` or `main`
- Force-push to `dev` or `main` (only use `--force-with-lease` if absolutely needed)
- Cherry-pick from `main` into feature branches (rebase onto `dev` instead)

---

## Commit Message Standards

### Format

```
{Type}: {Short Summary}

{Optional Body}
{Optional Body Lines}
```

### Types

- **Implement** — New code/feature
- **Fix** — Bug fix
- **Refactor** — Code cleanup
- **Docs** — Documentation
- **Plan** — Planning/proposal documents
- **Test** — Test additions/updates
- **Analysis** — Investigation results

### Examples

**Good:**
```
Implement: Trim hierarchy orphan safety net (Part 1 + Part 2)

Part 1 — implied_trim_variant_trims mechanism...
Part 2 — orphaned_record_rule DQ check...

Impact: Elantra TCR now finds N-line model...
```

**Bad:**
```
update stuff
Fixed things
WIP orphan safety net
```

### Guidelines

- Keep summary ≤70 characters
- Use imperative mood ("add", not "added")
- Reference issues/proposals if relevant: `Implement: ... (ref: trim_hierarchy_orphan_safety_net/PROPOSAL.md)`
- Body explains "why", not "what" (code is the "what")

---

## Testing Requirements Before PR

### Unit Tests
- [ ] All modified functions have unit tests
- [ ] Edge cases covered (null, empty, boundary values)
- [ ] Tests pass: `pytest accy_v2/tests/`

### Integration Tests
- [ ] Pipeline runs end-to-end for all modified OEMs
- [ ] No new DQ warnings (orphaned_record_rule, model_number_lookup_rule, etc.)
- [ ] Output workbook valid (all sheets present, columns correct)

### Code Quality
- [ ] No syntax errors (Python -m py_compile)
- [ ] Type hints on new functions (Optional[X], Dict[str, Y])
- [ ] No unused imports or dead code

### Documentation
- [ ] Docstrings on new functions (one-line + params if complex)
- [ ] Commit message explains "why"
- [ ] Planning doc updated if scope changed (PROPOSAL.md, README.md, etc.)

### Pipeline Verification
- [ ] Run Genesis pipeline (minimum): verify no new failures
- [ ] Spot-check DQ report (if model lookup touched)
- [ ] Verify output format matches downstream schema

---

## Code Style & Conventions

### Python

```python
# Type hints required for function signatures
def flag_orphaned_records(
    df: pd.DataFrame,
    dq_logger: Optional[DQLogger],
    sheet_name: str,
    model_number_column: str = "Model",
) -> pd.DataFrame:
    """One-line summary.
    
    Args:
        df: Description
        dq_logger: Description
    
    Returns:
        Modified DataFrame
    """
    # Docstrings only if non-obvious
    # Comments explain "why", not "what" (code names do that)
    
    return df
```

### YAML (Config)

```yaml
# Use descriptive comments above blocks
# Indent consistently (2 spaces)
implied_fuel_type_trims:
  - model_keywords: [tucson]
    trim_keywords: [n-line]
    fuel_type: hybrid
    years: [2024, 2025, 2026]
```

### Git Workflow Commands

```bash
# Start work
git checkout dev
git pull origin dev
git checkout -b feature/my-feature

# Develop & commit
git add accy_v2/path/to/file.py
git commit -m "Implement: Feature description"

# Before PR
git rebase dev  # Resolve conflicts if any
git push origin feature/my-feature

# After review + merge (locally clean up)
git checkout dev
git pull origin dev
git branch -d feature/my-feature
```

---

## Code Review Expectations

### What to Expect in Review

1. **Functional correctness** — Does it do what it claims?
2. **Architecture alignment** — Follows existing patterns (config-driven, cross-OEM)?
3. **Safety** — No SQL injection, command injection, XSS, etc.
4. **Testing** — Edge cases covered?
5. **Documentation** — Comments explain "why", docstrings clear?

### Responding to Feedback

- Address each comment explicitly
- Commit follow-up fixes (don't amend unless requested)
- Mark as "ready" only after all feedback resolved
- Approve button = "code is good, merge when ready"

---

## Deployment & Release

- **Merge to `dev`** — Tested feature branch, ready for integration
- **Merge to `main`** — Stable, release-ready code (via formal release process)
- **Tag versions** — After `main` merge, tag with semantic version (see VERSIONING.md)

### Version Scope (Quick Ref)

| Type | Trigger | Branch | Version |
|------|---------|--------|---------|
| **HOTFIX** | Critical prod bug (data loss, crash) | `hotfix/*` from `main` | `v2.5.0-hotfix.1` |
| **PATCH** | Bug fix, improvement, config | `fix/*` from `dev` | `v2.5.1` |
| **MINOR** | Feature, OEM port, upgrade | `feature/*` from `dev` | `v2.6.0` |
| **MAJOR** | Architecture change, redesign | `feature/*` from `dev` | `v3.0.0` |

**See `VERSIONING.md` for full details**, release process, and emergency procedures.

---

## Common Pitfalls & How to Avoid

| Pitfall | Fix |
|---------|-----|
| Developing on `dev` directly | Always create a feature branch first |
| Unclear commit messages | Follow "Type: Summary" format |
| Pushing without testing | Run local pipeline tests + pytest first |
| Force-pushing to dev/main | Use `--force-with-lease` only as last resort |
| Merging without review | Always create PR, even for simple fixes |
| Forgetting to update docs | Update PROPOSAL.md, README.md, CHANGELOG.md in same commit |

---

## Questions & Escalation

- **Config question?** → Check enrichment.yaml comment blocks first
- **Pipeline question?** → Check base_pipeline.py docstrings
- **Test failing?** → Check recent commits on that file via `git log -p file.py`
- **Unclear standard?** → Ask in PR or update this doc

---

**Next Step:** Use this template to refine guidelines based on team feedback; move to project root as CLAUDE.md once finalized.
