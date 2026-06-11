---
name: "source-command-plan-status"
description: "Show current planning status from task_plan.md at a glance."
---

# source-command-plan-status

Use this skill when the user asks to run the migrated source command `plan-status`.

## Command Template

Check the current state of file-based planning in the working directory:

## Steps

1. Look for `task_plan.md`, `findings.md`, `progress.md` in the current directory
2. If NONE exist, tell the user: "No planning session found. Run `/plan` to start one."
3. If they exist, read `task_plan.md` and display a compact status:

## Output Format

```
Planning Status

Current: Phase {N} of {total} ({percent}% complete)
Goal: {goal from task_plan.md}

  [done] Phase 1: {name}
  [ACTIVE] Phase 2: {name}  <-- you are here
  [ ] Phase 3: {name}
  ...

Files: task_plan.md [ok] | findings.md [ok] | progress.md [ok]
Errors logged: {count from Errors table}
Decisions made: {count from Decisions table}
```

## Rules

- Keep output to 15 lines maximum
- This is a quick status check, not a full report
- Do NOT modify any files
- Show just enough to answer "where am I?" without re-reading all files
- Use the actual phase names and statuses from the file
