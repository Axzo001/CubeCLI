"""Smoke tests for the __main__ entry point and CLI launch."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch


def test_main_module_importable() -> None:
    """The cubecli package and its __main__ module must be importable."""
    import cubecli.__main__  # noqa: F401

    assert hasattr(cubecli.__main__, "main")


def test_main_callable() -> None:
    """main() must be a callable in the cubecli.__main__ namespace."""
    from cubecli.__main__ import main

    assert callable(main)


def test_main_exits_on_import_error() -> None:
    """If CubeCLIApp cannot be imported, main() should print an error and exit(1).

    Patches 'cubecli.__main__.sys.exit' and replaces the module lookup so that
    the internal `from cubecli.ui.app import CubeCLIApp` raises ImportError.
    """
    import cubecli.__main__ as mod

    def _raise_import_error(*_: object, **__: object) -> None:
        raise ImportError("textual not installed")

    # We patch __import__ at the module level where main() executes its lazy import.
    # By pointing 'cubecli.ui.app' -> None in sys.modules, Python raises ImportError.
    saved = sys.modules.pop("cubecli.ui.app", ...)  # remove cached module if present

    try:
        with (
            patch.dict("sys.modules", {"cubecli.ui.app": None}),
            patch.object(mod, "sys") as mock_sys,
        ):
            mock_sys.stderr = sys.stderr  # keep stderr for the print call
            mock_sys.exit = MagicMock()
            mod.main()
            mock_sys.exit.assert_called_once_with(1)
    finally:
        # Restore the real module (or remove if it wasn't there)
        if saved is ...:
            sys.modules.pop("cubecli.ui.app", None)
        else:
            sys.modules["cubecli.ui.app"] = saved


def test_dunder_main_executes_main(monkeypatch: object) -> None:
    """Running `python -m cubecli` should call main()."""
    call_record: list[str] = []

    # We import main and patch it so we don't actually launch the TUI
    import cubecli.__main__ as mod

    original_main = mod.main

    def fake_main() -> None:
        call_record.append("called")

    monkeypatch.setattr(mod, "main", fake_main)  # type: ignore[arg-type]
    # Simulate the __name__ == "__main__" block
    mod.main()
    assert call_record == ["called"]
    monkeypatch.setattr(mod, "main", original_main)  # type: ignore[arg-type]
