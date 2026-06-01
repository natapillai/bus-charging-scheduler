"""Stage 1 tests, scenario loading and time parsing.

These exercise the loader against a synthetic scenario written to a temporary
file rather than the five shipped files, so the loader is tested in isolation.
The shipped files are validated end to end in test_scenarios.
"""

import json

import pytest

from scheduler.loader import load_scenario, parse_time


def test_parse_time_minutes():
    assert parse_time("00:00") == 0
    assert parse_time("19:00") == 1140
    assert parse_time("20:45") == 1245
    assert parse_time("21:15") == 1275


def _synthetic_scenario():
    """A small but complete scenario with a deliberately unknown operator.

    One station omits its charger count to prove the default applies, another
    sets two chargers to prove the capacity is read from data, and one bus uses
    an operator string that is not in the usual set to prove operators are not a
    fixed enum.
    """
    return {
        "scenario_id": "syn",
        "name": "Synthetic",
        "description": "A made up world for loader tests.",
        "world": {
            "route": {
                "nodes": ["Start", "M", "N", "End"],
                "segments": [
                    {"from": "Start", "to": "M", "distance_km": 100},
                    {"from": "M", "to": "N", "distance_km": 100},
                    {"from": "N", "to": "End", "distance_km": 100},
                ],
                "endpoints": ["Start", "End"],
            },
            "stations": [
                {"id": "M", "node": "M"},
                {"id": "N", "node": "N", "chargers": 2},
            ],
            "vehicle": {"range_km": 240, "charge_minutes": 25, "speed_kmph": 60},
            "weights": {"individual": 1.0, "operator": 2.0, "overall": 1.0},
        },
        "buses": [
            {"id": "f-1", "operator": "kpn", "origin": "Start", "destination": "End", "departure": "19:00"},
            {"id": "f-2", "operator": "zenbus", "origin": "Start", "destination": "End", "departure": "21:15"},
            {"id": "r-1", "operator": "freshbus", "origin": "End", "destination": "Start", "departure": "20:45"},
        ],
    }


@pytest.fixture
def synthetic_path(tmp_path):
    path = tmp_path / "synthetic.json"
    path.write_text(json.dumps(_synthetic_scenario()), encoding="utf-8")
    return path


def test_load_scenario_basic_fields(synthetic_path):
    scenario = load_scenario(synthetic_path)
    assert scenario.scenario_id == "syn"
    assert scenario.name == "Synthetic"
    assert scenario.description == "A made up world for loader tests."
    assert len(scenario.buses) == 3


def test_load_scenario_weights_are_open_floats(synthetic_path):
    scenario = load_scenario(synthetic_path)
    assert scenario.world.weights == {"individual": 1.0, "operator": 2.0, "overall": 1.0}
    for value in scenario.world.weights.values():
        assert isinstance(value, float)


def test_station_charger_capacity_defaults_and_reads(synthetic_path):
    scenario = load_scenario(synthetic_path)
    by_id = {station.id: station for station in scenario.world.stations}
    assert by_id["M"].chargers == 1
    assert by_id["N"].chargers == 2


def test_buses_reference_valid_route_nodes(synthetic_path):
    scenario = load_scenario(synthetic_path)
    nodes = set(scenario.world.route.nodes)
    for bus in scenario.buses:
        assert bus.origin in nodes
        assert bus.destination in nodes


def test_unknown_operator_loads(synthetic_path):
    scenario = load_scenario(synthetic_path)
    operators = {bus.operator for bus in scenario.buses}
    assert "zenbus" in operators


def test_departure_parsed_to_minutes_at_load(synthetic_path):
    scenario = load_scenario(synthetic_path)
    by_id = {bus.id: bus for bus in scenario.buses}
    assert by_id["f-1"].departure_min == 1140
    assert by_id["f-2"].departure_min == 1275
    assert isinstance(by_id["f-2"].departure_min, int)


def test_parsing_is_complete_at_load(synthetic_path):
    """No downstream parsing is needed because every value arrives typed."""
    scenario = load_scenario(synthetic_path)
    for bus in scenario.buses:
        assert isinstance(bus.departure_min, int)
    for segment in scenario.world.route.segments:
        assert isinstance(segment.distance_km, (int, float))
