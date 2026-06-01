"""Hard rules.

Each one reads the finished schedule and the world and returns the list of ways
the schedule breaks that constraint. A clean schedule returns an empty list from
every rule. The distances come from geometry so the same source of truth that
builds plans also checks them.
"""

from __future__ import annotations

from ..geometry import distance_from_origin
from .base import HardRule, register_hard


def _max_concurrent(intervals) -> int:
    """The largest number of charge intervals overlapping at one instant.

    Ends are processed before starts at the same minute, so a charge that begins
    exactly when another ends does not count as an overlap and back to back use
    of a single charger stays within capacity.
    """
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


@register_hard
class RangeConstraint(HardRule):
    """No bus may travel more than its range between consecutive charges."""

    name = "range_constraint"

    def validate(self, schedule, world):
        violations = []
        range_km = world.vehicle.range_km
        for bus_schedule in schedule.bus_schedules:
            offsets, total = distance_from_origin(world, bus_schedule.bus)
            points = [0.0]
            on_route = True
            for stop in bus_schedule.stops:
                if stop.station_id not in offsets:
                    on_route = False
                    break
                points.append(offsets[stop.station_id])
            if not on_route:
                continue
            points.append(total)
            for earlier, later in zip(points, points[1:]):
                gap = later - earlier
                if gap > range_km:
                    violations.append(
                        f"{bus_schedule.bus.id} covers {gap:g} km between charges "
                        f"which exceeds the {range_km:g} km range"
                    )
        return violations


@register_hard
class ChargerCapacity(HardRule):
    """A station never serves more buses at once than it has chargers."""

    name = "charger_capacity"

    def validate(self, schedule, world):
        violations = []
        capacity = {station.id: station.chargers for station in world.stations}
        intervals_by_station = {}
        for bus_schedule in schedule.bus_schedules:
            for stop in bus_schedule.stops:
                intervals_by_station.setdefault(stop.station_id, []).append(
                    (stop.charge_start_min, stop.charge_end_min)
                )
        for station_id, intervals in intervals_by_station.items():
            allowed = capacity.get(station_id, 1)
            peak = _max_concurrent(intervals)
            if peak > allowed:
                violations.append(
                    f"station {station_id} serves {peak} buses at once "
                    f"but has only {allowed} charger(s)"
                )
        return violations


@register_hard
class RouteOrder(HardRule):
    """A bus charges in its travel order with no backtracking."""

    name = "route_order"

    def validate(self, schedule, world):
        violations = []
        for bus_schedule in schedule.bus_schedules:
            offsets, _ = distance_from_origin(world, bus_schedule.bus)
            previous = -1.0
            for stop in bus_schedule.stops:
                if stop.station_id not in offsets:
                    violations.append(
                        f"{bus_schedule.bus.id} charges at {stop.station_id} "
                        f"which is not on its route"
                    )
                    break
                here = offsets[stop.station_id]
                if here <= previous:
                    violations.append(
                        f"{bus_schedule.bus.id} charges at {stop.station_id} out of route order"
                    )
                    break
                previous = here
        return violations


@register_hard
class ChargeDuration(HardRule):
    """Every charge lasts exactly the configured number of minutes."""

    name = "charge_duration"

    def validate(self, schedule, world):
        violations = []
        expected = world.vehicle.charge_minutes
        for bus_schedule in schedule.bus_schedules:
            for stop in bus_schedule.stops:
                actual = stop.charge_end_min - stop.charge_start_min
                if actual != expected:
                    violations.append(
                        f"{bus_schedule.bus.id} charges {actual} minutes at "
                        f"{stop.station_id} but the fixed charge is {expected} minutes"
                    )
        return violations
