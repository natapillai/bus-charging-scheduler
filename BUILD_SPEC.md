# Build Spec: Bus Charging Scheduler (Exponent Energy take home)

You are Claude Code. Build the complete project described below, end to end, then verify it runs and the tests pass. Everything here is derived strictly from the assignment PDF. Do not invent rules or numbers beyond what is stated. Where the spec leaves a gap, use the assumption already written in this document and record it in `ARCHITECTURE.md`.

## 1. Goal

A single Python and Streamlit application, one repo, one process, that reads any of five scenarios from data files, runs a scheduler that decides each bus's charging plan and the order buses use each charger, and shows the result in the UI. The app is hosted on Streamlit Community Cloud. The repo is public and contains all code, all five scenarios, a `README.md`, and an `ARCHITECTURE.md`.

The thing they care about most is that the scheduler is built to scale. Changing a weight must be one value in one obvious place. Adding a new rule must not require rewriting the engine. Growing the world (more buses, stations, chargers, operators, routes) must not require a rewrite. The architecture is graded directly, so the separation between the engine and the rules has to be clean and the data model has to anticipate change.

## 2. Pinned facts (do not change)

Route nodes in order: Bengaluru, A, B, C, D, Kochi. Segments and distances: Bengaluru to A is 100 km, A to B is 120 km, B to C is 100 km, C to D is 120 km, D to Kochi is 100 km. Total 540 km.

Only A, B, C, D are scheduling stations. Bengaluru and Kochi are endpoints with slow chargers, so every bus departs its origin fully charged. Endpoints are not part of the scheduling problem.

Battery range is 240 km on a full charge. Charging is always to full and takes exactly 25 minutes. All buses travel at the same speed. Use a consistent speed in the simulation. Use 60 km/h so a 100 km segment takes 100 minutes. Speed lives in the data so it is tunable.

Each station has 1 charger by default, so one bus charges at a station at a time. Twenty buses per scenario (ten each direction) except Scenario 3, which has fourteen. Each bus has a scheduled departure from its origin and belongs to one of three operators: kpn, freshbus, flixbus. Buses travel in both directions and share the same stations.

A bus cannot travel more than 240 km between two consecutive charges, or between its start and the first charge, or between the last charge and arrival. A Bengaluru to Kochi bus therefore must charge at least twice (540 km total). The scheduler chooses which stations a bus uses, in route order, with no backtracking.

Soft rules to weigh when the scheduler has flexibility: individual (no single bus waits too long), operator (each operator's fleet runs smoothly as a group), overall (total time across the network is low). Default weights are individual 1.0, operator 1.0, overall 1.0. Scenario 4 overrides operator to 2.0. Weights must be tunable and never hardcoded.

## 3. Chosen approach and why

Build a greedy, event driven (discrete event) scheduler with a pluggable rule registry and a tunable weighted objective. Frame it as a priority based discrete event scheduler that cleanly separates mechanism from policy.

The engine (mechanism) knows only generic concepts. A route is a sequence of nodes with distances. A station is a resource with a charger capacity. A bus traverses the route from an origin to a destination and makes charge stops. There is a clock. There is a set of rules and a weight vector. The engine advances time, moves buses, and when buses contend for a charger it resolves the conflict using a weighted priority built from the registered soft rules. Hard rules filter anything infeasible.

The rules (policy) live outside the engine. Hard rules are validators that return violations. Soft rules are scorers, each tagged with a category that maps to a weight key. The objective is the weighted sum over whatever soft rules are registered. Adding a rule is writing one small class and registering it. Adding a soft category is adding one key to the weights in the data plus one rule class. The engine code does not change.

Why this over a solver such as MILP or CP SAT. The assignment stresses that the world will grow and that adding a rule must be small and tested live. A discrete event greedy scheduler is close to linear in the number of buses times stations, so it scales to a large world without solver blowup, it is easy to read and defend, and adding a rule slots in as a registered function. The trade off is that it produces sensible and defensible schedules rather than provably optimal ones, which is exactly what the assignment asks for (sensible per bus plans, reasonable waits, and different weights producing different defensible schedules). State this trade off honestly in `ARCHITECTURE.md` and mention the solver alternative as the path you considered and rejected for scalability, extensibility, and simplicity reasons.

## 4. Repository layout

The GitHub repository is `bus-charging-scheduler` owned by `natapillai`, so the public URL is `https://github.com/natapillai/bus-charging-scheduler`. When cloned, the root directory is `bus-charging-scheduler` and it contains `app.py` and `requirements.txt` directly at the root so Streamlit Community Cloud finds them.

```
bus-charging-scheduler/              repo root, contains app.py and requirements.txt directly
  app.py                      Streamlit entry point, UI only, no scheduling logic
  requirements.txt
  README.md
  ARCHITECTURE.md
  scheduler/
    __init__.py
    domain.py                 dataclasses for inputs and outputs
    loader.py                 load_scenario(path) returns a Scenario, format isolated
    geometry.py               cumulative distances, travel time, feasible plan enumeration
    conflict.py               ConflictResolver, weighted priority for charger queue order
    objective.py              weighted objective aggregation and breakdown
    engine.py                 Scheduler, event simulation, returns ScheduleResult, validates
    viewmodel.py              pure helpers the UI calls, time formatting, direction labels, table builders
    rules/
      __init__.py             registry plus auto import of hard and soft modules
      base.py                 HardRule, SoftRule base classes and register decorators
      hard.py                 RangeConstraint, ChargerCapacity, RouteOrder, ChargeDuration
      soft.py                 IndividualWait, OperatorFairness, OverallMakespan
  scenarios/
    scenario_1.json
    scenario_2.json
    scenario_3.json
    scenario_4.json
    scenario_5.json
  tests/
    conftest.py               shared fixtures, a tiny synthetic world plus loaders for the real scenarios
    test_loader.py            stage 1, parsing and scenario loading
    test_geometry.py          stage 2, distances, travel time, feasible plan enumeration
    test_hard_rules.py        stage 3a, each hard rule, passing and failing cases
    test_soft_rules.py        stage 3b, each soft rule, score and priority behavior
    test_conflict.py          stage 4, weighted priority ranking and determinism
    test_engine.py            stage 5, full simulation invariants, capacity, shared stations, determinism
    test_objective.py         stage 6, weighted aggregation and new category pickup
    test_extensibility.py     stage 7, a new rule registers and is used with no engine change
    test_viewmodel.py         stage 8, UI helper functions without importing Streamlit
    test_scenarios.py         stage 9, all five scenarios load, counts, validity, weight sensitivity
```

Use only the Python standard library plus `streamlit` and `pandas`, and `pytest` for tests. Use dataclasses for the domain. No database, no auth, no maps. In memory state is fine.

Keep `app.py` thin. Every piece of logic that turns a `ScheduleResult` into something on screen lives in `scheduler/viewmodel.py` as a pure function that takes plain data and returns plain data, so the UI is testable without running Streamlit. The functions are `format_time(minutes)` returning an `HH:MM` string with a plus one day marker at or beyond 1440, `direction_label(origin, destination)` returning a readable label, `build_input_table(scenario)`, `build_bus_summary_table(result)`, `build_bus_stops_table(result, bus_id)`, and `build_station_table(result, station_id)`. Each returns a list of dicts or a pandas dataframe. `app.py` only arranges these on the page.

## 5. Domain and data model

A scenario file is self contained. It fully describes one situation: the world (route, stations with charger capacity, vehicle parameters, weights) and the buses. The five scenario files share the same world except Scenario 4 changes the operator weight. The format is JSON. Keep the loader as a single function so swapping to YAML or TOML later is a one function change.

Design the data so that nothing about the current small world is hardcoded. Charger count is a capacity number on each station, defaulting to 1. Operators are arbitrary string labels read off the buses, not a fixed set. The route is a list of nodes plus a list of segments with distances. A bus references an origin node and a destination node rather than a fixed direction enum, so reverse direction is just traversing the node order backwards and future intermediate origins or destinations need no new field. Weights are a dictionary keyed by category, so a new soft category is a new key, not a schema change.

Full example, `scenarios/scenario_1.json`. Use this exact world block in all five files and only swap the buses and the weights.

```json
{
  "scenario_id": "scenario_1",
  "name": "Even spacing",
  "description": "Buses depart every 15 minutes in each direction starting 19:00. Baseline case.",
  "world": {
    "route": {
      "nodes": ["Bengaluru", "A", "B", "C", "D", "Kochi"],
      "segments": [
        {"from": "Bengaluru", "to": "A", "distance_km": 100},
        {"from": "A", "to": "B", "distance_km": 120},
        {"from": "B", "to": "C", "distance_km": 100},
        {"from": "C", "to": "D", "distance_km": 120},
        {"from": "D", "to": "Kochi", "distance_km": 100}
      ],
      "endpoints": ["Bengaluru", "Kochi"]
    },
    "stations": [
      {"id": "A", "node": "A", "chargers": 1},
      {"id": "B", "node": "B", "chargers": 1},
      {"id": "C", "node": "C", "chargers": 1},
      {"id": "D", "node": "D", "chargers": 1}
    ],
    "vehicle": {
      "range_km": 240,
      "charge_minutes": 25,
      "speed_kmph": 60
    },
    "weights": {
      "individual": 1.0,
      "operator": 1.0,
      "overall": 1.0
    }
  },
  "buses": [
    {"id": "bus-BK-01", "operator": "kpn", "origin": "Bengaluru", "destination": "Kochi", "departure": "19:00"},
    {"id": "bus-BK-02", "operator": "freshbus", "origin": "Bengaluru", "destination": "Kochi", "departure": "19:15"},
    {"id": "bus-BK-03", "operator": "flixbus", "origin": "Bengaluru", "destination": "Kochi", "departure": "19:30"},
    {"id": "bus-BK-04", "operator": "kpn", "origin": "Bengaluru", "destination": "Kochi", "departure": "19:45"},
    {"id": "bus-BK-05", "operator": "freshbus", "origin": "Bengaluru", "destination": "Kochi", "departure": "20:00"},
    {"id": "bus-BK-06", "operator": "flixbus", "origin": "Bengaluru", "destination": "Kochi", "departure": "20:15"},
    {"id": "bus-BK-07", "operator": "kpn", "origin": "Bengaluru", "destination": "Kochi", "departure": "20:30"},
    {"id": "bus-BK-08", "operator": "freshbus", "origin": "Bengaluru", "destination": "Kochi", "departure": "20:45"},
    {"id": "bus-BK-09", "operator": "flixbus", "origin": "Bengaluru", "destination": "Kochi", "departure": "21:00"},
    {"id": "bus-BK-10", "operator": "kpn", "origin": "Bengaluru", "destination": "Kochi", "departure": "21:15"},
    {"id": "bus-KB-01", "operator": "freshbus", "origin": "Kochi", "destination": "Bengaluru", "departure": "19:00"},
    {"id": "bus-KB-02", "operator": "flixbus", "origin": "Kochi", "destination": "Bengaluru", "departure": "19:15"},
    {"id": "bus-KB-03", "operator": "kpn", "origin": "Kochi", "destination": "Bengaluru", "departure": "19:30"},
    {"id": "bus-KB-04", "operator": "freshbus", "origin": "Kochi", "destination": "Bengaluru", "departure": "19:45"},
    {"id": "bus-KB-05", "operator": "flixbus", "origin": "Kochi", "destination": "Bengaluru", "departure": "20:00"},
    {"id": "bus-KB-06", "operator": "kpn", "origin": "Kochi", "destination": "Bengaluru", "departure": "20:15"},
    {"id": "bus-KB-07", "operator": "freshbus", "origin": "Kochi", "destination": "Bengaluru", "departure": "20:30"},
    {"id": "bus-KB-08", "operator": "flixbus", "origin": "Kochi", "destination": "Bengaluru", "departure": "20:45"},
    {"id": "bus-KB-09", "operator": "kpn", "origin": "Kochi", "destination": "Bengaluru", "departure": "21:00"},
    {"id": "bus-KB-10", "operator": "freshbus", "origin": "Kochi", "destination": "Bengaluru", "departure": "21:15"}
  ]
}
```

Domain dataclasses to define in `domain.py`. Inputs: `Segment(from_node, to_node, distance_km)`, `Route(nodes, segments, endpoints)`, `Station(id, node, chargers)`, `Vehicle(range_km, charge_minutes, speed_kmph)`, `World(route, stations, vehicle, weights)` where weights is a plain dict, `Bus(id, operator, origin, destination, departure_min)`, `Scenario(scenario_id, name, description, world, buses)`. Parse the `departure` string `HH:MM` into integer minutes from midnight at load time.

Output dataclasses: `ChargeStop(station_id, arrival_min, charge_start_min, charge_end_min, wait_min)`, `BusSchedule(bus, stops, arrival_min)` where `arrival_min` is when the bus reaches its destination, `StationOrderEntry(order, bus_id, operator, direction_label, arrival_min, wait_min, charge_start_min, charge_end_min)`, `ScheduleResult(bus_schedules, station_orders, violations, objective_breakdown)`. `station_orders` is a dict from station id to a list of `StationOrderEntry` sorted by `charge_start_min`. `violations` is a list of strings, empty when the schedule is valid. `objective_breakdown` is a dict from category to weighted penalty plus a total.

## 6. The five scenarios

Write all five files. Reuse the world block from Scenario 1 verbatim and only change `scenario_id`, `name`, `description`, the `weights`, and the `buses`. Verify the bus counts: Scenarios 1, 2, 4, and 5 have twenty buses, Scenario 3 has fourteen. Operators are lowercase exactly as below.

Scenario 2, name "Bunched start", description "Buses from both directions depart in a tight cluster every 8 minutes over the first 50 minutes, then space out. Heavy early contention." Weights default.

```
bus-BK-01 kpn Bengaluru Kochi 19:00
bus-BK-02 freshbus Bengaluru Kochi 19:08
bus-BK-03 flixbus Bengaluru Kochi 19:16
bus-BK-04 kpn Bengaluru Kochi 19:24
bus-BK-05 freshbus Bengaluru Kochi 19:32
bus-BK-06 flixbus Bengaluru Kochi 19:40
bus-BK-07 kpn Bengaluru Kochi 19:48
bus-BK-08 freshbus Bengaluru Kochi 20:03
bus-BK-09 flixbus Bengaluru Kochi 20:18
bus-BK-10 kpn Bengaluru Kochi 20:33
bus-KB-01 freshbus Kochi Bengaluru 19:00
bus-KB-02 flixbus Kochi Bengaluru 19:08
bus-KB-03 kpn Kochi Bengaluru 19:16
bus-KB-04 freshbus Kochi Bengaluru 19:24
bus-KB-05 flixbus Kochi Bengaluru 19:32
bus-KB-06 kpn Kochi Bengaluru 19:40
bus-KB-07 freshbus Kochi Bengaluru 19:48
bus-KB-08 flixbus Kochi Bengaluru 20:03
bus-KB-09 kpn Kochi Bengaluru 20:18
bus-KB-10 freshbus Kochi Bengaluru 20:33
```

Scenario 3, name "Asymmetric load", description "Ten buses going Bengaluru to Kochi at 15 minute spacing, only four going Kochi to Bengaluru. Tests uneven traffic across directions." Weights default. Fourteen buses.

```
bus-BK-01 kpn Bengaluru Kochi 19:00
bus-BK-02 freshbus Bengaluru Kochi 19:15
bus-BK-03 flixbus Bengaluru Kochi 19:30
bus-BK-04 kpn Bengaluru Kochi 19:45
bus-BK-05 freshbus Bengaluru Kochi 20:00
bus-BK-06 flixbus Bengaluru Kochi 20:15
bus-BK-07 kpn Bengaluru Kochi 20:30
bus-BK-08 freshbus Bengaluru Kochi 20:45
bus-BK-09 flixbus Bengaluru Kochi 21:00
bus-BK-10 kpn Bengaluru Kochi 21:15
bus-KB-01 freshbus Kochi Bengaluru 19:00
bus-KB-02 flixbus Kochi Bengaluru 19:35
bus-KB-03 kpn Kochi Bengaluru 20:10
bus-KB-04 freshbus Kochi Bengaluru 20:45
```

Scenario 4, name "Operator heavy", description "KPN dominates the Bengaluru to Kochi fleet with eight of ten buses. Tuning the operator weight up versus down should produce visibly different schedules." Weights individual 1.0, operator 2.0, overall 1.0.

```
bus-BK-01 kpn Bengaluru Kochi 19:00
bus-BK-02 kpn Bengaluru Kochi 19:15
bus-BK-03 kpn Bengaluru Kochi 19:30
bus-BK-04 kpn Bengaluru Kochi 19:45
bus-BK-05 kpn Bengaluru Kochi 20:00
bus-BK-06 kpn Bengaluru Kochi 20:15
bus-BK-07 kpn Bengaluru Kochi 20:30
bus-BK-08 kpn Bengaluru Kochi 20:45
bus-BK-09 freshbus Bengaluru Kochi 21:00
bus-BK-10 flixbus Bengaluru Kochi 21:15
bus-KB-01 freshbus Kochi Bengaluru 19:00
bus-KB-02 flixbus Kochi Bengaluru 19:15
bus-KB-03 kpn Kochi Bengaluru 19:30
bus-KB-04 freshbus Kochi Bengaluru 19:45
bus-KB-05 flixbus Kochi Bengaluru 20:00
bus-KB-06 kpn Kochi Bengaluru 20:15
bus-KB-07 freshbus Kochi Bengaluru 20:30
bus-KB-08 flixbus Kochi Bengaluru 20:45
bus-KB-09 kpn Kochi Bengaluru 21:00
bus-KB-10 freshbus Kochi Bengaluru 21:15
```

Scenario 5, name "Worst case convergence", description "All twenty buses dispatched within a 72 minute window every 8 minutes from both ends. By the time buses reach the inner stations B and C they collide. Maximum contention." Weights default.

```
bus-BK-01 kpn Bengaluru Kochi 19:00
bus-BK-02 freshbus Bengaluru Kochi 19:08
bus-BK-03 flixbus Bengaluru Kochi 19:16
bus-BK-04 kpn Bengaluru Kochi 19:24
bus-BK-05 freshbus Bengaluru Kochi 19:32
bus-BK-06 flixbus Bengaluru Kochi 19:40
bus-BK-07 kpn Bengaluru Kochi 19:48
bus-BK-08 freshbus Bengaluru Kochi 19:56
bus-BK-09 flixbus Bengaluru Kochi 20:04
bus-BK-10 kpn Bengaluru Kochi 20:12
bus-KB-01 freshbus Kochi Bengaluru 19:00
bus-KB-02 flixbus Kochi Bengaluru 19:08
bus-KB-03 kpn Kochi Bengaluru 19:16
bus-KB-04 freshbus Kochi Bengaluru 19:24
bus-KB-05 flixbus Kochi Bengaluru 19:32
bus-KB-06 kpn Kochi Bengaluru 19:40
bus-KB-07 freshbus Kochi Bengaluru 19:48
bus-KB-08 flixbus Kochi Bengaluru 19:56
bus-KB-09 kpn Kochi Bengaluru 20:04
bus-KB-10 freshbus Kochi Bengaluru 20:12
```

## 7. Geometry and feasible charging plans

In `geometry.py` compute, for a given bus, the ordered list of stations it passes in its travel direction and the cumulative distance from the bus origin to each station and to the destination. Traversal from Bengaluru to Kochi visits A, B, C, D in that order. Traversal from Kochi to Bengaluru visits D, C, B, A in that order. Segment distance is symmetric, so reverse traversal sums the same segment distances in reverse order. Build this from the route data, never hardcode positions.

Travel time in minutes is distance_km divided by speed_kmph times 60. With speed 60 this equals distance in minutes.

Range feasibility is purely geometric. Waiting and time do not drain the battery, and a charge always refills to full, so plan feasibility depends only on distances and is independent of timing. A charging plan is a subset of the on route stations, in traversal order, where the gap from origin to the first charge, every gap between consecutive charges, and the gap from the last charge to the destination are all at most `range_km`.

Enumerate feasible plans with a reachability walk rather than a hardcoded count. From the origin you may reach any station within `range_km`. From any station you may reach any later station within `range_km`, or the destination if it is within `range_km`. Do a depth first or breadth first walk over these reachable hops to collect every plan that reaches the destination. This yields the minimum number of charges as an emergent property of the data. For the given route and 240 km range the two charge plans are A then C, B then C, and B then D for Bengaluru to Kochi, and the mirror images for the reverse direction, plus the various three and four charge plans. Do not encode these by hand. If a segment between two adjacent stations ever exceeds the range, no plan exists for that bus, so surface a clear violation rather than crashing.

Default plan selection for a bus: choose the feasible plan with the fewest charges. Break ties by preferring the plan whose chosen stations currently have the lowest assigned load so far, which spreads buses across stations. Break remaining ties by bus id for determinism. Keep plan selection as a small function so it can later become weight aware or pluggable.

## 8. The scheduling engine

In `engine.py` implement a discrete event simulation.

Each station is a resource with `chargers` parallel servers. Track per station the busy intervals or simply the next free time per server. The same station resource is shared by buses from both directions, so direction never creates a separate resource.

Workflow.

```
def schedule(scenario, weights=None):
    world = scenario.world
    weights = weights or world.weights
    for bus in scenario.buses:
        bus.plan = choose_plan(bus, world, load_so_far)   # ordered list of station ids
    # event queue holds charge requests, ordered by (time, station_index_in_plan, bus_id)
    push first charge request for every bus:
        time = bus.departure_min + travel_time(origin -> first plan station)
    state tracks per station free servers, per station wait queue, per operator accumulated wait,
          and per bus the timeline being built
    while queue not empty:
        pop the earliest event
        on a charge request at station S for bus at plan index i:
            record arrival time
            if a server at S is free at this time:
                assign immediately, charge_start = arrival, charge_end = arrival + charge_minutes
                advance bus: schedule arrival at next plan station, or mark destination arrival
            else:
                put the bus in the wait queue for S with its arrival time
        whenever a server at S becomes free:
            among buses waiting at S whose arrival time is at or before the server free time,
            pick the next bus by the ConflictResolver weighted priority, break ties by bus id
            assign it, charge_start = max(server_free_time, bus arrival), charge_end = start + charge_minutes
            wait = charge_start - arrival
            update operator accumulated wait
            advance that bus
```

Handle simultaneous events at the same timestamp deterministically by ordering the event key by time, then station index, then bus id, and by resolving any wait queue using the ConflictResolver so the order is explainable rather than arbitrary.

When a bus reaches its destination, its `arrival_min` is the time it leaves its last charge plus the travel time from that station to the destination. For a hypothetical bus with no charges this would be departure plus full travel time, though on this route every endpoint to endpoint bus needs at least two charges.

After building the full schedule, run every hard rule against it and collect violations into the result. A correct run has an empty violations list. Compute the objective breakdown via `objective.py`. The schedule must be deterministic: the same scenario and weights always produce the same result.

## 9. Rules system

In `rules/base.py` define the registry and base classes.

```python
HARD_RULES = []
SOFT_RULES = []

def register_hard(cls):
    HARD_RULES.append(cls())
    return cls

def register_soft(cls):
    SOFT_RULES.append(cls())
    return cls

class HardRule:
    name = "hard_rule"
    def validate(self, schedule, world):
        """Return a list of violation strings. Empty means the schedule is valid."""
        raise NotImplementedError

class SoftRule:
    name = "soft_rule"
    category = "overall"   # maps to a weight key in world.weights
    def score(self, schedule, world):
        """Penalty for a complete schedule. Lower is better."""
        raise NotImplementedError
    def priority(self, bus, station_id, now, state, world):
        """Higher means this bus should charge sooner. Used during conflict resolution."""
        return 0.0
```

In `rules/__init__.py` import `hard` and `soft` so the decorators run and populate the registries.

Hard rules in `rules/hard.py`, each a class decorated with `@register_hard`.

`RangeConstraint` checks that for every bus the distance from origin to first charge, between consecutive charges, and from last charge to destination never exceeds `range_km`.

`ChargerCapacity` checks that at every station the number of buses whose charge intervals overlap never exceeds that station's charger count.

`RouteOrder` checks that each bus's charge stops appear in its traversal order with no backtracking.

`ChargeDuration` checks that every charge lasts exactly `charge_minutes`.

Soft rules in `rules/soft.py`, each decorated with `@register_soft`, each carrying a `category` that matches a weight key.

`IndividualWait`, category `individual`. `score` returns the sum of per bus total wait, optionally squared to penalize long single waits more strongly, which captures no single bus waits too long. `priority` returns how long the bus has already been waiting at this station, so a bus that has waited longer is favored.

`OperatorFairness`, category `operator`. `score` returns the spread of total delay across operators, for example max minus min of per operator total wait, so balanced fleets score better. `priority` returns the calling operator's accumulated wait so far, so whichever operator is most behind is favored, which keeps that fleet moving as a group. With the operator weight raised, as in Scenario 4, this term dominates and the station order shifts visibly compared to the default weight.

`OverallMakespan`, category `overall`. `score` returns the network makespan, the latest destination arrival minus the earliest departure, or the sum of arrivals. `priority` returns the bus's remaining distance to its destination, so a bus with more trip left is favored to reduce overall completion time.

These penalty and priority definitions are the obvious place to refine later and they are isolated here. Keep them simple and readable.

How adding a rule works, and you must make this genuinely true so it can be demonstrated live. A new hard rule is a new class in `hard.py` with `@register_hard`. A new soft rule is a new class in `soft.py` with `@register_soft`, a `category`, a `score`, and optionally a `priority`. If the category is new, add that key to the `weights` block in the scenario files. The engine picks it up with no change. Example to include in the docs.

```python
@register_soft
class ElectricityCost(SoftRule):
    name = "electricity_cost"
    category = "electricity_cost"   # add "electricity_cost" to weights in each scenario
    def score(self, schedule, world):
        return total_cost_of_all_charges(schedule, world)
    def priority(self, bus, station_id, now, state, world):
        return cheaper_window_bonus(now, world)
```

## 10. Weights and objective

In `objective.py` compute the objective generically.

```python
def evaluate(schedule, world):
    breakdown = {}
    total = 0.0
    for rule in SOFT_RULES:
        w = world.weights.get(rule.category, 0.0)
        weighted = w * rule.score(schedule, world)
        breakdown[rule.category] = breakdown.get(rule.category, 0.0) + weighted
        total += weighted
    breakdown["total"] = total
    return breakdown
```

The `ConflictResolver` in `conflict.py` ranks waiting buses by a weighted sum of soft rule priorities.

```python
def pick_next(candidates, station_id, now, state, world):
    def rank(bus):
        s = 0.0
        for rule in SOFT_RULES:
            w = world.weights.get(rule.category, 0.0)
            s += w * rule.priority(bus, station_id, now, state, world)
        return s
    return max(candidates, key=lambda b: (rank(b), -negative_tiebreak(b.id)))
```

Use a deterministic tie break by bus id. Changing a weight is editing one number in a scenario file. There is no other place weights live in code. Make this literally true.

## 11. Streamlit UI

`app.py` contains UI only and calls into `scheduler`. Match the four required views exactly and add nothing heavy. No metrics dashboards, no maps, no animations.

Set a wide layout and a page title. At the top, a `st.selectbox` listing the five scenarios by their `name`, mapping back to the scenario file. The dropdown must be visible immediately on landing. Cache the load and schedule with `st.cache_data` keyed by scenario id and the active weights, since results are deterministic.

Scenario input view. Show the scenario description, a readable summary of the world (the segments and distances, the stations with charger counts, the vehicle parameters, and the active weights), and a table of the buses with columns bus id, operator, direction, departure. Direction is a readable label such as Bengaluru to Kochi derived from origin and destination. Use a pandas dataframe through `st.dataframe`.

Per bus timetable. Show a summary table with one row per bus: bus id, operator, direction, departure, the stations it charges at in order, total wait, and final arrival. Below it, for each bus, an expander revealing its full timeline with one row per charge stop showing station, arrival, wait, charge start, charge end, and the time it leaves that station. This satisfies showing, for each bus, charging stations used, time at each, wait if any, and final arrival.

Per station view. For each of A, B, C, D, show the order in which buses charged there as a table sorted by charge start, with columns order, bus id, operator, direction, arrival, wait, charge start, charge end. Use one section or one tab per station.

Time formatting. Times are absolute minutes from midnight and can exceed 24:00 because long trips cross midnight. Use `viewmodel.format_time` to render HH:MM and append a plus one day marker at or beyond 1440 minutes. All on screen tables come from the `viewmodel` functions so the UI stays thin and testable.

Optional weight panel, controlled by a flag. At the very top of `app.py` define a single boolean `SHOW_WEIGHT_PANEL = True`. When it is `True`, render a sidebar panel with three numeric inputs for individual, operator, and overall, each initialized to the active scenario's weights, plus a reset to scenario defaults. When a value changes, rerun the schedule so reviewers can watch different weights produce different schedules. When the flag is `False`, render no panel at all.

This flag only controls visibility and must be outcome neutral. The scheduler always defaults to the scenario's own weights. When the panel is hidden, call the scheduler without passing any weights so it uses the scenario weights. When the panel is shown, initialize the inputs to the scenario weights so an untouched panel calls the scheduler with those same values and produces the identical schedule. Do not put a hardcoded default weight behind the flag. The only thing that ever changes the result is a person actively editing an input. Removing the feature later is deleting the sidebar block and leaving the schedule call on scenario weights, with no change to the engine, rules, loader, or scenario files.

If any hard rule violation is ever present in a result, surface a short warning so correctness problems are visible rather than hidden. In normal operation there should be none.

## 12. Tests, one stage at a time

Use pytest. Build the tests alongside each stage, not all at the end, and run the relevant file as soon as that stage is written. Every schedule must be deterministic for a given scenario and weights, so determinism is asserted in several places. Keep tests fast and pure. Construct failure cases on a tiny synthetic world rather than the real scenarios, since the real scenarios are designed to be valid.

`tests/conftest.py`. Provide shared fixtures. A `tiny_world` fixture builds a small route with a handful of nodes and short segments plus one or two stations with a known charger count, used to construct controlled passing and failing cases. A `tiny_world_unreachable` fixture has one segment between adjacent stations longer than the range, so range failure and the no feasible plan path can be exercised. A `real_scenarios` fixture loads the five scenario files from `scenarios/`. A helper that builds a minimal valid `ScheduleResult` by hand, and helpers that deliberately corrupt one for the hard rule failure tests.

Stage 1, `tests/test_loader.py`. Assert that `HH:MM` parses to the correct integer minutes, including a time like 21:15. Assert that loading each of the five files yields a `Scenario` with the right `scenario_id`, the expected number of buses, weights that match the file including Scenario 4 at operator 2.0, stations with charger counts, and buses whose origin and destination are valid route nodes. Assert that an unknown operator string still loads, proving operators are not a fixed enum. Assert that the loader is the only place format specific parsing happens.

Stage 2, `tests/test_geometry.py`. Assert cumulative distances from the origin to each station and to the destination are correct in both directions, that a Bengaluru to Kochi bus passes A, B, C, D in order and a Kochi to Bengaluru bus passes D, C, B, A in order. Assert travel time equals distance at 60 km/h and scales correctly at a different speed. Assert the feasible plan enumeration on the real route with a 240 km range returns exactly the expected two charge plans for each direction, that every enumerated plan has all gaps at or below 240, and that the minimum charge count for an endpoint to endpoint bus is two. Assert that on `tiny_world_unreachable` a plan that charges at every station is still feasible when each segment is within range, and that when an adjacent segment exceeds the range the enumeration returns no plan so the caller can surface a violation. Assert default plan selection is deterministic and prefers the fewest charges, then lower loaded stations, then bus id.

Stage 3a, `tests/test_hard_rules.py`. Test each hard rule in isolation, both a passing case and a failing case. `RangeConstraint` passes on a valid plan and reports a violation when a gap exceeds the range. `ChargerCapacity` passes when overlapping charges stay within the charger count and reports a violation when two buses overlap on a single charger station, and passes when capacity is two and exactly two overlap. `RouteOrder` passes on in order stops and reports a violation on a backtracking sequence. `ChargeDuration` passes at exactly the configured minutes and reports a violation when a charge is shorter or longer. Assert each rule returns a list of strings and an empty list means valid.

Stage 3b, `tests/test_soft_rules.py`. For each soft rule assert the score moves in the expected direction, lower is better. `IndividualWait` scores zero when no bus waits and increases as waits grow. `OperatorFairness` scores lower when operator delays are balanced and higher when one operator carries all the delay. `OverallMakespan` scores lower for an earlier last arrival. For the priority functions assert the expected ordering signal, that a longer waiting bus ranks higher for individual, that the more delayed operator ranks higher for operator, and that a bus with more remaining distance ranks higher for overall. Assert each soft rule exposes a category that exists as a weight key.

Stage 4, `tests/test_conflict.py`. Assert that with only the individual weight active the resolver picks the longest waiting bus, with only the operator weight active it picks a bus from the most delayed operator, and with only the overall weight active it picks the bus with the most remaining trip. Assert that ties resolve deterministically by bus id and that calling the resolver twice on the same state returns the same choice.

Stage 5, `tests/test_engine.py`. On real scenarios assert the core invariants. No charger ever serves more buses at once than its capacity, so no two charge intervals overlap on a single charger station. Every charge lasts exactly the configured minutes. Every bus charges in route order with no backtracking. No bus ever exceeds its range between charges. Each bus charges enough times to reach its destination. Assert determinism by scheduling the same scenario twice and comparing the full result. On `tiny_world` assert that a station with capacity two lets two buses charge concurrently while capacity one serializes them, and that a station is shared across both travel directions so opposite direction buses contend for the same charger. Assert that the result carries an empty violations list for a normal run.

Stage 6, `tests/test_objective.py`. Assert the weighted aggregation sums weight times score across the registered soft rules and reports a per category breakdown plus a total. Assert that setting a category weight to zero removes its contribution. Register a temporary dummy soft rule with a new category, add that key to a copy of the weights, and assert the breakdown includes it with no change to the objective code, then deregister it so other tests are unaffected.

Stage 7, `tests/test_extensibility.py`. This test doubles as proof for the live interview. Define a throwaway soft rule and a throwaway hard rule inside the test, register them with the decorators, and assert they appear in the registries and are exercised by the engine and objective with no change to engine, conflict, or objective code. Assert that a new soft category flows through purely by adding a weight key. Clean up the registries at the end of the test so global state does not leak into other tests, for example with a fixture that snapshots and restores the registry lists.

Stage 8, `tests/test_viewmodel.py`. Assert `format_time` renders minutes as HH:MM, that 0 is 00:00, that a value past midnight such as 1730 renders as 04:50 with the plus one day marker, and that exactly 1440 is 00:00 plus one day. Assert `direction_label` produces the readable label from origin and destination. Assert the table builders return rows with the expected columns for the input view, the per bus summary, the per bus stops, and the per station order, and that the per station order is sorted by charge start. These run without importing Streamlit.

Stage 9, `tests/test_scenarios.py`. Assert all five files load, that the counts are twenty for Scenarios 1, 2, 4, and 5 and fourteen for Scenario 3, and that each produces a schedule with an empty violations list under its own weights. Assert weight sensitivity directly, running Scenario 4 with the operator weight at 1.0 and again at 2.0 and asserting the resulting per station order differs somewhere, which proves weights change the schedule. Add a second sensitivity check on a high contention scenario such as Scenario 5, raising the individual weight and asserting the maximum single bus wait does not increase, so the individual term demonstrably does its job.

Running the suite is `pytest` from the repo root. The suite must be green before deploying.

## 13. README.md

Write a `README.md` covering what the project is in two or three sentences, how to run it locally (clone `https://github.com/natapillai/bus-charging-scheduler`, create a virtual environment, install `requirements.txt`, run `streamlit run app.py`, and run `pytest` for the tests), how to deploy on Streamlit Community Cloud by connecting the public repo and selecting `app.py` as the entry point, how to change a weight with a concrete example pointing at the `weights` block in a scenario file and the optional sidebar panel, and how to add a new rule with the soft rule code example from this spec. Keep the writing concise and plain, in flowing prose, without filler.

## 14. ARCHITECTURE.md

This document is graded directly, especially the anticipated changes list. Cover the following.

The framework and approach you chose, the greedy event driven scheduler with a pluggable rule registry and a weighted objective, and why it fits: it scales close to linearly so the world can grow without a rewrite, it separates the engine from the rules so adding a rule is a small registered class, and weights are a single dictionary so tuning is trivial. State the trade off honestly, that it produces sensible and defensible schedules rather than provably optimal ones, and note that a MILP or CP SAT solver was the considered alternative, rejected because it scales worse with world size, is heavier to host and reason about, and makes the live add a rule and grow the world tests harder.

The data structure design, explaining each field and why direction is modeled as origin and destination nodes, why chargers is a capacity number, why operators are read off the buses rather than fixed, why the route is nodes plus segments, and why weights is an open dictionary.

The anticipated future changes list, which is the strongest signal. For each, name the change and show that the design absorbs it through data or a single new rule, with no engine rewrite. Include at least these. More buses, operators, stations, or a longer route, all data only because nothing is capped in code. More than one charger at a station, handled by the chargers capacity that the engine already treats as parallel servers. A brand new operator, handled because operators come from the bus list and the operator rule works over any set. Changed segment distances or a changed range, data only because feasible plans are recomputed from geometry. A new soft rule such as time of day electricity cost, a new SoftRule class plus one new weight key. A new hard rule such as a station maintenance window when a charger is unavailable, or a cap on buses per operator at a station, a new HardRule validator. Priority buses, either a per bus priority field consumed by a new rule or a weight, so data plus one rule. Driver shifts or a maximum driving time, a per bus or per route attribute plus a rule. Multiple routes sharing stations, the route becomes a list and buses reference a route id while stations stay keyed by node, and the engine already keys resources by station id. Heterogeneous vehicles with different range or charge time, a per bus or per fleet vehicle override since the vehicle is already a structured field. Variable or partial charging or a charge curve, since charge minutes is data and the charging step is isolated. A different objective sense such as minimizing the maximum wait instead of the sum, since the objective aggregation is configurable. Make the list broad and specific.

How you would change a weight, with the code or data example. How you would add a new rule, with the code example. The assumptions you made, listed plainly.

## 15. Assumptions to record

Speed is 60 km/h so one kilometer takes one minute, and speed lives in the data. Range feasibility is purely geometric since waiting does not drain the battery and charging always refills to full, so plan feasibility is independent of timing. Charging is always exactly the configured minutes to full with no partial charges, so a bus either charges fully at a station in its plan or skips it. The minimum number of charges emerges from range and geometry rather than a constant, and for this route an endpoint to endpoint bus needs at least two. Endpoints fully charge before departure and are not scheduling resources. Chargers are modeled as a station capacity defaulting to one. Operators are arbitrary labels read off the buses. Time is absolute minutes from midnight and may exceed 24:00 because long trips cross midnight. Conflict resolution is greedy and priority based using the weighted categories with a deterministic tie break by bus id. Default plan selection prefers the fewest charges, then the least loaded stations, then bus id. The soft penalties are sum of waits for individual, spread of operator delay for operator, and makespan for overall, all easily swapped. All buses run endpoint to endpoint, though the model supports intermediate origins and destinations. There is a single shared route and stations are shared across both directions.

## 16. requirements.txt

```
streamlit
pandas
```

Target a recent Python such as 3.11. Pin versions only if needed for the deploy.

## 17. Build order

This directory is already a clone of the remote, so do not run git init or git remote add. Add a `.gitignore` for the virtual environment, `__pycache__`, and `.pytest_cache`, or add those entries if one already exists. Build each stage, then write and run that stage's test file before moving on. Keep the registry clean between extensibility tests. Commit once per stage, after that stage's code is written and its tests pass, and tick the matching item in `PROGRESS.md` in the same commit so the history maps one to one with the milestones. Do not commit broken code. The only commits without passing tests are the initial scaffold and the docs. Never add any Claude Code or AI attribution to a commit, no Co-authored-by Claude trailer and no Generated with Claude Code line. Each commit is a short imperative subject line, capitalized, with no trailing period and no colons or dashes, then a blank line, then a short body of two or three plain sentences saying what changed, how it is tested, and why. Commit locally as you go and push to the remote at the final stage.

1. Add the `.gitignore`, then scaffold the package directories, `requirements.txt`, and `tests/conftest.py` with the fixtures. The repo `bus-charging-scheduler` already exists as a clone.
2. Implement the domain dataclasses and the output models in `domain.py`.
3. Implement the JSON loader in `loader.py`, parsing `HH:MM` to minutes. Run `test_loader.py`.
4. Write the five scenario JSON files from the data in section 6 and verify the bus counts.
5. Implement geometry and feasible plan enumeration in `geometry.py`. Run `test_geometry.py`.
6. Implement the rule base and registry in `rules/base.py`, the hard rules, and the soft rules, and wire the auto import in `rules/__init__.py`. Run `test_hard_rules.py` and `test_soft_rules.py`.
7. Implement the ConflictResolver in `conflict.py`. Run `test_conflict.py`.
8. Implement the engine in `engine.py`, producing a ScheduleResult and validating it with the hard rules. Run `test_engine.py`.
9. Implement the objective aggregation in `objective.py`. Run `test_objective.py` and `test_extensibility.py`.
10. Implement `viewmodel.py` helpers. Run `test_viewmodel.py`.
11. Implement the Streamlit app in `app.py` with the four views and the flag controlled weight panel, calling the viewmodel helpers.
12. Run the full suite with `pytest`, including `test_scenarios.py`, until green.
13. Write `README.md` and `ARCHITECTURE.md`.
14. Run `streamlit run app.py` locally and click through all five scenarios.
15. Confirm the repo is ready and push to `https://github.com/natapillai/bus-charging-scheduler` with `app.py` and `requirements.txt` at the root.

Suggested subject lines, one per stage, in order, each followed by its own what, how tested, and why body: `Scaffold project and tooling`, `Add domain models`, `Add scenario loader`, `Add five scenario data files`, `Add route geometry and feasible plan enumeration`, `Add rule registry, hard rules, and soft rules`, `Add weighted conflict resolver`, `Implement event driven engine and validate with hard rules`, `Add weighted objective aggregation`, `Add view model helpers`, `Add Streamlit app with the four views and weight panel`, `Get full test suite green`, `Add README and ARCHITECTURE docs`, `Verify all five scenarios end to end`, `Prepare for public push`.

## 18. Definition of done

The app opens on the scenario dropdown immediately. Picking any scenario shows the input data, a per bus timetable where every bus charges enough times to complete its trip with reasonable waits, and a per station order that makes sense for the active weights. All five scenarios produce valid, defensible schedules with no hard rule violations. Changing a weight is one value in one place and visibly changes the schedule. The weight panel flag is outcome neutral, so the schedule with the panel hidden matches the schedule with an untouched panel. Adding a rule is a single registered class with no engine change, proven by the extensibility test. The full per stage test suite is green under `pytest`. `README.md` and `ARCHITECTURE.md` are complete and honest about what is done, what is not, and what is next.
