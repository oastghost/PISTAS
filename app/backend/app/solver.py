"""Stand allocation as a constraint satisfaction problem, solved by our own engine (app/csp.py).

A pure module: a snapshot of the plan goes in, a proposal comes out. It never writes; the database
has the final say, so a proposal can still be refused and the caller then asks again.

Model
  variables    one per flight, its value is a stand
  constraints  the aircraft fits the stand, ANA did not remove it for this flight, nothing else
               occupies it during the flight (unary); two flights that overlap in time never share
               a stand (binary)
  objective    minimise: not the wanted stand, then another apron than the wanted one, then unused
               wingspan (keeps big stands free for big aircraft), then stand id

`propose` is the one-flight case the app uses: alternatives for a refused request. `assign` is the
general case: several flights at once.

Times are integers (minutes). `end` already includes the turnaround gap, like `stand_block`.
"""

from dataclasses import dataclass

from .csp import CSP, SearchTimeout, solve


class SolverError(Exception):
    """The solver could not produce a trustworthy answer."""


@dataclass(frozen=True)
class StandInfo:
    id: str
    apron: str
    max_wingspan_m: float


@dataclass(frozen=True)
class Block:
    """An interval a stand is already occupied, gap included."""

    stand_id: str
    start: int
    end: int


@dataclass(frozen=True)
class Flight:
    id: str
    wingspan_m: float
    start: int
    end: int  # includes the turnaround gap
    wanted: str | None = None
    banned: frozenset[str] = frozenset()


def _overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return a_start < b_end and b_start < a_end


def _add_flight(csp: CSP, stands: list[StandInfo], blocks: list[Block], flight: Flight, *, exclude_wanted: bool) -> None:
    by_id = {s.id: s for s in stands}
    wanted = by_id.get(flight.wanted) if flight.wanted else None
    busy = {b.stand_id for b in blocks if _overlap(b.start, b.end, flight.start, flight.end)}
    rank = {s.id: i for i, s in enumerate(stands)}  # stands are id-sorted by the caller of this helper

    def cost(stand_id: str) -> int:
        s = by_id[stand_id]
        moved = int(stand_id != flight.wanted)
        other_apron = int(wanted is None or s.apron != wanted.apron)
        spare_cm = round((s.max_wingspan_m - flight.wingspan_m) * 100)
        # Each criterion only breaks ties of the one before it: 100_000 is bigger than any spare in cm.
        return ((moved * 100_000 + other_apron) * 100_000 + spare_cm) * len(stands) + rank[stand_id]

    csp.add_variable(flight.id, [s.id for s in stands], cost)
    csp.restrict(flight.id, lambda sid: by_id[sid].max_wingspan_m >= flight.wingspan_m)
    csp.restrict(flight.id, lambda sid: sid not in flight.banned)
    csp.restrict(flight.id, lambda sid: sid not in busy)
    if exclude_wanted:
        csp.restrict(flight.id, lambda sid: sid != flight.wanted)


def propose(
    stands: list[StandInfo],
    blocks: list[Block],
    flight: Flight,
    *,
    limit: int = 5,
    time_limit_s: float = 2.0,
) -> list[str]:
    """Up to `limit` stands for the flight, best first, never the wanted stand itself."""
    csp = CSP()
    _add_flight(csp, sorted(stands, key=lambda s: s.id), blocks, flight, exclude_wanted=True)
    try:
        solutions = solve(csp, limit=limit, time_limit_s=time_limit_s)
    except SearchTimeout:
        raise SolverError("search timed out") from None
    return [s[flight.id] for s in solutions]


def assign(
    stands: list[StandInfo],
    blocks: list[Block],
    flights: list[Flight],
    *,
    time_limit_s: float = 2.0,
) -> dict[str, str] | None:
    """The cheapest way to place all flights together, or None when they cannot all fit.

    Flights keep their wanted stand when they can; flights that overlap in time never share a stand.
    """
    if len({f.id for f in flights}) != len(flights):
        raise ValueError("flight ids must be unique")
    ordered = sorted(stands, key=lambda s: s.id)
    csp = CSP()
    for f in flights:
        _add_flight(csp, ordered, blocks, f, exclude_wanted=False)
    for i, a in enumerate(flights):
        for b in flights[i + 1 :]:
            if _overlap(a.start, a.end, b.start, b.end):
                csp.add_binary(a.id, b.id, lambda x, y: x != y)
    try:
        solutions = solve(csp, limit=1, time_limit_s=time_limit_s)
    except SearchTimeout:
        raise SolverError("search timed out") from None
    return solutions[0] if solutions else None
