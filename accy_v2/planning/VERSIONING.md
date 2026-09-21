# Versioning & Release Lifecycle

**Purpose:** Track product evolution via semantic versioning tied to branch strategy and release cycles.  
**Format:** `v{MAJOR}.{MINOR}.{PATCH}[-hotfix.{N}]`

---

## Version Scope Definition

| Level | Format | Trigger | Example | Branch |
|-------|--------|---------|---------|--------|
| **HOTFIX** | `v2.5.0-hotfix.1` | Critical prod bug, urgent | Data loss, pipeline crash | `hotfix/*` from `main` |
| **PATCH** | `v2.5.1` | Bug fix, improvement, config | Fix csv_uniqueness, DQ message enhancement | `fix/*` from `dev` |
| **MINOR** | `v2.6.0` | Feature, OEM port, significant upgrade | Add Honda pipeline, new DQ rule | `feature/*` from `dev` |
| **MAJOR** | `v3.0.0` | Architecture change, redesign, pipeline rewrite | Rewrite search_engine core | `feature/*` from `dev` |

### Scope Examples

**HOTFIX** (v2.5.0-hotfix.1)
- Fix critical data loss in pipeline
- Revert broken main deployment
- Urgent security patch

**PATCH** (v2.5.1)
- Fix minor bug in DQ logger
- Enhance error message clarity
- Update config for known edge case
- Performance improvement (no behavior change)

**MINOR** (v2.6.0)
- Add new OEM pipeline (Honda, Kia)
- Implement new feature (trim hierarchy safety net)
- Add major DQ rule or validation
- Significant improvement to existing OEM

**MAJOR** (v3.0.0)
- Complete pipeline architecture redesign
- Rewrite core search algorithm
- Database schema changes
- Multi-OEM platform restructuring

---

## Branch Strategy

### Hotfix (Critical Production Issues)

```
Branch: hotfix/DESC
Base: main
Merge: main (tag release) + dev (cherry-pick)

Flow:
  1. git checkout main
  2. git pull origin main
  3. git checkout -b hotfix/data-loss-fix
  4. [fix code]
  5. Test all OEMs
  6. Merge to main + tag v2.5.0-hotfix.1
  7. Cherry-pick commit to dev
  8. Delete branch
```

### Patch/Minor/Major (Normal Development)

```
Branch: fix/DESC (patch), feature/DESC (minor/major)
Base: dev
Merge: dev → main (on release cycle)

Flow:
  1. git checkout dev && git pull
  2. git checkout -b feature/new-oem-port
  3. [develop work]
  4. Test all OEMs + update CHANGELOG
  5. Push to origin + create PR
  6. After review merge to dev
  7. On release: merge dev → main + tag version
  8. Delete branch
```

---

## Release Process

### Pre-Release Checklist

- [ ] **All work merged to dev** — No pending branches
- [ ] **All 4 OEMs tested** — Hyundai, Genesis, Mazda, Mitsubishi pipelines pass
- [ ] **CHANGELOG updated** — v{VERSION} section with Added/Fixed/Changed
- [ ] **No DQ regressions** — Baseline warnings consistent or improved
- [ ] **Tests passing** — `pytest accy_v2/tests/` with ≥95% pass rate
- [ ] **Documentation current** — SYSTEM_ARCHITECTURE.md, README.md updated if needed

### Release Execution

```bash
# Prepare release
git checkout dev
git pull origin dev
# [Verify checklist above]

# Merge to main
git checkout main
git pull origin main
git merge --no-ff dev -m "Release v2.6.0"

# Tag release (REQUIRED — creates permanent marker)
git tag -a v2.6.0 -m "Release v2.6.0: DQ report cleanup, message improvements"

# Push everything
git push origin main
git push origin main --tags

# Create GitHub release (optional, one-liner)
gh release create v2.6.0 --notes "See CHANGELOG.md for details"
```

---

## CHANGELOG Entry Format

Add to `accy_v2/docs/CHANGELOG.md` for each release:

```markdown
## [2.6.0] - 2026-09-21

### Added
- CSV uniqueness noise filtering for DQ export reports
- Enhanced implied_fuel_type_rule messages with config context (model, trim, years)

### Fixed
- Genesis GV70/G80 Electrified mismatch causing false DATABASE_NO_MATCH

### Changed
- DQ report now includes `filtered_rules` metadata for audit trail

### Technical
- Backward compatible: `exclude_rules` parameter in `write_dq_report()`
- 94% noise reduction in Genesis warnings (44 → 9 actionable)
```

---

## Agent Workflow (Quick Ref)

### At Session Start

1. **Read this file** (or see pointer in CLAUDE.md)
2. **Identify scope:**
   - Minor bug → `fix/*` (PATCH)
   - Feature/OEM → `feature/*` (MINOR)
   - Architecture → `feature/*` (MAJOR)
   - Urgent prod issue → `hotfix/*` (HOTFIX)
3. **Branch from correct base:**
   - HOTFIX: `main`
   - PATCH/MINOR/MAJOR: `dev`

### During Development

- Commit often with clear messages (see CLAUDE.md)
- Test all 4 OEMs before PR
- Update CHANGELOG.md in final commit

### Before Merge to Dev

- [ ] All OEM pipelines pass
- [ ] DQ report shows no regressions
- [ ] CHANGELOG.md entry added
- [ ] Code review approved

### On Release (Main→Main)

- Only maintainer tags and pushes
- Tag format: `v{MAJOR}.{MINOR}.{PATCH}`
- Push both code and tags: `git push origin main --tags`

---

## Hotfix Emergency Procedure

**Scenario:** Production data loss detected, must revert immediately

```bash
# 1. Identify bad commit on main
git log main --oneline | head -5

# 2. Revert (if single commit)
git checkout main
git revert <bad-commit-hash>
git push origin main

# OR revert to last stable (if multiple commits)
git reset --hard <last-good-hash>
git push origin main --force-with-lease

# 3. Create hotfix branch to diagnose + fix
git checkout -b hotfix/data-loss-fix
[fix the bug]

# 4. Merge hotfix to main + tag
git checkout main
git merge hotfix/data-loss-fix
git tag v2.5.0-hotfix.1
git push origin main --tags

# 5. Cherry-pick fix to dev
git checkout dev
git cherry-pick <hotfix-commit>
git push origin dev

# 6. Clean up
git branch -d hotfix/data-loss-fix
```

---

## Version History Example

```
v2.6.0    — DQ cleanup + message improvements (MINOR)
v2.5.1    — Genesis GV70 electrified fix (PATCH)
v2.5.0    — Trim hierarchy orphan safety net (MINOR)
v2.4.2    — Package differentiator cross-OEM (PATCH)
v2.4.1    — Deduplication after translation fix (PATCH)
v2.4.0    — Database standardization + scoring (MINOR)
v2.3.0    — Critical search gaps fixed (MINOR)
```

---

## Branch Cleanup After Release

After release tags on main:

```bash
# List branches merged to dev
git branch --merged dev

# Delete local branches that are merged
git branch -d feature/old-feature fix/old-fix

# Delete on remote
git push origin --delete feature/old-feature fix/old-fix

# Prune tracking branches
git fetch origin --prune
```

---

## Questions

- **"Is this a hotfix or patch?"** → Is it urgent/critical for prod? Yes = hotfix, No = patch
- **"Do I branch from main or dev?"** → Hotfix (main), everything else (dev)
- **"When do I tag?"** → Only on `main`, after merging release-ready code
- **"Can I push to main directly?"** → No. Always via merge from dev or hotfix branch
