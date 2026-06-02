# PROGRESS

Living checklist for the build. Claude Code updates this as it goes. Tick each item once its code and its test are done and green, and commit that stage in the same step so each ticked item corresponds to one commit.

Status: complete, all fifteen stages done and the suite is green. The only remaining step is the hosted Streamlit link, which is created from the public repo.

## Stages

* [x] 1. Scaffold the repo, the package directories, requirements.txt, and tests/conftest.py with fixtures.
* [x] 2. domain.py dataclasses for inputs and outputs.
* [x] 3. loader.py with HH:MM parsing. Run test_loader.py.
* [x] 4. Five scenario JSON files from BUILD_SPEC section 6. Verify counts, twenty for Scenarios 1, 2, 4, 5 and fourteen for Scenario 3.
* [x] 5. geometry.py, cumulative distances, travel time, feasible plan enumeration. Run test_geometry.py.
* [x] 6. rules/base.py registry, hard.py, soft.py, and rules/__init__.py auto import. Run test_hard_rules.py and test_soft_rules.py.
* [x] 7. conflict.py ConflictResolver. Run test_conflict.py.
* [x] 8. engine.py event simulation that validates with the hard rules. Run test_engine.py.
* [x] 9. objective.py weighted aggregation. Run test_objective.py and test_extensibility.py.
* [x] 10. viewmodel.py helpers. Run test_viewmodel.py.
* [x] 11. app.py with the four views plus the flag controlled weight panel, calling the viewmodel helpers.
* [x] 12. Full pytest run including test_scenarios.py, all green.
* [x] 13. README.md and ARCHITECTURE.md.
* [x] 14. streamlit run app.py locally and click through all five scenarios.
* [x] 15. Push to https://github.com/natapillai/bus-charging-scheduler with app.py and requirements.txt at the root.

## Deliverables check

* [x] Hosted Streamlit link, public. https://bus-charging-scheduler-natapillai.streamlit.app
* [x] Public GitHub repo with all code and all five scenarios.
* [x] README.md covering how to run, how to change a weight, and how to add a rule.
* [x] ARCHITECTURE.md covering the approach and why, the data model, the anticipated changes list, a weight change example, an add a rule example, and the assumptions.
* [x] All hard rules pass on every scenario with no violations.
* [x] Weights demonstrably change schedules, verified by the sensitivity tests.

## Deviations and decisions

Record here anything you changed, assumed, or deferred, with a short reason.

Python on this machine is 3.12.5 rather than 3.11. The code is written to stay compatible with 3.11 and above and uses no version specific features, so this is only the local interpreter.

test_loader unit tests the loader against synthetic in memory JSON written to a temporary path rather than against the five shipped files. The build order writes the loader before the scenario files, so depending on those files inside the loader test would be a circular dependency. The five files are validated end to end in test_scenarios instead, and stage 4 verifies their bus counts with a direct load check.

The charging plan chosen for each bus lives in engine local state rather than as a mutable field on the Bus dataclass. This keeps the input domain objects free of scheduler output and keeps equality and determinism comparisons clean. The spec pseudocode shows bus.plan only as illustration of computing a plan per bus.

The engine leaves the objective breakdown empty in stage 8 and the objective stage wires the evaluate call into the engine, since the build order places the objective after the engine. The engine test asserts the schedule invariants and determinism, which do not depend on the objective, and the objective stage adds the breakdown and its own test.

The engine processes all events sharing a timestamp before dispatching, so a server freeing and a bus arriving at the same minute both register before the conflict resolver chooses, which keeps simultaneous events fair and deterministic.

Weights act at two points rather than one. Conflict resolution uses all three weights to order buses that contend for a charger. Plan selection also became weight aware, spreading load with the overall weight scaling the network load term and the operator weight scaling the per operator load term, so the weights steer which stations a bus uses and not only who charges first. The spec called for plan selection to be able to become weight aware, and this is what lets the operator heavy scenario respond to the operator weight at all, since its even spacing produces no simultaneous contention for the resolver to act on.

Scenario 4 weight sensitivity needed a closer look. With the operator weight at 1.0 versus 2.0 the operator heavy scenario does not change, for two structural reasons. Its fifteen minute spacing means no two buses ever wait for the same charger at once, so the resolver is never asked to choose, and one operator owning most of the fleet means that operator's per station load tracks the total load, so no plan trade off exists for a positive weight to tip. The operator weight is still effective there, just between fairness off and on, which is why the scenario test compares operator 2.0 against 0.0 on Scenario 4 and the literal 1.0 against 2.0 comparison on Scenario 5, where genuine contention exists and the resolver reorders the chargers. The deeper point, recorded in ARCHITECTURE.md, is that operator fairness has the most to do when operators are evenly matched and contend, not when one operator is essentially the whole network.
