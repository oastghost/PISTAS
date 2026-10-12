"""The CP-SAT solver on its own: no database, no HTTP.

First-fit (tests/first_fit_oracle.py) is the oracle: for a single flight both must give the same
proposals. For several flights the answer is checked against the rules and against brute force.
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


def test_two_flights_compete_for_the_only_free_stand():
    stands = [StandInfo("S1", "1", 36), StandInfo("S2", "1", 36)]
    blocks = [Block("S2", 0, 1000)]
    flights = [Flight("F1", 30, 100, 200), Flight("F2", 30, 150, 250)]  # overlap in time
    result = assign(stands, blocks, flights)
    assert sorted(v for v in result.values() if v) == ["S1"]
    assert list(result.values()).count(None) == 1


def test_non_overlapping_flights_share_a_stand():
    stands = [StandInfo("S1", "1", 36)]
    flights = [Flight("F1", 30, 0, 100), Flight("F2", 30, 100, 200)]
    assert assign(stands, [], flights) == {"F1": "S1", "F2": "S1"}


def test_joint_assignment_is_valid_and_serves_as_many_flights_as_possible():
    rng = random.Random(11)
    small = [StandInfo(f"S{i}", "1", rng.choice([36, 52, 65])) for i in range(4)]
    for _ in range(60):
        flights = []
        for i in range(3):
            start = rng.randrange(0, 300, 30)
            flights.append(Flight(f"F{i}", rng.choice([30, 40, 60]), start, start + rng.choice([60, 120])))
        result = assign(small, [], flights)

        for stand in small:  # nobody overlaps on a stand, and every aircraft fits
            on = [f for f in flights if result[f.id] == stand.id]
            assert all(f.wingspan_m <= stand.max_wingspan_m for f in on)
            for a, b in itertools.combinations(on, 2):
                assert not (a.start < b.end and b.start < a.end)

        def feasible(choice, flights=flights) -> bool:
            for stand in small:
                on = [f for f, c in zip(flights, choice, strict=True) if c == stand.id]
                if any(f.wingspan_m > stand.max_wingspan_m for f in on):
                    return False
                if any(a.start < b.end and b.start < a.end for a, b in itertools.combinations(on, 2)):
                    return False
            return True

        options = [s.id for s in small] + [None]
        best = max(
            sum(c is not None for c in choice)
            for choice in itertools.product(options, repeat=len(flights))
            if feasible(choice)
        )
        assert sum(v is not None for v in result.values()) == best


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
