---
name: ralphone
description: Ralphone is a parallel v2 Ralph-style Codex loop for complex builds, fixes, refactors, and debugging tasks that need contracts, pre-code oracles, durable artifacts, scope guards, and compact resumable progress state. It is intentionally separate from the existing ralph skill.
metadata:
  short-description: Parallel v2 autonomous loop with compact progress and scope guard
---

# Ralphone Autonomous Loop

Use `ralphone` when the task is non-trivial and benefits from explicit contracts,
failing checks before code, structured state, and review gates. Ralphone is parallel
to Ralph, not a replacement or migration layer.

In command examples, replace `<skill-root>` with the directory that contains this
`SKILL.md`.

## Isolation Contract

Ralphone must never use Ralph's state paths or env vars.

- Skill root: `<skill-root>`
- Run state: `.context/ralphone/runs/<run-id>/...`
- Project memory: `$CODEX_HOME/ralphone/projects/<project-id>/...`
- Env vars: `RALPHONE_RUN_ID`, `RALPHONE_USE_LEGACY`
- Scripts: `bootstrap_ralphone.py`, `ralphone_state.py`, `ralphone_project.py`

Do not modify `.context/ralph`, `$CODEX_HOME/ralph`, or Ralph hooks unless the user
explicitly asks for Ralph itself to change.

## Core Loop

1. Assign a tier: `trivial`, `small`, `medium`, or `large`.
2. Bootstrap:

```bash
python3 "<skill-root>/scripts/bootstrap_ralphone.py"
```

3. Start the unit:

```bash
python3 "<skill-root>/scripts/ralphone_state.py" begin <unit-id> --title "<title>" --tier <tier>
```

4. Fill the unit contract and planner/review payloads under:

```text
.context/ralphone/runs/<run-id>/units/<unit-id>/
```

Before implementation, translate the user's request into a real Definition of
Done, not a structural proxy. The contract must capture the user's actual
success function: what a user or reader should understand, be able to do, or
prove after the artifact is finished.

For user-facing explainers, docs, websites, decks, onboarding artifacts, or
other knowledge surfaces, a valid DoD must optimize for zero-context
comprehension. At minimum, include:

- a **blind-reader oracle**: a reviewer who sees only the rendered artifact and
  reports what a new reader would understand, what remains confusing, and a
  clarity score
- a **code-aware adjudicator oracle**: a second reviewer with access to the
  source/code/docs who checks whether the blind reader's understanding is
  actually correct, complete enough, and free of misleading simplifications

Do not treat file existence, section coverage, clean rendering, or deployability
as sufficient DoD evidence for these artifacts.

5. Record the baseline failure before implementation:

```bash
python3 "<skill-root>/scripts/ralphone_state.py" run-check <unit-id> baseline_recorded --command "<oracle expected to fail>" --expect-exit <nonzero>
```

6. Configure and run the scope guard before completion:

```bash
python3 "<skill-root>/scripts/ralphone_state.py" set-scope <unit-id> --allowed path/or/dir --forbidden dangerous/path
python3 "<skill-root>/scripts/ralphone_state.py" scope-check <unit-id>
```

7. Run targeted checks and review. Complete only when all mandatory checks pass and
review is accepted.

## Canonical State

Treat JSON/JSONL as the source of truth and Markdown as a human view.

- `dag.json`: unit graph, active units, dependency state
- `units/<unit-id>/state.json`: per-unit status, checks, review state
- `artifact-index.json`: registered check/review/compaction artifacts
- `trace.jsonl`: append-only state-change events
- `progress.md`: compact current dashboard, regenerated with `compact-progress`

For long runs, keep `progress.md` short:

```bash
python3 "<skill-root>/scripts/ralphone_state.py" compact-progress
```

`compact-progress` archives the previous progress file under `logs/`, regenerates
the current dashboard from canonical state, and refuses to write if active units,
blocked units, or red gates would disappear from the summary.

## Gates

Mandatory checks:

- `contract_written`
- `tests_written`
- `baseline_recorded`
- `viability_gate_passed` (`skip` allowed only with a reason)
- `implementation_complete`
- `scope_guard_passed`
- `targeted_checks_passed`
- `review_complete`

For medium units use self-review plus independent review. For large units use an
additional challenge/re-review pass. Reviewers should see contract, oracle evidence,
test evidence, scope evidence, diff summary, and no implementer reasoning.

## More Detail

Load `reference/ralphone-full-rules.md` only when the compact rules above are not
enough for the task. Supporting templates live in `assets/`.
