"""Stage 3a tests, each hard rule in isolation with a passing and a failing case.

The failing cases are built by hand on the tiny world so a single corrupted
field trips exactly the rule under test.
"""

from scheduler.domain import BusSchedule, ChargeStop
from scheduler.rules.hard import (
    ChargeDuration,
    ChargerCapacity,
    RangeConstraint,
    RouteOrder,
)


def _stop(station_id, arrival=0, start=0, duration=25, wait=0):
    return ChargeStop(
        station_id=station_id,
        arrival_min=arrival,
        charge_start_min=start,
        charge_end_min=start + duration,
        wait_min=wait,
    )


def _schedule(bus, stops, arrival_min=0):
    return BusSchedule(bus=bus, stops=stops, arrival_min=arrival_min)


def test_range_constraint_passes_within_range(tiny_world, make_bus, make_result):
    bus = make_bus("b1")
    result = make_result([_schedule(bus, [_stop("P", arrival=100, start=100)], arrival_min=325)])
    violations = RangeConstraint().validate(result, tiny_world)
    assert violations == []


def test_range_constraint_reports_gap_over_range(tiny_world, make_bus, make_result):
    bus = make_bus("b1")
    # No charge at all on a 300 km trip leaves a single 300 km gap over the 240 range.
    result = make_result([_schedule(bus, [], arrival_min=300)])
    violations = RangeConstraint().validate(result, tiny_world)
    assert len(violations) == 1
    assert all(isinstance(message, str) for message in violations)


def test_charger_capacity_passes_when_back_to_back(tiny_world, make_bus, make_result):
    first = make_bus("b1")
    second = make_bus("b2")
    result = make_result(
        [
            _schedule(first, [_stop("P", start=100)]),
            _schedule(second, [_stop("P", start=125)]),
        ]
    )
    assert ChargerCapacity().validate(result, tiny_world) == []


def test_charger_capacity_reports_overlap_on_single_charger(tiny_world, make_bus, make_result):
    first = make_bus("b1")
    second = make_bus("b2")
    result = make_result(
        [
            _schedule(first, [_stop("P", start=100)]),
            _schedule(second, [_stop("P", start=110)]),
        ]
    )
    violations = ChargerCapacity().validate(result, tiny_world)
    assert len(violations) == 1


def test_charger_capacity_allows_two_overlaps_when_capacity_is_two(tiny_world, make_bus, make_result):
    tiny_world.stations[0].chargers = 2  # station P gains a second charger
    first = make_bus("b1")
    second = make_bus("b2")
    result = make_result(
        [
            _schedule(first, [_stop("P", start=100)]),
            _schedule(second, [_stop("P", start=110)]),
        ]
    )
    assert ChargerCapacity().validate(result, tiny_world) == []


def test_route_order_passes_in_order(tiny_world, make_bus, make_result):
    bus = make_bus("b1")
    result = make_result(
        [_schedule(bus, [_stop("P", start=100), _stop("Q", start=225)])]
    )
    assert RouteOrder().validate(result, tiny_world) == []


def test_route_order_reports_backtracking(tiny_world, make_bus, make_result):
    bus = make_bus("b1")
    # Q sits further along than P, so charging Q then P is a backtrack.
    result = make_result(
        [_schedule(bus, [_stop("Q", start=100), _stop("P", start=225)])]
    )
    violations = RouteOrder().validate(result, tiny_world)
    assert len(violations) == 1


def test_charge_duration_passes_at_exact_minutes(tiny_world, make_bus, make_result):
    bus = make_bus("b1")
    result = make_result([_schedule(bus, [_stop("P", start=100, duration=25)])])
    assert ChargeDuration().validate(result, tiny_world) == []


def test_charge_duration_reports_wrong_length(tiny_world, make_bus, make_result):
    bus = make_bus("b1")
    short = make_result([_schedule(bus, [_stop("P", start=100, duration=20)])])
    long = make_result([_schedule(make_bus("b2"), [_stop("P", start=100, duration=30)])])
    assert len(ChargeDuration().validate(short, tiny_world)) == 1
    assert len(ChargeDuration().validate(long, tiny_world)) == 1
