"""FMC (Fewest Moves Challenge) core logic and move verification."""

from __future__ import annotations

import re


def validate_fmc_move(move: str) -> bool:
    """Return True if the move token is a WCA-legal written move or rotation.

    WCA Regulations Article 12:
    - Face turns: U, D, R, L, F, B (with optional 2 or ')
    - Wide turns: Uw, Dw, Rw, Lw, Fw, Bw or u, d, r, l, f, b (with optional 2 or ')
    - Rotations: x, y, z (with optional 2 or ')

    Note: The '2'' modifier (two-prime, e.g. "R2'") is NOT included here because
    it is not used in standard WCA written FMC solutions.  The invert_algorithm
    helper handles it for historical algorithm databases, but the FMC solution
    validator enforces stricter WCA notation.
    """
    move = move.strip()
    if not move:
        return False

    # Regex matching:
    # 1. [UDRLFB]w? - Uppercase faces with optional 'w' for wide turns
    # 2. [udrlfb] - Lowercase face letters for wide turns
    # 3. [xyz] - Rotations
    # Followed by optional modifiers: 2 or ' (but NOT 2')
    pattern = r"^(?:[UDRLFB]w?|[udrlfb]|[xyz])(?:2|')?$"
    return bool(re.match(pattern, move))


def count_fmc_moves(solution: str) -> int:
    """Count the WCA Half Turn Metric (HTM) moves in a solution string.

    Rotations (x, y, z) count as 0 moves.
    Any invalid move token will result in returning -1.

    Args:
        solution: A space-separated move sequence.

    Returns:
        Move count (HTM), or -1 if the solution contains invalid tokens.
    """
    tokens = solution.strip().split()
    if not tokens:
        return 0

    count = 0
    for t in tokens:
        if not validate_fmc_move(t):
            return -1
        # Rotations don't count towards HTM
        if t[0] in ("x", "y", "z"):
            continue
        count += 1

    return count
