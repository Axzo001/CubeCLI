"""Unit tests for asynchronous audio player logic."""

from __future__ import annotations

import time
from unittest.mock import patch

from cubecli.core.audio import play_beep_async


def test_play_beep_async_mocked() -> None:
    # Patch beepy.beep so it does not actually play audio during testing
    with patch("beepy.beep") as mock_beep:
        play_beep_async("ping")
        # Give the background thread a moment to spawn and execute
        time.sleep(0.1)
        mock_beep.assert_called_once_with(sound="ping")
