"""The home-made CSP engine on classic problems that have known answers. No airport in here."""

import itertools

import pytest

from app.csp import CSP, SearchTimeout, solve


def _queens(n: int) -> CSP:
    csp = CSP()
    for r in range(n):
        csp.add_variable(f"q{r}", list(range(n)))
    for a, b in itertools.combinations(range(n), 2):
        csp.add_binary(f"q{a}", f"q{b}", lambda x, y, d=b - a: x != y and abs(x - y) != d)
    return csp


def test_n_queens_solution_counts_match_the_known_values():
    for n, expected in [(4, 2), (5, 10), (6, 4), (8, 92)]:
        assert len(solve(_queens(n), limit=1000, time_limit_s=30)) == expected


def test_n_queens_has_no_solution_for_2_and_3():
    assert solve(_queens(2)) == [] and solve(_queens(3)) == []


def test_map_colouring_australia():
    csp = CSP()
    regions = ["WA", "NT", "SA", "Q", "NSW", "V", "T"]
    for r in regions:
        csp.add_variable(r, ["red", "green", "blue"])
    for a, b in [("WA", "NT"), ("WA", "SA"), ("NT", "SA"), ("NT", "Q"), ("SA", "Q"), ("SA", "NSW"),
                 ("SA", "V"), ("Q", "NSW"), ("NSW", "V")]:
        csp.add_binary(a, b, lambda x, y: x != y)
    [colouring] = solve(csp)
    assert len(colouring) == 7
    for a, b in [("WA", "NT"), ("SA", "V"), ("Q", "NSW")]:
        assert colouring[a] != colouring[b]


def test_unsatisfiable_is_detected_by_arc_consistency_without_search():
    csp = CSP()
    csp.add_variable("a", [1])
    csp.add_variable("b", [1])
    csp.add_binary("a", "b", lambda x, y: x != y)
    assert solve(csp) == []


def test_unary_restriction_can_empty_a_domain():
    csp = CSP()
    csp.add_variable("a", [1, 2, 3])
    csp.restrict("a", lambda v: v > 3)
    assert solve(csp) == []


def test_k_cheapest_solutions_come_back_in_cost_order_and_match_brute_force():
    price = {"x": {1: 5, 2: 1, 3: 3}, "y": {1: 2, 2: 2, 3: 0}}
    csp = CSP()
    for v in price:
        csp.add_variable(v, [1, 2, 3], lambda val, v=v: price[v][val])
    csp.add_binary("x", "y", lambda a, b: a != b)
    brute = sorted(
        (price["x"][a] + price["y"][b], a, b) for a in (1, 2, 3) for b in (1, 2, 3) if a != b
    )
    got = solve(csp, limit=4)
    assert [(price["x"][s["x"]] + price["y"][s["y"]], s["x"], s["y"]) for s in got] == brute[:4]


def test_equal_cost_ties_follow_value_order_so_runs_repeat():
    csp = CSP()
    csp.add_variable("a", ["c", "a", "b"])
    assert [s["a"] for s in solve(csp, limit=3)] == ["c", "a", "b"]
    assert solve(csp, limit=3) == solve(csp, limit=3)


def test_time_limit_raises_instead_of_returning_a_guess():
    with pytest.raises(SearchTimeout):
        solve(_queens(14), limit=10**9, time_limit_s=0.05)
