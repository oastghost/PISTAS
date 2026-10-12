"""The original first-fit proposal, kept as the oracle the CP-SAT solver is tested against.

Deliberately simple and obviously correct, so a disagreement points at the CP-SAT model.
"""

from app.solver import Block, Flight, StandInfo


def first_fit(stands: list[StandInfo], blocks: list[Block], flight: Flight, limit: int = 5) -> list[str]:
    wanted_apron = next((s.apron for s in stands if s.id == flight.wanted), None)
    busy = {b.stand_id for b in blocks if b.start < flight.end and flight.start < b.end}
    candidates = [
        s
        for s in stands
        if s.id != flight.wanted
        and s.max_wingspan_m >= flight.wingspan_m
        and s.id not in busy
        and s.id not in flight.banned
    ]
    candidates.sort(key=lambda s: (s.apron != wanted_apron, s.max_wingspan_m, s.id))
    return [s.id for s in candidates[:limit]]
