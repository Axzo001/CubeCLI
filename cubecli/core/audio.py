"""Thread-safe, non-blocking audio alerts using beepy."""

from __future__ import annotations

import threading


def _play_beep_worker(sound: str | int) -> None:
    """Worker function to run in a background thread."""
    try:
        import beepy

        beepy.beep(sound=sound)
    except Exception:
        # Fallback: ignore audio play failures gracefully (e.g. no soundcard in headless envs)
        pass


def play_beep_async(sound: str | int = 1) -> None:
    """Play a beep sound asynchronously in a background thread.

    Does not block the main Textual event loop. Fails silently if no audio device
    is configured.

    Args:
        sound: Beep type. Can be integer (1-7) or string name:
            "coin", "robot_error", "error", "ping", "ready", "success", "wilhelm"
    """
    # Spawn a daemon thread so it doesn't prevent application shutdown
    thread = threading.Thread(target=_play_beep_worker, args=(sound,), daemon=True)
    thread.start()
