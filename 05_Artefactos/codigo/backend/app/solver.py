"""Proposes stands. A pure function: snapshot in, proposal out, no database code.

It never writes. The database has the final say, so a proposal can still be refused
(someone else got there first) and the caller then asks again.

First-fit for now. It stays as the test oracle when the CP-SAT model replaces it (build
order step 7).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class StandInfo:
    id: str
    apron: str
    max_wingspan_m: float


def propose(
    stands: list[StandInfo],
    *,
    wingspan_m: float,
    busy: set[str],
    banned: set[str],
    wanted: str | None = None,
    limit: int = 5,
) -> list[str]:
    """Stand ids the aircraft fits and that are free, best first.

    `busy` are stands with an overlapping block in the requested window, `banned` are stands
    ANA removed this flight from. Same apron as `wanted` first, then the tightest fit so large
    stands stay free for large aircraft.
    """
    wanted_apron = next((s.apron for s in stands if s.id == wanted), None)
    candidates = [
        s
        for s in stands
        if s.id != wanted and s.max_wingspan_m >= wingspan_m and s.id not in busy and s.id not in banned
    ]
    candidates.sort(key=lambda s: (s.apron != wanted_apron, s.max_wingspan_m, s.id))
    return [s.id for s in candidates[:limit]]
