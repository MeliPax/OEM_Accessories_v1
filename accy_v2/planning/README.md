# Planning Documents

This folder contains all strategic and architectural planning documents for the OEM Accessory Pipeline CI/CD and development process improvements.

---

## Document Index

### 1. 📋 [CI/CD Strategy](01_CI_CD_STRATEGY.md) — **Status: Draft**

**Overview:** High-level strategy for implementing a two-tier branching workflow with automated checks and staged deployments.

**Contains:**
- Current state analysis (staging, main branches exist)
- Proposed workflow (feature → staging → main → deploy)
- Automated check categories (linting, tests, security, docs)
- Merge requirements (checks + reviews)
- Deployment strategy (auto-deploy to staging, tag-based production deploy)
- Risk mitigation and success metrics
- Timeline (4 phases over 7 weeks)
- Questions for team review

**Audience:** Entire team (decisions needed here)

**Next step:** Review and answer "Questions for Team"

---

### 2. 🔍 [Automated Checks Specification](02_AUTOMATED_CHECKS.md) — **Status: Draft**

**Overview:** Concrete specification for every check that runs in CI: which tool, what it checks, how to run locally, expected time.

**Contains:**
- Style & format checks (flake8, black, isort)
- Type checking (mypy)
- Unit tests (pytest)
- Integration tests (pytest, longer timeout)
- Security scanning (detect-secrets, safety, bandit)
- Documentation checks (pydocstyle, links)
- Data quality validation (smoke tests)
- Run-time summary table
- Local developer workflow (commands to run before push)
- Questions for team

**Audience:** Developers implementing CI (tech-focused)

**Next step:** Decide on tools and thresholds (coverage %, timeouts, etc.)

---

### 3. 🔐 [Branch Protection Rules](03_BRANCH_PROTECTION.md) — **Status: Draft**

**Overview:** GitHub branch protection rules to enforce on `staging` and `main` branches.

**Contains:**
- Staging branch rules (1 review, status checks, no force push)
- Main branch rules (2 reviews, code owner approval, stricter merge rules)
- Comparison table (Staging vs. Main)
- Implementation steps (how to set in GitHub)
- GitHub settings JSON configuration
- Rationale for each rule
- Questions for team

**Audience:** Repository admins, developers (understanding expectations)

**Next step:** Configure rules in GitHub repository settings

---

### 4. 🧪 [Test Strategy](04_TEST_STRATEGY.md) — **Status: Draft**

**Overview:** Testing strategy for the pipeline: where to put tests, what to test, coverage targets, fixtures.

**Contains:**
- Folder structure for tests (unit/, integration/, fixtures/)
- Unit test categories (config, mappers, helpers, each step)
- Integration test cases (E2E pipeline, output schema, DQ report)
- Shared pytest fixtures (sample data, configs)
- Coverage targets by module (>80% overall)
- Test data management strategy
- Running tests locally (commands)
- CI integration (what runs on each trigger)
- Questions for team

**Audience:** Test developers, QA (implementation-focused)

**Next step:** Create test files and fixtures following this structure

---

## How to Use These Documents

### For Decision-Makers
1. Read `01_CI_CD_STRATEGY.md` cover-to-cover
2. Review the "Questions for Team" section
3. Discuss with team and document decisions
4. Mark document status as "Approved"

### For Developers Implementing CI/CD
1. Read `01_CI_CD_STRATEGY.md` for context
2. Use `02_AUTOMATED_CHECKS.md` to understand each check
3. Use `03_BRANCH_PROTECTION.md` to understand GitHub rules
4. Use `04_TEST_STRATEGY.md` to write tests

### For Repository Admins
1. Read `03_BRANCH_PROTECTION.md`
2. Configure rules in GitHub using provided JSON
3. Create `.github/CODEOWNERS` file if appropriate

### For Code Reviewers
1. Understand expectations from `02_AUTOMATED_CHECKS.md`
2. Know branch protection requirements from `03_BRANCH_PROTECTION.md`
3. Use test strategy from `04_TEST_STRATEGY.md` when reviewing PRs

---

## Status Tracking

| Document | Status | Last Updated | Owner | Approval |
|----------|--------|--------------|-------|----------|
| 01_CI_CD_STRATEGY.md | Draft | 2026-06-26 | Dev Team | ⏳ Pending |
| 02_AUTOMATED_CHECKS.md | Draft | 2026-06-26 | Dev Team | ⏳ Pending |
| 03_BRANCH_PROTECTION.md | Draft | 2026-06-26 | Dev Team | ⏳ Pending |
| 04_TEST_STRATEGY.md | Draft | 2026-06-26 | Dev Team | ⏳ Pending |

---

## Implementation Roadmap

### Phase 1: Decision & Planning (Week 1)
- [ ] Read all documents
- [ ] Answer "Questions for Team" in each doc
- [ ] Mark documents as "Approved"
- [ ] Assign owners for implementation

### Phase 2: GitHub Configuration (Week 2)
- [ ] Set up branch protection rules
- [ ] Create `.github/CODEOWNERS` file
- [ ] Configure webhook for CI/CD platform

### Phase 3: CI/CD Scripts & Tests (Weeks 3-4)
- [ ] Create `scripts/lint.sh`, `scripts/test.sh`, etc.
- [ ] Write unit tests following `04_TEST_STRATEGY.md`
- [ ] Create test fixtures
- [ ] Set up coverage reporting

### Phase 4: GitHub Actions Workflows (Weeks 5-6)
- [ ] Create `.github/workflows/ci.yml`
- [ ] Create `.github/workflows/staging.yml`
- [ ] Create `.github/workflows/release.yml`
- [ ] Test workflows on feature branch

### Phase 5: Team Onboarding (Week 7)
- [ ] Train team on new workflow
- [ ] Document troubleshooting
- [ ] Monitor CI/CD health

---

## Questions & Decisions Needed

### From `01_CI_CD_STRATEGY.md`
- [ ] Is GitHub Actions the preferred CI/CD platform?
- [ ] Who are primary code reviewers?
- [ ] Should staging auto-deploy or manual trigger?
- [ ] What monitoring/alerting tools?

### From `02_AUTOMATED_CHECKS.md`
- [ ] Prefer these tools or alternatives?
- [ ] Coverage threshold: 80% or higher?
- [ ] Type hints required or encouraged?
- [ ] Documentation check blocks merge?

### From `03_BRANCH_PROTECTION.md`
- [ ] Require Code Owners file? Which areas?
- [ ] Require last_push_approval on main?
- [ ] Allow admins to bypass? (recommend: no)
- [ ] Enforce commit message pattern?

### From `04_TEST_STRATEGY.md`
- [ ] Mock external dependencies?
- [ ] Integration tests use actual pipeline classes?
- [ ] Coverage threshold: 80% or higher?
- [ ] Test data in fixtures/ or generated?
- [ ] Need performance tests?

---

## Next Steps

1. **Review Phase** (This Week)
   - Distribute documents to team
   - Collect feedback on questions
   - Schedule review meeting

2. **Decision Phase** (Next Week)
   - Present recommendations
   - Make decisions on tools, policies, thresholds
   - Assign implementation owners

3. **Implementation Phase** (Following Weeks)
   - Follow Phase 1-5 roadmap above
   - Document any deviations
   - Update these status tables

---

## Related Documentation

- `accy_v2/DEVELOPER_GUIDE.md` — How to contribute code
- `accy_v2/CHANGELOG.md` — Change history
- `accy_v2/README.md` — Project overview
- `.github/CODEOWNERS` (to create) — Who reviews what

---

## Contact

For questions about these planning documents, contact the development team lead.

---

**Document Status:** ⏳ Awaiting team review and decision  
**Last Updated:** June 26, 2026  
**Next Review:** After team feedback

