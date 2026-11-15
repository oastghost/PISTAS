"""The stand solver on its own: no database, no HTTP.

First-fit (tests/first_fit_oracle.py) is the oracle: both must give the same proposals.
"""

import itertools
import json
import random
import time

from app.config import ROOT
from app.solver import Block, Flight, StandInfo, assign, propose

from .first_fit_oracle import first_fit

STANDS = [
    StandInfo(s["id"], s["apron"], float(s["max_wingspan_m"]))
    for s in json.loads((ROOT / "db" / "seed" / "stands.json").read_text(encoding="utf-8"))
]
WINGSPANS = [27.05, 28.72, 35.8, 38.05, 47.57, 60.3, 64.4, 64.8]


def _random_blocks(rng: random.Random, n: int) -> list[Block]:
    blocks = []
    for _ in range(n):
        start = rng.randrange(0, 24 * 60, 15)
        blocks.append(Block(rng.choice(STANDS).id, start, start + rng.choice([60, 90, 120, 180])))
    return blocks


def _random_flight(rng: random.Random, name: str = "F") -> Flight:
    start = rng.randrange(0, 24 * 60, 15)
    return Flight(
        id=name,
        wingspan_m=rng.choice(WINGSPANS),
        start=start,
        end=start + rng.choice([60, 90, 120, 180]) + 30,
        wanted=rng.choice(STANDS).id,
        banned=frozenset(rng.sample([s.id for s in STANDS], rng.choice([0, 0, 1, 3]))),
    )


def test_single_flight_matches_the_first_fit_oracle():
    rng = random.Random(2026)
    for case in range(150):
        blocks = _random_blocks(rng, rng.choice([0, 10, 40, 120]))
        flight = _random_flight(rng)
        assert propose(STANDS, blocks, flight) == first_fit(STANDS, blocks, flight), f"case {case}"


def test_proposals_respect_every_rule():
    rng = random.Random(7)
    by_id = {s.id: s for s in STANDS}
    for _ in range(40):
        blocks = _random_blocks(rng, 60)
        flight = _random_flight(rng)
        for stand_id in propose(STANDS, blocks, flight):
            assert stand_id != flight.wanted
            assert stand_id not in flight.banned
            assert by_id[stand_id].max_wingspan_m >= flight.wingspan_m
            assert not any(
                b.stand_id == stand_id and b.start < flight.end and flight.start < b.end for b in blocks
            )


def test_same_apron_first_then_tightest_fit():
    stands = [
        StandInfo("A1", "1", 36),
        StandInfo("A2", "1", 65),
        StandInfo("B1", "2", 36),
        StandInfo("B2", "2", 36),
    ]
    flight = Flight("F", 35.8, 0, 120, wanted="A1")
    assert propose(stands, [], flight) == ["A2", "B1", "B2"]


def test_removed_stand_is_never_proposed_and_busy_stands_are_skipped():
    stands = [StandInfo("S1", "1", 36), StandInfo("S2", "1", 36), StandInfo("S3", "1", 36)]
    blocks = [Block("S2", 60, 200)]
    flight = Flight("F", 30, 100, 220, wanted="S1", banned=frozenset({"S3"}))
    assert propose(stands, blocks, flight) == []


def test_solver_is_deterministic():
    rng = random.Random(5)
    blocks = _random_blocks(rng, 50)
    flight = _random_flight(rng)
    assert propose(STANDS, blocks, flight) == propose(STANDS, blocks, flight)


def test_full_airport_proposal_is_fast():
    rng = random.Random(3)
    blocks = _random_blocks(rng, 150)
    flight = _random_flight(rng)
    started = time.perf_counter()
    propose(STANDS, blocks, flight)
    assert time.perf_counter() - started < 2.0


def test_aircraft_larger_than_every_stand_gets_no_proposal():
    flight = Flight("F", 85.0, 0, 100, wanted="104")
    assert propose(STANDS, [], flight) == []


def _brute_force_cost(stands, blocks, flights):
    """Cheapest total of (wanted kept, same apron, tight fit) over every legal joint placement."""
    by_id = {s.id: s for s in stands}

    def one(f, sid):
        wanted = by_id.get(f.wanted)
        return (
            int(sid != f.wanted),
            int(wanted is None or by_id[sid].apron != wanted.apron),
            round((by_id[sid].max_wingspan_m - f.wingspan_m) * 100),
        )

    def legal(f, sid):
        s = by_id[sid]
        return (
            s.max_wingspan_m >= f.wingspan_m
            and sid not in f.banned
            and not any(b.stand_id == sid and b.start < f.end and f.start < b.end for b in blocks)
        )

    best = None
    for combo in itertools.product(sorted(by_id), repeat=len(flights)):
        if not all(legal(f, sid) for f, sid in zip(flights, combo, strict=True)):
            continue
        if any(
            a.start < b.end and b.start < a.end and x == y
            for (a, x), (b, y) in itertools.combinations(zip(flights, combo, strict=True), 2)
        ):
            continue
        costs = [one(f, sid) for f, sid in zip(flights, combo, strict=True)]
        total = tuple(sum(c[i] for c in costs) for i in range(3))
        best = total if best is None or total < best else best
    return best


def test_assign_is_a_valid_placement_and_as_cheap_as_brute_force():
    rng = random.Random(11)
    small = [
        StandInfo("A", "1", 36), StandInfo("B", "1", 65), StandInfo("C", "2", 36),
        StandInfo("D", "2", 50), StandInfo("E", "3", 65),
    ]
    for case in range(40):
        blocks = [Block(rng.choice(small).id, s := rng.randrange(0, 300, 30), s + 90) for _ in range(3)]
        flights = []
        for i in range(3):
            start = rng.randrange(0, 300, 30)
            flights.append(
                Flight(f"F{i}", rng.choice([30, 40, 60]), start, start + 120, wanted=rng.choice(small).id)
            )
        placement = assign(small, blocks, flights)
        expected = _brute_force_cost(small, blocks, flights)
        assert (placement is None) == (expected is None), f"case {case}"
        if placement is None:
            continue
        by_id = {s.id: s for s in small}
        cost = tuple(
            sum(part)
            for part in zip(
                *(
                    (
                        int(placement[f.id] != f.wanted),
                        int(by_id[placement[f.id]].apron != by_id[f.wanted].apron),
                        round((by_id[placement[f.id]].max_wingspan_m - f.wingspan_m) * 100),
                    )
                    for f in flights
                ),
                strict=True,
            )
        )
        assert cost == expected, f"case {case}"


def test_assign_keeps_wanted_stands_and_separates_overlapping_flights():
    stands = [StandInfo("S1", "1", 36), StandInfo("S2", "1", 36)]
    a = Flight("A", 30, 0, 100, wanted="S1")
    b = Flight("B", 30, 50, 150, wanted="S1")  # overlaps A, wants the same stand
    c = Flight("C", 30, 200, 300, wanted="S1")  # later: S1 is free again
    assert assign(stands, [], [a, b, c]) == {"A": "S1", "B": "S2", "C": "S1"}


def test_assign_returns_none_when_flights_cannot_all_fit():
    stands = [StandInfo("S1", "1", 36)]
    flights = [Flight("A", 30, 0, 100, wanted="S1"), Flight("B", 30, 50, 150, wanted="S1")]
    assert assign(stands, [], flights) is None
