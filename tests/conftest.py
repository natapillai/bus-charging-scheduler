"""Shared test fixtures.

Two synthetic worlds drive the controlled passing and failing cases. The tiny
world is small enough to reason about by hand and has every segment within
range, so a plan that charges everywhere is feasible. The unreachable world has
one segment between adjacent stations longer than the range, so range failure
and the no feasible plan path can both be exercised. The real scenarios fixture
loads the five shipped files for the integration style checks.

Imports of the scheduler package happen inside the fixtures so the conftest
loads cleanly while the package is still being built up stage by stage.
"""

from pathlib import Path

import pytest

SCENARIOS_DIR = Path(__file__).resolve().parent.parent / "scenarios"


@pytest.fixture
def tiny_world():
    """A short three segment route with two single charger stations.

    Origin O and destination Z are endpoints. Stations sit at P and Q. Every
    segment is 100 km and the range is 240 km, so a bus crossing the whole route
    can complete it with a single charge at either station or with charges at
    both, which makes plan enumeration and selection easy to assert.
    """
    from scheduler.domain import Route, Segment, Station, Vehicle, World

    route = Route(
        nodes=["O", "P", "Q", "Z"],
        segments=[
            Segment("O", "P", 100),
            Segment("P", "Q", 100),
            Segment("Q", "Z", 100),
        ],
        endpoints=["O", "Z"],
    )
    stations = [
        Station(id="P", node="P", chargers=1),
        Station(id="Q", node="Q", chargers=1),
    ]
    vehicle = Vehicle(range_km=240, charge_minutes=25, speed_kmph=60)
    weights = {"individual": 1.0, "operator": 1.0, "overall": 1.0}
    return World(route=route, stations=stations, vehicle=vehicle, weights=weights)


@pytest.fixture
def tiny_world_unreachable():
    """Same shape as the tiny world but the middle segment exceeds the range.

    P to Q is 300 km against a 240 km range, so no charging plan can bridge that
    gap and enumeration returns nothing, which lets a caller surface a clear
    violation rather than crash.
    """
    from scheduler.domain import Route, Segment, Station, Vehicle, World

    route = Route(
        nodes=["O", "P", "Q", "Z"],
        segments=[
            Segment("O", "P", 100),
            Segment("P", "Q", 300),
            Segment("Q", "Z", 100),
        ],
        endpoints=["O", "Z"],
    )
    stations = [
        Station(id="P", node="P", chargers=1),
        Station(id="Q", node="Q", chargers=1),
    ]
    vehicle = Vehicle(range_km=240, charge_minutes=25, speed_kmph=60)
    weights = {"individual": 1.0, "operator": 1.0, "overall": 1.0}
    return World(route=route, stations=stations, vehicle=vehicle, weights=weights)


@pytest.fixture
def real_scenarios():
    """Load all five shipped scenario files keyed by scenario id."""
    from scheduler.loader import load_scenario

    result = {}
    for path in sorted(SCENARIOS_DIR.glob("scenario_*.json")):
        scenario = load_scenario(path)
        result[scenario.scenario_id] = scenario
    return result


@pytest.fixture
def make_bus():
    """Factory for a single bus, defaulting to the tiny world endpoints."""

    def _make(bus_id, origin="O", destination="Z", operator="kpn", departure_min=0):
        from scheduler.domain import Bus

        return Bus(
            id=bus_id,
            operator=operator,
            origin=origin,
            destination=destination,
            departure_min=departure_min,
        )

    return _make


@pytest.fixture
def registry_guard():
    """Snapshot the rule registries and restore them after the test.

    Tests that register throwaway rules use this so the extra rules do not leak
    into other tests. The restore writes back in place so the same list objects
    the engine and objective hold references to stay valid.
    """
    from scheduler.rules import HARD_RULES, SOFT_RULES

    hard_snapshot = list(HARD_RULES)
    soft_snapshot = list(SOFT_RULES)
    yield
    HARD_RULES[:] = hard_snapshot
    SOFT_RULES[:] = soft_snapshot


@pytest.fixture
def make_result():
    """Factory that assembles a ScheduleResult from hand built bus schedules.

    It derives the per station order from the stops so the result looks like one
    the engine would produce, which lets the hard rule tests corrupt a single
    field and check that exactly the matching validator complains.
    """

    def _build(bus_schedules, violations=None, objective=None):
        from scheduler.domain import ScheduleResult, StationOrderEntry

        grouped = {}
        for schedule in bus_schedules:
            for stop in schedule.stops:
                grouped.setdefault(stop.station_id, []).append((schedule.bus, stop))

        station_orders = {}
        for station_id, pairs in grouped.items():
            pairs.sort(key=lambda pair: (pair[1].charge_start_min, pair[0].id))
            station_orders[station_id] = [
                StationOrderEntry(
                    order=index + 1,
                    bus_id=bus.id,
                    operator=bus.operator,
                    direction_label=f"{bus.origin} to {bus.destination}",
                    arrival_min=stop.arrival_min,
                    wait_min=stop.wait_min,
                    charge_start_min=stop.charge_start_min,
                    charge_end_min=stop.charge_end_min,
                )
                for index, (bus, stop) in enumerate(pairs)
            ]

        return ScheduleResult(
            bus_schedules=list(bus_schedules),
            station_orders=station_orders,
            violations=list(violations or []),
            objective_breakdown=dict(objective or {}),
        )

    return _build
