#!/usr/bin/env python3
from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import json
import os
import re
import shutil
from datetime import datetime, timezone
from json import JSONDecodeError, JSONDecoder
from pathlib import Path
import subprocess
import sys
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ralph_project import (
    ensure_project_registry,
    ralph_base_context_dir,
    ralph_context_dir,
    selected_run_id,
    write_local_project_pointer,
)

CHECK_NAMES = [
    "contract_written",
    "tests_written",
    "baseline_recorded",
    "viability_gate_passed",
    "implementation_complete",
    "targeted_checks_passed",
    "review_complete",
]
CHECK_VALUES = {"pass", "fail", "skip"}
TERMINAL_STATUSES = {"blocked", "complete", "landed"}
MANDATORY_CHECKS = list(CHECK_NAMES)
SKIPPABLE_CHECKS = {"viability_gate_passed"}
REVIEW_INVALIDATING_CHECKS = {
    "tests_written",
    "baseline_recorded",
    "viability_gate_passed",
    "implementation_complete",
    "targeted_checks_passed",
}
REVIEW_STATUSES = {"pending", "accepted", "rejected", "blocked"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def context_dir() -> Path:
    return ralph_context_dir(Path.cwd())


def units_dir() -> Path:
    return context_dir() / "units"


def dag_path() -> Path:
    return context_dir() / "dag.json"


def status_path() -> Path:
    return context_dir() / "status.json"


def skill_root() -> Path:
    return Path(__file__).resolve().parents[1]


def ensure_context_dirs() -> None:
    context_dir().mkdir(parents=True, exist_ok=True)
    units_dir().mkdir(parents=True, exist_ok=True)
    write_local_project_pointer(context_dir(), Path.cwd())


@contextmanager
def dag_lock():
    ensure_context_dirs()
    lock_path = context_dir() / ".state.lock"
    with lock_path.open("w", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def safe_load_json(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except JSONDecodeError:
        decoder = JSONDecoder()
        parsed, _ = decoder.raw_decode(text)
        if isinstance(parsed, dict):
            return parsed
        raise


def default_check_state() -> dict[str, Any]:
    return {
        name: {
            "value": "fail",
            "artifact_path": None,
            "command": None,
            "exit_code": None,
            "summary": "",
            "updated_at": None,
        }
        for name in CHECK_NAMES
    }


def default_review_state() -> dict[str, Any]:
    return {
        "status": "pending",
        "verdict": None,
        "artifact_path": None,
        "updated_at": None,
        "summary": "",
    }


def check_satisfied(name: str, value: str) -> bool:
    if value == "pass":
        return True
    return name in SKIPPABLE_CHECKS and value == "skip"


def default_unit(unit_id: str, title: str = "", tier: str = "small", deps: Optional[list[str]] = None) -> dict[str, Any]:
    timestamp = now_iso()
    return {
        "id": unit_id,
        "title": title,
        "tier": tier,
        "deps": deps or [],
        "status": "pending",
        "checks": default_check_state(),
        "review": default_review_state(),
        "notes": [],
        "artifacts": {},
        "commit": None,
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def default_dag() -> dict[str, Any]:
    timestamp = now_iso()
    project = ensure_project_registry(Path.cwd())
    run_id = selected_run_id(Path.cwd())
    return {
        "version": 2,
        "project_id": project["project_id"],
        "project_root": project["project_root"],
        "run_id": run_id,
        "loop_active": False,
        "allow_stop": True,
        "active_units": [],
        "units": {},
        "notes": [],
        "updated_at": timestamp,
    }


def unit_dir(unit_id: str) -> Path:
    return units_dir() / unit_id


def unit_state_path(unit_id: str) -> Path:
    return unit_dir(unit_id) / "state.json"


def unit_artifacts_dir(unit_id: str) -> Path:
    return unit_dir(unit_id) / "artifacts"


def active_units(dag: dict[str, Any]) -> list[str]:
    return [unit_id for unit_id in dag.get("active_units", []) if unit_id in dag.get("units", {})]


def ensure_review_state(unit: dict[str, Any]) -> dict[str, Any]:
    review = unit.setdefault("review", {})
    for key, value in default_review_state().items():
        review.setdefault(key, value)
    if review.get("status") not in REVIEW_STATUSES:
        review["status"] = "pending"
    return review


def parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def add_note(container: dict[str, Any], message: str) -> None:
    container.setdefault("notes", []).append({"timestamp": now_iso(), "message": message})


def load_legacy_status() -> Optional[dict[str, Any]]:
    path = status_path()
    if not path.exists():
        return None
    return safe_load_json(path)


def migrate_from_legacy(legacy: dict[str, Any]) -> dict[str, Any]:
    dag = default_dag()
    dag["loop_active"] = bool(legacy.get("loop_active"))
    dag["allow_stop"] = bool(legacy.get("allow_stop", True))
    dag["notes"] = legacy.get("notes", [])
    current = legacy.get("current_unit") or {}
    current_id = current.get("id")
    if current_id:
        unit = default_unit(current_id, current.get("title", ""))
        unit["status"] = "active" if dag["loop_active"] else "pending"
        for name, value in (legacy.get("checks") or {}).items():
            if name in unit["checks"]:
                unit["checks"][name]["value"] = value
                unit["checks"][name]["summary"] = "Migrated from legacy status.json"
                unit["checks"][name]["updated_at"] = legacy.get("updated_at")
        dag["units"][current_id] = unit
        if unit["status"] == "active":
            dag["active_units"] = [current_id]
    return dag


def load_dag() -> dict[str, Any]:
    ensure_context_dirs()
    path = dag_path()
    if path.exists():
        dag = safe_load_json(path)
        project = ensure_project_registry(Path.cwd())
        dag.setdefault("project_id", project["project_id"])
        dag.setdefault("project_root", project["project_root"])
        normalize_dag(dag)
        return dag

    legacy = load_legacy_status()
    dag = migrate_from_legacy(legacy) if legacy else default_dag()
    normalize_dag(dag)
    save_dag(dag)
    return dag


def legacy_context_dir() -> Path:
    return ralph_base_context_dir(Path.cwd())


def legacy_dag_path() -> Path:
    return legacy_context_dir() / "dag.json"


def current_context_is_legacy() -> bool:
    return context_dir().resolve() == legacy_context_dir().resolve()


def load_legacy_dag() -> Optional[dict[str, Any]]:
    path = legacy_dag_path()
    if current_context_is_legacy() or not path.exists():
        return None
    try:
        dag = safe_load_json(path)
    except (JSONDecodeError, OSError):
        return None
    normalize_dag(dag)
    return dag


def import_legacy_dag_for_unit(unit_id: str) -> Optional[dict[str, Any]]:
    legacy = load_legacy_dag()
    if not legacy or unit_id not in legacy.get("units", {}):
        return None

    ensure_context_dirs()
    source_units = legacy_context_dir() / "units"
    target_units = units_dir()
    if source_units.exists():
        shutil.copytree(source_units, target_units, dirs_exist_ok=True)

    imported = json.loads(json.dumps(legacy))
    imported["run_id"] = selected_run_id(Path.cwd())
    add_note(
        imported,
        f"Imported legacy project-level Ralph DAG into run {imported.get('run_id')} because unit {unit_id} was requested explicitly.",
    )
    save_dag(imported)
    return imported


def summarize_checks(unit: dict[str, Any]) -> dict[str, str]:
    return {name: data.get("value", "fail") for name, data in unit.get("checks", {}).items()}


def save_legacy_status(dag: dict[str, Any]) -> None:
    active = active_units(dag)
    current_id = active[0] if active else None
    current_unit = None
    checks: dict[str, str] = {}
    if current_id:
        unit = dag["units"][current_id]
        current_unit = {"id": unit["id"], "title": unit.get("title", "")}
        checks = summarize_checks(unit)

    status = {
        "version": 2,
        "loop_active": bool(active),
        "allow_stop": dag.get("allow_stop", True),
        "current_unit": current_unit,
        "active_units": active,
        "checks": checks,
        "notes": dag.get("notes", []),
        "updated_at": now_iso(),
    }
    status_path().write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")


def save_unit_state(unit: dict[str, Any]) -> None:
    path = unit_state_path(unit["id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(unit, indent=2) + "\n", encoding="utf-8")


def save_dag(dag: dict[str, Any]) -> None:
    normalize_dag(dag)
    project = ensure_project_registry(Path.cwd())
    dag["project_id"] = project["project_id"]
    dag["project_root"] = project["project_root"]
    dag["run_id"] = selected_run_id(Path.cwd())
    dag["updated_at"] = now_iso()
    dag_path().write_text(json.dumps(dag, indent=2) + "\n", encoding="utf-8")
    for unit in dag.get("units", {}).values():
        unit["updated_at"] = now_iso()
        save_unit_state(unit)
    save_legacy_status(dag)


def replace_placeholders(text: str, unit_id: str, title: str) -> str:
    return text.replace("<unit-id>", unit_id).replace("<title>", title or unit_id)


def scaffold_unit_files(unit_id: str, title: str) -> None:
    directory = unit_dir(unit_id)
    directory.mkdir(parents=True, exist_ok=True)
    unit_artifacts_dir(unit_id).mkdir(parents=True, exist_ok=True)

    contract_path = directory / "contract.md"
    if not contract_path.exists():
        template = (skill_root() / "assets" / "unit-contract.template.md").read_text(encoding="utf-8")
        contract_path.write_text(replace_placeholders(template, unit_id, title), encoding="utf-8")

    file_templates = {
        "planner-output.json": "planner-output.template.json",
        "executor-output.json": "executor-output.template.json",
        "review-input.json": "review-input.template.json",
        "feedback.md": "feedback-log.template.md",
    }
    for output_name, template_name in file_templates.items():
        output_path = directory / output_name
        if output_path.exists():
            continue
        template = (skill_root() / "assets" / template_name).read_text(encoding="utf-8")
        output_path.write_text(replace_placeholders(template, unit_id, title), encoding="utf-8")


def get_unit(dag: dict[str, Any], unit_id: str) -> dict[str, Any]:
    unit = dag.get("units", {}).get(unit_id)
    if unit is None:
        imported = import_legacy_dag_for_unit(unit_id)
        if imported is not None:
            unit = imported.get("units", {}).get(unit_id)
            if unit is not None:
                dag.clear()
                dag.update(imported)
                return unit
        raise SystemExit(f"Unknown unit: {unit_id}")
    return unit


def resolve_target_unit(dag: dict[str, Any], unit_id: Optional[str]) -> dict[str, Any]:
    if unit_id:
        return get_unit(dag, unit_id)
    active = active_units(dag)
    if len(active) != 1:
        raise SystemExit("Specify --unit when there is not exactly one active unit.")
    return get_unit(dag, active[0])


def deps_landed(dag: dict[str, Any], unit: dict[str, Any]) -> bool:
    for dep in unit.get("deps", []):
        dep_unit = dag.get("units", {}).get(dep)
        if not dep_unit or dep_unit.get("status") != "landed":
            return False
    return True


def ready_unit_ids(dag: dict[str, Any]) -> list[str]:
    ready: list[str] = []
    active = set(active_units(dag))
    for unit_id, unit in dag.get("units", {}).items():
        if unit_id in active:
            continue
        if unit.get("status") in TERMINAL_STATUSES:
            continue
        if deps_landed(dag, unit):
            ready.append(unit_id)
    return sorted(ready)


def refresh_allow_stop(dag: dict[str, Any]) -> None:
    dag["active_units"] = [unit_id for unit_id in active_units(dag) if dag["units"][unit_id].get("status") == "active"]
    dag["allow_stop"] = len(active_units(dag)) == 0
    dag["loop_active"] = bool(active_units(dag))


def ensure_unit_exists(
    dag: dict[str, Any],
    unit_id: str,
    title: str,
    tier: str,
    deps: list[str],
    activate: bool,
) -> dict[str, Any]:
    units = dag.setdefault("units", {})
    unit = units.get(unit_id)
    if unit is None:
        unit = default_unit(unit_id, title=title, tier=tier, deps=deps)
        units[unit_id] = unit
    else:
        if title:
            unit["title"] = title
        if tier:
            unit["tier"] = tier
        if deps:
            unit["deps"] = deps

    if activate:
        if unit.get("deps") and not deps_landed(dag, unit):
            raise SystemExit(f"Cannot activate {unit_id}: dependencies are not landed.")
        unit["status"] = "active"
        dag["loop_active"] = True
        active = dag.setdefault("active_units", [])
        if unit_id not in active:
            active.append(unit_id)
    else:
        if unit["status"] == "pending" and deps_landed(dag, unit):
            unit["status"] = "ready"

    scaffold_unit_files(unit_id, unit.get("title", ""))
    save_unit_state(unit)
    refresh_allow_stop(dag)
    return unit


def artifact_required_for_pass(name: str) -> bool:
    return name in CHECK_NAMES


def normalize_review_verdict(verdict: str) -> str:
    normalized = verdict.strip().upper()
    aliases = {
        "ACCEPT": "ACCEPT",
        "PASS": "ACCEPT",
        "REJECT": "REJECT",
    }
    result = aliases.get(normalized)
    if result is None:
        raise SystemExit("review_complete requires a review verdict artifact with verdict ACCEPT/PASS or REJECT.")
    return result


def parse_review_verdict(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    try:
        payload = json.loads(text)
    except JSONDecodeError:
        match = re.search(r"^\s*Verdict:\s*([A-Za-z_]+)\s*$", text, flags=re.IGNORECASE | re.MULTILINE)
        if not match:
            raise SystemExit("review_complete requires a review verdict artifact with a Verdict field.")
        return normalize_review_verdict(match.group(1))

    return normalize_review_verdict(str(payload.get("verdict", "")))


def set_review_state(
    unit: dict[str, Any],
    *,
    status: str,
    verdict: Optional[str],
    artifact_path: Optional[str],
    summary: str,
    updated_at: Optional[str] = None,
) -> None:
    review = ensure_review_state(unit)
    review["status"] = status
    review["verdict"] = verdict
    review["artifact_path"] = artifact_path
    review["summary"] = summary
    review["updated_at"] = updated_at or now_iso()


def sync_review_state_from_check(unit: dict[str, Any]) -> None:
    review = ensure_review_state(unit)
    check = unit.setdefault("checks", {}).setdefault("review_complete", default_check_state()["review_complete"])
    artifact_path = check.get("artifact_path")
    verdict = None
    if artifact_path:
        try:
            verdict = parse_review_verdict(Path(artifact_path))
        except SystemExit:
            verdict = None
    if check.get("value") == "pass" and verdict == "ACCEPT":
        set_review_state(
            unit,
            status="accepted",
            verdict=verdict,
            artifact_path=artifact_path,
            summary=check.get("summary", ""),
            updated_at=check.get("updated_at"),
        )
        return
    if check.get("value") == "fail" and verdict == "REJECT":
        set_review_state(
            unit,
            status="rejected",
            verdict=verdict,
            artifact_path=artifact_path,
            summary=check.get("summary", ""),
            updated_at=check.get("updated_at"),
        )
        return
    if review.get("status") not in {"pending", "blocked"}:
        set_review_state(
            unit,
            status="pending",
            verdict=None,
            artifact_path=None,
            summary=check.get("summary", ""),
            updated_at=check.get("updated_at"),
        )


def invalidate_review_state(unit: dict[str, Any], reason: str) -> None:
    check = unit.setdefault("checks", {}).setdefault("review_complete", default_check_state()["review_complete"])
    timestamp = now_iso()
    check["value"] = "fail"
    check["artifact_path"] = None
    check["command"] = None
    check["exit_code"] = None
    check["summary"] = reason
    check["updated_at"] = timestamp
    set_review_state(
        unit,
        status="pending",
        verdict=None,
        artifact_path=None,
        summary=reason,
        updated_at=timestamp,
    )


def invalidate_review_if_stale(unit: dict[str, Any]) -> bool:
    sync_review_state_from_check(unit)
    review = ensure_review_state(unit)
    if review.get("status") not in {"accepted", "rejected"}:
        return False
    review_time = parse_iso(review.get("updated_at"))
    if review_time is None:
        return False
    for check_name in REVIEW_INVALIDATING_CHECKS:
        check_time = parse_iso(unit.get("checks", {}).get(check_name, {}).get("updated_at"))
        if check_time and check_time > review_time:
            invalidate_review_state(unit, f"Review invalidated: {check_name} updated after the last review.")
            return True
    return False


def sync_review_input_artifacts(unit: dict[str, Any]) -> bool:
    path = unit_dir(unit["id"]) / "review-input.json"
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except JSONDecodeError:
        return False
    artifacts = []
    viability_artifacts = []
    for check_name in ("baseline_recorded", "viability_gate_passed", "targeted_checks_passed"):
        artifact = unit.get("checks", {}).get(check_name, {}).get("artifact_path")
        if artifact:
            try:
                artifact = str(Path(artifact).resolve().relative_to(Path.cwd()))
            except ValueError:
                artifact = str(artifact)
            artifacts.append(artifact)
            if check_name == "viability_gate_passed":
                viability_artifacts.append(artifact)
    payload["oracle_artifacts"] = list(artifacts)
    payload["test_artifacts"] = list(artifacts)
    payload["viability_artifacts"] = list(viability_artifacts)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return True


def normalize_unit(dag: dict[str, Any], unit: dict[str, Any]) -> None:
    ensure_review_state(unit)
    sync_review_state_from_check(unit)
    invalidate_review_if_stale(unit)
    if unit.get("status") == "complete" and ensure_review_state(unit).get("status") != "accepted":
        unit["status"] = "ready" if deps_landed(dag, unit) else "pending"
    if unit.get("status") == "pending" and deps_landed(dag, unit):
        unit["status"] = "ready"


def normalize_dag(dag: dict[str, Any]) -> None:
    dag.setdefault("units", {})
    for unit in dag["units"].values():
        normalize_unit(dag, unit)
    dag["active_units"] = [unit_id for unit_id in active_units(dag) if dag["units"][unit_id].get("status") == "active"]
    refresh_allow_stop(dag)


def update_check(
    unit: dict[str, Any],
    name: str,
    value: str,
    *,
    artifact_path: Optional[Path],
    command: Optional[str],
    exit_code: Optional[int],
    summary: str,
) -> None:
    if name not in unit["checks"]:
        unit["checks"][name] = {
            "value": "fail",
            "artifact_path": None,
            "command": None,
            "exit_code": None,
            "summary": "",
            "updated_at": None,
        }

    if value == "pass" and artifact_required_for_pass(name) and artifact_path is None:
        raise SystemExit(f"Passing {name} requires --artifact-path or use run-check.")
    if name == "review_complete" and artifact_path is not None:
        verdict = parse_review_verdict(artifact_path)
        if value == "pass" and verdict != "ACCEPT":
            raise SystemExit("review_complete pass requires a review artifact with verdict ACCEPT or PASS.")
        if value == "fail" and verdict != "REJECT":
            raise SystemExit("review_complete fail requires a review artifact with verdict REJECT.")

    check = unit["checks"][name]
    check["value"] = value
    check["artifact_path"] = str(artifact_path) if artifact_path else None
    check["command"] = command
    check["exit_code"] = exit_code
    check["summary"] = summary
    check["updated_at"] = now_iso()
    if name == "review_complete":
        sync_review_state_from_check(unit)


def unit_review_accepted(unit: dict[str, Any]) -> bool:
    sync_review_state_from_check(unit)
    return ensure_review_state(unit).get("status") == "accepted"


def required_checks_passed(unit: dict[str, Any]) -> bool:
    for name in MANDATORY_CHECKS:
        if name == "review_complete":
            if not unit_review_accepted(unit):
                return False
            continue
        check = unit["checks"].get(name, {})
        if not check_satisfied(name, check.get("value", "fail")):
            return False
    return True


def state_script_command() -> str:
    return f'python3 "{Path(__file__).resolve()}"'


def cmd_bootstrap(_: argparse.Namespace) -> int:
    dag = load_dag()
    add_note(dag, "ralph_state.py bootstrap called.")
    save_dag(dag)
    print(f"Initialized {dag_path()}")
    return 0


def cmd_begin(args: argparse.Namespace) -> int:
    dag = load_dag()
    unit = ensure_unit_exists(
        dag,
        args.unit_id,
        args.title,
        args.tier,
        args.deps or [],
        activate=True,
    )
    add_note(dag, f"Started unit {args.unit_id}.")
    add_note(unit, "Unit activated.")
    refresh_allow_stop(dag)
    save_dag(dag)
    print(f"Started unit: {args.unit_id}")
    return 0


def cmd_add_unit(args: argparse.Namespace) -> int:
    dag = load_dag()
    ensure_unit_exists(
        dag,
        args.unit_id,
        args.title,
        args.tier,
        args.deps or [],
        activate=args.activate,
    )
    add_note(dag, f"Registered unit {args.unit_id}.")
    save_dag(dag)
    print(f"Registered unit: {args.unit_id}")
    return 0


def cmd_activate(args: argparse.Namespace) -> int:
    dag = load_dag()
    unit = get_unit(dag, args.unit_id)
    if not deps_landed(dag, unit):
        raise SystemExit(f"Cannot activate {args.unit_id}: dependencies are not landed.")
    unit["status"] = "active"
    dag["loop_active"] = True
    active = dag.setdefault("active_units", [])
    if args.unit_id not in active:
        active.append(args.unit_id)
    add_note(unit, "Unit activated.")
    refresh_allow_stop(dag)
    save_dag(dag)
    print(f"Activated unit: {args.unit_id}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    if args.value not in CHECK_VALUES:
        raise SystemExit(f"Invalid check value: {args.value}")
    dag = load_dag()
    unit = resolve_target_unit(dag, args.unit)
    artifact_path = Path(args.artifact_path).resolve() if args.artifact_path else None
    exit_code = args.exit_code if args.exit_code is not None else None
    update_check(
        unit,
        args.name,
        args.value,
        artifact_path=artifact_path,
        command=args.command,
        exit_code=exit_code,
        summary=args.summary or "",
    )
    if args.name != "review_complete" and args.name in REVIEW_INVALIDATING_CHECKS:
        invalidate_review_if_stale(unit)
        sync_review_input_artifacts(unit)
    if args.name == "review_complete":
        sync_review_input_artifacts(unit)
    add_note(unit, f"Check {args.name} -> {args.value}.")
    refresh_allow_stop(dag)
    save_dag(dag)
    print(f"{unit['id']} {args.name} = {args.value}")
    return 0


def cmd_run_check(args: argparse.Namespace) -> int:
    artifacts_dir = unit_artifacts_dir(args.unit_id)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    started_at = now_iso()
    completed = subprocess.run(
        args.command,
        shell=True,
        cwd=Path.cwd(),
        executable=os.environ.get("SHELL", "/bin/sh"),
        capture_output=True,
        text=True,
    )
    finished_at = now_iso()

    artifact_path = artifacts_dir / f"{args.name}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}.json"
    artifact = {
        "unit_id": args.unit_id,
        "check_name": args.name,
        "command": args.command,
        "expected_exit": args.expect_exit,
        "actual_exit": completed.returncode,
        "started_at": started_at,
        "finished_at": finished_at,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "passed": completed.returncode == args.expect_exit,
    }
    artifact_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")

    value = "pass" if artifact["passed"] else "fail"
    summary = args.summary or f"Recorded by run-check with exit {completed.returncode}."
    with dag_lock():
        dag = load_dag()
        unit = get_unit(dag, args.unit_id)
        update_check(
            unit,
            args.name,
            value,
            artifact_path=artifact_path,
            command=args.command,
            exit_code=completed.returncode,
            summary=summary,
        )
        unit.setdefault("artifacts", {}).setdefault(args.name, []).append(str(artifact_path))
        if args.name != "review_complete" and args.name in REVIEW_INVALIDATING_CHECKS:
            invalidate_review_if_stale(unit)
            sync_review_input_artifacts(unit)
        add_note(unit, f"run-check {args.name} -> {value}.")
        refresh_allow_stop(dag)
        save_dag(dag)
    print(f"{args.unit_id} {args.name} = {value}")
    print(f"artifact: {artifact_path}")
    return 0 if artifact["passed"] else 1


def cmd_note(args: argparse.Namespace) -> int:
    dag = load_dag()
    if args.unit:
        unit = get_unit(dag, args.unit)
        add_note(unit, args.message)
    else:
        add_note(dag, args.message)
    save_dag(dag)
    print("Note appended.")
    return 0


def cmd_block(args: argparse.Namespace) -> int:
    dag = load_dag()
    unit = resolve_target_unit(dag, args.unit)
    checks = unit.get("checks", {})
    implementation_ready = all(
        checks.get(name, {}).get("value") == "pass"
        for name in ("baseline_recorded", "viability_gate_passed", "implementation_complete")
    )
    quality_incomplete = any(
        checks.get(name, {}).get("value") != "pass"
        for name in ("targeted_checks_passed", "review_complete")
    )
    if (
        unit.get("status") == "active"
        and implementation_ready
        and quality_incomplete
        and not args.terminal
    ):
        add_note(
            unit,
            "Non-terminal block refused: "
            f"{args.reason}. targeted_checks_passed/review_complete are still incomplete; "
            "keep repairing or use --terminal only for an explicitly irrecoverable blocker.",
        )
        refresh_allow_stop(dag)
        save_dag(dag)
        print(
            "Refused non-terminal block: targeted_checks_passed/review_complete are incomplete. "
            "Continue the repair loop or rerun with --terminal for an irrecoverable blocker.",
            file=sys.stderr,
        )
        return 2
    unit["status"] = "blocked"
    add_note(unit, f"Blocked: {args.reason}")
    dag["active_units"] = [unit_id for unit_id in active_units(dag) if unit_id != unit["id"]]
    refresh_allow_stop(dag)
    save_dag(dag)
    print(f"Blocked unit: {unit['id']}")
    return 0


def cmd_complete_unit(args: argparse.Namespace) -> int:
    dag = load_dag()
    unit = resolve_target_unit(dag, args.unit)
    sync_review_input_artifacts(unit)
    if not required_checks_passed(unit):
        raise SystemExit(f"Cannot complete {unit['id']}: required checks are not all pass/skip.")
    unit["status"] = "complete"
    dag["active_units"] = [unit_id for unit_id in active_units(dag) if unit_id != unit["id"]]
    add_note(unit, "Unit completed and ready to land.")
    add_note(dag, f"Completed unit {unit['id']}.")
    refresh_allow_stop(dag)
    save_dag(dag)
    print(f"Completed unit: {unit['id']}")
    return 0


def cmd_land_unit(args: argparse.Namespace) -> int:
    dag = load_dag()
    unit = get_unit(dag, args.unit_id)
    sync_review_input_artifacts(unit)
    if not required_checks_passed(unit):
        raise SystemExit(f"Cannot land {unit['id']}: required checks are not all pass/skip.")
    unit["status"] = "landed"
    unit["commit"] = args.commit
    dag["active_units"] = [unit_id for unit_id in active_units(dag) if unit_id != unit["id"]]
    add_note(unit, f"Landed at commit {args.commit}.")
    add_note(dag, f"Landed unit {unit['id']} at commit {args.commit}.")
    refresh_allow_stop(dag)
    save_dag(dag)
    print(f"Landed unit: {unit['id']}")
    return 0


def cmd_ready(_: argparse.Namespace) -> int:
    dag = load_dag()
    active = active_units(dag)
    ready = ready_unit_ids(dag)
    print(f"active: {', '.join(active) if active else 'none'}")
    print(f"ready: {', '.join(ready) if ready else 'none'}")
    return 0


def cmd_status(_: argparse.Namespace) -> int:
    dag = load_dag()
    active = active_units(dag)
    print(f"DAG file: {dag_path()}")
    print(f"project_id: {dag.get('project_id', 'unknown')}")
    print(f"project_root: {dag.get('project_root', 'unknown')}")
    print(f"loop_active: {dag.get('loop_active')}")
    print(f"allow_stop: {dag.get('allow_stop')}")
    print(f"active_units: {', '.join(active) if active else 'none'}")
    ready = ready_unit_ids(dag)
    print(f"ready_units: {', '.join(ready) if ready else 'none'}")
    for unit_id in sorted(dag.get("units", {})):
        unit = dag["units"][unit_id]
        print(f"- {unit_id}: status={unit.get('status')} tier={unit.get('tier')} deps={unit.get('deps', [])}")
        review = ensure_review_state(unit)
        print(f"  * review_state: status={review.get('status')} verdict={review.get('verdict')}")
        for check_name in CHECK_NAMES:
            check = unit.get("checks", {}).get(check_name, {})
            print(f"  * {check_name}: {check.get('value', 'fail')}")
    return 0


def cmd_refresh_unit(args: argparse.Namespace) -> int:
    dag = load_dag()
    unit = resolve_target_unit(dag, args.unit)
    prior_status = unit.get("status")
    prior_review = ensure_review_state(unit).copy()
    normalize_unit(dag, unit)
    sync_review_input_artifacts(unit)
    add_note(unit, "Refreshed unit state and review payloads.")
    refresh_allow_stop(dag)
    save_dag(dag)
    print(f"Refreshed unit: {unit['id']}")
    print(f"status: {prior_status} -> {unit.get('status')}")
    print(f"review: {prior_review.get('status')} -> {ensure_review_state(unit).get('status')}")
    return 0


def cmd_finish_loop(_: argparse.Namespace) -> int:
    dag = load_dag()
    dag["loop_active"] = False
    dag["active_units"] = []
    refresh_allow_stop(dag)
    add_note(dag, "Finished Ralph loop.")
    save_dag(dag)
    print("Ralph loop finished.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Ralph loop state.")
    parser.add_argument("--run-id", help="Use .context/ralph/runs/<run-id> instead of the thread/default run.")
    parser.add_argument("--legacy", action="store_true", help="Use the legacy project-level .context/ralph state.")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    subparsers.add_parser("bootstrap")

    begin = subparsers.add_parser("begin")
    begin.add_argument("unit_id")
    begin.add_argument("--title", default="")
    begin.add_argument("--tier", default="small")
    begin.add_argument("--deps", nargs="*", default=[])

    add_unit = subparsers.add_parser("add-unit")
    add_unit.add_argument("unit_id")
    add_unit.add_argument("--title", default="")
    add_unit.add_argument("--tier", default="small")
    add_unit.add_argument("--deps", nargs="*", default=[])
    add_unit.add_argument("--activate", action="store_true")

    activate = subparsers.add_parser("activate")
    activate.add_argument("unit_id")

    check = subparsers.add_parser("check")
    check.add_argument("name")
    check.add_argument("value")
    check.add_argument("--unit")
    check.add_argument("--artifact-path")
    check.add_argument("--command")
    check.add_argument("--exit-code", type=int)
    check.add_argument("--summary", default="")

    run_check = subparsers.add_parser("run-check")
    run_check.add_argument("unit_id")
    run_check.add_argument("name")
    run_check.add_argument("--command", required=True)
    run_check.add_argument("--expect-exit", type=int, default=0)
    run_check.add_argument("--summary", default="")

    note = subparsers.add_parser("note")
    note.add_argument("message")
    note.add_argument("--unit")

    block = subparsers.add_parser("block")
    block.add_argument("reason")
    block.add_argument("--unit")
    block.add_argument(
        "--terminal",
        action="store_true",
        help="Allow ending an active unit as blocked even when quality gates are still incomplete. Use only for irrecoverable blockers.",
    )

    complete = subparsers.add_parser("complete-unit")
    complete.add_argument("--unit")

    refresh = subparsers.add_parser("refresh-unit")
    refresh.add_argument("--unit")

    land = subparsers.add_parser("land-unit")
    land.add_argument("unit_id")
    land.add_argument("--commit", required=True)

    subparsers.add_parser("ready")
    subparsers.add_parser("finish-loop")
    subparsers.add_parser("status")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.run_id:
        os.environ["RALPH_RUN_ID"] = args.run_id
    if args.legacy:
        os.environ["RALPH_USE_LEGACY"] = "1"
    if args.subcommand in {"bootstrap", "begin"} or (
        args.subcommand == "add-unit" and getattr(args, "activate", False)
    ):
        os.environ.setdefault("RALPH_CREATE_RUN", "1")
    handlers = {
        "bootstrap": cmd_bootstrap,
        "begin": cmd_begin,
        "add-unit": cmd_add_unit,
        "activate": cmd_activate,
        "check": cmd_check,
        "run-check": cmd_run_check,
        "note": cmd_note,
        "block": cmd_block,
        "complete-unit": cmd_complete_unit,
        "refresh-unit": cmd_refresh_unit,
        "land-unit": cmd_land_unit,
        "ready": cmd_ready,
        "finish-loop": cmd_finish_loop,
        "status": cmd_status,
    }
    handler = handlers[args.subcommand]
    if args.subcommand in {"ready", "status", "run-check"}:
        return handler(args)
    with dag_lock():
        return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
