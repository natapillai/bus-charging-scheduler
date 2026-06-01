"""Rule registry and base classes.

This is where policy plugs into the engine. Hard rules are validators that look
at a finished schedule and return violation strings, empty when all is well.
Soft rules are scorers that penalise a finished schedule and also expose a
priority used while resolving who charges next. Each soft rule carries a category
that maps to a weight key, so a new category is one new class plus one weight.

Registering a rule is decorating its class. The engine never names a rule, it
just walks these two lists, which is what lets a new rule slot in with no engine
change.
"""

from __future__ import annotations

HARD_RULES = []
SOFT_RULES = []


def register_hard(cls):
    """Add a hard rule instance to the registry and return the class."""
    HARD_RULES.append(cls())
    return cls


def register_soft(cls):
    """Add a soft rule instance to the registry and return the class."""
    SOFT_RULES.append(cls())
    return cls


class HardRule:
    """A constraint that a valid schedule must never break."""

    name = "hard_rule"

    def validate(self, schedule, world):
        """Return a list of violation strings. Empty means the schedule is valid."""
        raise NotImplementedError


class SoftRule:
    """A preference the scheduler weighs when it has freedom to choose.

    The score penalises a finished schedule, lower being better. The priority
    ranks a waiting bus during conflict resolution, higher meaning the bus should
    charge sooner. The priority reads a small state object the engine maintains,
    which carries the accumulated wait per operator in operator_wait and the
    arrival minute of each waiting bus in arrivals keyed by the bus id and the
    station id.
    """

    name = "soft_rule"
    category = "overall"

    def score(self, schedule, world):
        """Penalty for a complete schedule. Lower is better."""
        raise NotImplementedError

    def priority(self, bus, station_id, now, state, world):
        """Higher means this bus should charge sooner. Used in conflict resolution."""
        return 0.0
