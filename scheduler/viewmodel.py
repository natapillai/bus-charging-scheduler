"""Pure helpers the UI calls.

Every function here takes plain domain or result data and returns plain data,
either a formatted string or a pandas dataframe, so the whole UI layer can be
tested without running Streamlit. The Streamlit app only arranges what these
return on the page.
"""

from __future__ import annotations

import pandas as pd


def format_time(minutes) -> str:
    """Render absolute minutes from midnight as HH:MM.

    Long trips cross midnight, so a value at or beyond a full day shows a plus
    day marker. 1440 reads as 00:00 with a plus one day marker.
    """
    minutes = int(minutes)
    days, remainder = divmod(minutes, 1440)
    hours, mins = divmod(remainder, 60)
    text = f"{hours:02d}:{mins:02d}"
    if days == 1:
        text += " (+1 day)"
    elif days >= 2:
        text += f" (+{days} days)"
    return text


def direction_label(origin, destination) -> str:
    """A readable direction such as Bengaluru to Kochi."""
    return f"{origin} to {destination}"


def build_input_table(scenario) -> pd.DataFrame:
    """One row per bus describing the scheduler input."""
    rows = [
        {
            "Bus": bus.id,
            "Operator": bus.operator,
            "Direction": direction_label(bus.origin, bus.destination),
            "Departure": format_time(bus.departure_min),
        }
        for bus in scenario.buses
    ]
    return pd.DataFrame(rows, columns=["Bus", "Operator", "Direction", "Departure"])


def build_bus_summary_table(result) -> pd.DataFrame:
    """One row per bus with the stations used, the total wait, and the arrival."""
    rows = []
    for bus_schedule in result.bus_schedules:
        bus = bus_schedule.bus
        rows.append(
            {
                "Bus": bus.id,
                "Operator": bus.operator,
                "Direction": direction_label(bus.origin, bus.destination),
                "Departure": format_time(bus.departure_min),
                "Charges at": ", ".join(stop.station_id for stop in bus_schedule.stops),
                "Total wait (min)": sum(stop.wait_min for stop in bus_schedule.stops),
                "Arrival": format_time(bus_schedule.arrival_min),
            }
        )
    return pd.DataFrame(
        rows,
        columns=[
            "Bus",
            "Operator",
            "Direction",
            "Departure",
            "Charges at",
            "Total wait (min)",
            "Arrival",
        ],
    )


def build_bus_stops_table(result, bus_id) -> pd.DataFrame:
    """One row per charge stop for a single bus, in route order."""
    columns = ["Station", "Arrival", "Wait (min)", "Charge start", "Charge end", "Leaves"]
    match = next((bs for bs in result.bus_schedules if bs.bus.id == bus_id), None)
    if match is None:
        return pd.DataFrame(columns=columns)
    rows = [
        {
            "Station": stop.station_id,
            "Arrival": format_time(stop.arrival_min),
            "Wait (min)": stop.wait_min,
            "Charge start": format_time(stop.charge_start_min),
            "Charge end": format_time(stop.charge_end_min),
            "Leaves": format_time(stop.charge_end_min),
        }
        for stop in match.stops
    ]
    return pd.DataFrame(rows, columns=columns)


def build_station_table(result, station_id) -> pd.DataFrame:
    """The order buses charged at one station, sorted by charge start."""
    columns = [
        "Order",
        "Bus",
        "Operator",
        "Direction",
        "Arrival",
        "Wait (min)",
        "Charge start",
        "Charge end",
    ]
    entries = result.station_orders.get(station_id, [])
    rows = [
        {
            "Order": entry.order,
            "Bus": entry.bus_id,
            "Operator": entry.operator,
            "Direction": entry.direction_label,
            "Arrival": format_time(entry.arrival_min),
            "Wait (min)": entry.wait_min,
            "Charge start": format_time(entry.charge_start_min),
            "Charge end": format_time(entry.charge_end_min),
        }
        for entry in entries
    ]
    return pd.DataFrame(rows, columns=columns)
