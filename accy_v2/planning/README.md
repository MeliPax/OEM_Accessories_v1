# Planning Documents

This folder contains all strategic and architectural planning documents organized by topic.

---

## Folder Structure

```
accy_v2/planning/
├── README.md                    (this file)
├── dev_workflow/                (CI/CD and development process)
│   ├── 01_CI_CD_STRATEGY.md
│   ├── 02_AUTOMATED_CHECKS.md
│   ├── 03_BRANCH_PROTECTION.md
│   └── 04_TEST_STRATEGY.md
└── oem_pipeline/                (OEM pipeline modernization)
    └── 05_HONDA_HYUNDAI_V2_PORT.md
```

---

## Development Workflow Documents

### 1. 📋 [CI/CD Strategy](dev_workflow/01_CI_CD_STRATEGY.md) — **Status: Draft**

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

### 2. 🔍 [Automated Checks Specification](dev_workflow/02_AUTOMATED_CHECKS.md) — **Status: Draft**

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

### 3. 🔐 [Branch Protection Rules](dev_workflow/03_BRANCH_PROTECTION.md) — **Status: Draft**

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

### 4. 🧪 [Test Strategy](dev_workflow/04_TEST_STRATEGY.md) — **Status: Draft**

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

## OEM Pipeline Modernization Documents

### 5. 🏭 [Honda & Hyundai v2 Port](oem_pipeline/05_HONDA_HYUNDAI_V2_PORT.md) — **Status: Approved**

**Overview:** Plan to bring Honda and Hyundai pipelines into the `accy_v2` modular architecture.

**Contains:**
- Current state of Honda (3,298-line script) and Hyundai (flat notebooks)
- Design decisions: dynamic trim detection, directory-based loading, FR integration
- Hyundai Phase 1 (3–4 days): flat master sheet → modular pipeline
- Honda Phase 2 (5–7 days): multi-file loading with 6 sections per sheet
- Step-by-step implementation guide for both OEMs
- Prerequisite: Hyundai model data migration into unified DB

**Audience:** Implementation team (tech-focused)

**Next step:** Execute Phase 1 (Hyundai data migration + pipeline build)

---

## How to Use These Documents

### For Decision-Makers (Development Workflow)
1. Read `dev_workflow/01_CI_CD_STRATEGY.md` cover-to-cover
2. Review the "Questions for Team" section
3. Discuss with team and document decisions

### For Decision-Makers (OEM Modernization)
1. Read `oem_pipeline/05_HONDA_HYUNDAI_V2_PORT.md` for context
2. Review all design decisions (marked ✅ as approved)
3. Approve implementation sequence (Hyundai → Honda)

### For Developers Implementing CI/CD
1. Read `dev_workflow/01_CI_CD_STRATEGY.md` for context
2. Use `dev_workflow/02_AUTOMATED_CHECKS.md` to understand each check
3. Use `dev_workflow/03_BRANCH_PROTECTION.md` to understand GitHub rules
4. Use `dev_workflow/04_TEST_STRATEGY.md` to write tests

### For Developers Porting OEM Pipelines
1. Read `oem_pipeline/05_HONDA_HYUNDAI_V2_PORT.md` cover-to-cover
2. Follow Phase 1 (Hyundai) implementation guide
3. Use `accy_v2/oems/mitsubishi/` and `accy_v2/oems/mazda/` as blueprint
4. Consult `accy_v2/core/base_pipeline.py` for shared base class

### For Repository Admins (Branches)
1. Read `dev_workflow/03_BRANCH_PROTECTION.md`
2. Configure rules in GitHub using provided JSON
3. Create `.github/CODEOWNERS` file if appropriate

### For Code Reviewers
1. Understand expectations from `dev_workflow/02_AUTOMATED_CHECKS.md`
2. Know branch protection requirements from `dev_workflow/03_BRANCH_PROTECTION.md`
3. Use test strategy from `dev_workflow/04_TEST_STRATEGY.md` when reviewing PRs

---

## Status Tracking

### Development Workflow (CI/CD)

| Document | Status | Last Updated | Approval |
|----------|--------|--------------|----------|
| dev_workflow/01_CI_CD_STRATEGY.md | Draft | 2026-06-26 | ⏳ Pending |
| dev_workflow/02_AUTOMATED_CHECKS.md | Draft | 2026-06-26 | ⏳ Pending |
| dev_workflow/03_BRANCH_PROTECTION.md | Draft | 2026-06-26 | ⏳ Pending |
| dev_workflow/04_TEST_STRATEGY.md | Draft | 2026-06-26 | ⏳ Pending |

### OEM Pipeline Modernization

| Document | Status | Last Updated | Approval |
|----------|--------|--------------|----------|
| oem_pipeline/05_HONDA_HYUNDAI_V2_PORT.md | Approved | 2026-06-26 | ✅ Approved |

---

## Implementation Roadmap

### Development Workflow (CI/CD Setup)

| Phase | Timeline | Tasks |
|-------|----------|-------|
| 1: Decision & Planning | Week 1 | Read all docs, answer team questions, mark approved |
| 2: GitHub Configuration | Week 2 | Branch protection rules, CODEOWNERS file, webhook setup |
| 3: CI/CD Scripts & Tests | Weeks 3–4 | Write lint/test scripts, unit tests, fixtures, coverage |
| 4: GitHub Actions Workflows | Weeks 5–6 | CI workflow, staging workflow, release workflow |
| 5: Team Onboarding | Week 7 | Training, troubleshooting docs, health monitoring |

### OEM Pipeline Modernization

| Phase | Timeline | Tasks |
|-------|----------|-------|
| 0: Planning Folder Reorganization | ✅ **Done** | Created dev_workflow/ and oem_pipeline/ subfolders |
| 1: Hyundai Port | ~3–4 days | Data migration + 5-step pipeline build |
| 2: Honda Port | ~5–7 days | Directory-based loading, section extraction, FR integration |

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

