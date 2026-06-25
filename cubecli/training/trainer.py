"""OLL/PLL Training logic, case loading, algorithm inversion, and spaced repetition."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path

from cubecli.data.models import Solve


@dataclass
class Case:
    """A single OLL or PLL training case."""

    id: str
    name: str
    algorithm: str
    diagram: str
    group: str = "PLL"


def load_cases(mode: str) -> list[Case]:
    """Load all OLL or PLL cases from JSON databases.

    Args:
        mode: "oll" or "pll"

    Returns:
        List of Case objects.
    """
    mode = mode.lower()
    if mode not in ("oll", "pll"):
        raise ValueError("Mode must be 'oll' or 'pll'.")

    json_path = Path(__file__).parent / "data" / f"{mode}.json"
    if not json_path.exists():
        raise FileNotFoundError(f"Case database not found at {json_path}")

    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    cases = []
    for item in data:
        cases.append(
            Case(
                id=item["id"],
                name=item["name"],
                algorithm=item["algorithm"],
                diagram=item["diagram"],
                group=item.get("group", "PLL"),
            )
        )
    return cases


def invert_move(move: str) -> str:
    """Invert a single WCA move token."""
    # Clean parentheses or brackets
    move = move.replace("(", "").replace(")", "").replace("[", "").replace("]", "")
    if not move:
        return ""
    if move.endswith("'"):
        return move[:-1]
    elif move.endswith("2'"):
        return move[:-2] + "2"
    elif move.endswith("2"):
        return move
    else:
        return move + "'"


def invert_algorithm(alg: str) -> str:
    """Invert a space-separated algorithm string.

    Example:
        >>> invert_algorithm("R U R'")
        "R U' R'"
    """
    tokens = alg.strip().split()
    inverted = []
    for t in reversed(tokens):
        inv_t = invert_move(t)
        if inv_t:
            inverted.append(inv_t)
    return " ".join(inverted)


def get_setup_scramble(alg: str) -> str:
    """Generate a setup scramble by wrapping the inverted algorithm in U pre/post-rotations.

    Args:
        alg: The standard algorithm for the case.

    Returns:
        A space-separated scramble string.
    """
    inverted = invert_algorithm(alg)
    pre = random.choice(["", "U", "U'", "U2"])
    post = random.choice(["", "U", "U'", "U2"])
    parts = [pre, inverted, post]
    return " ".join([p for p in parts if p])


def select_next_case(cases: list[Case], solves: list[Solve]) -> Case:
    """Select the next case to drill using spaced repetition performance weighting.

    Args:
        cases: The active list of cases to choose from.
        solves: Solve history for the current training mode to compute weights.

    Returns:
        The selected Case.
    """
    if not cases:
        raise ValueError("Active cases list is empty.")

    # Group solves by case ID (stored in Solve.notes)
    solves_by_case: dict[str, list[Solve]] = {}
    for s in solves:
        cid = s.notes
        if cid:
            solves_by_case.setdefault(cid, []).append(s)

    weights: list[float] = []
    for c in cases:
        c_solves = solves_by_case.get(c.id, [])
        if not c_solves:
            # Unseen cases get a high weight
            weights.append(10.0)
        else:
            recent = c_solves[-5:]
            # Check for DNF in the last or second last solve
            if recent[-1].penalty == "DNF" or (len(recent) >= 2 and recent[-2].penalty == "DNF"):
                weights.append(15.0)
            else:
                times = [s.effective_ms for s in recent if s.effective_ms is not None]
                if not times:
                    weights.append(15.0)
                else:
                    mean_sec = sum(times) / (1000.0 * len(times))
                    weights.append(max(1.0, mean_sec))

    return random.choices(cases, weights=weights, k=1)[0]
