"""Stage 6 tests, weighted aggregation and new category pickup."""

from dataclasses import replace

from scheduler.engine import schedule
from scheduler.objective import evaluate
from scheduler.rules import SOFT_RULES, register_soft
from scheduler.rules.base import SoftRule


def test_breakdown_sums_weighted_scores(real_scenarios):
    scenario = real_scenarios["scenario_1"]
    world = scenario.world
    result = schedule(scenario)
    breakdown = evaluate(result, world)
    for rule in SOFT_RULES:
        weight = world.weights.get(rule.category, 0.0)
        assert breakdown[rule.category] == weight * rule.score(result, world)
    categories = [key for key in breakdown if key != "total"]
    assert breakdown["total"] == sum(breakdown[key] for key in categories)


def test_zero_weight_removes_contribution(real_scenarios):
    scenario = real_scenarios["scenario_1"]
    result = schedule(scenario)
    silenced = replace(scenario.world, weights={"individual": 1.0, "operator": 0.0, "overall": 1.0})
    breakdown = evaluate(result, silenced)
    assert breakdown["operator"] == 0.0


def test_new_category_flows_through_without_objective_change(real_scenarios, registry_guard):
    @register_soft
    class DummyCost(SoftRule):
        name = "dummy_cost"
        category = "dummy_cost"

        def score(self, schedule, world):
            return 5.0

    scenario = real_scenarios["scenario_1"]
    result = schedule(scenario)
    world = replace(scenario.world, weights={**scenario.world.weights, "dummy_cost": 3.0})
    breakdown = evaluate(result, world)
    assert breakdown["dummy_cost"] == 15.0
