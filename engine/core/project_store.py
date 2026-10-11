"""Project layout on disk: projects/<id>/{project.json,analysis,edit,subtitles,renders,logs,qc}."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .models import Project

ROOT = Path(__file__).resolve().parents[2]
PROJECTS_DIR = ROOT / "projects"

SUBDIRS = ("analysis", "edit", "subtitles", "renders", "logs", "qc")


def new_project_id() -> str:
    # Microsecond granularity: one-second ids collided when several projects
    # were created within the same second, silently reusing (and corrupting)
    # the directory. Found via Phase 8 test failures (2026-09-17).
    return "project_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")


def create_project(input_path: str, template: str = "youtube", preset: str = "youtube_1080p") -> Project:
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    pid = new_project_id()
    pdir = PROJECTS_DIR / pid
    for sub in SUBDIRS:
        (pdir / sub).mkdir(parents=True, exist_ok=True)
    project = Project(id=pid, input_path=str(input_path), template=template, preset=preset)
    save_project(project)
    return project


def project_dir(pid: str) -> Path:
    return PROJECTS_DIR / pid


def save_project(project: Project) -> Path:
    pdir = project_dir(project.id)
    pdir.mkdir(parents=True, exist_ok=True)
    dest = pdir / "project.json"
    dest.write_text(json.dumps(project.to_dict(), indent=2), encoding="utf-8")
    return dest


def load_project(pid: str) -> Project:
    dest = project_dir(pid) / "project.json"
    if not dest.is_file():
        raise FileNotFoundError(f"unknown project '{pid}' (missing {dest})")
    return Project.from_dict(json.loads(dest.read_text(encoding="utf-8")))


def write_artifact(pid: str, subdir: str, name: str, payload: dict | str) -> Path:
    dest = project_dir(pid) / subdir / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, str):
        dest.write_text(payload, encoding="utf-8")
    else:
        dest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return dest


def mark_stage(project: Project, stage: str, status: str, artifact: str = "") -> Project:
    project.stages[stage] = {"status": status, "artifact": artifact}
    save_project(project)
    return project
