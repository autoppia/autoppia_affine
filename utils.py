from __future__ import annotations

import json
from pathlib import Path

import autoppia_iwa  # type: ignore[import]
from autoppia_iwa.src.data_generation.tasks.classes import Task


def load_autobooks_task() -> Task:
    """
    Load the single Autobooks demo task used by the fixed agent benchmark.

    Canonical location is inside this repo under:
        data/autoppia_books_tasks.json

    If that file is missing, we try to copy it once from the autoppia_iwa
    repo (either the installed package data tree or a sibling repo in the
    monorepo layout), so Docker images and local runs stay in sync.
    """
    repo_root = Path(__file__).resolve().parent
    local_tasks_path = repo_root / "data" / "autoppia_books_tasks.json"

    if local_tasks_path.exists():
        tasks_path = local_tasks_path
    else:
        candidates = []

        # 1) Installed autoppia_iwa package layout (Docker / pip install).
        try:
            pkg_root = Path(autoppia_iwa.__file__).resolve().parent  # type: ignore[attr-defined]
            repo_root_iwa = pkg_root.parent
            candidates.append(
                repo_root_iwa
                / "data"
                / "outputs"
                / "benchmark"
                / "cache"
                / "tasks"
                / "autoppia_books_tasks.json"
            )
        except Exception:
            pass

        # 2) Dev layouts / monorepo: sibling autoppia_iwa repo.
        candidates.append(
            repo_root.parent
            / "autoppia_iwa"
            / "data"
            / "outputs"
            / "benchmark"
            / "cache"
            / "tasks"
            / "autoppia_books_tasks.json"
        )

        source_path: Path | None = None
        for cand in candidates:
            if cand.exists():
                source_path = cand
                break

        if source_path is None:
            raise RuntimeError(
                "Could not locate autoppia_books_tasks.json in autoppia_affine data/ "
                "or in installed/sibling autoppia_iwa."
            )

        try:
            local_tasks_path.parent.mkdir(parents=True, exist_ok=True)
            local_tasks_path.write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Failed to copy Autobooks tasks file to {local_tasks_path}: {exc}") from exc

        tasks_path = local_tasks_path

    data = json.loads(tasks_path.read_text(encoding="utf-8"))
    tasks = data.get("tasks", [])
    if len(tasks) != 1:
        raise RuntimeError("Expected exactly one Autobooks benchmark task")
    raw = tasks[0]

    return Task(
        id=raw["id"],
        is_web_real=bool(raw.get("is_web_real", False)),
        web_project_id=raw["web_project_id"],
        url=raw["url"],
        prompt=raw["prompt"],
        tests=raw.get("tests", []),
        relevant_data=raw.get("relevant_data", {}),
    )

