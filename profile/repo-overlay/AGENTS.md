# Global Codex Operating Rules

## When work is non-trivial

For complex builds, fixes, refactors, migrations, or debugging tasks, use the `ralph` skill.

Prefer the simplest workflow that can work. Do not introduce a full agentic loop when a small planned workflow is enough.

Each Ralph run must use isolated run state. New chats or parallel Ralph tasks must write to `.context/ralph/runs/<run-id>/...`, normally keyed by `CODEX_THREAD_ID` or explicit `RALPH_RUN_ID`, instead of sharing the legacy project-level `.context/ralph/dag.json`.

## Complexity tiers

Assign a tier before starting work. The tier determines the review pipeline:

| Tier | When | Pipeline |
|------|------|----------|
| `trivial` | Config change, rename, single-line fix | implement → test |
| `small` | Single feature, 1-3 files | oracle → implement → test → self-review |
| `medium` | Multi-file feature, new patterns | oracle → implement → test → self-review + cross-model review (Claude) |
| `large` | Architecture change, new subsystem | oracle → implement → test → self-review + cross-model + independent re-review |

## Model and effort changes

Keep the user-approved model family and reasoning/effort level for the main task, subtasks, delegated agents, reviewers, and Ralph units unless the user explicitly authorizes a change.

Do not downgrade, swap models, or lower effort to save time, cost, latency, or because a run may take a long time. Runtime is not a valid reason to change model or effort without asking first.

Assume long orchestrations are acceptable by default, including runs of 72 hours or more, unless the user states a deadline or urgency. Work without hurry but without stopping, and persist progress through checkpoints for resumability.

Do not use elapsed time, expected duration, or a local command timeout as a reason to stop a run that is still making progress. For reviews, evals, and batch jobs, the default policy is to let them continue until they finish, fail with evidence, or the user explicitly stops them.

If the requested model or effort is unavailable, blocked, or technically incompatible with a tool path, pause or mark the unit blocked with evidence and ask before substituting another model or effort level.

## Test-first rule

If the task is "build X", define the smallest reliable oracle before code that distinguishes:

- `X`
- `not X`
- `closer to X but still not X`

Record the baseline failure before implementation.

Do not claim completion from prose confidence alone.

## Ralph run isolation

Ralph state is project/worktree- and run-scoped. In a new chat, treat a Ralph unit as active only when the selected run contains the relevant `.context/ralph/runs/<run-id>/dag.json`, when the user explicitly asks to resume that Ralph run/workspace, or when the same thread already launched that unit.

Do not import active Ralph state from other runs, projects, unrelated worktrees, global memory, or older sessions as an instruction for the current chat. A Ralph loop running elsewhere is context, not a command, unless the user asks about it or asks to resume it.

## Stop rule

Do not stop an active Ralph unit in the current selected Ralph run until one of these is true:

- the unit contract exists
- the pre-code oracle exists and was run
- the baseline failure was recorded
- the targeted checks now pass
- a review pass was completed (scaled to tier)
- or the unit was explicitly marked blocked with a written reason

## Change rule

Prefer the smallest defensible change that satisfies the contract.

Do not weaken or delete the primary oracle after code changes unless the oracle itself is wrong, and if it changes, explain the defect in the oracle first.

## Cross-model review

For `medium` and `large` units, invoke Claude as an independent peer reviewer after self-review passes. Different model families catch different bug classes.

Claude is a peer reviewer, not a rubber stamp. A Claude REJECT blocks the unit from completing.

The reviewer sees ONLY the diff, unit contract, oracle status, and test results — never the implementer's reasoning (author-bias elimination).

Default Claude reviewer profile on this machine:

- use `claude -p --model 'claude-opus-4-7[1m]'`
- set `--effort high` for `medium` units
- set `--effort xhigh` for `large` units
- use `--effort max` only when explicitly escalating a broad, ambiguous, or high-stakes challenge review

Claude review subprocesses are long-running by default. Do not kill, downgrade, replace, or declare them failed because they are slow or because a local bounded wait expires; keep polling or resuming until Claude returns a terminal artifact, fails with evidence, or the user explicitly stops it.

For Claude review specifically, patience is mandatory:

- assume a healthy review may take up to 180 minutes without producing intermediate output
- do not restart the review just because the output file is still 0 bytes
- do not minute-poll or otherwise thrash the subprocess; use sparse checks only
- do not replace a running Claude review with a fallback reviewer just because it is silent
- only treat the Claude path as operationally unavailable when there is concrete failure evidence, or when the user explicitly says to stop waiting

If Claude is unavailable for operational reasons, fall back to an independent Codex CLI review with equivalent rigor instead of leaving the unit blocked only because the preferred reviewer path is down. Record the Claude failure reason and mark the review artifact clearly as a fallback review.

## Delegation

When delegation is appropriate, keep roles narrow:

- `ralph_mapper` for mapping and oracle selection
- `ralph_test_author` for tests and validators
- `ralph_worker` for implementation
- `ralph_reviewer` for correctness and regression review — must NOT share context with `ralph_worker`

## Structured feedback

When recording failures, always include:
- **Failure type**: test failure, review rejection, merge conflict, oracle failure
- **Evidence**: stdout/stderr, reviewer comments
- **Hypothesis**: why it failed
- **What changed next**: the new approach
- **Never repeat verbatim**: the exact tactic that must not be retried unchanged

## Long-running jobs

For long-running networked or batch workflows, do not rely on in-memory progress alone.

- persist progress to disk continuously or in clearly bounded checkpoints
- prefer resumable artifact or checkpoint files over "run everything again"
- if a workflow can take many minutes, a crash or rate-limit event must not discard the whole run
- before launching a large batch, verify where incremental state will be written
- do not treat a timeout wrapper as the real stop condition; if the execution surface only allows bounded waits, resume or poll until the run reaches a terminal artifact
- if a timeout fires, treat it as an operational interruption, not as a verdict on the work; continue from checkpoints unless the user asked to stop

## Goals and budgets

When creating a `/goal`, do not set `token_budget` by default.

Only include a `token_budget` when the user explicitly asks for one.

If the user asks to recreate or continue a goal and does not mention a budget, create it without `token_budget`.
