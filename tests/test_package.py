"""
Placeholder test — will be replaced with real tests in Phase 1.
Run with: pytest tests/
"""

import importlib


def test_package_importable() -> None:
    """CubeCLI package should be importable."""
    mod = importlib.import_module("cubecli")
    assert mod.__version__ == "0.1.0"


def test_version_string_format() -> None:
    """Version should follow semver X.Y.Z pattern."""
    import re

    from cubecli import __version__

    assert re.match(r"^\d+\.\d+\.\d+", __version__)
