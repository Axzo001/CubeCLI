# GitHub Repository Setup Guide

This file is for maintainers. It lists everything to configure after pushing to GitHub.

---

## 1. Repository Settings

### General
- **Description:** `🧊 Professional Rubik's Cube speedcubing timer for your terminal — WCA scrambles, ANSI cube preview, braille charts, OLL/PLL trainer`
- **Website:** `https://pypi.org/project/cubecli` (after PyPI publish)
- **Topics / Tags:**
  ```
  rubiks-cube  speedcubing  timer  cli  tui  terminal  python  wca
  scramble  cube  puzzle  textual  rich  oll  pll  cfop
  ```

### Features to enable
- [x] Issues
- [x] Discussions
- [x] Projects
- [ ] Wiki (optional)

### Branch Protection (main)
- [x] Require pull request reviews (1 reviewer minimum)
- [x] Require status checks to pass before merging
  - `lint` (CI)
  - `test (ubuntu-latest, 3.11)`
- [x] Require branches to be up to date before merging
- [x] Do not allow bypassing the above settings

---

## 2. Secrets (for CI)

Go to **Settings → Secrets and Variables → Actions**:

| Secret | Value | Used for |
|---|---|---|
| `CODECOV_TOKEN` | Codecov project token | Coverage upload |
| `PYPI_API_TOKEN` | PyPI trusted publisher | Auto-publish on tag |

For PyPI, use **Trusted Publishing** (OIDC) — no token needed, just configure on PyPI side.

---

## 3. Labels to Create

Run this script or create manually:

```bash
gh label create "bug"             --color "d73a4a" --description "Something isn't working"
gh label create "enhancement"     --color "a2eeef" --description "New feature or request"
gh label create "needs-triage"    --color "e4e669" --description "Awaiting maintainer review"
gh label create "good first issue" --color "7057ff" --description "Good for newcomers"
gh label create "help wanted"     --color "008672" --description "Extra attention needed"
gh label create "documentation"   --color "0075ca" --description "Docs improvements"
gh label create "phase-1"         --color "f9a826" --description "Phase 1: Core Timer"
gh label create "phase-2"         --color "f9a826" --description "Phase 2: Cube Preview"
gh label create "phase-3"         --color "f9a826" --description "Phase 3: Stats & Charts"
gh label create "phase-4"         --color "f9a826" --description "Phase 4: Training Mode"
gh label create "duplicate"       --color "cfd3d7" --description "Already reported"
gh label create "wontfix"         --color "ffffff" --description "Will not be addressed"
```

---

## 4. Project Board

Create a **GitHub Project** with columns:
- 📋 Backlog
- 🔜 Up Next
- 🚧 In Progress
- 👀 In Review
- ✅ Done

---

## 5. First Push

```bash
cd CubeCLI
git init
git add .
git commit -m "chore: initial project scaffold 🧊"
git branch -M main
git remote add origin https://github.com/Axzo001/CubeCLI.git
git push -u origin main
```

---

## 6. Codecov Setup

1. Go to [codecov.io](https://codecov.io) and add the repo
2. Copy the upload token → add as `CODECOV_TOKEN` secret
3. Add the Codecov badge to README (auto-generated on the Codecov dashboard)

---

## 7. PyPI Trusted Publisher

1. Go to [pypi.org](https://pypi.org) → Your Account → Publishing
2. Add a new **Trusted Publisher**:
   - Owner: `Axzo001`
   - Repo: `CubeCLI`
   - Workflow: `ci.yml`
   - Environment: (leave blank)

Then publishing is fully automated when you push a `vX.Y.Z` tag.
