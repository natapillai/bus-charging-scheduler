"""The scheduling engine.

This is the mechanism. It knows a route, stations as resources with a charger
capacity, a clock, a set of rules, and a weight vector, and nothing about the
particular small world. It picks a charging plan for each bus, then runs a
discrete event simulation that advances time, moves buses between stations, and
resolves contention for a charger through the weighted ConflictResolver. After
the timeline is built it runs every hard rule to collect any violations. The
same scenario and weights always produce the same result.
"""

from __future__ import annotations

import heapq
import itertools
from dataclasses import replace

from .conflict import ConflictResolver, SchedulerState
from .domain import BusSchedule, ChargeStop, ScheduleResult, StationOrderEntry
from .geometry import choose_plan, distance_from_origin, travel_time
from .objective import evaluate
from .rules import HARD_RULES

_ARRIVAL = 0
_SERVER_FREE = 1


def _direction_label(bus) -> str:
    return f"{bus.origin} to {bus.destination}"


def _build_station_orders(bus_schedules):
    """Group every charge into a per station order sorted by charge start."""
    grouped = {}
    for bus_schedule in bus_schedules:
        for stop in bus_schedule.stops:
            grouped.setdefault(stop.station_id, []).append((bus_schedule.bus, stop))
    station_orders = {}
    for station_id, pairs in grouped.items():
        pairs.sort(key=lambda pair: (pair[1].charge_start_min, pair[0].id))
        station_orders[station_id] = [
            StationOrderEntry(
                order=index + 1,
                bus_id=bus.id,
                operator=bus.operator,
                direction_label=_direction_label(bus),
                arrival_min=stop.arrival_min,
                wait_min=stop.wait_min,
                charge_start_min=stop.charge_start_min,
                charge_end_min=stop.charge_end_min,
            )
            for index, (bus, stop) in enumerate(pairs)
        ]
    return station_orders


def schedule(scenario, weights=None) -> ScheduleResult:
    """Run the scheduler and return a complete, validated result.

    When weights are passed they override the scenario weights for this run only,
    leaving the scenario untouched, which is how the optional weight panel stays
    outcome neutral. With no weights the scenario's own weights are used.
    """
    world = scenario.world
    if weights is not None:
        world = replace(world, weights=dict(weights))
    speed = world.vehicle.speed_kmph
    charge_minutes = world.vehicle.charge_minutes
    buses = scenario.buses
    resolver = ConflictResolver()

    # Choose a plan for each bus in scenario order, spreading load across stations.
    load: dict[str, int] = {}
    plans: dict[str, list] = {}
    offsets_by_bus: dict[str, dict] = {}
    totals: dict[str, float] = {}
    plan_violations: list[str] = []
    for bus in buses:
        offsets, total = distance_from_origin(world, bus)
        offsets_by_bus[bus.id] = offsets
        totals[bus.id] = total
        plan = choose_plan(world, bus, load)
        if plan is None:
            plan_violations.append(f"{bus.id} has no feasible charging plan within range")
            plan = []
        plans[bus.id] = plan
        for station_id in plan:
            load[station_id] = load.get(station_id, 0) + 1

    # Simulation state.
    timelines: dict[str, list] = {bus.id: [] for bus in buses}
    final_arrival: dict[str, int] = {}
    station_state = {
        station.id: {"free": station.chargers, "waiting": []}
        for station in world.stations
    }
    state = SchedulerState()

    events: list = []
    counter = itertools.count()

    def push(time, kind, data):
        heapq.heappush(events, (time, next(counter), kind, data))

    def minutes(distance) -> int:
        return round(travel_time(distance, speed))

    # Seed the first event for every bus.
    for bus in buses:
        plan = plans[bus.id]
        if plan:
            first = plan[0]
            arrival = bus.departure_min + minutes(offsets_by_bus[bus.id][first])
            push(arrival, _ARRIVAL, (bus, plan, 0, arrival))
        else:
            final_arrival[bus.id] = bus.departure_min + minutes(totals[bus.id])

    def dispatch(station_id, now):
        station = station_state[station_id]
        while station["free"] > 0 and station["waiting"]:
            candidate_buses = [item[0] for item in station["waiting"]]
            chosen = resolver.pick_next(candidate_buses, station_id, now, state, world)
            item = next(i for i in station["waiting"] if i[0].id == chosen.id)
            station["waiting"].remove(item)
            bus, plan, index, arrival = item
            charge_start = now
            charge_end = charge_start + charge_minutes
            wait = charge_start - arrival
            timelines[bus.id].append(
                ChargeStop(
                    station_id=station_id,
                    arrival_min=arrival,
                    charge_start_min=charge_start,
                    charge_end_min=charge_end,
                    wait_min=wait,
                )
            )
            state.operator_wait[bus.operator] = state.operator_wait.get(bus.operator, 0) + wait
            station["free"] -= 1
            push(charge_end, _SERVER_FREE, station_id)
            offsets = offsets_by_bus[bus.id]
            if index + 1 < len(plan):
                following = plan[index + 1]
                next_arrival = charge_end + minutes(offsets[following] - offsets[station_id])
                push(next_arrival, _ARRIVAL, (bus, plan, index + 1, next_arrival))
            else:
                final_arrival[bus.id] = charge_end + minutes(totals[bus.id] - offsets[station_id])

    # Process events one timestamp at a time so simultaneous arrivals and freed
    # servers are all registered before anyone is dispatched.
    while events:
        current_time = events[0][0]
        touched = set()
        while events and events[0][0] == current_time:
            _, _, kind, data = heapq.heappop(events)
            if kind == _ARRIVAL:
                bus, plan, index, arrival = data
                station_id = plan[index]
                state.arrivals[(bus.id, station_id)] = arrival
                station_state[station_id]["waiting"].append(data)
                touched.add(station_id)
            else:
                station_id = data
                station_state[station_id]["free"] += 1
                touched.add(station_id)
        for station_id in sorted(touched):
            dispatch(station_id, current_time)

    bus_schedules = [
        BusSchedule(bus=bus, stops=timelines[bus.id], arrival_min=final_arrival.get(bus.id, bus.departure_min))
        for bus in buses
    ]
    station_orders = _build_station_orders(bus_schedules)
    result = ScheduleResult(
        bus_schedules=bus_schedules,
        station_orders=station_orders,
        violations=[],
        objective_breakdown={},
    )

    violations = list(plan_violations)
    for rule in HARD_RULES:
        violations.extend(rule.validate(result, world))
    result.violations = violations
    result.objective_breakdown = evaluate(result, world)
    return result
