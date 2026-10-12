"""Stand assignment as a constraint satisfaction problem, solved with OR-Tools CP-SAT.

A pure module: a snapshot of the plan goes in, a proposal comes out. No database code, so it
can be tested and explained on its own. It never writes. The database has the final say, so a
proposal can still be refused (someone committed first) and the caller then asks again.

Model
  variables  one per (flight, stand): "this flight uses this stand"
  domains    a stand is in a flight's domain only if the aircraft fits it and the flight was not
             removed from it by ANA
  constraints
    - each flight gets exactly one stand, or none (then it pays a large penalty)
    - on one stand, flights never overlap each other and never overlap an existing block
      (NoOverlap over optional intervals plus the fixed blocks)
  objective  minimise, in this order of importance: another apron than the wanted stand,
             unused wingspan of the stand (keeps large stands free for large aircraft), stand id

Times are integers (minutes). An interval is half open [start, end) and `end` already includes
the turnaround gap, exactly like the `stand_block` rows in the database.
"""

from dataclasses import dataclass

from ortools.sat.python import cp_model

UNASSIGNED_PENALTY = 10**12
APRON_MISMATCH_COST = 10**9
WINGSPAN_UNIT = 1000  # cost units per 0.01 m of unused wingspan; always above any stand index


class SolverError(Exception):
    """The solver could not produce a trustworthy answer (timeout or internal failure)."""


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


def _overlaps(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return a_start < b_end and b_start < a_end


def assign(
    stands: list[StandInfo],
    blocks: list[Block],
    flights: list[Flight],
    *,
    excluded: dict[str, frozenset[str]] | None = None,
    time_limit_s: float = 2.0,
) -> dict[str, str | None]:
    """Best joint assignment of the flights. A flight with no valid stand maps to None.

    `excluded` removes extra stands from a flight's domain (used to ask for alternatives).
    """
    excluded = excluded or {}
    ordered = sorted(stands, key=lambda s: s.id)
    index = {s.id: i for i, s in enumerate(ordered)}
    apron_of = {s.id: s.apron for s in ordered}
    blocks_by_stand: dict[str, list[Block]] = {}
    for b in blocks:
        blocks_by_stand.setdefault(b.stand_id, []).append(b)

    model = cp_model.CpModel()
    use: dict[tuple[str, str], cp_model.IntVar] = {}
    intervals: dict[str, list] = {s.id: [] for s in ordered}
    cost_terms = []

    for f in flights:
        wanted_apron = apron_of.get(f.wanted) if f.wanted else None
        options = []
        for s in ordered:
            if s.max_wingspan_m < f.wingspan_m or s.id in f.banned or s.id in excluded.get(f.id, ()):
                continue
            if any(_overlaps(f.start, f.end, b.start, b.end) for b in blocks_by_stand.get(s.id, ())):
                continue
            var = model.NewBoolVar(f"use_{f.id}_{s.id}")
            use[(f.id, s.id)] = var
            options.append(var)
            intervals[s.id].append(
                model.NewOptionalFixedSizeIntervalVar(f.start, f.end - f.start, var, f"iv_{f.id}_{s.id}")
            )
            mismatch = int(wanted_apron is not None and s.apron != wanted_apron)
            slack = round((s.max_wingspan_m - f.wingspan_m) * 100)
            cost = mismatch * APRON_MISMATCH_COST + slack * WINGSPAN_UNIT + index[s.id]
            cost_terms.append(cost * var)

        unassigned = model.NewBoolVar(f"unassigned_{f.id}")
        model.AddExactlyOne([*options, unassigned])
        cost_terms.append(UNASSIGNED_PENALTY * unassigned)

    # Existing blocks are already excluded from the domains above, so only flights of this
    # batch can still clash with each other on a stand.
    for stand_intervals in intervals.values():
        if len(stand_intervals) > 1:
            model.AddNoOverlap(stand_intervals)

    model.Minimize(sum(cost_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.num_workers = 1  # deterministic
    solver.parameters.random_seed = 0
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise SolverError(f"solver status {solver.StatusName(status)}")
    if status != cp_model.OPTIMAL:
        raise SolverError("solver hit the time limit before proving the best answer")

    result: dict[str, str | None] = {f.id: None for f in flights}
    for (flight_id, stand_id), var in use.items():
        if solver.Value(var):
            result[flight_id] = stand_id
    return result


def propose(
    stands: list[StandInfo],
    blocks: list[Block],
    flight: Flight,
    *,
    limit: int = 5,
    time_limit_s: float = 2.0,
) -> list[str]:
    """Up to `limit` stands for one flight, best first, never the wanted stand itself.

    Each round solves the model again with the previous winners removed from the domain.
    """
    excluded: set[str] = {flight.wanted} if flight.wanted else set()
    proposals: list[str] = []
    for _ in range(limit):
        chosen = assign(
            stands,
            blocks,
            [flight],
            excluded={flight.id: frozenset(excluded)},
            time_limit_s=time_limit_s,
        )[flight.id]
        if chosen is None:
            break
        proposals.append(chosen)
        excluded.add(chosen)
    return proposals
