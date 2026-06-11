#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "ralph-autonomous-loop" / "scripts"))
from ralph_project import ralph_context_dir

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

DANGEROUS_PATTERNS = [
    (re.compile(r"(^|\s)git\s+reset\s+--hard(\s|$)"), "Blocked destructive git reset."),
    (re.compile(r"(^|\s)git\s+checkout\s+--(\s|$)"), "Blocked destructive git checkout."),
    (re.compile(r"(^|\s)git\s+clean\s+-[^\n]*f[^\n]*(d|x)"), "Blocked destructive git clean."),
    (re.compile(r"(^|\s)rm\s+-rf\s+(\.|/|~/|\.\./)"), "Blocked destructive rm -rf command."),
]
LANDING_PATTERNS = [
    re.compile(r"(^|\s)git\s+commit(\s|$)"),
    re.compile(r"(^|\s)git\s+push(\s|$)"),
]


def check_satisfied(name: str, value: str) -> bool:
    if value == "pass":
        return True
    return name in SKIPPABLE_CHECKS and value == "skip"


def load_dag(cwd: Path) -> Optional[dict]:
    path = ralph_context_dir(
        cwd,
        fallback_to_legacy=os.environ.get("CODEX_THREAD_ID") is None or os.environ.get("RALPH_USE_LEGACY") == "1",
    ) / "dag.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def active_blockers(dag: dict) -> list[str]:
    units = dag.get("units", {})
    blockers = []
    for unit_id in dag.get("active_units", []):
        unit = units.get(unit_id)
        if not unit:
            continue
        missing = [
            name
            for name in CHECK_NAMES
            if not check_satisfied(name, unit.get("checks", {}).get(name, {}).get("value", "fail"))
        ]
        if missing:
            blockers.append(f"{unit_id}: {', '.join(missing)}")
    return blockers


def main() -> int:
    payload = json.load(sys.stdin)
    command = payload.get("tool_input", {}).get("command", "")
    if "RALPH_ALLOW_DESTRUCTIVE=1" in command:
        return 0

    for pattern, reason in DANGEROUS_PATTERNS:
        if pattern.search(command):
            print(json.dumps({"decision": "block", "reason": reason}))
            return 0

    cwd_value = payload.get("cwd") or payload.get("tool_input", {}).get("cwd")
    if not cwd_value:
        return 0

    dag = load_dag(Path(cwd_value).resolve())
    if not dag or not dag.get("loop_active"):
        return 0

    if any(pattern.search(command) for pattern in LANDING_PATTERNS):
        blockers = active_blockers(dag)
        if blockers:
            print(
                json.dumps(
                    {
                        "decision": "block",
                        "reason": "Blocked landing command while Ralph active units are incomplete: " + "; ".join(blockers),
                    }
                )
            )
            return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
