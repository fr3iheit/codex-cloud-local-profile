# Ralphone Execution Plan

## Task

- Goal:
- User-visible outcome:
- Constraints:
- Non-goals:

## Eval Flywheel

- Deterministic checks:
- Scenario fixtures:
- Regression cases to add:
- Failure categories to track:
- Viability gate question:
- Viability proof command:
- Block-if thresholds:

## Model Routing

- Mapping / inventory:
- Oracle authoring:
- Implementation:
- Review:
- When to escalate reasoning:

## Parallelization Layers

- Layer 0 single-agent default:
- Layer 1 read-only exploration:
- Layer 2 review lenses:
- Layer 3 truly disjoint implementation units:
- Explicitly forbidden fan-out:

## Unit Table

| id | tier | status | deps | allowed surface | oracle before code | review mode | model routing |
| --- | --- | --- | --- | --- | --- | --- | --- |
| unit-id | small | pending | [] | path/or/system | command or validator | self-review | map: mini / impl: 5.4 / review: 5.4 |

## Unit Details

### unit-id

- Tier: {trivial | small | medium | large}
- Outcome to prove:
- Why this unit exists:
- Non-goals:
- Near-miss signals: (what "closer but not done" looks like)
- Depends on:
- Likely files or systems:
- Allowed surface: (files this unit may modify)
- Oracle before code:
- Baseline expectation:
- Viability gate:
- Viability proof:
- Viability block condition:
- Final checks:
- Review payload:
- Parallelization layer:
- Model routing:
- Risks to watch:
