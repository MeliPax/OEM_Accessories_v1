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

## Commit & Push Checklist (every agent, every commit)

1. **`git status` first.** Know every changed file before staging anything.
2. **Stage files by name** (`git add path/to/file`). Never `git add -A` / `git add .`: pipeline runs leave changes behind that don't belong in your commit.
3. **Never commit** (all in `.gitignore`; if one shows up, fix `.gitignore`, don't commit it):
   - `__pycache__/`, `*.pyc` — Python bytecode
   - `.claude/settings.json`, `.claude/settings.local.json`, `.claude/scheduled_tasks.lock` — per-person Claude settings
   - `creds/`, `*.env` — credentials (never read, print or commit them)
4. **Don't mix data and code.** A pipeline run can change files you didn't edit (see below). Keep them out of a code commit.
5. **Push only what the user asked for**, and never push `dev` / `main` without tests passing (see Key Rules).
6. **After a merge:** delete the branch (local and `origin`).
7. **No stashes.** A stash is uncommitted work set aside outside any branch; it isn't on GitHub and gets forgotten. Don't leave work in one: commit it to a branch (`git stash branch <type>/<name>`), or drop it once you've confirmed it holds nothing needed. If `git stash list` shows anything, tell the user what each one holds.
8. **Switching branches with uncommitted changes:** if the user has files open or modified (often notebooks), don't stash or discard them. Do the branch work in a separate worktree (`git worktree add <dir> <branch>`) and remove it afterwards.

### Long-lived branches: keep them in sync with `dev`

A branch that lives for weeks (e.g. a Honda pipeline branch) must pick up what lands on `dev`, especially shared code: `accy_v2/core/`, `accy_v2/model_lookup/`, `run_pipeline.py`.

- **Check:** `git fetch` then `git log --oneline <branch>..origin/dev -- accy_v2/core accy_v2/model_lookup run_pipeline.py`. Anything listed → sync.
- **Sync = merge `dev` into the branch** (`git merge origin/dev` on the branch). Don't rebase a long-lived branch: it rewrites every commit.
- Resolve conflicts keeping both sides' intent, run that OEM's pipeline before and after the merge, and say in the merge commit what was tested.

### Vehicle DB: keep `dev` up to date

Pipeline runs fetch new vehicles and append them to `accy_v2/model_lookup/db/db_vehicle_models.csv`. `dev` should always have the latest DB:

- **When `git status` shows the DB changed:** commit it on its own `data/vehicle-db-YYYY-MM-DD` branch from `dev` (DB file only), merge `--no-ff` into `dev`, push `dev`, delete the branch. Commit message: what was added (makes, models, years, row count).
- **Keyword configs** (`accy_v2/model_lookup/configs/*_keywords.json`) are rewritten on every run. If only `generated_at` changed, discard the change (`git checkout -- <file>`). If the `keywords` list changed, commit it with the DB.
- Rows with a blank `TrimName` / `ModelName` are committed as fetched; mention them in the commit message.

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
