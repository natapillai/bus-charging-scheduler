"""Stage 4 tests, the weighted resolver picks the right bus per active weight."""

from types import SimpleNamespace

from scheduler.conflict import ConflictResolver, SchedulerState


def _world_with_weights(real_scenarios, weights):
    world = real_scenarios["scenario_1"].world
    world.weights = weights
    return world


def test_individual_weight_picks_longest_waiting(real_scenarios, make_bus):
    world = _world_with_weights(real_scenarios, {"individual": 1.0, "operator": 0.0, "overall": 0.0})
    waited_long = make_bus("bus-01", origin="Bengaluru", destination="Kochi")
    waited_short = make_bus("bus-02", origin="Bengaluru", destination="Kochi")
    state = SchedulerState(arrivals={("bus-01", "B"): 0, ("bus-02", "B"): 50})
    resolver = ConflictResolver()
    assert resolver.pick_next([waited_short, waited_long], "B", 100, state, world) is waited_long


def test_operator_weight_picks_most_delayed_operator(real_scenarios, make_bus):
    world = _world_with_weights(real_scenarios, {"individual": 0.0, "operator": 1.0, "overall": 0.0})
    behind = make_bus("bus-01", origin="Bengaluru", destination="Kochi", operator="kpn")
    ahead = make_bus("bus-02", origin="Bengaluru", destination="Kochi", operator="freshbus")
    state = SchedulerState(operator_wait={"kpn": 120.0, "freshbus": 10.0})
    resolver = ConflictResolver()
    assert resolver.pick_next([ahead, behind], "B", 100, state, world) is behind


def test_overall_weight_picks_most_remaining_trip(real_scenarios, make_bus):
    world = _world_with_weights(real_scenarios, {"individual": 0.0, "operator": 0.0, "overall": 1.0})
    forward = make_bus("bus-01", origin="Bengaluru", destination="Kochi")
    backward = make_bus("bus-02", origin="Kochi", destination="Bengaluru")
    state = SchedulerState()
    resolver = ConflictResolver()
    # At B the forward bus has 320 km left, the backward bus 220 km.
    assert resolver.pick_next([backward, forward], "B", 100, state, world) is forward


def test_ties_break_by_bus_id(real_scenarios, make_bus):
    world = _world_with_weights(real_scenarios, {"individual": 0.0, "operator": 0.0, "overall": 0.0})
    high_id = make_bus("bus-09", origin="Bengaluru", destination="Kochi")
    low_id = make_bus("bus-01", origin="Bengaluru", destination="Kochi")
    state = SchedulerState()
    resolver = ConflictResolver()
    assert resolver.pick_next([high_id, low_id], "B", 100, state, world) is low_id
    # Order of candidates does not matter for the tie break.
    assert resolver.pick_next([low_id, high_id], "B", 100, state, world) is low_id


def test_resolver_is_deterministic(real_scenarios, make_bus):
    world = _world_with_weights(real_scenarios, {"individual": 1.0, "operator": 1.0, "overall": 1.0})
    first = make_bus("bus-01", origin="Bengaluru", destination="Kochi", operator="kpn")
    second = make_bus("bus-02", origin="Bengaluru", destination="Kochi", operator="freshbus")
    state = SchedulerState(
        operator_wait={"kpn": 30.0, "freshbus": 30.0},
        arrivals={("bus-01", "B"): 10, ("bus-02", "B"): 10},
    )
    resolver = ConflictResolver()
    choice_one = resolver.pick_next([first, second], "B", 100, state, world)
    choice_two = resolver.pick_next([first, second], "B", 100, state, world)
    assert choice_one is choice_two
