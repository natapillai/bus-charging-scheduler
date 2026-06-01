# CLAUDE.md

Project memory for Claude Code. Read this first every session.

## What this is

A charging scheduler for electric buses on a fixed route from Bengaluru to Kochi with four shared charging stations. Python and Streamlit, one repo, one process, hosted on Streamlit Community Cloud. Repo: https://github.com/natapillai/bus-charging-scheduler.

## Source of truth

BUILD_SPEC.md is the authoritative plan. Follow it exactly. If an original assignment markdown is also present in the repo or in uploads, treat it as a reference only and defer to BUILD_SPEC.md whenever anything looks different.

## Stack and constraints

Python 3.11. Dependencies are streamlit, pandas, and pytest. Lean on the standard library. No database, no auth, no maps. In memory state is fine. Use dataclasses for the domain.

## Architecture in one paragraph

A greedy, event driven scheduler with a pluggable rule registry and a tunable weighted objective. The engine knows only generic concepts, a route of nodes with distances, stations as resources with a charger capacity, a clock, a set of rules, and a weight vector. Hard rules are validators that return violations. Soft rules are scorers tagged with a category that maps to a weight key. Policy lives in the rules, never in the engine.

## Non negotiables

Nothing about the current small world is hardcoded. Charger count is a capacity per station. Operators are read off the buses. The route comes from data. Weights are an open dictionary. Changing a weight is one value in a scenario JSON file and nowhere else in code. Adding a rule is one registered class with no engine change. Schedules are deterministic, with ties broken by bus id. SHOW_WEIGHT_PANEL controls visibility only and is outcome neutral, so the schedule with the panel hidden equals the schedule with an untouched panel.

## Where things live

app.py is the Streamlit entry point and holds UI only. scheduler/ holds the logic: domain.py for dataclasses, loader.py for JSON loading, geometry.py for distances and feasible plans, conflict.py for the weighted queue order, objective.py for the weighted aggregation, engine.py for the event simulation, viewmodel.py for pure UI helpers, and rules/ for base.py, hard.py, soft.py with the registry. scenarios/ holds the five JSON files. tests/ holds the per stage suite plus conftest.py.

## How to run

Local app with streamlit run app.py. Tests with pytest from the repo root.

## Testing discipline

Write and run each stage's test file before moving to the next stage, following the build order in BUILD_SPEC.md. In the extensibility test, snapshot and restore the rule registries so global state does not leak into other tests.

## Writing style for docs and comments

Match the owner's voice in README.md, ARCHITECTURE.md, and code comments. Plain flowing prose, concise, no filler. Do not use dashes of any kind, no hyphens, no en dashes, no em dashes, including as bullet markers or as sentence connectors. Use separate sentences or prose instead. Real file names and code identifiers keep their actual spelling.

## Git workflow

Git is already initialized since this directory is a clone of the remote, so do not run git init or git remote add. If a .gitignore is not already present, add one for the virtual environment, __pycache__, and .pytest_cache, and if one exists add those entries to it. Commit once per stage, after that stage's code is written and its tests pass, and tick the matching item in PROGRESS.md in the same commit, so the history maps one to one with the milestones. Do not commit broken code. The only commits without passing tests are the initial scaffold and the docs.

Write normal, human commit messages and never add any Claude Code or AI attribution. Do not append a Co-authored-by Claude trailer, a Generated with Claude Code line, or any similar footer. Each commit is a short imperative subject line, capitalized, with no trailing period and no colons or dashes, for example Add scenario loader, then a blank line, then a short body of two or three plain sentences that say what changed, how the change is verified or tested, and why it was made. Keep the body in flowing prose with no colons, dashes, or bullet points. Commit locally as you go and push to the remote at the final stage.

## Progress

Update PROGRESS.md at the end of every stage. Tick the item and note any deviation or assumption under deviations and decisions.
