"""Stage 9 tests, the five scenarios load, stay valid, and respond to weights.

Weight sensitivity is shown two ways. On the worst case scenario, which has
genuine simultaneous contention, the operator weight at 1.0 versus 2.0 reorders
the chargers through conflict resolution, and raising the individual weight does
not increase the longest single wait. On the operator heavy scenario, whose even
spacing produces no simultaneous contention and whose single dominant operator
leaves operator fairness little to balance, the operator weight still changes the
schedule through plan selection, which is visible when fairness is toggled on
versus off. See ARCHITECTURE.md for why the operator heavy case behaves this way.
"""

from scheduler.engine import schedule

EXPECTED_COUNTS = {
    "scenario_1": 20,
    "scenario_2": 20,
    "scenario_3": 14,
    "scenario_4": 20,
    "scenario_5": 20,
}


def _station_orders(result):
    return {
        station_id: [entry.bus_id for entry in entries]
        for station_id, entries in result.station_orders.items()
    }


def _max_single_wait(result):
    return max(
        sum(stop.wait_min for stop in bus_schedule.stops)
        for bus_schedule in result.bus_schedules
    )


def test_all_five_load_with_expected_counts(real_scenarios):
    assert set(real_scenarios) == set(EXPECTED_COUNTS)
    for scenario_id, expected in EXPECTED_COUNTS.items():
        assert len(real_scenarios[scenario_id].buses) == expected


def test_each_scenario_valid_under_its_own_weights(real_scenarios):
    for scenario in real_scenarios.values():
        result = schedule(scenario)
        assert result.violations == []


def test_weight_panel_is_outcome_neutral(real_scenarios):
    # Passing the scenario's own weights must equal passing none, which is what
    # keeps an untouched weight panel from changing the schedule.
    for scenario in real_scenarios.values():
        assert schedule(scenario) == schedule(scenario, dict(scenario.world.weights))


def test_operator_weight_reorders_contended_scenario(real_scenarios):
    scenario = real_scenarios["scenario_5"]
    low = schedule(scenario, {"individual": 1.0, "operator": 1.0, "overall": 1.0})
    high = schedule(scenario, {"individual": 1.0, "operator": 2.0, "overall": 1.0})
    assert _station_orders(low) != _station_orders(high)


def test_operator_weight_changes_operator_heavy_scenario(real_scenarios):
    scenario = real_scenarios["scenario_4"]
    on = schedule(scenario, {"individual": 1.0, "operator": 2.0, "overall": 1.0})
    off = schedule(scenario, {"individual": 1.0, "operator": 0.0, "overall": 1.0})
    assert _station_orders(on) != _station_orders(off)


def test_individual_weight_does_not_raise_max_wait(real_scenarios):
    scenario = real_scenarios["scenario_5"]
    base = schedule(scenario, {"individual": 1.0, "operator": 1.0, "overall": 1.0})
    boosted = schedule(scenario, {"individual": 5.0, "operator": 1.0, "overall": 1.0})
    assert _max_single_wait(boosted) <= _max_single_wait(base)
