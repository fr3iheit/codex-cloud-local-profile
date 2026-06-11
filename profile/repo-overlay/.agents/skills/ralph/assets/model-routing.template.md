# Ralph Model Routing

## Default

- Start with the simplest model that can plausibly succeed.
- Escalate only when the current task is ambiguous, architecture-heavy, or evidence is conflicting.

## GPT-5.4-Mini

- Use for codebase mapping, classification, prompt linting, oracle candidate generation, source gathering, and review pretriage.
- Thinking:
  - `low` for inventories, classification, formatting, checklist validation
  - `medium` for mapping, oracle selection, bounded synthesis

## GPT-5.4

- Use for implementation, debugging, and primary review.
- Thinking:
  - `high` for most implementation and reviewer work
  - `xhigh` for architecture review, ambiguous root-cause analysis, and final challenge review

## Parallelization Rule

- Do not fan out implementation work unless write surfaces are disjoint.
- Prefer `gpt-5.4-mini` for parallel read-only exploration.
