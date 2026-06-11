# Unit Contract: <unit-id>

## Tier
{trivial | small | medium | large}

## Outcome to prove

Build X, meaning:

- observable 1
- observable 2

## Near-miss signals

If this unit is still not X after an iteration, what should improve next?

- signal 1
- signal 2

## Non-goals

- non-goal 1
- non-goal 2

## Allowed surface

- likely files:
- likely commands:
- risky areas to avoid:

## Oracles to create before code

- primary executable check:
- negative or regression check:
- optional review-only check:

For production LLM or agentic-chat units, separate these oracles:

- orchestration/tool oracle:
- live answer-quality oracle:
- smaller-model robustness oracle:
- replay/observability oracle:
- frontier judge or critic oracle:
- live-call integrity manifest:
- blind frontier-baseline comparison:
- multi-model jury scoring:
- repeat-roll stability:
- task-class tool-floor check:
- latency/token/call-count envelope:
- regression lock against previously green scenarios:

If there is no existing oracle, create the smallest gap-revealing harness first.

## Baseline

- command:
- expected failure signature:
- actual result:
- notes:

## Viability gate

Answer this before implementation or retrain/eval:

- what must still exist after the latest fix or filter?
- what is the cheapest proof command or query?
- what row-count / coverage / provenance / sample-size threshold makes the unit not worth running?
- if the gate fails, what work replaces implementation?

For data- or model-dependent units, this section is mandatory. Do not continue to retrain/evaluate while the real dataset is collapsed, semantically wrong, or dominated by one accidental slice.

## Runtime artifacts

- planner-output.json:
- executor-output.json:
- review-input.json:
- oracle artifacts:
- test artifacts:
- viability artifacts:

## Implementation rule

Do not relax, delete, or silently rewrite the primary oracle after code changes unless the oracle is wrong. If it changes, explain the defect in the oracle first.

## Pass conditions

- condition 1
- condition 2
- viability gate is explicitly `pass` or explicitly `skip` with a real reason

## Review tier

{trivial: no formal review | small: self-review | medium: self + cross-model (Claude) | large: self + cross-model + independent re-review}

Claude reviewer profile when applicable: prefer the strongest available Opus extended-context profile. Default tier mapping: `medium` -> `high`; `large` -> `xhigh`. Use `max` only when the review itself is unusually broad, ambiguous, or otherwise needs an explicit escalation.

## Review questions

- What can still be wrong even if the checks pass?
- What integration or rollout risk remains?
- For LLM products: did the real user-facing model path run, did the private tools/data materially improve the answer, and would a strong generic frontier model without those tools still be worse?
