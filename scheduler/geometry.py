"""Route geometry and feasible charging plans.

Everything here is built from the route data, so a longer route, different
distances, or a different range change the answers without changing the code.
Range feasibility is purely geometric. Waiting does not drain the battery and a
charge always refills to full, so whether a plan is feasible depends only on
distances and never on timing.
"""

from __future__ import annotations


def traversal(route, origin, destination) -> list[str]:
    """Return the nodes from origin to destination in the order the bus visits.

    A forward trip slices the node order, a reverse trip walks it backwards, so
    direction never needs its own representation.
    """
    nodes = route.nodes
    start = nodes.index(origin)
    end = nodes.index(destination)
    if start <= end:
        return nodes[start : end + 1]
    return list(reversed(nodes[end : start + 1]))


def _adjacent_distances(route) -> dict[tuple[str, str], float]:
    """Map each adjacent node pair to its segment distance in both directions."""
    distances = {}
    for segment in route.segments:
        distances[(segment.from_node, segment.to_node)] = segment.distance_km
        distances[(segment.to_node, segment.from_node)] = segment.distance_km
    return distances


def cumulative_distances(route, origin, destination):
    """Return the visited nodes and the distance from the origin to each.

    The first entry is the origin at distance zero and the last is the
    destination at the total trip distance.
    """
    path = traversal(route, origin, destination)
    distances = _adjacent_distances(route)
    cumulative = [0.0]
    for current, following in zip(path, path[1:]):
        cumulative.append(cumulative[-1] + distances[(current, following)])
    return path, cumulative


def travel_time(distance_km, speed_kmph) -> float:
    """Minutes to cover a distance at a speed.

    Multiplying by sixty before dividing keeps whole distances at sixty km/h on
    exact whole minutes rather than drifting through floating point.
    """
    return distance_km * 60 / speed_kmph


def distance_from_origin(world, bus):
    """Map each station the bus passes to its distance from the bus origin.

    Returns the mapping and the total trip distance. Endpoints are skipped
    because they are not scheduling stations.
    """
    path, cumulative = cumulative_distances(world.route, bus.origin, bus.destination)
    station_by_node = {station.node: station.id for station in world.stations}
    offsets = {}
    for node, distance in zip(path, cumulative):
        if node in (bus.origin, bus.destination):
            continue
        if node in station_by_node:
            offsets[station_by_node[node]] = distance
    return offsets, cumulative[-1]


def feasible_plans(world, bus) -> list[list[str]]:
    """Enumerate every feasible charging plan for a bus.

    A plan is a subset of the stations the bus passes, in traversal order, where
    the gap from the origin to the first charge, every gap between consecutive
    charges, and the gap from the last charge to the destination are all within
    range. The walk reaches the destination from any point within range and hops
    to any later station within range, so the minimum number of charges falls out
    of the data rather than being a constant. When an adjacent gap exceeds the
    range no plan exists and the list is empty.
    """
    offsets, total = distance_from_origin(world, bus)
    stops = sorted(offsets.items(), key=lambda item: item[1])
    range_km = world.vehicle.range_km
    plans: list[list[str]] = []

    def walk(last_index, last_distance, chosen):
        if total - last_distance <= range_km:
            plans.append(list(chosen))
        for index in range(last_index + 1, len(stops)):
            station_id, distance = stops[index]
            if distance - last_distance <= range_km:
                chosen.append(station_id)
                walk(index, distance, chosen)
                chosen.pop()

    walk(-1, 0.0, [])
    return plans


def choose_plan(world, bus, load_so_far=None, operator_load=None):
    """Pick the plan for a bus.

    The first preference is always the fewest charges, which keeps trips short
    and feasible. Among plans with the same charge count the choice spreads load
    across stations, and the spread is weight aware. The overall weight pushes a
    bus away from stations that are already busy across the whole network, and
    the operator weight pushes a bus away from stations its own operator is
    already stacking on, so a fleet runs more smoothly as a group. Remaining ties
    fall to the station identifiers so the choice is deterministic. This is the
    second place the weights act, alongside conflict resolution, which lets the
    operator weight change a schedule even when buses never queue at once.
    Returns None when no plan is feasible so the caller can surface a violation.
    """
    load_so_far = load_so_far or {}
    operator_load = operator_load or {}
    plans = feasible_plans(world, bus)
    if not plans:
        return None

    overall_weight = world.weights.get("overall", 0.0)
    operator_weight = world.weights.get("operator", 0.0)

    def key(plan):
        station_load = sum(load_so_far.get(station_id, 0) for station_id in plan)
        own_load = sum(operator_load.get((bus.operator, station_id), 0) for station_id in plan)
        spread = overall_weight * station_load + operator_weight * own_load
        return (len(plan), spread, tuple(plan))

    return min(plans, key=key)
