"""Soft rules.

Each one penalises a finished schedule through score, lower being better, and
nudges who charges next through priority, higher meaning sooner. The three
categories match the three weight keys. These penalty and priority shapes are
the obvious place to refine later, so they are kept simple and isolated here.
"""

from __future__ import annotations

from ..geometry import distance_from_origin
from .base import SoftRule, register_soft


def _bus_wait(bus_schedule) -> int:
    """Total minutes a bus spent waiting across all its stops."""
    return sum(stop.wait_min for stop in bus_schedule.stops)


@register_soft
class IndividualWait(SoftRule):
    """No single bus should wait too long."""

    name = "individual_wait"
    category = "individual"

    def score(self, schedule, world):
        # Squaring each bus total makes one long wait cost more than the same
        # minutes spread thinly, which is what keeps any single bus from being
        # left waiting.
        return sum(_bus_wait(bus_schedule) ** 2 for bus_schedule in schedule.bus_schedules)

    def priority(self, bus, station_id, now, state, world):
        arrived = state.arrivals.get((bus.id, station_id), now)
        return now - arrived


@register_soft
class OperatorFairness(SoftRule):
    """Each operator's fleet should run smoothly as a group."""

    name = "operator_fairness"
    category = "operator"

    def score(self, schedule, world):
        totals = {}
        for bus_schedule in schedule.bus_schedules:
            operator = bus_schedule.bus.operator
            totals[operator] = totals.get(operator, 0) + _bus_wait(bus_schedule)
        if not totals:
            return 0
        return max(totals.values()) - min(totals.values())

    def priority(self, bus, station_id, now, state, world):
        return state.operator_wait.get(bus.operator, 0.0)


@register_soft
class OverallMakespan(SoftRule):
    """Total time across the whole network should be low."""

    name = "overall_makespan"
    category = "overall"

    def score(self, schedule, world):
        if not schedule.bus_schedules:
            return 0
        latest_arrival = max(bs.arrival_min for bs in schedule.bus_schedules)
        earliest_departure = min(bs.bus.departure_min for bs in schedule.bus_schedules)
        return latest_arrival - earliest_departure

    def priority(self, bus, station_id, now, state, world):
        offsets, total = distance_from_origin(world, bus)
        return total - offsets.get(station_id, total)
