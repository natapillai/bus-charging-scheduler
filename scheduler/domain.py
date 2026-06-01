"""Domain models for the scheduler.

The input models describe a world and the buses that run through it. The output
models describe what the scheduler decided. Everything here is plain data with
no behaviour, so the engine and the rules can read it without depending on how
it was built. The design deliberately avoids baking in the current small world.
Charger count is a capacity per station, operators are arbitrary strings carried
on each bus, the route is nodes plus segments, and the weights are an open
dictionary keyed by category.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# Input models.


@dataclass
class Segment:
    """One stretch of road between two adjacent nodes.

    Distance is symmetric, so the same segment serves travel in both directions
    and the reverse traversal simply sums the segments in reverse order.
    """

    from_node: str
    to_node: str
    distance_km: float


@dataclass
class Route:
    """An ordered list of nodes joined by segments.

    Endpoints are the nodes where buses start and finish fully charged. They are
    not scheduling stations. Keeping the route as data means a longer route or a
    different set of stops is a data change rather than a code change.
    """

    nodes: list[str]
    segments: list[Segment]
    endpoints: list[str]


@dataclass
class Station:
    """A charging resource at a node.

    Chargers is the capacity, the number of buses that can charge at once, and it
    defaults to one. Treating it as a number is what lets a station gain a second
    charger purely through data.
    """

    id: str
    node: str
    chargers: int = 1


@dataclass
class Vehicle:
    """The shared vehicle parameters.

    Speed lives here so travel time is tunable. Range and charge minutes live
    here so a different battery or a different charging time is a data change.
    """

    range_km: float
    charge_minutes: int
    speed_kmph: float


@dataclass
class World:
    """Everything shared across the buses in a scenario.

    Weights is a plain dictionary keyed by soft rule category, so a new category
    is a new key rather than a schema change.
    """

    route: Route
    stations: list[Station]
    vehicle: Vehicle
    weights: dict[str, float]


@dataclass
class Bus:
    """A single bus run from an origin node to a destination node.

    Direction is modelled as origin and destination rather than a fixed enum, so
    the reverse direction is just traversing the node order backwards and a future
    intermediate origin or destination needs no new field. Departure is stored as
    integer minutes from midnight, parsed once by the loader.
    """

    id: str
    operator: str
    origin: str
    destination: str
    departure_min: int


@dataclass
class Scenario:
    """A self contained situation the scheduler can read and run."""

    scenario_id: str
    name: str
    description: str
    world: World
    buses: list[Bus]


# Output models.


@dataclass
class ChargeStop:
    """One charging event in a bus timeline.

    Arrival is when the bus reaches the station, the charge start and end bracket
    the charging itself, and wait is the gap the bus spent queued before its
    charger was free.
    """

    station_id: str
    arrival_min: int
    charge_start_min: int
    charge_end_min: int
    wait_min: int


@dataclass
class BusSchedule:
    """The full plan and timeline for one bus.

    Arrival is when the bus reaches its destination, which is the time it leaves
    its last charge plus the travel time from that station to the destination.
    """

    bus: Bus
    stops: list[ChargeStop]
    arrival_min: int


@dataclass
class StationOrderEntry:
    """One row in the order buses used a single station.

    Order is the position in the charging sequence at that station, starting at
    one, and the remaining fields describe the bus and its timing there.
    """

    order: int
    bus_id: str
    operator: str
    direction_label: str
    arrival_min: int
    wait_min: int
    charge_start_min: int
    charge_end_min: int


@dataclass
class ScheduleResult:
    """The complete output of a scheduling run.

    Bus schedules hold the per bus timelines. Station orders maps each station id
    to the list of entries sorted by charge start. Violations is empty when the
    schedule is valid. The objective breakdown maps each category to its weighted
    penalty and carries a total.
    """

    bus_schedules: list[BusSchedule]
    station_orders: dict[str, list[StationOrderEntry]]
    violations: list[str] = field(default_factory=list)
    objective_breakdown: dict[str, float] = field(default_factory=dict)
