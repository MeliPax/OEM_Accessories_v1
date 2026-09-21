# Development Standards & Workflow

**Quick Links:**
- 📋 **Versioning & Release** → `accy_v2/planning/VERSIONING.md` (branch strategy, version format, release process)
- 📖 **Development Standards** → `accy_v2/planning/CLAUDE.md` (branch naming, commits, testing, code style)
- 🚀 **Getting Started** → `accy_v2/planning/DEVELOPMENT_GUIDE.md` (step-by-step workflow for new work)

---

## For Agents: Read This First

1. **What scope is this work?** → See VERSIONING.md (hotfix/patch/minor/major)
2. **What branch do I create?** → See VERSIONING.md + CLAUDE.md (branch naming & strategy)
3. **How do I develop & test?** → See DEVELOPMENT_GUIDE.md (end-to-end workflow)
4. **How do I release?** → See VERSIONING.md (release checklist & process)

---

## At Session Start: Agent Checklist

- [ ] Read **VERSIONING.md** (2 min) — Identify work scope, branch type, base
- [ ] Review **CLAUDE.md** (branch section, 2 min) — Naming convention, branch lifecycle
- [ ] Check recent **CHANGELOG.md** — Understand current version & past work
- [ ] Run `git status` — Verify on correct branch, working tree clean

---

## Key Rules (Non-Negotiable)

✋ **Never do this:**
- Develop directly on `dev` or `main`
- Force-push to `dev` or `main`
- Skip testing before merge PR
- Tag versions on branches (only on `main`)

✅ **Always do this:**
- Create feature/fix/hotfix branch from correct base (dev or main)
- Test all available/configured OEM pipelines before PR
- Update CHANGELOG.md for any version-level change
- Delete branch after merge

---

## Versioning at a Glance

```
v{MAJOR}.{MINOR}.{PATCH}[-hotfix.{N}]

HOTFIX  v2.5.0-hotfix.1    Critical prod bug          hotfix/* from main
PATCH   v2.5.1             Bug fix, improvement       fix/* from dev
MINOR   v2.6.0             Feature, OEM, upgrade      feature/* from dev
MAJOR   v3.0.0             Architecture change        feature/* from dev
```

**See VERSIONING.md for scope examples & release process.**

---

## Directory Reference

```
accy_v2/
├── planning/
│   ├── CLAUDE.md                    ← Development standards (full details)
│   ├── VERSIONING.md                ← Versioning strategy & release process
│   ├── DEVELOPMENT_GUIDE.md         ← Step-by-step workflow guide
│   ├── oem_pipeline/                ← OEM architecture & implementation plans
│   └── research/                    ← Investigation findings & proposals
├── docs/
│   ├── CHANGELOG.md                 ← Version history (read for context)
│   ├── SYSTEM_ARCHITECTURE.md       ← Pipeline design & data flow
│   └── INDEX.md                     ← Documentation index
└── oems/
    ├── hyundai_genesis/pipeline/    ← Hyundai + Genesis pipeline
    ├── mazda/pipeline/              ← Mazda pipeline
    ├── mitsubishi/pipeline/         ← Mitsubishi pipeline
    └── honda/pipeline/              ← Honda pipeline (scaffold)
```

---

## Quick Commands

```bash
# Start new work (pick correct branch type)
git checkout dev && git pull
git checkout -b feature/my-feature          # For features/OEM/upgrades
# OR
git checkout -b fix/my-bugfix               # For patches
# OR (HOTFIX ONLY)
git checkout main && git pull
git checkout -b hotfix/critical-bug         # For urgent prod issues

# Before committing
pytest accy_v2/tests/                       # Run unit tests
python run_pipeline.py hyundai              # Test pipelines

# Before PR/merge
git log --oneline dev..HEAD                 # See your commits
git diff dev                                # Review changes

# On release (maintainer only)
git tag -a v2.6.0 -m "Release v2.6.0"      # Tag on main
git push origin main --tags                 # Push with tags
```

---

**Questions?** Check the relevant doc above or update this file if something is unclear.
