# Planning with Files -- Reference Guide

## Context Engineering Principles

### Principle 1: Filesystem as Memory
Context window is RAM -- volatile and limited. Filesystem is disk -- persistent and unlimited. Write important information to disk. Re-read before decisions. This is the foundational principle that makes planning-with-files work.

### Principle 2: Attention Refresh
After ~50 tool calls, models drift from original goals ("lost in the middle" effect). Re-reading task_plan.md places goals back in the attention window. This is why Rule 3 (Read Before Decide) exists and is non-negotiable.

### Principle 3: KV-Cache Optimization
Cached tokens cost 10x less than new tokens. Keep the beginning of context stable. Planning files provide stable, re-readable context that doesn't change shape between reads. This makes re-reading plans efficient.

### Principle 4: Preserve Failed Attempts
Logging errors prevents the model from retrying the same failed approach. The error log in progress.md serves as negative knowledge -- it tells the model what NOT to do, which is as valuable as knowing what to do.

### Principle 5: Introduce Variation
When stuck, mutate the approach rather than retrying. Change one variable at a time. Document what changed and why. This prevents hallucination drift where the model generates increasingly confident but incorrect solutions.

### Principle 6: Minimal Tool Sets Per Phase
Each phase should use the minimum tools needed:
- Phase 1 (Research): Read, Grep, Glob, WebSearch
- Phase 2 (Planning): Read, Write
- Phase 3 (Implementation): Write, Edit, Bash
- Phase 4 (Testing): Bash, Read, /codex
- Phase 5 (Delivery): Read

Fewer tools = more focused context = better results.

## The 2-Action Rule -- Detailed Rationale

Visual content (screenshots, browser pages, images, PDFs) does NOT persist in context after scrolling or navigating. If you view a page and then view another page, the first page's content may be gone from context entirely.

**The rule:** After every 2 search/view/browser/grep operations, IMMEDIATELY save key findings to `findings.md`.

**Why 2?** One operation may not yield enough to be worth saving. Two operations is the sweet spot -- enough to accumulate useful information, not so many that you risk losing earlier findings.

**What to save:**
- Exact file paths and line numbers
- Key function/class names discovered
- API endpoints or data structures found
- Error messages or unexpected behaviors observed
- Browser/visual content captured as text descriptions

## The 3-Strike Error Protocol -- Detailed

### Strike 1: Root-cause Diagnosis
- Read the error message carefully -- the full message, not just the summary
- Check if similar errors exist in progress.md error log
- Identify the actual root cause (not just the symptom)
- Apply a targeted, specific fix
- Log: what the error was, what you think caused it, what fix you applied

### Strike 2: Alternative Approach
- The targeted fix failed -- the problem is structural, not surface-level
- Try a fundamentally different method (different library, different algorithm, different tool)
- Document why Strike 1 failed and what Strike 2 changes
- Log: why Strike 1 didn't work, what different approach you're trying

### Strike 3: Strategic Rethink
- Re-read task_plan.md from the very top (Goal section)
- Question every assumption: Is the goal correct? Are constraints valid?
- Search for solutions: web, docs, codebase examples
- Consider whether the phase breakdown needs restructuring
- Log: what assumptions were wrong, what new approach you're considering

### Strike 4: Escalation
- Present ALL 3 attempts to the user with specific failure modes
- Include exact error messages
- Suggest remaining alternative approaches if any exist
- Ask for guidance, additional context, or constraint relaxation
- Do NOT attempt a 4th fix without user input

## Integration with CLAUDE.md Patterns

### Anti-Shortcut Rules Alignment
The user's CLAUDE.md has strict anti-shortcut rules. Planning-with-files reinforces these:
- "ALWAYS log intermediate results to files" -> findings.md and progress.md
- "NEVER skip a step" -> Phase checkboxes enforce sequential completion
- "ALWAYS verify outputs match expected schema" -> Test Results table in progress.md
- "NEVER batch multiple items" -> 2-Action Rule prevents batching discoveries

### Codex Subagent Integration
During Phase 4 (Testing & Verification):
1. Write implementation summary to `/tmp/codex_question.txt`
2. Include specific concerns from findings.md
3. Run: `cat /tmp/codex_question.txt | codex exec --full-auto -m gpt-5.2 -c model_reasoning_effort=high -o /tmp/codex_reply.txt`
4. Read and evaluate `/tmp/codex_reply.txt`
5. Log Codex findings in progress.md Test Results table

### Logging Requirements Alignment
The three planning files map to the existing logging structure:
- task_plan.md -> orchestration log (what should happen)
- findings.md -> intermediate results (what was discovered)
- progress.md -> execution log (what did happen)

## The 5-Question Reboot Test

This test verifies your context is solid. Run it when starting, resuming, or feeling lost:

| # | Question | Source | Action if blank |
|---|----------|--------|-----------------|
| 1 | Where am I? | Current phase in task_plan.md | Read task_plan.md |
| 2 | What's left? | Remaining unchecked phases | Read task_plan.md |
| 3 | What's the goal? | Goal statement in task_plan.md | Read task_plan.md |
| 4 | What did I learn? | findings.md content | Read findings.md |
| 5 | What's done? | Completed phases + progress.md | Read progress.md |

If you cannot answer all 5 questions, read the corresponding files before proceeding.

## When to Use This Pattern

**Use for:**
- Multi-step tasks (3+ steps)
- Research-heavy tasks
- Building/creating projects from scratch
- Debugging sessions spanning many tool calls
- Any task where you might lose track of the goal

**Skip for:**
- Simple questions ("what does this function do?")
- Single-file edits (one function change)
- Quick lookups (find a file, check a value)
- Tasks completable in under 5 tool calls
