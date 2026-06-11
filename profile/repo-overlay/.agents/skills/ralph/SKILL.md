---
name: ralph
description: Run a repo-agnostic Ralph loop for complex builds, fixes, or refactors in Codex. Use when the user wants autonomous execution, explicit quality gates, and a harness-first loop with artifact-backed state.
metadata:
  short-description: Harness-first autonomous Codex loop with complexity tiers
---

# Ralph Autonomous Loop

Use this skill for non-trivial work that benefits from explicit contracts, failing tests first, structured handoffs, and durable eval artifacts.

In command examples, replace `<skill-root>` with the directory that contains this `SKILL.md`.

Every Ralph run must use isolated run state. In Codex Desktop, new chats normally select `.context/ralph/runs/<CODEX_THREAD_ID>/...`; manual parallel runs can set `RALPH_RUN_ID=<name>`. Use `RALPH_USE_LEGACY=1` only when intentionally resuming a pre-existing legacy `.context/ralph/dag.json`.

This workflow is repo-agnostic. It is for general product engineering, not a stack-specific playbook.

## Project/worktree isolation rule

Ralph state is project- and run-scoped. A Ralph loop is active for the current chat only when it is active in the selected Ralph run, meaning one of these is true:

- the current chat's project root or working directory contains the relevant `.context/ralph/runs/<run-id>/dag.json`
- the user explicitly asks to resume a named Ralph loop, handoff, unit, or workspace
- this same thread already launched or accepted the Ralph unit being continued

Do not search other runs, other projects, global memory, session history, or unrelated worktrees for active Ralph DAGs when deciding what a new chat should do. An active Ralph loop in a different run or project is context, not a command. Mention it only when the user asks about it or it is directly relevant, then continue with the user's current request.

This isolation rule must not break running Ralph loops: do not stop processes, delete state, rewrite another run's `.context/ralph`, or weaken evidence gates just because a new unrelated chat started.

## Continuous auto-resume rule

When Ralph is active in the current selected Ralph run, it must keep going until every mandatory gate for the active unit or dependency chain is green, or the user explicitly says to stop.

Treat these as operational interruptions, not as valid stop conditions:

- the assistant being redirected to a related side question inside the same Ralph run while the loop is still open
- a stop hook reminder
- a tool timeout or bounded wait
- a session boundary or new chat that is explicitly continuing the same Ralph run
- a partial green state such as implementation passing while review is still red

Required behavior while a loop is active:

- update Ralph state when a new blocker, regression, or real-user failure is discovered
- return to the active unit after handling any necessary bookkeeping
- rerun the failing gate after each repair cycle
- keep resuming until `targeted_checks_passed` and `review_complete` are both green when those checks are required by the unit

Inside the current selected Ralph run, do not treat "Ralph is still active in the DAG" as merely informative state. It is a command to continue that loop. Outside the current run, follow the project/worktree isolation rule above.

## Real-user failure generalization rule

When a real user prompt exposes a miss that the current suite did not catch, do not patch only the literal example unless the user explicitly wants a one-off workaround.

Instead:

1. identify the broader failure class
2. patch the runtime for that class
3. update the oracle/review set to cover that class generically
4. rerun the relevant gate

For broad chat or product-behavior work, the suite must include some open or generic prompts, not only strongly scaffolded prompts. Examples of required broad classes when relevant:

- natural symptom-picture questions that do not say `repertorize` or `materia medica`
- generic product/capability questions
- generic account/scope questions
- author/source comparison questions such as differences between authors or corpora

Bad pattern:

- a user tests one natural prompt
- Ralph adds that exact literal prompt only
- the suite still misses nearby prompts from the same class

Good pattern:

- a user reveals a new miss
- Ralph names the class
- the contract/oracle is widened to that class
- the runtime and suite are both repaired

## Core law

If the task says "build X", the first job is to define the smallest reliable oracle that can distinguish:

- `X`
- `not X`
- `closer to X, but still insufficient`

Do not start implementation until that oracle exists and has been run once.

If the task depends on external data, labels, filters, joins, or evaluation slices, ask one more question before implementation or retrain:

- does the real input still exist in enough quantity and with the right contract after the latest fix, filter, or split?

If the answer is not proven with a command-backed artifact, the unit is not ready.

## Definition of Done gate

Every explicit user success criterion is part of the Definition of Done.

Before implementation, the contract must list:

- each requested outcome
- each requested threshold, score, reviewer, model, cadence, or redundancy level
- the artifact or command that proves each criterion
- which gate is allowed to reject completion
- the near-miss state that must still fail
- the minimum population, surface area, or coverage that must remain when the user asked
  for broad, global, complete, all-source, or production-wide output

Structural checks are not substitutes for stated acceptance gates. A unit cannot be
complete while any explicit DoD criterion is unproven, stale, below threshold, or only
partially run.

Scope preservation is a completion gate. If a unit improves quality by excluding,
quarantining, sampling, filtering, or narrowing the output, it must prove that the
remaining artifact still satisfies the user's requested breadth. A high score on a
small subset is a near miss, not completion, unless the user explicitly changed the
target to that subset.

When breadth is part of the request, define the first oracle so it fails for
scope-collapse cases such as:

- a polished subset replacing the requested full/broad artifact
- a validation pass that ignores omitted rows/items/sources
- a coverage collapse hidden behind a higher quality score
- a fallback artifact that cannot serve the user's stated production use

If the user gives a target such as `92+`, `three passes`, `xhigh`, `all rows`, `no
duplicates`, `production-ready`, or any similar measurable or reviewable condition,
encode it in `contract.md` and `review-input.json` as a mandatory completion gate.

The first oracle should fail when the DoD target is unmet, not merely when files are
missing. If a later gate rejects the artifact, reopen or create a remediation unit; do
not treat an earlier count/schema/format pass as sufficient closure.

As a general acceptability gate for non-trivial work, include a top-tier model check
before completion:

- show the original request
- show the produced result or the relevant chunks of it
- ask whether the result satisfies the request
- require concrete issues and a verdict, not encouragement
- aggregate chunk verdicts before declaring the unit complete

This check is a starting point, not the whole validation strategy. Add task-specific
oracles whenever correctness needs more than a top-tier acceptability review.

## No pretend-completion rule

Ralph must not complete a unit by proving only that files exist, schemas parse, counts
match, or a polished artifact renders. Structural validators are useful smoke tests,
but they are not acceptance gates when the user asked for a working system, product,
game, workflow, model, or real behavior.

If the user asks for something to be `end-to-end`, `ready`, `validated`, `tested`,
`playable`, `usable`, `production-ready`, or any equivalent, the unit contract must
include a behavior-level oracle. The oracle must exercise the artifact through the
same path a real user or downstream system would use. A near miss must still fail.

Examples of insufficient completion evidence:

- a game with generated cards but no complete rules and no legal turn transcript
- a model with an aggregate metric but no inspected failing slices
- a UI with screenshots but no critical user-flow execution
- a pipeline with output files but no source-to-output provenance check
- an "AI playtest" that is only a heuristic script when the user requested model
  players

When the requested artifact is a game or interactive system, Ralph must require:

- a complete rulebook that defines setup, state, legal moves, illegal moves, turn
  phases, win/loss conditions, examples, and edge cases
- an executable state engine or validator that rejects illegal moves
- at least one human-readable full turn-by-turn transcript from setup to win/loss
- a reviewer prompt that asks whether a new player could actually play from the rules
- if the user requested model players, an explicit model-player transcript or a
  clearly recorded blocker explaining why the requested model could not be run

Do not label a unit complete if the strongest honest statement is only "prototype
structure exists". In that case, record the unit as incomplete or open a remediation
unit with the missing behavioral gates as mandatory DoD.

## Batch and redundancy gate

For long-running or repeated workflows:

- run a pilot through the same schema and gates before the full run
- verify that redundant passes are independent when independence is part of the DoD
- persist every batch result and prompt before moving to the next batch
- aggregate only from valid batch artifacts
- rerun the final gate on the aggregate artifact, not only on intermediate pieces
- if the task has an explicit target score, the final gate must meet or exceed it before
  completion
- never use elapsed time by itself as a stop condition while the run is still making
  progress
- default to no artificial timeout for reviews, evals, and batch runs; if the tool only
  supports bounded waits, keep polling or resuming the same run until it finishes, fails
  with evidence, or the user explicitly stops it
- if a timeout occurs, treat it as an execution-surface interruption, not as a verdict on
  the unit, and resume from persisted artifacts or checkpoints

When a DoD gate fails, prefer an iterative repair loop:

1. materialize the failing classes or slices
2. repair only the failing classes or slices
3. preserve the original gate unchanged
4. rerun the same gate
5. repeat until the target is met or block the unit with evidence

Do not repair a failing broad artifact by silently redefining the release as only the
cleanest subset. Use tiers, confidence labels, advisory modes, quarantine, or staged
promotion only if the final artifact still contains the requested usable breadth, and
the review gate explicitly sees both the released portion and the omitted/backlog
portion.

If a new real-user failure appears during the loop, fold it into this same repair cycle.
Do not defer it to a vague future pass when the active unit is supposed to prove broad
real-world behavior.

## Production LLM product loops

When Ralph is used to make an LLM product or agentic chat production-ready, the
unit must prove the behavior through the real model and tool path that users will
hit. Dry runs, stubbed model calls, structural smoke checks, and trace-only
validators can be useful pre-checks, but they are not completion evidence for
answer quality.

The contract must explicitly separate:

- orchestration/tool correctness: whether the right tools, sources, permissions,
  and intermediate steps were chosen
- answer quality: whether the final user-facing answer is excellent, precise,
  source-grounded, and better because of the product's private tools/data
- model-routing robustness: whether the orchestration still works when the final
  answer model is intentionally smaller than the frontier reviewer

For all-purpose agentic chat systems, the oracle must exercise the whole
decision chain:

- interpret the user request and choose a plan
- run the relevant tools, preferably in parallel when independent
- retrieve and rerank evidence
- fetch full documents or larger source spans when the task requires them
- synthesize intermediate tool outputs with model calls when useful
- produce the final answer through the same model-serving path used in the app
- persist the full redacted trace so bad answers can be replayed and converted
  into regression cases

The reviewer must see each prompt, answer, tool call, retrieval result, model
route, and trace needed to decide where quality was lost. A reviewer cannot
accept a production LLM unit by judging only the final answer or only the trace.

When the intended production design is to run a smaller answer model behind a
strong orchestrator, the quality gate must include that smaller-model execution.
Frontier models such as GPT-5.5 extra-high or Claude Opus extended-context max
can be used as judges, critics, planners, or remediation advisers, but they must
not hide weak orchestration by being the only model that ever answers the user.

If the goal is excellence against a frontier generic model, the review prompt
must ask that directly: whether the answer is structurally strong, clinically or
domain-wise credible, source-grounded in the product's real tools, and clearly
better than what a generic frontier chat could have produced without those
private tools. Anything less is a near miss.

For production-ready LLM products, the contract should add hard gates for the
following whenever feasible:

- live-call integrity: provider/model/request IDs, timestamps, token usage, and
  raw redacted response envelopes for every planner, synthesis, and answer call
- smaller-model isolation: a mandatory configuration where all answer-path LLM
  calls use the production candidate smaller model, so a frontier model cannot
  hide weak orchestration
- actual frontier baseline: generate and blind-score the product answer against
  a strong generic frontier baseline that does not use private tools/data
- multi-model jury: use structured numeric verdicts from independent judges
  across model families/providers, with disagreement escalation
- repeat rolls: run stochastic scenarios multiple times and require stable
  quality, not a single lucky pass
- minimum tool floors per task class, so the system cannot decide that no
  retrieval, full-document fetch, or synthesis was "useful" for every case
- replay and observability: every accepted quality claim must be traceable to a
  durable redacted artifact readable after the turn
- regression lock: previously green production scenarios must remain green under
  the new, stricter oracle
- latency, call-count, and token envelopes when the claim is production readiness

## Complexity Tiers

Assign each unit a tier to avoid over-engineering simple changes or under-reviewing complex ones:

| Tier | Criteria | Pipeline |
|------|----------|----------|
| `trivial` | Config change, rename, single-line fix | implement -> test |
| `small` | Single feature, 1-3 files | contract -> oracle -> implement -> test -> review |
| `medium` | Multi-file feature, new patterns | contract -> planner -> oracle -> implement -> test -> dual-review |
| `large` | Architecture change, new subsystem, cross-cutting | contract -> planner -> oracle -> implement -> test -> challenge-review |

## Bootstrap

1. Run:

```bash
python3 "<skill-root>/scripts/bootstrap_ralph.py"
```

2. Inspect the selected repo-local Ralph run:
   - `.context/ralph/plan.md`
   - `.context/ralph/model-routing.md`
   - `.context/ralph/review-rubric.md`
   - `.context/ralph/runs/<run-id>/dag.json`
3. Create the first unit:

```bash
python3 "<skill-root>/scripts/ralph_state.py" begin <unit-id> --title "<title>" --tier <tier>
```

4. Add dependent units when needed:

```bash
python3 "<skill-root>/scripts/ralph_state.py" add-unit <unit-id> --title "<title>" --tier <tier> --deps dep-a dep-b
```

## Runtime layout

Ralph now treats `.context/ralph/runs/<run-id>` as the harness root for new
runs. The project root is resolved with `git rev-parse --show-toplevel` when
possible, so running Ralph from a subdirectory such as `web/` still uses the
same project identity, but each Codex thread or explicit `RALPH_RUN_ID` gets its
own run state.

- `.context/ralph/runs/<run-id>/dag.json`: run loop state, unit map, active units
- `.context/ralph/runs/<run-id>/project.json`: pointer to the project-scoped global Ralph memory
- `.context/ralph/runs/<run-id>/units/<unit-id>/state.json`: per-unit state
- `.context/ralph/runs/<run-id>/units/<unit-id>/contract.md`: unit contract
- `.context/ralph/runs/<run-id>/units/<unit-id>/planner-output.json`: planner artifact
- `.context/ralph/runs/<run-id>/units/<unit-id>/executor-output.json`: implementation handoff
- `.context/ralph/runs/<run-id>/units/<unit-id>/review-input.json`: narrow reviewer payload
- `.context/ralph/runs/<run-id>/units/<unit-id>/artifacts/*.json`: command-backed evidence

Legacy `.context/ralph/dag.json` remains readable only for old runs. Use
`RALPH_USE_LEGACY=1` when intentionally resuming that state.

Global Ralph memory is project-scoped under:

- `$CODEX_HOME/ralph/projects/<project_id>/project.json`
- `$CODEX_HOME/ralph/projects/<project_id>/memory.md`
- `$CODEX_HOME/ralph/projects/<project_id>/logs/`

Do not store cross-project Ralph decisions in a single shared memory file. If a
task spans multiple repositories, record the project-local evidence in each
project's Ralph context and use a separate coordination unit for cross-project
state.

## Per-unit loop

1. Clarify the unit:
   - outcome to prove
   - non-goals
   - near-miss signals
   - allowed surface
   - dependencies
   - final checks
   - viability gate: what must still exist after filtering or fixing, and what count/provenance threshold would make the unit not worth running
2. Mark contract creation with evidence:

```bash
python3 "<skill-root>/scripts/ralph_state.py" check contract_written pass --unit <unit-id> --artifact-path .context/ralph/runs/<run-id>/units/<unit-id>/contract.md --summary "Contract written"
```

3. Fill:
   - `contract.md`
   - `planner-output.json`
   - `review-input.json`
4. Record the baseline by running the oracle through the harness:

```bash
python3 "<skill-root>/scripts/ralph_state.py" run-check <unit-id> baseline_recorded --command "<oracle command expected to fail>" --expect-exit <nonzero>
```

5. Only then implement.
6. For data- or model-dependent work, record the viability gate before retrain/eval:

```bash
python3 "<skill-root>/scripts/ralph_state.py" run-check <unit-id> viability_gate_passed --command "<coverage/provenance/query command>" --expect-exit 0
```

If viability is not relevant to the unit, mark it explicitly:

```bash
python3 "<skill-root>/scripts/ralph_state.py" check viability_gate_passed skip --unit <unit-id> --summary "No external dataset/filter viability risk in this unit."
```

If the gate shows the dataset collapsed, stop the unit and pivot to acquisition/parsing/join debugging instead of retraining.

Record viability before the final review whenever possible. If viability evidence changes after review, the review should be considered stale.
7. Record passing evidence for tests and checks with `run-check` whenever possible:

```bash
python3 "<skill-root>/scripts/ralph_state.py" run-check <unit-id> targeted_checks_passed --command "<narrow passing command>" --expect-exit 0
```

8. Use `check ... pass` only when the evidence is a file rather than a command:

```bash
python3 "<skill-root>/scripts/ralph_state.py" check review_complete pass --unit <unit-id> --artifact-path .context/ralph/runs/<run-id>/units/<unit-id>/review-verdict.md --summary "Review artifact completed"
```

9. When required checks are green, mark the unit complete:

```bash
python3 "<skill-root>/scripts/ralph_state.py" complete-unit --unit <unit-id>
```

10. When landed:

```bash
python3 "<skill-root>/scripts/ralph_state.py" land-unit <unit-id> --commit <sha>
```

11. Inspect runnable work:

```bash
python3 "<skill-root>/scripts/ralph_state.py" ready
python3 "<skill-root>/scripts/ralph_state.py" status
```

If blocked:

```bash
python3 "<skill-root>/scripts/ralph_state.py" block "reason" --unit <unit-id> --terminal
```

Use terminal blocking only for an irrecoverable blocker: missing external access,
missing source data, an impossible model/tool path, or an explicit user stop. A
quality failure after implementation is not terminal by itself. If
`targeted_checks_passed` or `review_complete` is still red after baseline,
viability, and implementation are green, keep the active unit running and repair
the failing slices; do not end the loop just because the current tactic failed.
The state script refuses non-terminal `block` in that situation so the stop hook
continues the loop.

## Artifact-backed checks

Ralph is harness-first. A green check should point to evidence:

- `artifact_path`
- `command`
- `exit_code`
- `summary`

Bad substitutes:

- vague self-ratings
- "looks good" prose
- setting `pass` without an artifact

## Viability gate

For any unit that trains, evaluates, migrates, or depends on filtered inputs, Ralph must prove the thing still exists before spending time on the next expensive step.

Ask these first:

- what exact population is left after the latest fix, join, or filter?
- how many rows/examples/items remain by split, year, and dominant category?
- what share is verified vs fallback vs missing?
- where does the missing mass go?
- is the remaining sample still broad, or is it now one accidental slice?
- if the population is tiny, is the real task now data acquisition/parsing instead of modeling?

Minimum expectations for data/model units:

- a command-backed artifact with post-filter counts
- provenance split or source-of-truth split
- sample-size table for train/validation/holdout
- at least a few concrete missing or dropped examples traced end-to-end when coverage collapses

Typical failure pattern to avoid:

- fix one bug
- assume retrain is the next step
- ignore that the dataset fell from thousands of rows to a handful
- waste time optimizing a model on a dead sample

When the viability gate fails, block the unit or create a new dependency unit for:

- parsing/debugging
- join repair
- coverage backfill
- source replacement

## Planner / Executor / Reviewer split

Use these three artifacts as narrow interfaces:

- `planner-output.json`
  - unit goal
  - oracle strategy
  - parallelization layer
  - model routing
- `executor-output.json`
  - files touched
  - oracle artifacts
  - test artifacts
  - known gaps
- `review-input.json`
  - contract path
  - oracle artifacts
  - test artifacts
  - diff summary
  - review questions

The reviewer should see only:

- contract
- oracle evidence
- test evidence
- diff
- viability evidence when relevant

## Parallelization Layers

Ralph should not fan out by default.

1. `Layer 0`: single-agent default
   - use for most `small` units
   - use whenever one agent can hold the whole state
2. `Layer 1`: parallel read-only exploration
   - use for source gathering, codebase mapping, bounded comparisons
3. `Layer 2`: parallel review lenses
   - correctness review
   - regression review
   - integration-risk review
4. `Layer 3`: parallel implementation units
   - only when write surfaces are disjoint
   - only when dependency edges are explicit in `dag.json`

Never parallelize:

- final synthesis
- final merge decisions
- final plan approval
- overlapping writes

## GPT-5.4-Mini

Use `gpt-5.4-mini` aggressively, but only for bounded work.

Good default uses:

- codebase mapping
- file and symbol inventory
- source gathering
- contract linting
- oracle candidate generation
- diff summarization
- review pretriage
- stale artifact detection

Suggested thinking:

- `low`
  - inventories
  - classification
  - deterministic formatting
  - checklist validation
- `medium`
  - mapping
  - bounded synthesis
  - oracle selection
  - review pretriage

Do not default to `gpt-5.4-mini` for:

- ambiguous root-cause debugging
- multi-file implementation with architectural consequences
- final review on medium/large units
- challenge review when the oracle is incomplete

## Model routing

Recommended routing:

- `ralph_triager`
  - `gpt-5.4-mini`, `low`
  - scope classification and next-step triage
- `ralph_mapper`
  - `gpt-5.4-mini`, `medium`
  - mapping and oracle candidates
- `ralph_planner`
  - `gpt-5.4`, `high`
  - planner-output and model-routing choice
- `ralph_test_author`
  - `gpt-5.4`, `high`
  - oracle and harness authoring
- `ralph_worker`
  - `gpt-5.4`, `high`
  - implementation
- `ralph_reviewer`
  - `gpt-5.4`, `high`
  - primary correctness review

Escalate to `xhigh` only for:

- architecture review
- root-cause ambiguity after one pass
- final challenge review on large units
- final challenge review when the user gave an explicit high score target

## Thinking policy

Do not add extra reasoning everywhere.

Use deliberate thinking only when:

- tool outputs are long or conflicting
- policy-heavy review requires rule comparison
- multiple next-step branches are plausible
- the root cause remains ambiguous after the first pass

Avoid extra thinking for:

- file enumeration
- intent classification
- prompt templating
- simple schema validation

## Review modes

- `small`
  - self-review using `review-input.json`
- `medium`
  - self-review plus one independent reviewer
- `large`
  - self-review plus challenge review plus independent re-review

Cross-model review is encouraged when available, but the harness should still produce reviewer payloads even when the external reviewer is temporarily unavailable.

Preferred Claude Code reviewer profile:

- use the strongest available Opus reviewer profile in Claude Code for independent review
- prefer the extended-context Opus profile when the local install/account exposes it
- on this machine, treat `claude -p --model 'claude-opus-4-8'` as the standard target profile when available
- choose effort by tier without downgrading for convenience
  - `medium` -> `--effort high`
  - `large` -> `--effort xhigh`
  - use `--effort max` only as an explicit escalation for especially broad, ambiguous, or high-stakes challenge review; do not make it the default
- do not use `--bare` for Claude review unless you are intentionally supplying API-key-only auth via `ANTHROPIC_API_KEY` or `apiKeyHelper`; `--bare` disables the normal OAuth/keychain auth path and can create false "Not logged in" failures

When the preferred Claude reviewer is unavailable for operational reasons (for example not installed, not authenticated, or failing before it can review), use an independent Codex CLI review as the default redundancy fallback instead of leaving the unit blocked only for reviewer-path unavailability.

Requirements for this fallback:

- record that Claude was unavailable and why
- keep the reviewer isolated to contract, oracle evidence, test evidence, and diff
- use a separate Codex run, not the implementer's ongoing reasoning context
- choose the closest available Codex CLI review effort for the unit tier
  - `medium` -> `gpt-5.4` with `high`
  - `large` -> `gpt-5.4` with `xhigh`
- mark the artifact clearly as a fallback redundancy review

Independent reviews are long-running by default. Do not cancel, kill, downgrade, or
replace a review because it is slow. If the execution surface imposes bounded waits or
session windows, keep resuming or polling until the review produces a terminal artifact,
fails with evidence, or the user explicitly stops it.

Hard rule for Claude review waiting discipline:

- A silent Claude review is still considered healthy for up to 180 minutes.
- Do not restart it, supersede it, or declare it stuck just because the artifact is still empty.
- Do not poll aggressively. Sparse status checks are enough; the point is to avoid operator thrash.
- Fall back only after concrete failure evidence, or after the user explicitly redirects.

## Delegation

Use delegation only when the user explicitly authorizes subagents or parallel work.

When that happens, prefer these project agents:

- `ralph_triager`
- `ralph_mapper`
- `ralph_planner`
- `ralph_test_author`
- `ralph_worker`
- `ralph_reviewer`

Suggested sequence:

1. `ralph_triager`
2. `ralph_mapper`
3. `ralph_planner`
4. `ralph_test_author`
5. `ralph_worker`
6. `ralph_reviewer`

Parallelize only across disjoint read-only questions, independent review lenses, or truly disjoint implementation units.

## Landing and merge

When a unit passes:

1. re-run the narrow oracle
2. re-run tests
3. confirm the review artifact is current
4. `complete-unit`
5. land and record the commit through `land-unit`

If a merge conflict happens:

- record the conflicting files in the unit feedback
- do not discard the work
- re-run oracle and tests after rebase

## Supporting files

Load these when needed:

- `assets/plan.template.md`
- `assets/unit-contract.template.md`
- `assets/planner-output.template.json`
- `assets/executor-output.template.json`
- `assets/review-input.template.json`
- `assets/model-routing.template.md`
- `assets/review-rubric.template.md`
- `assets/feedback-log.template.md`

## CI / codex exec mode

For `codex exec` or CI:

- prefer `--json` when event logs matter
- prefer `--output-schema` when downstream tools parse the result
- keep sandbox at the minimum needed
- re-run the real test command after Codex finishes
- keep the repo-local artifacts as the source of truth
- when Ralph is the requested workflow, launch it with a prompt that explicitly says to
  continue the active unit in the current selected Ralph run until all mandatory gates pass or the user explicitly stops it
- if the execution surface allows the process to stay alive across turns, prefer that over
  manually restarting from scratch
