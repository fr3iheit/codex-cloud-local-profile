---
name: bet-dices-docset-sync
description: Keep the BET_DICES repo context docset aligned with README-level docs. Use when working in <BET_DICES repo root> and README.md, CSV_LLM_PARSING.md, live-odds/README.md, AGENTS.md, or CLAUDE.md changed, or when the user asks to refresh the docset/context bundle.
---

# BET_DICES docset sync

Use this skill only for `<BET_DICES repo root>`.

## Context entrypoint

- Start from `agent-docset/README.md`.
- Read `agent-docset/catalog.jsonl` first.
- Open only the linked generated docs or indexes relevant to the current task.

## Sync trigger

- Refresh the docset whenever one of these tracked context docs changes:
  - `README.md`
  - `CSV_LLM_PARSING.md`
  - `live-odds/README.md`
  - `AGENTS.md`
  - `CLAUDE.md`

## Workflow

1. Check status if needed:

```bash
python3 scripts/check_docset_sync.py --repo .
```

Use `--changed-path <tracked-file>` only when you need a trigger-style check right after a specific edit.

2. Rebuild:

```bash
python3 scripts/build_agent_docset.py --repo . --out agent-docset
```

3. Validate:

```bash
python3 scripts/verify_agent_docset.py --repo . --docset agent-docset
```

4. Do not finish the task with a stale `agent-docset/`.
