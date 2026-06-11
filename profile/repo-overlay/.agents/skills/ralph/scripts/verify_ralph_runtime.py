#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Optional


def run(cmd: list[str], cwd: Optional[Path] = None, *, thread_id: Optional[str] = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if thread_id is not None:
        env["CODEX_THREAD_ID"] = thread_id
    return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify the Ralph runtime redesign.")
    parser.add_argument("--codex-home", type=Path, required=True)
    parser.add_argument("--tmp-root", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    codex_home = args.codex_home.expanduser().resolve()
    os.environ["CODEX_HOME"] = str(codex_home)
    tmp_root = args.tmp_root.expanduser().resolve()
    workspace = tmp_root / "workspace"
    thread_id = "runtime-verify-thread"
    os.environ["CODEX_THREAD_ID"] = thread_id
    errors: list[str] = []

    if tmp_root.exists():
        shutil.rmtree(tmp_root)
    workspace.mkdir(parents=True, exist_ok=True)
    run(["git", "init"], cwd=workspace)

    bootstrap = codex_home / "skills" / "ralph-autonomous-loop" / "scripts" / "bootstrap_ralph.py"
    state = codex_home / "skills" / "ralph-autonomous-loop" / "scripts" / "ralph_state.py"
    skill = codex_home / "skills" / "ralph-autonomous-loop" / "SKILL.md"
    start_hook = codex_home / "hooks" / "session_start_context.py"
    stop_hook = codex_home / "hooks" / "stop_continue.py"

    require(bootstrap.exists(), f"missing bootstrap script: {bootstrap}", errors)
    require(state.exists(), f"missing state script: {state}", errors)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    result = run([sys.executable, str(bootstrap)], cwd=workspace, thread_id=thread_id)
    require(result.returncode == 0, f"bootstrap failed: {result.stderr.strip() or result.stdout.strip()}", errors)

    context_path = workspace / ".context" / "ralph" / "runs" / thread_id
    dag_path = context_path / "dag.json"
    project_path = context_path / "project.json"
    require(dag_path.exists(), f"missing dag.json after bootstrap: {dag_path}", errors)
    require(project_path.exists(), f"missing project.json after bootstrap: {project_path}", errors)
    require(not (workspace / ".context" / "ralph" / "dag.json").exists(), "bootstrap should not create shared legacy dag for threaded runs", errors)

    if dag_path.exists():
        dag = json.loads(dag_path.read_text(encoding="utf-8"))
        require(isinstance(dag.get("units"), dict), "dag.json does not expose a units map", errors)
        require(bool(dag.get("project_id")), "dag.json missing project_id", errors)
        require(str(workspace) == dag.get("project_root"), "dag.json project_root should be the git project root", errors)

    if project_path.exists():
        project = json.loads(project_path.read_text(encoding="utf-8"))
        registry_dir = Path(project.get("project_registry_dir", ""))
        memory_path = Path(project.get("project_memory_path", ""))
        require(registry_dir.exists(), f"project registry missing: {registry_dir}", errors)
        require(memory_path.exists(), f"project memory missing: {memory_path}", errors)

    result = run([sys.executable, str(state), "begin", "unit-a", "--title", "Unit A", "--tier", "small"], cwd=workspace, thread_id=thread_id)
    require(result.returncode == 0, f"begin unit-a failed: {result.stderr.strip() or result.stdout.strip()}", errors)
    nested = workspace / "nested"
    nested.mkdir()
    result = run([sys.executable, str(state), "status"], cwd=nested, thread_id=thread_id)
    require(result.returncode == 0, f"status from nested project dir failed: {result.stderr.strip() or result.stdout.strip()}", errors)
    require(f"DAG file: {dag_path}" in result.stdout, "nested cwd should use project-root .context/ralph DAG", errors)
    result = run(
        [
            sys.executable,
            str(state),
            "add-unit",
            "unit-b",
            "--title",
            "Unit B",
            "--tier",
            "small",
            "--deps",
            "unit-a",
        ],
        cwd=workspace,
        thread_id=thread_id,
    )
    require(result.returncode == 0, f"add-unit unit-b failed: {result.stderr.strip() or result.stdout.strip()}", errors)

    result = run([sys.executable, str(state), "add-unit", "unit-c", "--title", "Blocked Unit", "--tier", "small"], cwd=workspace, thread_id=thread_id)
    require(result.returncode == 0, f"add-unit unit-c failed: {result.stderr.strip() or result.stdout.strip()}", errors)
    result = run([sys.executable, str(state), "block", "blocked by verifier", "--unit", "unit-c"], cwd=workspace, thread_id=thread_id)
    require(result.returncode == 0, f"block unit-c failed: {result.stderr.strip() or result.stdout.strip()}", errors)
    result = run([sys.executable, str(state), "status"], cwd=workspace, thread_id=thread_id)
    require("unit-c: status=blocked" in result.stdout, "blocked unit-c should remain blocked after status normalization", errors)
    result = run([sys.executable, str(state), "ready"], cwd=workspace, thread_id=thread_id)
    require("unit-c" not in result.stdout, "ready units output should not include blocked unit-c", errors)

    unit_a_dir = context_path / "units" / "unit-a"
    unit_b_dir = context_path / "units" / "unit-b"
    require((unit_a_dir / "state.json").exists(), "unit-a state.json missing", errors)
    require((unit_a_dir / "planner-output.json").exists(), "unit-a planner-output.json missing", errors)
    require((unit_a_dir / "executor-output.json").exists(), "unit-a executor-output.json missing", errors)
    require((unit_a_dir / "review-input.json").exists(), "unit-a review-input.json missing", errors)
    require((unit_b_dir / "state.json").exists(), "unit-b state.json missing", errors)

    result = run(
        [
            sys.executable,
            str(state),
            "run-check",
            "unit-a",
            "contract_written",
            "--command",
            "python3 -c 'print(\"ok\")'",
            "--expect-exit",
            "0",
        ],
        cwd=workspace,
    )
    require(result.returncode == 0, f"artifact-backed run-check failed: {result.stderr.strip() or result.stdout.strip()}", errors)

    result = run([sys.executable, str(state), "check", "review_complete", "pass"], cwd=workspace)
    require(result.returncode != 0, "legacy self-reported check unexpectedly still passes without evidence", errors)

    result = run(
        [
            sys.executable,
            str(state),
            "check",
            "review_complete",
            "pass",
            "--unit",
            "unit-a",
            "--artifact-path",
            str(unit_a_dir / "review-input.json"),
            "--summary",
            "This should fail because review-input is not a verdict artifact",
        ],
        cwd=workspace,
    )
    require(result.returncode != 0, "review_complete unexpectedly accepts review-input.json as a verdict artifact", errors)

    result = run(
        [
            sys.executable,
            str(state),
            "run-check",
            "unit-a",
            "tests_written",
            "--command",
            "python3 -c 'print(\"tests\")'",
            "--expect-exit",
            "0",
        ],
        cwd=workspace,
    )
    require(result.returncode == 0, f"tests_written run-check failed: {result.stderr.strip() or result.stdout.strip()}", errors)

    result = run(
        [
            sys.executable,
            str(state),
            "run-check",
            "unit-a",
            "baseline_recorded",
            "--command",
            "python3 -c 'import sys; sys.exit(1)'",
            "--expect-exit",
            "1",
        ],
        cwd=workspace,
    )
    require(result.returncode == 0, f"baseline_recorded run-check failed: {result.stderr.strip() or result.stdout.strip()}", errors)

    result = run(
        [
            sys.executable,
            str(state),
            "run-check",
            "unit-a",
            "implementation_complete",
            "--command",
            "python3 -c 'print(\"implementation\")'",
            "--expect-exit",
            "0",
        ],
        cwd=workspace,
    )
    require(result.returncode == 0, f"implementation_complete run-check failed: {result.stderr.strip() or result.stdout.strip()}", errors)

    result = run(
        [
            sys.executable,
            str(state),
            "run-check",
            "unit-a",
            "targeted_checks_passed",
            "--command",
            "python3 -c 'print(\"targeted\")'",
            "--expect-exit",
            "0",
        ],
        cwd=workspace,
    )
    require(result.returncode == 0, f"targeted_checks_passed run-check failed: {result.stderr.strip() or result.stdout.strip()}", errors)

    result = run(
        [
            sys.executable,
            str(state),
            "check",
            "review_complete",
            "skip",
            "--unit",
            "unit-a",
        ],
        cwd=workspace,
    )
    require(result.returncode == 0, f"review_complete skip setup failed: {result.stderr.strip() or result.stdout.strip()}", errors)

    result = run(
        [
            sys.executable,
            str(state),
            "complete-unit",
            "--unit",
            "unit-a",
        ],
        cwd=workspace,
    )
    require(result.returncode != 0, "complete-unit unexpectedly allows mandatory skip values", errors)

    review_verdict = unit_a_dir / "review-verdict.md"
    review_verdict.write_text("Verdict: PASS\nNotes: validator-created review artifact\n", encoding="utf-8")

    result = run(
        [
            sys.executable,
            str(state),
            "check",
            "review_complete",
            "pass",
            "--unit",
            "unit-a",
            "--artifact-path",
            str(review_verdict),
            "--summary",
            "Review payload present before viability gate",
        ],
        cwd=workspace,
    )
    require(result.returncode == 0, f"review_complete pre-viability artifact check failed: {result.stderr.strip() or result.stdout.strip()}", errors)

    result = run(
        [
            sys.executable,
            str(state),
            "complete-unit",
            "--unit",
            "unit-a",
        ],
        cwd=workspace,
    )
    require(result.returncode != 0, "complete-unit unexpectedly succeeds without viability gate evidence", errors)

    result = run(
        [
            sys.executable,
            str(state),
            "check",
            "viability_gate_passed",
            "skip",
            "--unit",
            "unit-a",
            "--summary",
            "Generic runtime unit with no external dataset viability risk",
        ],
        cwd=workspace,
    )
    require(result.returncode == 0, f"viability_gate_passed skip setup failed: {result.stderr.strip() or result.stdout.strip()}", errors)

    result = run(
        [
            sys.executable,
            str(state),
            "check",
            "review_complete",
            "pass",
            "--unit",
            "unit-a",
            "--artifact-path",
            str(review_verdict),
            "--summary",
            "Review payload present after viability gate",
        ],
        cwd=workspace,
    )
    require(result.returncode == 0, f"review_complete artifact check failed: {result.stderr.strip() or result.stdout.strip()}", errors)

    result = run(
        [
            sys.executable,
            str(state),
            "complete-unit",
            "--unit",
            "unit-a",
        ],
        cwd=workspace,
    )
    require(result.returncode == 0, f"complete-unit failed after viability gate skip: {result.stderr.strip() or result.stdout.strip()}", errors)

    result = run([sys.executable, str(state), "ready"], cwd=workspace)
    require(result.returncode == 0, f"ready command failed: {result.stderr.strip() or result.stdout.strip()}", errors)
    require("unit-a" not in result.stdout, "ready units output should not include completed unit-a", errors)
    require("unit-b" not in result.stdout, "ready units output should not include dependent unit-b before landing unit-a", errors)

    result = run([sys.executable, str(state), "land-unit", "unit-a", "--commit", "deadbeef"], cwd=workspace)
    require(result.returncode == 0, f"land-unit unit-a failed: {result.stderr.strip() or result.stdout.strip()}", errors)
    result = run([sys.executable, str(state), "ready"], cwd=workspace)
    require("unit-b" in result.stdout, "unit-b should become ready after unit-a lands", errors)

    skill_text = skill.read_text(encoding="utf-8")
    require("<skill-root>/scripts/ralph_state.py" not in skill_text, "SKILL.md still hardcodes source-machine state-script path", errors)
    require("Parallelization Layers" in skill_text, "SKILL.md missing explicit parallelization guidance", errors)
    require("GPT-5.4-Mini" in skill_text, "SKILL.md missing mini routing guidance", errors)
    require("## Viability gate" in skill_text, "SKILL.md missing viability gate guidance", errors)

    for hook_path in (start_hook, stop_hook):
        hook_text = hook_path.read_text(encoding="utf-8")
        require("<skill-root>/scripts/ralph_state.py" not in hook_text, f"{hook_path.name} still hardcodes source-machine state-script path", errors)

    if errors:
        print("Ralph runtime verification failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Ralph runtime verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
