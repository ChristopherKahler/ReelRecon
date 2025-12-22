# Git Workflow Setup Summary

**Date:** December 22, 2024
**Project:** ReelRecon
**Purpose:** Learning reference for Git workflow and CI/CD pipeline setup

---

## The Problem We Solved

You had two versions of ReelRecon:
- **v1** in `/mnt/c/Users/Chris/Documents/ReelRecon` - Connected to GitHub, working but basic
- **v2** in `/mnt/c/Users/Chris/Documents/ReelRecon v2` - Enhanced code, NOT on GitHub

**Goals:**
1. Get v2 code into GitHub without losing v1
2. Set up a branching strategy for safe development
3. Allow your partner to get stable updates
4. Work on features without anxiety about breaking production

---

## What We Did (Step by Step)

### Step 1: Tag v1 as a Release

**What:** Created release tag `v1.0.0-alpha` on GitHub

**Why:**
- Preserves v1 forever - you can always go back to this exact code
- Tags are like bookmarks in Git history
- The `-alpha` suffix signals "early testing phase"

**Command equivalent:**
```bash
git tag v1.0.0-alpha
git push origin v1.0.0-alpha
```
(We did this via GitHub UI)

---

### Step 2: Clean Up v1 Working Directory

**What:** Ran `git checkout -- .`

**Why:**
- v1 had uncommitted changes (80 lines in app.py and core.py)
- Since v2 has better code, we didn't need those changes
- This reset the files to match the last commit

**Key Concept:**
```
Git has 3 locations:
├── GitHub (remote)     ← Cloud storage
├── .git folder (local) ← History database
└── Your files (local)  ← What you edit

"git checkout -- ." only changes your files, not GitHub or history
```

---

### Step 3: Create Develop Branch

**What:** Created `develop` branch from `main`

**Commands:**
```bash
git checkout -b develop    # Create and switch to develop
git push -u origin develop # Push to GitHub, set up tracking
```

**Why:**
- `main` stays stable (what users download)
- `develop` is where active work happens
- Features branch off develop, not main
- This is called "Git Flow" branching strategy

**Result:**
```
main     ← Stable releases (v1.0.0-alpha)
develop  ← Active development
```

---

### Step 4: Copy v2 Code into Develop

**What:** Copied enhanced files from v2 folder to v1 folder (on develop branch)

**Files copied:**
| File | What It Contains |
|------|------------------|
| `app.py` | State management, error endpoints, cleanup handlers |
| `scraper/core.py` | Retry logic, heartbeat updates, logging |
| `scraper/tiktok.py` | TikTok scraper (NEW) |
| `scraper/__init__.py` | Module exports (updated) |
| `utils/` | NEW folder: logger, state_manager, retry utilities |
| `static/js/app.js` | Error code display, fixed auto-hide bug |
| `static/css/tactical.css` | Enhanced styles |
| `templates/index.html` | Updated HTML |
| `requirements.txt` | Updated dependencies |

**Commands:**
```bash
cp "/path/to/v2/file" "/path/to/v1/file"
```

**Why not just replace everything?**
- We wanted to keep v1's `.git` folder (history)
- We wanted to keep v1's `.gitignore` (and update it)
- Selective copying is safer

---

### Step 5: Update .gitignore

**What:** Added v2's runtime folders to .gitignore

**Added:**
```
logs/           # Runtime log files
state/          # Persistent state JSON
output_*/       # Any output folder variants
tiktok_cookies.txt
```

**Why:**
- These files are generated at runtime
- They contain personal/local data
- They shouldn't be in the repo

---

### Step 6: Commit and Push

**What:** Saved all changes to Git and uploaded to GitHub

**Commands:**
```bash
git add .                    # Stage all changes
git commit -m "message..."   # Save to local Git database
git push origin develop      # Upload to GitHub
```

**The commit message:**
```
v2.0.0-alpha: Robust error handling, state persistence, retry logic

- Add utils/ module: logger, state_manager, retry utilities
- Persistent scrape state survives server restarts
- Trackable error codes (e.g., SCRAPE-12345-ABCD)
- Exponential backoff retry for downloads
- Heartbeat progress updates during transcription
- Frontend: errors require manual dismissal, show error codes
- Updated .gitignore for runtime folders
```

**Why this format?**
- First line: Summary (what changed)
- Bullet points: Details (why/how)
- Future you can understand what this commit did

---

### Step 7: Add Documentation

**What:** Created `CONTRIBUTING.md` with workflow instructions

**Why:**
- Documents how to use the branching strategy
- Reference for yourself and collaborators
- Includes command cheat sheet

---

## Key Git Concepts Learned

### Branches
```
Think of branches like parallel universes.
Changes in one branch don't affect others until you merge.

main ─────●─────●─────●────────────────── (stable)
           \
develop ────●─────●─────●─────●────────── (active work)
                   \
feature/x ──────────●─────●─────────────── (isolated feature)
```

### The Git Workflow
```
1. Edit files           (your filesystem)
2. git add .            (stage changes)
3. git commit           (save to local .git)
4. git push             (upload to GitHub)
```

### Tags vs Branches
- **Branch:** Moving pointer, changes as you commit
- **Tag:** Fixed bookmark, always points to same commit

---

## Current Repository State

```
GitHub: ChristopherKahler/ReelRecon
│
├── main branch
│   └── Tagged: v1.0.0-alpha (original release)
│
└── develop branch
    └── Commits:
        ├── v2.0.0-alpha: Robust error handling...
        ├── Add development workflow documentation
        └── Add TikTok scraper module
```

---

## Going Forward

### To work on a new feature:
```bash
git checkout develop
git pull origin develop
git checkout -b feature/my-feature
# ... make changes ...
git add .
git commit -m "Add my feature"
git push -u origin feature/my-feature
# Create Pull Request on GitHub
```

### To release to production:
```bash
# On GitHub: Create PR from develop → main
# Merge it
# Create new release tag (e.g., v2.0.0)
```

### Your partner pulls stable releases:
```bash
git checkout main
git pull origin main
```

---

## Files Changed Today

| File | Action | Lines |
|------|--------|-------|
| `app.py` | Modified | +600 |
| `scraper/core.py` | Modified | +400 |
| `scraper/tiktok.py` | Created | +408 |
| `scraper/__init__.py` | Modified | +7 |
| `utils/__init__.py` | Created | +5 |
| `utils/logger.py` | Created | +150 |
| `utils/state_manager.py` | Created | +200 |
| `utils/retry.py` | Created | +100 |
| `static/js/app.js` | Modified | +50 |
| `static/css/tactical.css` | Modified | +400 |
| `templates/index.html` | Modified | +20 |
| `.gitignore` | Modified | +6 |
| `CONTRIBUTING.md` | Created | +176 |

**Total: ~3,500 lines of code migrated from v2 to v1 repo**

---

## Quick Reference Card

| I want to... | Command |
|--------------|---------|
| See what branch I'm on | `git branch` |
| See uncommitted changes | `git status` |
| Switch to a branch | `git checkout branch-name` |
| Create new branch | `git checkout -b new-branch` |
| Save my changes | `git add . && git commit -m "msg"` |
| Upload to GitHub | `git push origin branch-name` |
| Download latest | `git pull origin branch-name` |
| Undo uncommitted changes | `git checkout -- .` |
| See commit history | `git log --oneline -10` |
