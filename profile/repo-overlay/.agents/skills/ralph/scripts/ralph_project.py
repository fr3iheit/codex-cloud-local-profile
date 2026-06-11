#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser().resolve()


def run_git(cwd: Path, args: list[str]) -> Optional[str]:
    try:
        result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    except (FileNotFoundError, OSError):
        return None
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


def project_root(cwd: Optional[Path] = None) -> Path:
    start = (cwd or Path.cwd()).resolve()
    root = run_git(start, ["rev-parse", "--show-toplevel"])
    if root:
        return Path(root).resolve()
    return start


def slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-._").lower()
    return slug or "project"


def run_slug(value: str) -> str:
    return slugify(value)[:96] or "run"


def project_identity(cwd: Optional[Path] = None) -> dict[str, Any]:
    root = project_root(cwd)
    remote = run_git(root, ["config", "--get", "remote.origin.url"])
    head = run_git(root, ["rev-parse", "--short", "HEAD"])
    source = remote or str(root)
    digest = hashlib.sha1(source.encode("utf-8")).hexdigest()[:10]
    name_source = Path(remote.rstrip("/").removesuffix(".git")).name if remote else root.name
    project_id = f"{slugify(name_source)}-{digest}"
    return {
        "version": 1,
        "project_id": project_id,
        "project_name": root.name,
        "project_root": str(root),
        "identity_source": source,
        "remote_origin": remote,
        "head": head,
        "created_or_refreshed_at": now_iso(),
    }


def ralph_base_context_dir(cwd: Optional[Path] = None) -> Path:
    return project_root(cwd) / ".context" / "ralph"


def selected_run_id(cwd: Optional[Path] = None, *, create_for_current_thread: bool = False) -> Optional[str]:
    if os.environ.get("RALPH_USE_LEGACY") == "1":
        return None

    explicit = os.environ.get("RALPH_RUN_ID")
    if explicit:
        return run_slug(explicit)

    thread_id = os.environ.get("CODEX_THREAD_ID")
    if not thread_id:
        return None

    return run_slug(thread_id)


def ralph_context_dir(
    cwd: Optional[Path] = None,
    *,
    create_for_current_thread: bool = False,
    fallback_to_legacy: bool = True,
) -> Path:
    base = ralph_base_context_dir(cwd)
    run_id = selected_run_id(cwd, create_for_current_thread=create_for_current_thread)
    if run_id:
        return base / "runs" / run_id
    if fallback_to_legacy:
        return base
    return base / "runs" / "__no_active_run__"


def project_registry_dir(cwd: Optional[Path] = None) -> Path:
    identity = project_identity(cwd)
    return codex_home() / "ralph" / "projects" / identity["project_id"]


def ensure_project_registry(cwd: Optional[Path] = None) -> dict[str, Any]:
    identity = project_identity(cwd)
    registry = codex_home() / "ralph" / "projects" / identity["project_id"]
    registry.mkdir(parents=True, exist_ok=True)
    (registry / "logs").mkdir(exist_ok=True)
    project_path = registry / "project.json"
    if project_path.exists():
        try:
            existing = json.loads(project_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}
    else:
        existing = {}
    merged = {**existing, **identity, "updated_at": now_iso()}
    if "created_at" not in merged:
        merged["created_at"] = now_iso()
    project_path.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    memory_path = registry / "memory.md"
    if not memory_path.exists():
        memory_path.write_text(
            "# Ralph Project Memory\n\n"
            f"- Project: {identity['project_name']}\n"
            f"- Project ID: `{identity['project_id']}`\n"
            f"- Root: `{identity['project_root']}`\n\n"
            "Append project-level Ralph decisions, durable constraints, and loop outcomes here.\n",
            encoding="utf-8",
        )
    return merged


def write_local_project_pointer(context_dir: Path, cwd: Optional[Path] = None) -> dict[str, Any]:
    identity = ensure_project_registry(cwd)
    registry = codex_home() / "ralph" / "projects" / identity["project_id"]
    pointer = {
        **identity,
        "ralph_context_dir": str(context_dir.resolve()),
        "project_registry_dir": str(registry.resolve()),
        "project_memory_path": str((registry / "memory.md").resolve()),
        "updated_at": now_iso(),
    }
    context_dir.mkdir(parents=True, exist_ok=True)
    (context_dir / "project.json").write_text(json.dumps(pointer, indent=2) + "\n", encoding="utf-8")
    return pointer
