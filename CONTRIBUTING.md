# Contributing to CubeCLI

Thank you for your interest in contributing to CubeCLI! 🧊

This document covers everything you need to know to get started — from setting up your environment to submitting a pull request.

---

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How Can I Contribute?](#how-can-i-contribute)
- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Code Style](#code-style)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)
- [Release Process](#release-process)

---

## Code of Conduct

This project follows our [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you agree to uphold it. Please report unacceptable behavior to the maintainers.

---

## How Can I Contribute?

### 🐛 Reporting Bugs

Before filing a bug report:
1. Check the [existing issues](https://github.com/Axzo001/CubeCLI/issues) to avoid duplicates
2. Update to the latest version and see if the issue persists

When filing a bug report, use the **Bug Report** issue template and include:
- Your OS and Python version
- Terminal emulator + version
- Steps to reproduce
- Expected vs actual behavior
- Any relevant error output

### 💡 Suggesting Features

Feature requests are welcome! Use the **Feature Request** issue template. Be as specific as possible:
- What problem does the feature solve?
- How would it work? (UX description)
- Are there any related timers/tools that already do this?

### 🔌 Adding Puzzle Support

Want to add a new puzzle event? Here's what's needed:
1. The puzzle must be supported by `pyTwistyScrambler`
2. A 2D net renderer for the ANSI cube preview
3. Tests for the scramble and preview

### 🎓 Adding Algorithm Cases

OLL/PLL/F2L data lives in `cubecli/training/data/*.json`. To add or correct a case:
1. Edit the relevant JSON file
2. Follow the existing schema exactly
3. Include at minimum: `id`, `name`, `algorithm`, `group`
4. Open a PR with the change

---

## Development Setup

### Prerequisites

- Python 3.11 or newer
- Git

### Clone and Install

```bash
# 1. Fork the repo on GitHub, then:
git clone https://github.com/YOUR_USERNAME/CubeCLI.git
cd CubeCLI

# 2. Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 3. Install in editable mode with dev extras
pip install -e ".[dev]"

# 4. Install pre-commit hooks
pre-commit install
```

### Verify Setup

```bash
# Run the app
cubecli

# Run all tests
pytest tests/ -v

# Run linting
ruff check cubecli/
black --check cubecli/
mypy cubecli/
```

---

## Project Structure

```
cubecli/
├── core/           # Business logic (no UI dependencies)
│   ├── timer.py    # Timing engine
│   ├── scramble.py # Scramble generation wrapper
│   ├── cube.py     # 3x3 state machine for preview
│   └── stats.py    # Statistics calculations
├── ui/             # Textual TUI screens and widgets
├── training/       # Training mode logic + algorithm data
└── data/           # SQLite interface + models
```

**Important architecture rule:** `core/` must **never** import from `ui/`. Keep business logic dependency-free from the TUI layer.

---

## Code Style

We use **Ruff** for linting and **Black** for formatting. Both run automatically via pre-commit hooks.

```bash
# Auto-fix lint issues
ruff check --fix cubecli/

# Format code
black cubecli/ tests/
```

### Style Guidelines

- **Type annotations** are required for all function signatures
- **Docstrings** for all public classes and functions (Google style)
- **Max line length:** 100 characters
- **Imports:** sorted by Ruff's isort rules (stdlib → third-party → local)
- **No magic numbers** — use named constants or config values
- **f-strings** over `.format()` or `%`-formatting

### Example

```python
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Solve:
    """Represents a single timed solve attempt.

    Attributes:
        time_ms: Solve time in milliseconds.
        scramble: The scramble string used.
        penalty: Optional penalty applied ('+2' or 'DNF').
        notes: Optional user-attached comment.
    """

    time_ms: int
    scramble: str
    penalty: Optional[str] = None
    notes: str = ""
    timestamp: float = field(default_factory=lambda: __import__("time").time())

    @property
    def display_time(self) -> str:
        """Return a formatted time string accounting for penalties."""
        if self.penalty == "DNF":
            return "DNF"
        ms = self.time_ms + (2000 if self.penalty == "+2" else 0)
        seconds = ms / 1000
        minutes = int(seconds // 60)
        secs = seconds % 60
        if minutes:
            return f"{minutes}:{secs:06.3f}"
        return f"{secs:.3f}"
```

---

## Testing

We use **pytest** with async support. Aim for >80% coverage on `core/` modules.

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run a specific test file
pytest tests/test_stats.py

# Run with coverage report
pytest --cov=cubecli --cov-report=html
open htmlcov/index.html
```

### Writing Tests

- Place tests in `tests/` mirroring the package structure
- Name test files `test_<module>.py`
- Name test functions `test_<what_is_being_tested>()`
- Use `pytest.fixture` for reusable setup
- Use `pytest.mark.asyncio` for async tests (Textual widget tests)

```python
# tests/test_stats.py
import pytest
from cubecli.core.stats import calculate_ao5


def test_ao5_trims_best_and_worst():
    times = [10000, 12000, 11000, 13000, 9000]  # milliseconds
    result = calculate_ao5(times)
    # Should exclude 9000 (best) and 13000 (worst), average [10, 12, 11]
    assert result == pytest.approx(11000.0)


def test_ao5_returns_none_for_dnf_majority():
    times = [10000, None, None, 12000, None]  # None = DNF
    assert calculate_ao5(times) is None
```

---

## Submitting Changes

### Branching

Use descriptive branch names:
```
feat/oll-trainer
fix/timer-precision-windows
docs/add-keyboard-reference
refactor/cube-simulator
```

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add OLL trainer with spaced repetition
fix: timer stops early on fast key release
docs: update keyboard reference in README
test: add coverage for Ao5 with DNFs
refactor: extract cube state into separate module
chore: bump pyTwistyScrambler to 1.5.0
```

### Pull Request Checklist

Before submitting a PR, make sure:

- [ ] All tests pass (`pytest`)
- [ ] No lint errors (`ruff check cubecli/`)
- [ ] Code is formatted (`black --check cubecli/`)
- [ ] Type annotations are correct (`mypy cubecli/`)
- [ ] New features have tests
- [ ] CHANGELOG.md is updated (under `[Unreleased]`)
- [ ] PR description explains **what** and **why**

---

## Release Process

Releases are managed by maintainers:

1. Update version in `pyproject.toml`
2. Update `CHANGELOG.md` — move `[Unreleased]` to `[X.Y.Z] - YYYY-MM-DD`
3. Commit: `chore: release vX.Y.Z`
4. Tag: `git tag vX.Y.Z && git push --tags`
5. GitHub Actions automatically publishes to PyPI

---

## Questions?

Open a [Discussion](https://github.com/Axzo001/CubeCLI/discussions) — we're happy to help!
