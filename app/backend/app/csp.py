"""A small constraint satisfaction engine, written from scratch (standard library only).

Techniques (the classic AI course toolbox):
  node consistency      unary constraints filter each domain once, before any search
  AC-3                  arc consistency over the binary constraints, before any search
  backtracking search   depth first, one variable at a time
  MRV + degree          pick the variable with the fewest remaining values, then the most neighbours
  forward checking      after each choice, remove the values it rules out from the neighbours
  branch and bound      values are tried cheapest first; a branch is cut when even the best case for
                        the unassigned variables cannot beat the k-th best solution found so far

The engine knows nothing about airports. It solves: variables with finite domains, unary
restrictions, binary constraints, and an additive integer cost per (variable, value). It returns the
`limit` cheapest solutions, cheapest first, and the order is deterministic (cost, then value order).
"""

from __future__ import annotations

import bisect
import time
from collections.abc import Callable, Hashable
from dataclasses import dataclass, field

Value = Hashable


class SearchTimeout(Exception):
    """The time limit ran out before the search could prove its answer."""


@dataclass
class CSP:
    domains: dict[str, list[Value]] = field(default_factory=dict)
    costs: dict[str, Callable[[Value], int]] = field(default_factory=dict)
    unary: dict[str, list[Callable[[Value], bool]]] = field(default_factory=dict)
    # binary[x][y] is a list of predicates ok(vx, vy); the mirror entry binary[y][x] is kept in sync.
    binary: dict[str, dict[str, list[Callable[[Value, Value], bool]]]] = field(default_factory=dict)

    def add_variable(self, name: str, values: list[Value], cost: Callable[[Value], int] | None = None) -> None:
        if name in self.domains:
            raise ValueError(f"variable {name!r} already exists")
        self.domains[name] = list(values)
        self.costs[name] = cost or (lambda _v: 0)
        self.unary[name] = []
        self.binary[name] = {}

    def restrict(self, name: str, ok: Callable[[Value], bool]) -> None:
        self.unary[name].append(ok)

    def add_binary(self, x: str, y: str, ok: Callable[[Value, Value], bool]) -> None:
        self.binary[x].setdefault(y, []).append(ok)
        self.binary[y].setdefault(x, []).append(lambda vy, vx: ok(vx, vy))


def _compatible(csp: CSP, x: str, vx: Value, y: str, vy: Value) -> bool:
    return all(ok(vx, vy) for ok in csp.binary[x][y])


def _revise(csp: CSP, domains: dict[str, list[Value]], x: str, y: str) -> bool:
    """Drop values of x that have no partner left in y. True when x lost something."""
    keep = [vx for vx in domains[x] if any(_compatible(csp, x, vx, y, vy) for vy in domains[y])]
    changed = len(keep) != len(domains[x])
    domains[x] = keep
    return changed


def _ac3(csp: CSP, domains: dict[str, list[Value]]) -> bool:
    """Arc consistency. False when some domain became empty (no solution exists)."""
    queue = [(x, y) for x in csp.binary for y in csp.binary[x]]
    while queue:
        x, y = queue.pop()
        if _revise(csp, domains, x, y):
            if not domains[x]:
                return False
            queue.extend((z, x) for z in csp.binary[x] if z != y)
    return True


def solve(csp: CSP, *, limit: int = 1, time_limit_s: float = 2.0) -> list[dict[str, Value]]:
    """The `limit` cheapest complete assignments, cheapest first. Empty when none exists.

    Raises SearchTimeout if the time limit ends before the search finished.
    """
    deadline = time.monotonic() + time_limit_s
    names = list(csp.domains)
    order_of = {n: {v: i for i, v in enumerate(csp.domains[n])} for n in names}

    # Node consistency, then cheapest value first. sorted() is stable, so equal costs keep input order.
    domains: dict[str, list[Value]] = {}
    for n in names:
        allowed = [v for v in csp.domains[n] if all(ok(v) for ok in csp.unary[n])]
        domains[n] = sorted(allowed, key=csp.costs[n])
        if not domains[n]:
            return []
    if not _ac3(csp, domains):
        return []

    best: list[tuple[int, tuple[int, ...], dict[str, Value]]] = []  # sorted by (cost, order key)
    assignment: dict[str, Value] = {}

    def floor_of(unassigned: list[str]) -> int:
        return sum(csp.costs[n](domains[n][0]) for n in unassigned)

    def search(unassigned: list[str], cost: int) -> None:
        if time.monotonic() > deadline:
            raise SearchTimeout
        if not unassigned:
            key = tuple(order_of[n][assignment[n]] for n in names)
            bisect.insort(best, (cost, key, dict(assignment)), key=lambda e: (e[0], e[1]))
            del best[limit:]
            return

        # MRV, then degree (most unassigned neighbours), then declaration order.
        var = min(
            unassigned,
            key=lambda n: (len(domains[n]), -sum(1 for m in csp.binary[n] if m not in assignment)),
        )
        rest = [n for n in unassigned if n != var]
        rest_floor = floor_of(rest)

        for value in list(domains[var]):
            step = cost + csp.costs[var](value)
            if len(best) == limit and step + rest_floor > best[-1][0]:
                break  # values are cost-sorted: every later one is at least as expensive
            saved: dict[str, list[Value]] = {}
            dead = False
            for m in csp.binary[var]:
                if m in assignment:
                    continue
                kept = [w for w in domains[m] if _compatible(csp, var, value, m, w)]
                if len(kept) != len(domains[m]):
                    saved[m] = domains[m]
                    domains[m] = kept
                    if not kept:
                        dead = True
                        break
            if not dead:
                assignment[var] = value
                search(rest, step)
                del assignment[var]
            for m, old in saved.items():
                domains[m] = old

    search(names, 0)
    return [a for _, _, a in best]
