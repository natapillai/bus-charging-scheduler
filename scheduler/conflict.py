"""Conflict resolution.

When several buses wait for the same charger the resolver decides who goes next.
It ranks each waiting bus by the weighted sum of the soft rule priorities, using
the same weights that drive the objective, and breaks ties by bus id so the
order is explainable and the schedule is deterministic. The resolver reads the
soft rules from the registry, so a new soft rule influences the order with no
change here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .rules import SOFT_RULES


@dataclass
class SchedulerState:
    """The running state the engine maintains and the priorities read.

    operator_wait accumulates the wait each operator's fleet has taken on so far.
    arrivals records the minute each waiting bus reached a station, keyed by the
    bus id and the station id, so an individual bus's wait so far is the current
    time minus its arrival.
    """

    operator_wait: dict = field(default_factory=dict)
    arrivals: dict = field(default_factory=dict)


class ConflictResolver:
    """Ranks waiting buses by the weighted soft rule priorities."""

    def __init__(self, soft_rules=None):
        self.soft_rules = soft_rules if soft_rules is not None else SOFT_RULES

    def rank(self, bus, station_id, now, state, world) -> float:
        """The weighted priority score for one bus. Higher charges sooner."""
        total = 0.0
        for rule in self.soft_rules:
            weight = world.weights.get(rule.category, 0.0)
            total += weight * rule.priority(bus, station_id, now, state, world)
        return total

    def pick_next(self, candidates, station_id, now, state, world):
        """Choose the next bus to charge from those waiting.

        The highest weighted priority wins. On an exact tie the lower bus id
        wins, which keeps the choice deterministic and easy to explain.
        """
        scored = [
            (self.rank(bus, station_id, now, state, world), bus) for bus in candidates
        ]
        best = max(score for score, _ in scored)
        tied = [bus for score, bus in scored if score == best]
        return min(tied, key=lambda bus: bus.id)
