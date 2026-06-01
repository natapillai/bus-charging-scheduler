"""The weighted objective.

The objective is the weighted sum over whatever soft rules are registered. It
walks the registry, multiplies each rule's score by the weight for its category,
and reports a per category breakdown plus a total. Because it reads the registry
and the weight dictionary, a new soft category contributes the moment its rule is
registered and its weight key exists, with no change here.
"""

from __future__ import annotations

from .rules import SOFT_RULES


def evaluate(schedule, world) -> dict:
    """Return the weighted penalty per category plus a total. Lower is better."""
    breakdown: dict[str, float] = {}
    total = 0.0
    for rule in SOFT_RULES:
        weight = world.weights.get(rule.category, 0.0)
        weighted = weight * rule.score(schedule, world)
        breakdown[rule.category] = breakdown.get(rule.category, 0.0) + weighted
        total += weighted
    breakdown["total"] = total
    return breakdown
