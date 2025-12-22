# ReelRecon Development Workflow

This document outlines the Git workflow and development process for ReelRecon.

---

## Branch Strategy

```
main (production)
  │
  └── develop (integration)
        │
        ├── feature/xyz
        ├── feature/abc
        └── hotfix/urgent-fix
```

| Branch | Purpose | Merges To |
|--------|---------|-----------|
| `main` | Stable releases only. What users download. | - |
| `develop` | Active development. Integration branch. | `main` (via PR) |
| `feature/*` | Individual features or improvements | `develop` (via PR) |
| `hotfix/*` | Urgent fixes for production | `main` AND `develop` |

---

## Day-to-Day Development

### Starting a New Feature

```bash
# Make sure you're on develop and up-to-date
git checkout develop
git pull origin develop

# Create a feature branch
git checkout -b feature/my-feature-name

# Work on your changes...
# Then commit
git add .
git commit -m "Add my feature description"

# Push to GitHub
git push -u origin feature/my-feature-name
```

### Submitting Your Feature

1. Go to GitHub
2. Create a Pull Request: `feature/my-feature-name` → `develop`
3. Review the changes
4. Merge the PR
5. Delete the feature branch

### Syncing with Latest Changes

```bash
git checkout develop
git pull origin develop

# If you're on a feature branch, merge in latest develop
git checkout feature/my-feature
git merge develop
```

---

## Releasing to Production

When `develop` is stable and tested:

1. **Create a Pull Request**: `develop` → `main`
2. **Review** all changes since last release
3. **Merge** the PR
4. **Tag the release** on GitHub:
   - Go to Releases → Create new release
   - Tag: `v2.1.0` (use semantic versioning)
   - Title: `ReelRecon v2.1.0`
   - Describe what's new

### Semantic Versioning

```
v[MAJOR].[MINOR].[PATCH]-[PRERELEASE]

Examples:
v1.0.0        - First stable release
v1.1.0        - New feature added
v1.1.1        - Bug fix
v2.0.0        - Breaking changes
v2.0.0-alpha  - Pre-release testing
v2.0.0-beta   - Feature complete, testing
```

---

## Hotfixes (Urgent Production Fixes)

For critical bugs in production:

```bash
# Branch from main
git checkout main
git pull origin main
git checkout -b hotfix/fix-description

# Make the fix
git add .
git commit -m "Fix critical bug in X"

# Push and create PRs to BOTH main AND develop
git push -u origin hotfix/fix-description
```

Create two Pull Requests:
1. `hotfix/fix-description` → `main` (deploy the fix)
2. `hotfix/fix-description` → `develop` (keep develop updated)

---

## Quick Reference

| Task | Command |
|------|---------|
| See current branch | `git branch` |
| See all branches | `git branch -a` |
| Switch branches | `git checkout branch-name` |
| Create & switch | `git checkout -b new-branch` |
| See changes | `git status` |
| See diff | `git diff` |
| Stage changes | `git add .` |
| Commit | `git commit -m "message"` |
| Push | `git push origin branch-name` |
| Pull latest | `git pull origin branch-name` |
| View history | `git log --oneline -10` |

---

## Files Not Committed (gitignore)

These files/folders are local only and never pushed:

- `cookies.txt`, `tiktok_cookies.txt` - Personal authentication
- `config.json` - Local configuration
- `output/`, `output_*/` - Scrape output folders
- `logs/` - Runtime log files
- `state/` - Persistent state files
- `scrape_history.json` - Local scrape history
- `__pycache__/` - Python cache
- `*.pt` - Whisper model files

---

## Current Release Tags

| Tag | Description |
|-----|-------------|
| `v1.0.0-alpha` | Initial release, basic functionality |
| (develop) | v2.0.0-alpha: Error handling, state persistence |

---

## Need Help?

```bash
# Undo uncommitted changes
git checkout -- .

# Undo last commit (keep changes)
git reset --soft HEAD~1

# See what would be pushed
git log origin/develop..HEAD
```
