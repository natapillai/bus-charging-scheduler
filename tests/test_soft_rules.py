"""Stage 3b tests, each soft rule scores and ranks in the expected direction."""

from types import SimpleNamespace

from scheduler.domain import BusSchedule, ChargeStop
from scheduler.rules import SOFT_RULES
from scheduler.rules.soft import IndividualWait, OperatorFairness, OverallMakespan


def _stop(station_id, wait=0, start=0, duration=25):
    return ChargeStop(
        station_id=station_id,
        arrival_min=start - wait,
        charge_start_min=start,
        charge_end_min=start + duration,
        wait_min=wait,
    )


def _schedule(bus, stops, arrival_min=0):
    return BusSchedule(bus=bus, stops=stops, arrival_min=arrival_min)


# IndividualWait.


def test_individual_wait_is_zero_with_no_waiting(make_bus, make_result):
    bus = make_bus("b1")
    result = make_result([_schedule(bus, [_stop("P", wait=0)])])
    assert IndividualWait().score(result, None) == 0


def test_individual_wait_grows_with_waits(make_bus, make_result):
    small = make_result([_schedule(make_bus("b1"), [_stop("P", wait=10)])])
    large = make_result([_schedule(make_bus("b2"), [_stop("P", wait=20)])])
    assert IndividualWait().score(large, None) > IndividualWait().score(small, None)


def test_individual_wait_priority_favours_longer_waiting_bus(make_bus):
    rule = IndividualWait()
    waited_long = make_bus("b1")
    waited_short = make_bus("b2")
    state = SimpleNamespace(
        operator_wait={},
        arrivals={("b1", "P"): 0, ("b2", "P"): 50},
    )
    assert rule.priority(waited_long, "P", 100, state, None) > rule.priority(
        waited_short, "P", 100, state, None
    )


# OperatorFairness.


def test_operator_fairness_lower_when_balanced(make_bus, make_result):
    balanced = make_result(
        [
            _schedule(make_bus("b1", operator="kpn"), [_stop("P", wait=50)]),
            _schedule(make_bus("b2", operator="freshbus"), [_stop("P", wait=50)]),
        ]
    )
    skewed = make_result(
        [
            _schedule(make_bus("b3", operator="kpn"), [_stop("P", wait=100)]),
            _schedule(make_bus("b4", operator="freshbus"), [_stop("P", wait=0)]),
        ]
    )
    rule = OperatorFairness()
    assert rule.score(balanced, None) < rule.score(skewed, None)


def test_operator_fairness_priority_favours_more_delayed_operator(make_bus):
    rule = OperatorFairness()
    behind = make_bus("b1", operator="kpn")
    ahead = make_bus("b2", operator="freshbus")
    state = SimpleNamespace(operator_wait={"kpn": 100.0, "freshbus": 10.0}, arrivals={})
    assert rule.priority(behind, "P", 0, state, None) > rule.priority(ahead, "P", 0, state, None)


# OverallMakespan.


def test_overall_makespan_lower_for_earlier_last_arrival(make_bus, make_result):
    early = make_result([_schedule(make_bus("b1", departure_min=100), [], arrival_min=500)])
    late = make_result([_schedule(make_bus("b2", departure_min=100), [], arrival_min=600)])
    rule = OverallMakespan()
    assert rule.score(early, None) < rule.score(late, None)


def test_overall_makespan_priority_favours_more_remaining_distance(real_scenarios, make_bus):
    world = real_scenarios["scenario_1"].world
    rule = OverallMakespan()
    forward = make_bus("f", origin="Bengaluru", destination="Kochi")
    backward = make_bus("r", origin="Kochi", destination="Bengaluru")
    # At station B the forward bus has 320 km left, the backward bus only 220 km.
    state = SimpleNamespace(operator_wait={}, arrivals={})
    assert rule.priority(forward, "B", 0, state, world) > rule.priority(backward, "B", 0, state, world)


def test_every_soft_category_is_a_weight_key(real_scenarios):
    weights = real_scenarios["scenario_1"].world.weights
    for rule in SOFT_RULES:
        assert rule.category in weights
