#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ralphone_project import project_root, ralphone_context_dir, selected_run_id, write_local_project_pointer


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def copy_if_missing(src: Path, dst: Path) -> None:
    if dst.exists():
        return
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")


def default_dag() -> dict:
    timestamp = now_iso()
    return {
        "version": 2,
        "run_id": selected_run_id(Path.cwd(), create_for_current_thread=True),
        "loop_active": False,
        "allow_stop": True,
        "active_units": [],
        "units": {},
        "notes": [
            {
                "timestamp": timestamp,
                "message": "bootstrap_ralphone.py initialized the Ralphone workspace.",
            }
        ],
        "updated_at": timestamp,
    }


def main() -> int:
    repo_root = project_root(Path.cwd())
    skill_root = Path(__file__).resolve().parents[1]
    if "RALPHONE_USE_LEGACY" not in os.environ:
        os.environ.setdefault("RALPHONE_CREATE_RUN", "1")
    context_dir = ralphone_context_dir(repo_root, create_for_current_thread=True)
    units_dir = context_dir / "units"
    context_dir.mkdir(parents=True, exist_ok=True)
    units_dir.mkdir(parents=True, exist_ok=True)
    (context_dir / "logs").mkdir(exist_ok=True)

    copy_if_missing(skill_root / "assets" / "plan.template.md", context_dir / "plan.md")
    copy_if_missing(
        skill_root / "assets" / "feedback-log.template.md",
        context_dir / "feedback.md",
    )
    copy_if_missing(
        skill_root / "assets" / "model-routing.template.md",
        context_dir / "model-routing.md",
    )
    copy_if_missing(
        skill_root / "assets" / "review-rubric.template.md",
        context_dir / "review-rubric.md",
    )

    progress_path = context_dir / "progress.md"
    if not progress_path.exists():
        progress_path.write_text(
            "# Ralphone Progress\n\n"
            f"- Bootstrapped: {now_iso()}\n"
            "- Next: fill `plan.md`, define units, scaffold the first contract, configure scope with `ralphone_state.py set-scope`, record the baseline through `ralphone_state.py`, and decide whether the unit needs a viability gate before implementation or retrain.\n",
            encoding="utf-8",
        )

    trace_path = context_dir / "trace.jsonl"
    if not trace_path.exists():
        trace_path.write_text(
            json.dumps({"timestamp": now_iso(), "event": "bootstrap", "payload": {"script": "bootstrap_ralphone.py"}}, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    artifact_index_path = context_dir / "artifact-index.json"
    if not artifact_index_path.exists():
        artifact_index_path.write_text(json.dumps({"version": 1, "artifacts": []}, indent=2) + "\n", encoding="utf-8")

    dag_path = context_dir / "dag.json"
    project_pointer = write_local_project_pointer(context_dir, repo_root)
    if dag_path.exists():
        dag = json.loads(dag_path.read_text(encoding="utf-8"))
    else:
        dag = default_dag()
    dag["project_id"] = project_pointer["project_id"]
    dag["project_root"] = project_pointer["project_root"]
    dag_path.write_text(json.dumps(dag, indent=2) + "\n", encoding="utf-8")

    status_path = context_dir / "status.json"
    if not status_path.exists():
        legacy_status = {
            "version": 2,
            "loop_active": False,
            "allow_stop": True,
            "current_unit": None,
            "active_units": [],
            "checks": {},
            "notes": [],
            "updated_at": now_iso(),
        }
        status_path.write_text(json.dumps(legacy_status, indent=2) + "\n", encoding="utf-8")

    print("Bootstrapped Ralphone workspace:")
    print(f"- {context_dir}")
    print(f"- {context_dir / 'plan.md'}")
    print(f"- {context_dir / 'feedback.md'}")
    print(f"- {context_dir / 'model-routing.md'}")
    print(f"- {context_dir / 'review-rubric.md'}")
    print(f"- {context_dir / 'progress.md'}")
    print(f"- {context_dir / 'artifact-index.json'}")
    print(f"- {context_dir / 'trace.jsonl'}")
    print(f"- {context_dir / 'dag.json'}")
    print(f"- {context_dir / 'status.json'}")
    print(f"- {context_dir / 'project.json'}")
    print(f"- {project_pointer['project_memory_path']}")
    print("")
    print("Next steps:")
    print("1. Fill .context/ralphone/plan.md")
    print('2. Run: python3 "<skill-root>/scripts/ralphone_state.py" begin <unit-id> --title "<title>" --tier <tier>')
    print("3. Fill the selected run's units/<unit-id>/contract.md and planner-output.json")
    print(
        '4. Configure scope with: python3 "<skill-root>/scripts/ralphone_state.py" set-scope <unit-id> --allowed <path> --forbidden <path>'
    )
    print(
        '5. Record baseline with: python3 "<skill-root>/scripts/ralphone_state.py" run-check <unit-id> baseline_recorded --command "<oracle command>" --expect-exit <expected>'
    )
    print(
        '6. For data/model/filter-dependent units, record viability with: python3 "<skill-root>/scripts/ralphone_state.py" run-check <unit-id> viability_gate_passed --command "<coverage/provenance command>" --expect-exit 0'
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
