"""Stage 7 tests, the live proof that a new rule slots in with no engine change.

These define throwaway rules inside the test, register them with the decorators,
and show the engine, the conflict resolver, and the objective all pick them up
with no edit to engine.py, conflict.py, or objective.py. The registry guard
fixture restores the registries afterwards so nothing leaks.
"""

from dataclasses import replace

from scheduler.engine import schedule
from scheduler.objective import evaluate
from scheduler.rules import HARD_RULES, SOFT_RULES, register_hard, register_soft
from scheduler.rules.base import HardRule, SoftRule


def test_new_soft_rule_is_registered_and_scored(real_scenarios, registry_guard):
    @register_soft
    class ElectricityCost(SoftRule):
        name = "electricity_cost"
        category = "electricity_cost"

        def score(self, schedule, world):
            return sum(len(bus_schedule.stops) for bus_schedule in schedule.bus_schedules)

        def priority(self, bus, station_id, now, state, world):
            return 1.0

    assert any(rule.name == "electricity_cost" for rule in SOFT_RULES)

    scenario = real_scenarios["scenario_1"]
    weights = {**scenario.world.weights, "electricity_cost": 2.0}
    result = schedule(scenario, weights=weights)
    world = replace(scenario.world, weights=weights)
    breakdown = evaluate(result, world)

    charges = sum(len(bus_schedule.stops) for bus_schedule in result.bus_schedules)
    assert breakdown["electricity_cost"] == 2.0 * charges


def test_new_hard_rule_is_registered_and_validated(real_scenarios, registry_guard):
    @register_hard
    class AlwaysComplains(HardRule):
        name = "always_complains"

        def validate(self, schedule, world):
            return ["synthetic violation from a new rule"]

    assert any(rule.name == "always_complains" for rule in HARD_RULES)

    result = schedule(real_scenarios["scenario_1"])
    assert "synthetic violation from a new rule" in result.violations


def test_registries_restored_between_tests():
    # By the time this runs the guard has restored the registries to their base
    # state, proving the throwaway rules did not leak.
    assert all(rule.name != "electricity_cost" for rule in SOFT_RULES)
    assert all(rule.name != "always_complains" for rule in HARD_RULES)
