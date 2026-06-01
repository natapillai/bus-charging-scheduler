"""Streamlit entry point.

This file is UI only. It loads a scenario, asks the scheduler for a result, and
arranges what the view model returns on the page. All of the formatting lives in
scheduler.viewmodel and all of the deciding lives in scheduler.engine, so this
file holds no scheduling logic.

SHOW_WEIGHT_PANEL controls only whether the sidebar tuning panel appears. It is
outcome neutral. The scheduler always defaults to the scenario's own weights, and
when the panel is shown its inputs start at those same weights, so an untouched
panel produces the identical schedule. The only thing that ever changes a result
is a person editing a weight.
"""

from pathlib import Path

import pandas as pd
import streamlit as st

from scheduler.engine import schedule
from scheduler.loader import load_scenario
from scheduler.viewmodel import (
    build_bus_stops_table,
    build_bus_summary_table,
    build_input_table,
    build_station_table,
    direction_label,
    format_time,
)

SHOW_WEIGHT_PANEL = True

SCENARIO_DIR = Path(__file__).parent / "scenarios"


@st.cache_data
def load_cached(path_str):
    return load_scenario(path_str)


@st.cache_data
def schedule_cached(path_str, weight_items):
    """Schedule deterministically, keyed by the file and the active weights.

    weight_items is None when the scenario weights should be used, or a sorted
    tuple of weight pairs when the panel has supplied an active set.
    """
    scenario = load_scenario(path_str)
    weights = dict(weight_items) if weight_items is not None else None
    return schedule(scenario, weights)


st.set_page_config(page_title="Bus Charging Scheduler", layout="wide")
st.title("Bus Charging Scheduler")
st.caption(
    "Electric buses share four chargers on the route between Bengaluru and Kochi. "
    "Pick a scenario to see the input and what the scheduler decided."
)

paths = sorted(SCENARIO_DIR.glob("scenario_*.json"))
scenarios_by_name = {load_cached(str(path)).name: str(path) for path in paths}
choice = st.selectbox("Scenario", list(scenarios_by_name))
path_str = scenarios_by_name[choice]
scenario = load_cached(path_str)
defaults = scenario.world.weights

# Weight panel. Outcome neutral, so it starts at the scenario weights.
if SHOW_WEIGHT_PANEL:
    st.sidebar.header("Weights")
    st.sidebar.caption(
        "Tune the soft rule weights and watch the schedule change. They start at "
        "the scenario's own weights, so leaving them produces the scenario result."
    )
    if st.session_state.get("active_scenario") != scenario.scenario_id:
        st.session_state["active_scenario"] = scenario.scenario_id
        for category, value in defaults.items():
            st.session_state[f"weight_{category}"] = float(value)
    if st.sidebar.button("Reset to scenario defaults"):
        for category, value in defaults.items():
            st.session_state[f"weight_{category}"] = float(value)
    active_weights = {
        category: st.sidebar.number_input(
            category.capitalize(), key=f"weight_{category}", step=0.5, min_value=0.0
        )
        for category in defaults
    }
    result = schedule_cached(path_str, tuple(sorted(active_weights.items())))
    used_weights = active_weights
else:
    result = schedule_cached(path_str, None)
    used_weights = dict(defaults)

if SHOW_WEIGHT_PANEL:
    st.sidebar.markdown("**Objective**")
    st.sidebar.caption("Weighted penalty, lower is better.")
    st.sidebar.write({key: round(value, 1) for key, value in result.objective_breakdown.items()})

if result.violations:
    st.warning("Hard rule violations: " + "; ".join(result.violations))

# Scenario input.
st.header("Scenario input")
st.write(scenario.description)
left, right = st.columns(2)
with left:
    st.markdown("**Route segments**")
    st.dataframe(
        pd.DataFrame(
            [
                {"From": segment.from_node, "To": segment.to_node, "Distance (km)": segment.distance_km}
                for segment in scenario.world.route.segments
            ]
        ),
        hide_index=True,
    )
    st.markdown("**Stations**")
    st.dataframe(
        pd.DataFrame(
            [{"Station": station.id, "Node": station.node, "Chargers": station.chargers} for station in scenario.world.stations]
        ),
        hide_index=True,
    )
with right:
    vehicle = scenario.world.vehicle
    st.markdown("**Vehicle**")
    st.write(
        f"Range {vehicle.range_km} km, charge {vehicle.charge_minutes} minutes to full, "
        f"speed {vehicle.speed_kmph} km/h."
    )
    st.markdown("**Active weights**")
    st.write({key: float(value) for key, value in used_weights.items()})

st.markdown("**Buses**")
st.dataframe(build_input_table(scenario), hide_index=True)

# Per bus timetable.
st.header("Per bus timetable")
st.dataframe(build_bus_summary_table(result), hide_index=True)
for bus_schedule in result.bus_schedules:
    bus = bus_schedule.bus
    title = (
        f"{bus.id}    {direction_label(bus.origin, bus.destination)}    "
        f"arrives {format_time(bus_schedule.arrival_min)}"
    )
    with st.expander(title):
        st.dataframe(build_bus_stops_table(result, bus.id), hide_index=True)

# Per station order.
st.header("Per station order")
station_ids = [station.id for station in scenario.world.stations]
for tab, station_id in zip(st.tabs(station_ids), station_ids):
    with tab:
        st.dataframe(build_station_table(result, station_id), hide_index=True)
