"""Stage 5 tests, full simulation invariants and determinism."""

from scheduler.domain import Bus, Route, Scenario, Segment, Station, Vehicle, World
from scheduler.engine import schedule
from scheduler.geometry import distance_from_origin


def _max_concurrent(intervals):
    events = []
    for start, end in intervals:
        events.append((start, 1))
        events.append((end, -1))
    events.sort(key=lambda event: (event[0], event[1]))
    current = peak = 0
    for _, delta in events:
        current += delta
        peak = max(peak, current)
    return peak


def _intervals_by_station(result):
    intervals = {}
    for bus_schedule in result.bus_schedules:
        for stop in bus_schedule.stops:
            intervals.setdefault(stop.station_id, []).append(
                (stop.charge_start_min, stop.charge_end_min)
            )
    return intervals


# Invariants on the real scenarios.


def test_no_hard_violations_on_real_scenarios(real_scenarios):
    for scenario in real_scenarios.values():
        result = schedule(scenario)
        assert result.violations == []


def test_charger_capacity_respected(real_scenarios):
    for scenario in real_scenarios.values():
        result = schedule(scenario)
        capacity = {s.id: s.chargers for s in scenario.world.stations}
        for station_id, intervals in _intervals_by_station(result).items():
            assert _max_concurrent(intervals) <= capacity[station_id]


def test_every_charge_is_exact_duration(real_scenarios):
    for scenario in real_scenarios.values():
        expected = scenario.world.vehicle.charge_minutes
        result = schedule(scenario)
        for bus_schedule in result.bus_schedules:
            for stop in bus_schedule.stops:
                assert stop.charge_end_min - stop.charge_start_min == expected


def test_charges_in_route_order_and_within_range(real_scenarios):
    for scenario in real_scenarios.values():
        world = scenario.world
        result = schedule(scenario)
        for bus_schedule in result.bus_schedules:
            offsets, total = distance_from_origin(world, bus_schedule.bus)
            points = [0.0]
            previous = -1.0
            for stop in bus_schedule.stops:
                here = offsets[stop.station_id]
                assert here > previous  # route order, no backtracking
                previous = here
                points.append(here)
            points.append(total)
            for earlier, later in zip(points, points[1:]):
                assert later - earlier <= world.vehicle.range_km


def test_every_bus_charges_enough_to_arrive(real_scenarios):
    for scenario in real_scenarios.values():
        result = schedule(scenario)
        for bus_schedule in result.bus_schedules:
            # On this route every endpoint to endpoint bus needs at least two charges.
            assert len(bus_schedule.stops) >= 2


def test_schedule_is_deterministic(real_scenarios):
    for scenario in real_scenarios.values():
        assert schedule(scenario) == schedule(scenario)


# Controlled behaviour on small worlds.


def _single_station_world(chargers):
    route = Route(
        nodes=["O", "P", "Z"],
        segments=[Segment("O", "P", 200), Segment("P", "Z", 200)],
        endpoints=["O", "Z"],
    )
    return World(
        route=route,
        stations=[Station(id="P", node="P", chargers=chargers)],
        vehicle=Vehicle(range_km=240, charge_minutes=25, speed_kmph=60),
        weights={"individual": 1.0, "operator": 1.0, "overall": 1.0},
    )


def test_single_charger_serializes_two_buses():
    world = _single_station_world(chargers=1)
    scenario = Scenario(
        scenario_id="t",
        name="t",
        description="t",
        world=world,
        buses=[
            Bus("b1", "kpn", "O", "Z", 0),
            Bus("b2", "kpn", "O", "Z", 0),
        ],
    )
    result = schedule(scenario)
    intervals = _intervals_by_station(result)["P"]
    assert _max_concurrent(intervals) == 1
    waits = sorted(sum(s.wait_min for s in bs.stops) for bs in result.bus_schedules)
    assert waits == [0, 25]  # one charges first, the other waits a full charge


def test_two_chargers_serve_two_buses_at_once():
    world = _single_station_world(chargers=2)
    scenario = Scenario(
        scenario_id="t",
        name="t",
        description="t",
        world=world,
        buses=[
            Bus("b1", "kpn", "O", "Z", 0),
            Bus("b2", "kpn", "O", "Z", 0),
        ],
    )
    result = schedule(scenario)
    intervals = _intervals_by_station(result)["P"]
    assert _max_concurrent(intervals) == 2
    assert all(sum(s.wait_min for s in bs.stops) == 0 for bs in result.bus_schedules)


def test_station_is_shared_across_directions():
    world = _single_station_world(chargers=1)
    scenario = Scenario(
        scenario_id="t",
        name="t",
        description="t",
        world=world,
        buses=[
            Bus("b1", "kpn", "O", "Z", 0),
            Bus("b2", "freshbus", "Z", "O", 0),
        ],
    )
    result = schedule(scenario)
    order = result.station_orders["P"]
    # Both directions queue at the one shared charger and are serialized.
    assert {entry.bus_id for entry in order} == {"b1", "b2"}
    assert _max_concurrent(_intervals_by_station(result)["P"]) == 1
