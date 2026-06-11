#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "ralph-autonomous-loop" / "scripts"))
from ralph_project import project_root, ralph_context_dir

CHECK_NAMES = [
    "contract_written",
    "tests_written",
    "baseline_recorded",
    "viability_gate_passed",
    "implementation_complete",
    "targeted_checks_passed",
    "review_complete",
]
SKIPPABLE_CHECKS = {"viability_gate_passed"}


def check_satisfied(name: str, value: str) -> bool:
    if value == "pass":
        return True
    return name in SKIPPABLE_CHECKS and value == "skip"


def state_script_command() -> str:
    codex_home = Path(__file__).resolve().parents[1]
    state_script = codex_home / "skills" / "ralph-autonomous-loop" / "scripts" / "ralph_state.py"
    return f'python3 "{state_script}"'


def missing_checks(unit: dict) -> list[str]:
    checks = unit.get("checks", {})
    return [
        name
        for name in CHECK_NAMES
        if not check_satisfied(name, checks.get(name, {}).get("value", "fail"))
    ]


def main() -> int:
    payload = json.load(sys.stdin)
    if payload.get("stop_hook_active"):
        print(json.dumps({"continue": True}))
        return 0

    cwd = Path(payload["cwd"]).resolve()
    root = project_root(cwd)
    dag_path = ralph_context_dir(
        root,
        fallback_to_legacy=os.environ.get("CODEX_THREAD_ID") is None or os.environ.get("RALPH_USE_LEGACY") == "1",
    ) / "dag.json"
    if not dag_path.exists():
        print(json.dumps({"continue": True}))
        return 0

    try:
        dag = json.loads(dag_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print(json.dumps({"continue": True}))
        return 0

    if not dag.get("loop_active"):
        print(json.dumps({"continue": True}))
        return 0

    units = dag.get("units", {})
    active_units = [unit_id for unit_id in dag.get("active_units", []) if unit_id in units]
    blockers = []
    for unit_id in active_units:
        unit = units[unit_id]
        missing = missing_checks(unit)
        if missing:
            blockers.append(f"{unit_id}: {', '.join(missing)}")

    if not blockers:
        print(json.dumps({"continue": True}))
        return 0

    reason = (
        "Ralph still has active units with incomplete evidence-backed checks. "
        f"Blockers: {'; '.join(blockers)}. "
        f"Update the loop with `{state_script_command()}` and continue."
    )
    print(json.dumps({"decision": "block", "reason": reason}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
