"""WCA-equivalent scramble generation via pyTwistyScrambler."""

from __future__ import annotations

import random

# Maps display names → pyTwistyScrambler function names
PUZZLE_MAP: dict[str, str] = {
    "3x3": "333",
    "2x2": "222",
    "4x4": "444",
    "5x5": "555",
    "6x6": "666",
    "7x7": "777",
    "Pyraminx": "pyram",
    "Megaminx": "mega",
    "Skewb": "skewb",
    "Square-1": "sq1",
    "Clock": "clock",
}

PUZZLE_NAMES: list[str] = list(PUZZLE_MAP.keys())

# Expected move counts per puzzle (for UI display)
EXPECTED_MOVES: dict[str, int] = {
    "3x3": 20,
    "2x2": 11,
    "4x4": 40,
    "5x5": 60,
    "6x6": 80,
    "7x7": 100,
    "Pyraminx": 11,
    "Megaminx": 70,
    "Skewb": 11,
    "Square-1": 40,
    "Clock": 12,
}


def _fallback_scramble(moves: int = 20) -> str:
    """Generate a naive (non-random-state) 3x3 scramble as a fallback."""
    faces = ["R", "L", "U", "D", "F", "B"]
    mods = ["", "'", "2"]
    result: list[str] = []
    prev = ""
    for _ in range(moves):
        face = random.choice([f for f in faces if f != prev])
        result.append(face + random.choice(mods))
        prev = face
    return " ".join(result)


def get_scramble(puzzle: str = "3x3") -> str:
    """Return a WCA-equivalent scramble string for the given puzzle.

    Uses pyTwistyScrambler (csTimer source) when available,
    falls back to a naive scramble generator otherwise.

    Args:
        puzzle: Puzzle display name, e.g. ``"3x3"``, ``"Pyraminx"``.

    Returns:
        A space-separated scramble string, e.g. ``"R2 U' F B' L2 ..."``.
    """
    try:
        from pyTwistyScrambler import scrambler as s

        fn_map: dict[str, object] = {
            "333": s.scramble333,
            "222": s.scramble222,
            "444": s.scramble444,
            "555": s.scramble555,
            "666": s.scramble666,
            "777": s.scramble777,
            "pyram": s.scramblePyraminx,
            "mega": s.scrambleMegaminx,
            "skewb": s.scrambleSkewb,
            "sq1": s.scrambleSq1,
            "clock": s.scrambleClock,
        }
        key = PUZZLE_MAP.get(puzzle, "333")
        fn = fn_map.get(key, s.scramble333)
        return str(fn())  # type: ignore[operator]

    except ImportError:
        return _fallback_scramble(EXPECTED_MOVES.get(puzzle, 20))


def count_moves(scramble: str) -> int:
    """Return the number of moves in a scramble string."""
    return len(scramble.strip().split()) if scramble.strip() else 0
