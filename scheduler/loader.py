"""Scenario loading.

This module is the only place that knows the on disk format. It reads a JSON
scenario file and returns fully typed domain objects, parsing the departure
clock times into integer minutes so nothing downstream has to parse anything.
Keeping the format behind one function means swapping JSON for YAML or TOML
later is a change here and nowhere else.
"""

from __future__ import annotations

import json
from pathlib import Path

from .domain import Bus, Route, Scenario, Segment, Station, Vehicle, World


def parse_time(value: str) -> int:
    """Turn an HH:MM clock string into minutes from midnight.

    A time like 21:15 becomes 1275. The result is plain minutes, so a long trip
    that crosses midnight simply produces arrival times at or beyond 1440.
    """
    hours, minutes = value.split(":")
    return int(hours) * 60 + int(minutes)


def _build_world(data: dict) -> World:
    route_data = data["route"]
    route = Route(
        nodes=list(route_data["nodes"]),
        segments=[
            Segment(
                from_node=segment["from"],
                to_node=segment["to"],
                distance_km=segment["distance_km"],
            )
            for segment in route_data["segments"]
        ],
        endpoints=list(route_data["endpoints"]),
    )
    stations = [
        Station(
            id=station["id"],
            node=station["node"],
            chargers=station.get("chargers", 1),
        )
        for station in data["stations"]
    ]
    vehicle_data = data["vehicle"]
    vehicle = Vehicle(
        range_km=vehicle_data["range_km"],
        charge_minutes=vehicle_data["charge_minutes"],
        speed_kmph=vehicle_data["speed_kmph"],
    )
    weights = {key: float(value) for key, value in data["weights"].items()}
    return World(route=route, stations=stations, vehicle=vehicle, weights=weights)


def _scenario_from_dict(data: dict) -> Scenario:
    world = _build_world(data["world"])
    buses = [
        Bus(
            id=bus["id"],
            operator=bus["operator"],
            origin=bus["origin"],
            destination=bus["destination"],
            departure_min=parse_time(bus["departure"]),
        )
        for bus in data["buses"]
    ]
    return Scenario(
        scenario_id=data["scenario_id"],
        name=data["name"],
        description=data["description"],
        world=world,
        buses=buses,
    )


def load_scenario(path) -> Scenario:
    """Load one scenario file and return a fully typed Scenario."""
    with open(Path(path), encoding="utf-8") as handle:
        data = json.load(handle)
    return _scenario_from_dict(data)
