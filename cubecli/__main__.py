"""Entry point for `python -m cubecli` and the `cubecli` CLI command."""

from __future__ import annotations

import sys


def main() -> None:
    """Launch CubeCLI."""
    # Lazy import keeps startup fast; Textual/Rich are only loaded when needed.
    try:
        from cubecli.ui.app import CubeCLIApp  # noqa: PLC0415
    except ImportError as exc:
        print(f"[cubecli] Failed to start: {exc}", file=sys.stderr)
        print("Try: pip install cubecli", file=sys.stderr)
        sys.exit(1)

    app = CubeCLIApp()
    app.run()


if __name__ == "__main__":
    main()
