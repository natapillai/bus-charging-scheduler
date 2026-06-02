# Bus Charging Scheduler

A charging scheduler for electric buses that share four chargers along the fixed route between Bengaluru and Kochi. It reads any of five scenarios from data files, decides each bus's charging plan and the order buses use each charger, and shows the result in a Streamlit app. The scheduler is a greedy event driven simulation with a pluggable rule registry and a tunable weighted objective, so the world can grow and the rules can change through data rather than rewrites.

The app is hosted on Streamlit Community Cloud at https://bus-charging-scheduler-natapillai.streamlit.app.

## Running locally

Clone the repository and create a virtual environment.

```
git clone https://github.com/natapillai/bus-charging-scheduler.git
cd bus-charging-scheduler
python -m venv .venv
```

Activate the environment, on Windows with `.venv\Scripts\activate` and on macOS or Linux with `source .venv/bin/activate`, then install the dependencies and start the app.

```
pip install -r requirements.txt
streamlit run app.py
```

The app opens on the scenario dropdown. Pick a scenario to see the input data, the per bus timetable, and the per station order.

To run the tests, install pytest and run it from the repository root.

```
pip install pytest
pytest
```

## Deploying on Streamlit Community Cloud

Push the repository to GitHub and keep it public. On Streamlit Community Cloud create a new app, point it at this repository, and choose `app.py` as the entry point. Streamlit reads `requirements.txt` and installs everything automatically, so there is nothing else to configure.

## Changing a weight

Weights live in the `weights` block of each scenario file under `scenarios/`. They are an open dictionary keyed by soft rule category. To make operator fairness matter twice as much, open a scenario file such as `scenarios/scenario_1.json` and change one value.

```json
"weights": {
  "individual": 1.0,
  "operator": 2.0,
  "overall": 1.0
}
```

That is the only place a weight lives. Nothing in the code carries a hardcoded weight. The app also has an optional sidebar panel, controlled by the `SHOW_WEIGHT_PANEL` flag at the top of `app.py`, that tunes the weights live so you can watch the schedule change. The panel starts at each scenario's own weights, so leaving it untouched produces the scenario's own schedule.

## Adding a rule

A new soft rule is one class with a category, a score, and an optional priority, registered with the decorator. If the category is new, add its key to the `weights` block in the scenario files and the engine picks it up with no change.

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

A new hard rule follows the same pattern with `register_hard` and a `validate` method that returns a list of violation strings, empty when the schedule is valid. The engine runs every registered hard rule against the finished schedule, so the new rule is enforced without touching the engine.

## Layout

`app.py` is the Streamlit entry point and holds the user interface only. The `scheduler` package holds the logic, with `domain.py` for the data models, `loader.py` for reading scenarios, `geometry.py` for distances and feasible plans, `conflict.py` for the charger queue order, `objective.py` for the weighted aggregation, `engine.py` for the event simulation, `viewmodel.py` for pure helpers the interface calls, and `rules/` for the registry and the hard and soft rules. The five scenario files are in `scenarios/` and the per stage tests are in `tests/`. ARCHITECTURE.md explains the approach, the data model, and the changes the design anticipates.
