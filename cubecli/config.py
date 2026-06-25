"""Configuration management for CubeCLI."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

CONFIG_DIR: Path = Path.home() / ".cubecli"
CONFIG_FILE: Path = CONFIG_DIR / "config.json"
DB_FILE: Path = CONFIG_DIR / "solves.db"
BACKUP_DIR: Path = CONFIG_DIR / "backups"


@dataclass
class Config:
    """User configuration — persisted to ~/.cubecli/config.json."""

    puzzle: str = "3x3"
    session_name: str = "Default"
    inspection_enabled: bool = False
    inspection_seconds: int = 15
    hold_threshold_ms: int = 500
    show_cube_preview: bool = True
    theme: str = "dark"
    hide_timer_running: bool = False
    use_voice_countdown: bool = False

    # Phase 5 Power Features
    bld_mode_enabled: bool = False
    fmc_mode_enabled: bool = False
    cfop_splits_enabled: bool = False
    metronome_enabled: bool = False
    metronome_tps: float = 2.0  # Turns per second (1.0 to 10.0)

    # Internal fields (not user-facing)
    _valid_puzzles: list[str] = field(
        default_factory=lambda: [
            "3x3",
            "2x2",
            "4x4",
            "5x5",
            "6x6",
            "7x7",
            "Pyraminx",
            "Megaminx",
            "Skewb",
            "Square-1",
            "Clock",
        ],
        repr=False,
        compare=False,
    )

    @classmethod
    def load(cls) -> Config:
        """Load config from disk, falling back to defaults on any error."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if CONFIG_FILE.exists():
            try:
                raw = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
                valid_fields = {
                    k: v
                    for k, v in raw.items()
                    if k in cls.__dataclass_fields__ and not k.startswith("_")
                }
                return cls(**valid_fields)
            except Exception:
                pass
        return cls()

    def save(self) -> None:
        """Persist config to disk."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = {k: v for k, v in asdict(self).items() if not k.startswith("_")}
        CONFIG_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def next_puzzle(self) -> str:
        """Cycle to the next puzzle in the list."""
        puzzles = self._valid_puzzles
        idx = puzzles.index(self.puzzle) if self.puzzle in puzzles else 0
        self.puzzle = puzzles[(idx + 1) % len(puzzles)]
        return self.puzzle
