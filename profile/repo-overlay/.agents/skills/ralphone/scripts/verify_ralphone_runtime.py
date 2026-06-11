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


def run(cmd: list[str], cwd: Optional[Path] = None, *, env: Optional[dict[str, str]] = None) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run(cmd, cwd=cwd, env=merged, capture_output=True, text=True)


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify the Ralphone v2 runtime.")
    parser.add_argument("--codex-home", type=Path, required=True)
    parser.add_argument("--tmp-root", type=Path, required=True)
    return parser.parse_args()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    args = parse_args()
    skill_root = Path(__file__).resolve().parents[1]
    bootstrap = skill_root / "scripts" / "bootstrap_ralphone.py"
    state = skill_root / "scripts" / "ralphone_state.py"
    skill = skill_root / "SKILL.md"
    scripts = [
        skill_root / "scripts" / "bootstrap_ralphone.py",
        skill_root / "scripts" / "ralphone_project.py",
        skill_root / "scripts" / "ralphone_state.py",
    ]

    codex_home = args.codex_home.expanduser().resolve()
    tmp_root = args.tmp_root.expanduser().resolve()
    workspace = tmp_root / "workspace"
    thread_id = "ralphone-runtime-verify-thread"
    env = {
        "CODEX_HOME": str(codex_home),
        "CODEX_THREAD_ID": thread_id,
    }
    errors: list[str] = []

    if tmp_root.exists():
        shutil.rmtree(tmp_root)
    if codex_home.exists():
        shutil.rmtree(codex_home)
    workspace.mkdir(parents=True, exist_ok=True)
    codex_home.mkdir(parents=True, exist_ok=True)

    require(bootstrap.exists(), f"missing bootstrap script: {bootstrap}", errors)
    require(state.exists(), f"missing state script: {state}", errors)
    require(skill.exists(), f"missing skill file: {skill}", errors)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    result = run(["git", "init"], cwd=workspace)
    require(result.returncode == 0, f"git init failed: {result.stderr.strip()}", errors)

    result = run([sys.executable, str(bootstrap)], cwd=workspace, env=env)
    require(result.returncode == 0, f"bootstrap failed: {result.stderr.strip() or result.stdout.strip()}", errors)

    context_path = workspace / ".context" / "ralphone" / "runs" / thread_id
    dag_path = context_path / "dag.json"
    progress_path = context_path / "progress.md"
    artifact_index_path = context_path / "artifact-index.json"
    trace_path = context_path / "trace.jsonl"
    require(dag_path.exists(), f"missing dag.json after bootstrap: {dag_path}", errors)
    require(progress_path.exists(), f"missing progress.md after bootstrap: {progress_path}", errors)
    require(artifact_index_path.exists(), f"missing artifact-index.json after bootstrap: {artifact_index_path}", errors)
    require(trace_path.exists(), f"missing trace.jsonl after bootstrap: {trace_path}", errors)
    require(not (workspace / ".context" / "ralph").exists(), "Ralphone bootstrap wrote a .context/ralph tree", errors)
    require(not (workspace / ".context" / "ralphone" / "dag.json").exists(), "bootstrap should not create shared legacy dag for threaded runs", errors)
    require((codex_home / "ralphone" / "projects").exists(), "Ralphone project memory was not created under CODEX_HOME/ralphone", errors)
    require(not (codex_home / "ralph").exists(), "Ralphone wrote CODEX_HOME/ralph", errors)

    if dag_path.exists():
        dag = read_json(dag_path)
        require(dag.get("run_id") == thread_id, "dag.json run_id does not match CODEX_THREAD_ID", errors)
        require(str(workspace) == dag.get("project_root"), "dag.json project_root should be the git root", errors)

    result = run([sys.executable, str(state), "begin", "unit-a", "--title", "Unit A", "--tier", "medium"], cwd=workspace, env=env)
    require(result.returncode == 0, f"begin failed: {result.stderr.strip() or result.stdout.strip()}", errors)

    result = run([sys.executable, str(state), "compact-progress"], cwd=workspace, env=env)
    require(result.returncode == 0, f"compact-progress failed: {result.stderr.strip() or result.stdout.strip()}", errors)
    compacted = progress_path.read_text(encoding="utf-8") if progress_path.exists() else ""
    require("unit-a" in compacted, "compacted progress lost active unit-a", errors)
    require("baseline_recorded" in compacted, "compacted progress lost red gate names", errors)
    require("artifact-index.json" in compacted and "trace.jsonl" in compacted, "compacted progress omits canonical state pointers", errors)
    logs = list((context_path / "logs").glob("progress-*.md"))
    require(bool(logs), "compact-progress did not archive the previous progress file", errors)

    result = run([sys.executable, str(state), "scope-check", "unit-a"], cwd=workspace, env=env)
    require(result.returncode != 0, "scope-check unexpectedly passed before set-scope", errors)

    result = run(
        [sys.executable, str(state), "set-scope", "unit-a", "--allowed", "src", "--forbidden", "forbidden", "--non-goal", "do not edit docs"],
        cwd=workspace,
        env=env,
    )
    require(result.returncode == 0, f"set-scope failed: {result.stderr.strip() or result.stdout.strip()}", errors)
    (workspace / "src").mkdir(exist_ok=True)
    (workspace / "src" / "ok.txt").write_text("ok\n", encoding="utf-8")
    result = run([sys.executable, str(state), "scope-check", "unit-a"], cwd=workspace, env=env)
    require(result.returncode == 0, f"scope-check should pass for allowed file: {result.stderr.strip() or result.stdout.strip()}", errors)

    (workspace / "forbidden").mkdir(exist_ok=True)
    (workspace / "forbidden" / "bad.txt").write_text("bad\n", encoding="utf-8")
    result = run([sys.executable, str(state), "scope-check", "unit-a"], cwd=workspace, env=env)
    require(result.returncode != 0, "scope-check unexpectedly allowed a forbidden file", errors)
    shutil.rmtree(workspace / "forbidden")
    result = run([sys.executable, str(state), "scope-check", "unit-a"], cwd=workspace, env=env)
    require(result.returncode == 0, f"scope-check did not recover after forbidden file removal: {result.stderr.strip() or result.stdout.strip()}", errors)

    checks = [
        ("contract_written", "python3 -c 'print(\"contract\")'", 0),
        ("tests_written", "python3 -c 'print(\"tests\")'", 0),
        ("baseline_recorded", "python3 -c 'import sys; sys.exit(1)'", 1),
        ("implementation_complete", "python3 -c 'print(\"implementation\")'", 0),
        ("targeted_checks_passed", "python3 -c 'print(\"targeted\")'", 0),
    ]
    for check_name, command, expected in checks:
        result = run(
            [sys.executable, str(state), "run-check", "unit-a", check_name, "--command", command, "--expect-exit", str(expected)],
            cwd=workspace,
            env=env,
        )
        require(result.returncode == 0, f"{check_name} failed: {result.stderr.strip() or result.stdout.strip()}", errors)

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
            "No external data viability risk.",
        ],
        cwd=workspace,
        env=env,
    )
    require(result.returncode == 0, f"viability skip failed: {result.stderr.strip() or result.stdout.strip()}", errors)

    review_verdict = context_path / "units" / "unit-a" / "review-verdict.md"
    review_verdict.write_text("Verdict: PASS\nNotes: verifier-created review artifact\n", encoding="utf-8")
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
            "Verifier review artifact accepted.",
        ],
        cwd=workspace,
        env=env,
    )
    require(result.returncode == 0, f"review_complete failed: {result.stderr.strip() or result.stdout.strip()}", errors)

    result = run([sys.executable, str(state), "complete-unit", "--unit", "unit-a"], cwd=workspace, env=env)
    require(result.returncode == 0, f"complete-unit failed: {result.stderr.strip() or result.stdout.strip()}", errors)

    index = read_json(artifact_index_path) if artifact_index_path.exists() else {}
    kinds = {item.get("kind") for item in index.get("artifacts", [])}
    require({"check", "scope", "progress-archive", "progress-current"}.issubset(kinds), "artifact-index.json missing required artifact kinds", errors)
    trace_text = trace_path.read_text(encoding="utf-8") if trace_path.exists() else ""
    require("check_updated" in trace_text and "artifact_registered" in trace_text, "trace.jsonl missing expected state events", errors)

    skill_lines = skill.read_text(encoding="utf-8").splitlines()
    require(len(skill_lines) <= 130, "SKILL.md is not compact", errors)
    require("reference/ralphone-full-rules.md" in "\n".join(skill_lines), "SKILL.md does not point to reference rules", errors)

    for script in scripts:
        text = script.read_text(encoding="utf-8")
        require("RALPH_" not in text, f"{script.name} still references RALPH_ env vars", errors)
        require('".context" / "ralph"' not in text, f"{script.name} still references .context/ralph path construction", errors)
        require(".context/ralph/" not in text, f"{script.name} still references .context/ralph/", errors)
        require("from ralph_project" not in text, f"{script.name} imports ralph_project", errors)
        require("ralph-autonomous-loop" not in text, f"{script.name} references the Ralph skill root", errors)

    require(not (workspace / ".context" / "ralph").exists(), "Verifier workspace ended with .context/ralph present", errors)
    require(not (codex_home / "ralph").exists(), "Verifier CODEX_HOME ended with ralph registry present", errors)

    if errors:
        print("Ralphone runtime verification failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Ralphone runtime verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
