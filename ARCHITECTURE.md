# Architecture

## Approach and why it fits

The scheduler is a greedy, event driven simulation with a pluggable rule registry and a tunable weighted objective. It separates mechanism from policy. The engine is the mechanism and knows only generic concepts, a route of nodes with distances, stations as resources with a charger capacity, a clock, a set of rules, and a weight vector. It advances time, moves buses between stations, and when buses contend for a charger it resolves the conflict with a weighted priority built from the registered rules. The rules are the policy and live outside the engine. Hard rules are validators that return violation strings. Soft rules are scorers, each tagged with a category that maps to a weight key, and each also exposing a priority used during conflict resolution. The objective is the weighted sum over whatever soft rules are registered.

This fits the problem because the assignment stresses that the world will grow and that the framework must absorb new rules and a bigger world without a rewrite. A greedy event driven scheduler is close to linear in the number of buses times stations, so it scales to a large world without the blowup a solver would suffer. Adding a rule is writing one small class and registering it, with no engine change. Tuning behaviour is editing one number in a scenario file, because the weights are a single open dictionary. The separation between the engine and the rules is the property the assignment grades, and here it is enforced by the engine never naming a rule and instead walking the two registries.

The honest trade off is that this produces sensible and defensible schedules rather than provably optimal ones. The greedy choices, the plan with the fewest charges and the weighted priority for the queue, are good and explainable but not guaranteed to minimise any global objective. The considered alternative was a mathematical program such as MILP or CP SAT. That was rejected because it scales worse as the world grows, it is heavier to host and to reason about, and it makes the two things the assignment wants to test live, adding a rule and growing the world, much harder, since a new rule there means new constraints and a new model rather than one small registered class.

## Two places the weights act

The weights influence the schedule at two decision points rather than one.

The first is conflict resolution. When several buses wait for the same charger, the resolver ranks them by the weighted sum of the soft rule priorities and breaks ties by bus id. The individual priority favours the bus that has already waited longest, the operator priority favours the operator whose fleet is most behind, and the overall priority favours the bus with the most trip remaining. This is the natural home of the weights and it drives the order at every contended charger.

The second is plan selection. Among the feasible plans with the fewest charges, the chooser spreads load across stations, and the spread is weight aware. The overall weight scales a term that pushes a bus away from stations that are already busy across the whole network, and the operator weight scales a term that pushes a bus away from stations its own operator is already stacking on. This is what lets the weights change a schedule even when buses never queue at the same instant, and it is why the chooser takes the world and reads its weights rather than being a fixed greedy rule.

This second point matters for the operator heavy scenario. That scenario uses an even fifteen minute spacing, which means no two buses ever wait for the same charger at the same moment, so the resolver is never asked to choose there. It also has one operator owning most of the fleet, so operator fairness has very little to balance, because that operator is essentially the whole network. The lesson, which is worth stating plainly, is that operator fairness has the most to do when operators are evenly matched and genuinely contend, as in the bunched and worst case scenarios, and the least to do when one operator dominates. The worst case scenario is where the operator weight visibly reorders the chargers, and the operator heavy scenario still responds to the operator weight through plan selection when fairness is toggled between off and on.

## Data model

A scenario file is self contained and fully describes one situation, the world and the buses. The format is JSON and a single loader function turns it into typed objects, so swapping JSON for YAML or TOML later is a change in one function. The models are plain dataclasses with no behaviour.

* `Segment(from_node, to_node, distance_km)` is one stretch of road. Distance is symmetric, so the same segment serves both directions and a reverse trip sums the same segments in reverse order.
* `Route(nodes, segments, endpoints)` is the ordered list of nodes joined by segments. Endpoints are where buses start and finish fully charged and are not scheduling stations. Keeping the route as nodes plus segments means a longer route or different stops is a data change.
* `Station(id, node, chargers)` is a charging resource at a node. Chargers is the capacity, the number of buses that can charge at once, and it defaults to one. Treating it as a number is what lets a station gain a second charger purely through data.
* `Vehicle(range_km, charge_minutes, speed_kmph)` holds the shared vehicle parameters. Speed lives here so travel time is tunable, and range and charge minutes live here so a different battery or charging time is a data change.
* `World(route, stations, vehicle, weights)` is everything shared across the buses, with weights a plain dictionary keyed by category so a new category is a new key rather than a schema change.
* `Bus(id, operator, origin, destination, departure_min)` is one bus run. Direction is modelled as an origin node and a destination node rather than a fixed enum, so the reverse direction is just traversing the node order backwards and a future intermediate origin or destination needs no new field. Operator is an arbitrary string read off the bus, not a member of a fixed set. Departure is integer minutes from midnight, parsed once by the loader.
* `Scenario(scenario_id, name, description, world, buses)` ties it together.

The outputs mirror this. `ChargeStop` records one charging event with its arrival, charge start, charge end, and wait. `BusSchedule` holds a bus, its stops, and the arrival at its destination. `StationOrderEntry` is one row in the order buses used a station. `ScheduleResult` carries the bus schedules, the per station orders sorted by charge start, the violations, which is empty for a valid schedule, and the objective breakdown per category plus a total.

## Changes the design anticipates

For each likely change the design absorbs it through data or one new registered rule, with no engine rewrite.

* More buses, operators, stations, or a longer route. Data only. Buses are a list, operators are strings read off the buses, stations are a list each with a capacity, and the route is nodes plus segments. Nothing is capped in code.
* More than one charger at a station. The chargers field is a capacity the engine already treats as parallel servers, so set it to two in that station's data.
* A brand new operator. Operators come from the bus list, so a new label flows in with no code change, and the operator rule works over whatever set of operators appears.
* Changed segment distances or a changed range. Data only. Feasible plans are recomputed from geometry, so the set of feasible plans and the minimum number of charges follow the data rather than a constant.
* A new soft rule such as a time of day electricity cost. One SoftRule class with a category, a score, and an optional priority, plus one weight key in the scenario files.
* A new hard rule such as a station maintenance window when a charger is unavailable, or a cap on buses per operator at a station. One HardRule validator that returns violation strings.
* Priority buses. A per bus priority field consumed by a new rule, or expressed as a weight, so data plus one rule.
* Driver shifts or a maximum driving time. A per bus or per route attribute plus a rule that reads it.
* Multiple routes sharing stations. The route becomes a list and buses reference a route id, while stations stay keyed by node and the engine already keys its resources by station id, so a station shared by two routes is the same resource.
* Heterogeneous vehicles with different range or charge time. A per bus or per fleet vehicle override, since the vehicle is already a structured field rather than a set of constants.
* Variable or partial charging or a charge curve. Charge minutes is data and the charging step is isolated in the engine, so a richer charging model replaces that one step.
* A different objective sense such as minimising the maximum wait instead of the sum. The objective aggregation is configurable and the soft scores are isolated, so the shape of a penalty changes in its rule.

## How to change a weight

Edit one value in the `weights` block of a scenario file. To double operator fairness in a scenario, set its operator weight to 2.0.

```json
"weights": {
  "individual": 1.0,
  "operator": 2.0,
  "overall": 1.0
}
```

There is no other place a weight lives. The objective and the conflict resolver both read `world.weights`, the loader reads the same block, and the optional sidebar panel starts from these values, so the schedule with the panel hidden equals the schedule with an untouched panel.

## How to add a rule

A new soft rule is one class.

```python
from scheduler.rules.base import SoftRule, register_soft

@register_soft
class ElectricityCost(SoftRule):
    name = "electricity_cost"
    category = "electricity_cost"   # add "electricity_cost" to weights in each scenario

    def score(self, schedule, world):
        return total_cost_of_all_charges(schedule, world)

    def priority(self, bus, station_id, now, state, world):
        return cheaper_window_bonus(now, world)
```

Registering it adds it to the registry. The objective then includes its category, weighted by the new key, and the resolver folds its priority into the queue order, all with no change to the engine. A new hard rule is the same pattern with `register_hard` and a `validate` method. The extensibility test registers a throwaway soft rule and a throwaway hard rule inside the test and shows they flow through the engine, the resolver, and the objective with no edit to those files.

## What is done, what is not, and what is next

What is done. All five scenarios load and produce valid schedules with no hard rule violations. Every bus charges the minimum number of times its range requires and reaches its destination. Weights are tunable from one place and visibly change the schedule where there is freedom to choose. Adding a rule is a single registered class, proven by the extensibility test. The schedule is deterministic for a given scenario and weights, and the weight panel flag only controls visibility.

What is not done. The schedules are sensible and defensible, not provably optimal. Plan selection is greedy with a weight aware tie break rather than a search over the joint assignment. The soft penalties, the squared sum of waits for the individual term, the spread of operator delay for the operator term, and the network makespan for the overall term, are deliberately simple. The shipped scenarios use one route and one vehicle type, although the model already carries the shape for several routes and per fleet vehicles.

What is next. The obvious refinements are weight aware plan selection that estimates contention rather than spreading by load, richer soft penalty shapes, and the new rules the field will ask for, time of day cost, priority buses, driver shifts, each of which is a registered class. None of these need an engine rewrite, which is the point of the design.

## Assumptions

* Speed is 60 km per hour so one kilometre takes one minute, and speed lives in the data so it is tunable.
* Range feasibility is purely geometric, since waiting does not drain the battery and charging always refills to full, so a plan's feasibility depends only on distances and not on timing.
* Charging is always exactly the configured minutes to full, with no partial charges, so a bus either charges fully at a station in its plan or skips it.
* The minimum number of charges emerges from range and geometry rather than a constant, and for this route an endpoint to endpoint bus needs at least two.
* Endpoints fully charge before departure and are not scheduling resources.
* Chargers are modelled as a station capacity defaulting to one.
* Operators are arbitrary labels read off the buses.
* Time is absolute minutes from midnight and may exceed 1440 because long trips cross midnight.
* Conflict resolution is greedy and priority based using the weighted categories, with a deterministic tie break by bus id.
* Default plan selection prefers the fewest charges, then spreads load across stations weighted by the overall and operator categories, then breaks ties by the station identifiers.
* The soft penalties are the sum of waits for the individual term, the spread of operator delay for the operator term, and the makespan for the overall term, all easily swapped.
* All buses run endpoint to endpoint, although the model supports intermediate origins and destinations.
* There is a single shared route and stations are shared across both directions.
* The chosen plan for each bus is kept in engine local state rather than written back onto the bus, so the input objects stay free of scheduler output.
