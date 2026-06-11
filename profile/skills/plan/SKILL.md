---
name: plan
description: >
  Manus-style persistent markdown planning for complex tasks.
  Creates task_plan.md, findings.md, progress.md as filesystem-based working memory.
  Use for any task requiring >5 tool calls, multi-step research, feature builds,
  or debugging sessions. Automatically recovers previous sessions.
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
---

# Planning with Files

Work like Manus: Use persistent markdown files as your "working memory on disk."

## Core Principle

```
Context Window = RAM (volatile, limited)
Filesystem     = Disk (persistent, unlimited)

-> Anything important gets written to disk immediately.
-> Re-read files before major decisions to refresh attention.
```

## Activation Protocol

### Step 1: Session Detection

Check if planning files already exist in the current working directory:

1. Look for `task_plan.md`, `findings.md`, `progress.md`
2. **ALL THREE exist** -> This is a **session recovery**. Read all three files, run the 5-Question Reboot Check (see Session Recovery below), summarize current state to the user, and ask what to do next.
3. **SOME exist** -> Warn the user. Ask whether to resume (create missing files) or start fresh (overwrite all).
4. **NONE exist** -> Proceed to Step 2.

### Step 2: Understand the Task

Ask the user: "What are we building/fixing/researching?"

Parse their response into:
- **Goal**: One clear sentence describing the end state
- **Scope**: What's in and out of scope
- **Constraints**: Timeline, tech stack, dependencies, special requirements

### Step 3: Create Planning Files

Read the templates from this skill's directory and adapt them to the user's task:

1. Read `templates/task_plan.md` -> Create `./task_plan.md` with phases specific to the user's task
2. Read `templates/findings.md` -> Create `./findings.md` with the requirements section filled in
3. Read `templates/progress.md` -> Create `./progress.md` with today's session started

**Important:** Planning files go in the **current project directory**, not the skill installation folder.

### Step 4: Confirm and Begin

Show the user:
- The phase breakdown from task_plan.md
- Ask which phase to start with (default: Phase 1)
- Begin execution following the Operating Rules below

## Operating Rules

These rules are NON-NEGOTIABLE throughout the entire planning session.

### Rule 1: Create Plan First
Never start a complex task without `task_plan.md`. Non-negotiable. If the user tries to skip planning, remind them that the plan is required.

### Rule 2: The 2-Action Rule
> After every 2 search/view/browser/grep operations, IMMEDIATELY save key findings to `findings.md`.

Do not wait. Do not batch. Visual/browser content is especially volatile -- capture it as text before it scrolls out of context. This prevents information loss when context compacts.

### Rule 3: Read Before Decide
Before ANY major decision (changing approach, starting a new phase, choosing between alternatives):
1. Re-read `task_plan.md` to refresh goals in the attention window
2. This counters the "lost in the middle" effect after ~50 tool calls

### Rule 4: Update After Completion
When completing any phase:
1. Mark phase checkbox `[x]` in `task_plan.md`
2. Update status: `in_progress` -> `complete`
3. Log what was done in `progress.md` (actions taken, files modified)
4. Move any open questions to the next phase

### Rule 5: Log ALL Errors
Every error, warning, or unexpected result gets logged immediately to:
- `task_plan.md` Errors Encountered table (brief)
- `progress.md` Error Log table (detailed with timestamp)

This builds knowledge and prevents repetition of the same mistakes.

### Rule 6: 3-Strike Error Protocol

```
STRIKE 1: Diagnose & Fix
  -> Read the error carefully
  -> Check progress.md error log for similar past failures
  -> Identify root cause
  -> Apply targeted fix

STRIKE 2: Alternative Approach
  -> Same error? The problem is structural, not surface-level
  -> Try a fundamentally different method
  -> Different tool? Different library? Different strategy?
  -> NEVER repeat the exact same failing action

STRIKE 3: Broader Rethink
  -> Re-read task_plan.md from the top
  -> Question assumptions: Is the goal correct? Are constraints valid?
  -> Search for solutions (web, docs, codebase)
  -> Consider updating the plan phases

AFTER 3 FAILURES: Escalate to User
  -> Explain what you tried (all 3 attempts)
  -> Share the specific errors
  -> Suggest alternative approaches if any remain
  -> Ask for guidance or constraint relaxation
```

### Rule 7: Never Repeat Failures
Before attempting any operation, check the Errors section of `progress.md`. If the same or similar approach has failed before, you MUST use a different strategy. Mutate your approach.

```
if action_failed:
    next_action != same_action
```

### Rule 8: Codex Verification
When reaching any Testing/Verification phase, invoke `/codex` for a second opinion on the implementation. This is NOT optional for medium and large tasks.

**Invocation pattern:**
1. Write context to `/tmp/codex_question.txt`:
   - What was implemented (summary + key file paths)
   - The acceptance criteria from task_plan.md
   - Specific concerns or areas of uncertainty
2. Run:
   ```bash
   cat /tmp/codex_question.txt | codex exec --full-auto -m gpt-5.4 -c model_reasoning_effort=xhigh -o /tmp/codex_reply.txt
   ```
3. Read `/tmp/codex_reply.txt` and evaluate critically
4. Log findings to `findings.md` under a "## Codex Verification" heading
5. For security-sensitive code, use the pro model instead:
   ```bash
   cat /tmp/codex_question.txt | codex exec --full-auto -m gpt-5.2-pro -c model_reasoning_effort=xhigh -o /tmp/codex_reply.txt
   ```

**Skip conditions:** Only skip Codex for trivial changes (config edits, typo fixes, single-line changes).

## Read vs Write Decision Matrix

| Situation | Action | Reason |
|-----------|--------|--------|
| Just wrote a file | DON'T read it | Content still in context |
| Viewed image/PDF/browser | Write findings NOW | Multimodal content doesn't persist |
| Browser returned data | Write to findings.md | Screenshots don't persist in context |
| Starting new phase | Read plan + findings | Re-orient if context stale |
| Error occurred | Read relevant file | Need current state to fix |
| Resuming after gap | Read ALL planning files | Recover full state |

## Session Recovery Protocol

When planning files already exist (resuming a session):

1. Read all three files: `task_plan.md`, `findings.md`, `progress.md`
2. Run the **5-Question Reboot Check**:

| Question | Answer Source |
|----------|--------------|
| Where am I? | Current phase in task_plan.md |
| What's left? | Remaining unchecked phases |
| What's the goal? | Goal statement in task_plan.md |
| What did I learn? | findings.md content |
| What's done? | Completed phases + progress.md |

3. Present the summary to the user
4. Ask what to work on next
5. Resume from the current phase

## Phase Bridge: Plan → Ralph Execution

When all phases are planned and the user wants autonomous execution, offer to convert the plan into a Ralph-compatible execution plan.

### Conversion Protocol

1. Read `task_plan.md` and extract all phases
2. For each phase, create a Ralph work unit:
   - `id`: kebab-case of the phase name
   - `name`: phase name as-is
   - `tier`: assign based on phase complexity:
     - Single file change → `trivial`
     - 1-3 files, single concern → `small`
     - Multi-file, new patterns → `medium`
     - Architecture change, cross-cutting → `large`
   - `deps`: derive from phase ordering (Phase N depends on Phase N-1 unless explicitly independent)
   - `description`: phase description from task_plan.md
   - `files`: extract file paths mentioned in the phase
   - `acceptance`: extract from phase success criteria or create from phase goals
3. Write the result to `.context/ralph-plan.yaml` in Ralph format:

```yaml
# Ralph Execution Plan
# Converted from: task_plan.md
# Generated: {ISO timestamp}

units:
  - id: {phase-kebab-id}
    name: "{Phase Name}"
    tier: {complexity}
    deps: [{dependency ids}]
    description: |
      {phase description}
    files:
      - {file paths}
    acceptance:
      - "{criterion}"
```

4. Tell the user: "Piano convertito in `.context/ralph-plan.yaml`. Esegui `/ralph` per lanciare l'esecuzione autonoma."

### When to Offer

- When the user says "esegui", "ralph", "lancia", "autonomo", or similar
- When all planning phases are defined and the user seems ready to execute
- When the user explicitly asks to convert the plan

### Integration Notes

- The plan's `findings.md` becomes context for Ralph's Research stages
- The plan's `progress.md` entries for completed phases map to `landed` status in Ralph's DAG
- If some phases are already `[x]` complete, mark those units as `landed` in the Ralph plan

## Anti-Patterns (DO NOT DO)

| Don't | Do Instead |
|-------|------------|
| Start executing without a plan | Create task_plan.md FIRST |
| State goals once and forget | Re-read plan before decisions |
| Hide errors and retry silently | Log errors to plan + progress |
| Stuff everything in context | Store large content in files |
| Repeat failed actions | Track attempts, mutate approach |
| Batch findings for later | Save after every 2 operations (2-Action Rule) |
| Create files in skill directory | Create files in your PROJECT directory |

## Additional Resources

For detailed context engineering principles, the complete 3-Strike Protocol breakdown, and integration notes with AGENTS.md patterns, see [reference.md](reference.md).

Templates for creating planning files are in the [templates/](templates/) directory:
- [templates/task_plan.md](templates/task_plan.md) -- Phase tracking template
- [templates/findings.md](templates/findings.md) -- Research storage template
- [templates/progress.md](templates/progress.md) -- Session logging template
