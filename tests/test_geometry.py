"""Stage 2 tests, geometry and feasible plan enumeration."""

from scheduler.geometry import (
    choose_plan,
    cumulative_distances,
    distance_from_origin,
    feasible_plans,
    travel_time,
    traversal,
)


def _gaps(world, bus, plan):
    """The distances the bus covers between charges given a plan."""
    offsets, total = distance_from_origin(world, bus)
    points = [0.0] + [offsets[station_id] for station_id in plan] + [total]
    return [later - earlier for earlier, later in zip(points, points[1:])]


def test_traversal_order_both_directions(real_scenarios):
    route = real_scenarios["scenario_1"].world.route
    assert traversal(route, "Bengaluru", "Kochi") == ["Bengaluru", "A", "B", "C", "D", "Kochi"]
    assert traversal(route, "Kochi", "Bengaluru") == ["Kochi", "D", "C", "B", "A", "Bengaluru"]


def test_cumulative_distances_both_directions(real_scenarios):
    route = real_scenarios["scenario_1"].world.route
    _, forward = cumulative_distances(route, "Bengaluru", "Kochi")
    assert forward == [0, 100, 220, 320, 440, 540]
    _, backward = cumulative_distances(route, "Kochi", "Bengaluru")
    assert backward == [0, 100, 220, 320, 440, 540]


def test_station_offsets_from_origin(real_scenarios):
    world = real_scenarios["scenario_1"].world
    forward = next(b for b in real_scenarios["scenario_1"].buses if b.origin == "Bengaluru")
    offsets, total = distance_from_origin(world, forward)
    assert offsets == {"A": 100, "B": 220, "C": 320, "D": 440}
    assert total == 540
    backward = next(b for b in real_scenarios["scenario_1"].buses if b.origin == "Kochi")
    offsets, total = distance_from_origin(world, backward)
    assert offsets == {"D": 100, "C": 220, "B": 320, "A": 440}
    assert total == 540


def test_travel_time_matches_distance_at_sixty():
    assert travel_time(100, 60) == 100
    assert travel_time(120, 60) == 120
    assert travel_time(240, 60) == 240


def test_travel_time_scales_with_speed():
    assert travel_time(100, 30) == 200
    assert travel_time(120, 120) == 60


def test_feasible_two_charge_plans_forward(real_scenarios):
    world = real_scenarios["scenario_1"].world
    bus = next(b for b in real_scenarios["scenario_1"].buses if b.origin == "Bengaluru")
    plans = feasible_plans(world, bus)
    two_charge = {tuple(plan) for plan in plans if len(plan) == 2}
    assert two_charge == {("A", "C"), ("B", "C"), ("B", "D")}


def test_feasible_two_charge_plans_reverse(real_scenarios):
    world = real_scenarios["scenario_1"].world
    bus = next(b for b in real_scenarios["scenario_1"].buses if b.origin == "Kochi")
    plans = feasible_plans(world, bus)
    two_charge = {tuple(plan) for plan in plans if len(plan) == 2}
    assert two_charge == {("D", "B"), ("C", "B"), ("C", "A")}


def test_every_plan_within_range(real_scenarios):
    world = real_scenarios["scenario_1"].world
    for bus in real_scenarios["scenario_1"].buses:
        for plan in feasible_plans(world, bus):
            assert all(gap <= world.vehicle.range_km for gap in _gaps(world, bus, plan))


def test_minimum_charges_is_two_endpoint_to_endpoint(real_scenarios):
    world = real_scenarios["scenario_1"].world
    for bus in real_scenarios["scenario_1"].buses:
        plans = feasible_plans(world, bus)
        assert min(len(plan) for plan in plans) == 2


def test_charge_everywhere_feasible_when_segments_within_range(tiny_world, make_bus):
    bus = make_bus("t-1", origin="O", destination="Z")
    plans = feasible_plans(tiny_world, bus)
    assert ["P", "Q"] in plans
    assert min(len(plan) for plan in plans) == 1


def test_no_plan_when_adjacent_segment_exceeds_range(tiny_world_unreachable, make_bus):
    bus = make_bus("t-1", origin="O", destination="Z")
    assert feasible_plans(tiny_world_unreachable, bus) == []
    assert choose_plan(tiny_world_unreachable, bus) is None


def test_choose_plan_prefers_fewest_charges(tiny_world, make_bus):
    bus = make_bus("t-1", origin="O", destination="Z")
    chosen = choose_plan(tiny_world, bus)
    assert len(chosen) == 1


def test_choose_plan_is_deterministic(real_scenarios):
    world = real_scenarios["scenario_1"].world
    bus = next(b for b in real_scenarios["scenario_1"].buses if b.origin == "Bengaluru")
    first = choose_plan(world, bus, {})
    second = choose_plan(world, bus, {})
    assert first == second
    assert len(first) == 2


def test_choose_plan_spreads_to_lower_loaded_stations(real_scenarios):
    world = real_scenarios["scenario_1"].world
    bus = next(b for b in real_scenarios["scenario_1"].buses if b.origin == "Bengaluru")
    loaded = choose_plan(world, bus, {"A": 5, "C": 5})
    assert loaded == ["B", "D"]
