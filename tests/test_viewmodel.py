"""Stage 8 tests, the UI helpers, with no Streamlit imported."""

from scheduler.engine import schedule
from scheduler.viewmodel import (
    build_bus_stops_table,
    build_bus_summary_table,
    build_input_table,
    build_station_table,
    direction_label,
    format_time,
)


def test_format_time_basic():
    assert format_time(0) == "00:00"
    assert format_time(1140) == "19:00"
    assert format_time(290) == "04:50"


def test_format_time_past_midnight_marks_next_day():
    assert format_time(1730) == "04:50 (+1 day)"
    assert format_time(1440) == "00:00 (+1 day)"


def test_direction_label():
    assert direction_label("Bengaluru", "Kochi") == "Bengaluru to Kochi"
    assert direction_label("Kochi", "Bengaluru") == "Kochi to Bengaluru"


def test_input_table_columns(real_scenarios):
    table = build_input_table(real_scenarios["scenario_1"])
    assert list(table.columns) == ["Bus", "Operator", "Direction", "Departure"]
    assert len(table) == 20


def test_bus_summary_table_columns(real_scenarios):
    result = schedule(real_scenarios["scenario_1"])
    table = build_bus_summary_table(result)
    assert list(table.columns) == [
        "Bus",
        "Operator",
        "Direction",
        "Departure",
        "Charges at",
        "Total wait (min)",
        "Arrival",
    ]
    assert len(table) == 20


def test_bus_stops_table_columns_and_rows(real_scenarios):
    scenario = real_scenarios["scenario_1"]
    result = schedule(scenario)
    bus_id = scenario.buses[0].id
    table = build_bus_stops_table(result, bus_id)
    assert list(table.columns) == [
        "Station",
        "Arrival",
        "Wait (min)",
        "Charge start",
        "Charge end",
        "Leaves",
    ]
    # Each endpoint to endpoint bus charges at least twice on this route.
    assert len(table) >= 2


def test_station_table_columns_and_sorted_by_charge_start(real_scenarios):
    result = schedule(real_scenarios["scenario_1"])
    table = build_station_table(result, "B")
    assert list(table.columns) == [
        "Order",
        "Bus",
        "Operator",
        "Direction",
        "Arrival",
        "Wait (min)",
        "Charge start",
        "Charge end",
    ]
    assert list(table["Order"]) == list(range(1, len(table) + 1))
    starts = [entry.charge_start_min for entry in result.station_orders["B"]]
    assert starts == sorted(starts)
