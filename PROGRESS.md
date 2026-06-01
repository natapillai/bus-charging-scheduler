# PROGRESS

Living checklist for the build. Claude Code updates this as it goes. Tick each item once its code and its test are done and green, and commit that stage in the same step so each ticked item corresponds to one commit.

Status: in progress.

## Stages

* [x] 1. Scaffold the repo, the package directories, requirements.txt, and tests/conftest.py with fixtures.
* [x] 2. domain.py dataclasses for inputs and outputs.
* [x] 3. loader.py with HH:MM parsing. Run test_loader.py.
* [x] 4. Five scenario JSON files from BUILD_SPEC section 6. Verify counts, twenty for Scenarios 1, 2, 4, 5 and fourteen for Scenario 3.
* [x] 5. geometry.py, cumulative distances, travel time, feasible plan enumeration. Run test_geometry.py.
* [x] 6. rules/base.py registry, hard.py, soft.py, and rules/__init__.py auto import. Run test_hard_rules.py and test_soft_rules.py.
* [ ] 7. conflict.py ConflictResolver. Run test_conflict.py.
* [ ] 8. engine.py event simulation that validates with the hard rules. Run test_engine.py.
* [ ] 9. objective.py weighted aggregation. Run test_objective.py and test_extensibility.py.
* [ ] 10. viewmodel.py helpers. Run test_viewmodel.py.
* [ ] 11. app.py with the four views plus the flag controlled weight panel, calling the viewmodel helpers.
* [ ] 12. Full pytest run including test_scenarios.py, all green.
* [ ] 13. README.md and ARCHITECTURE.md.
* [ ] 14. streamlit run app.py locally and click through all five scenarios.
* [ ] 15. Push to https://github.com/natapillai/bus-charging-scheduler with app.py and requirements.txt at the root.

## Deliverables check

* [ ] Hosted Streamlit link, public.
* [ ] Public GitHub repo with all code and all five scenarios.
* [ ] README.md covering how to run, how to change a weight, and how to add a rule.
* [ ] ARCHITECTURE.md covering the approach and why, the data model, the anticipated changes list, a weight change example, an add a rule example, and the assumptions.
* [ ] All hard rules pass on every scenario with no violations.
* [ ] Weights demonstrably change schedules, verified by the sensitivity tests.

## Deviations and decisions

Record here anything you changed, assumed, or deferred, with a short reason.

Python on this machine is 3.12.5 rather than 3.11. The code is written to stay compatible with 3.11 and above and uses no version specific features, so this is only the local interpreter.

test_loader unit tests the loader against synthetic in memory JSON written to a temporary path rather than against the five shipped files. The build order writes the loader before the scenario files, so depending on those files inside the loader test would be a circular dependency. The five files are validated end to end in test_scenarios instead, and stage 4 verifies their bus counts with a direct load check.

The charging plan chosen for each bus lives in engine local state rather than as a mutable field on the Bus dataclass. This keeps the input domain objects free of scheduler output and keeps equality and determinism comparisons clean. The spec pseudocode shows bus.plan only as illustration of computing a plan per bus.
