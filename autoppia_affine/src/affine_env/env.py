from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List

import httpx
from fastapi import FastAPI, HTTPException
from loguru import logger
from pydantic import BaseModel, Field, HttpUrl

import autoppia_iwa  # type: ignore[import]
from autoppia_iwa.src.data_generation.tasks.classes import Task
from autoppia_iwa.src.execution.actions.actions import NavigateAction
from autoppia_iwa.src.evaluation.stateful_evaluator import ScoreDetails, StatefulEvaluator


app = FastAPI(title="Autoppia Affine Environment", version="0.1.0")


# --------------------------------------------------------------------------- #
# Environment wiring (minimal: only evaluator limits)
# --------------------------------------------------------------------------- #

_DEFAULT_MAX_STEPS = 30


def _get_default_max_steps() -> int:
    """
    Resolve the default max_steps for evaluations.

    Precedence:
      1. AUTOPPIA_AFFINE_MAX_STEPS env var (must be positive int)
      2. Hard-coded default of 30
    """
    raw = os.getenv("AUTOPPIA_AFFINE_MAX_STEPS")
    if not raw:
        return _DEFAULT_MAX_STEPS
    try:
        value = int(raw)
        return value if value > 0 else _DEFAULT_MAX_STEPS
    except Exception:
        return _DEFAULT_MAX_STEPS


_max_steps = _get_default_max_steps()


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #


class EvaluateRequest(BaseModel):
    model: str = Field(..., description="Miner model identifier")
    base_url: HttpUrl = Field(..., description="Base URL of miner /act API")
    max_steps: int | None = Field(
        None,
        description="Max environment steps per task (defaults to config).",
    )


class TaskEvaluationDetail(BaseModel):
    task_id: str
    project_id: str
    score: float
    raw_score: float
    success: bool
    tests_passed: int
    total_tests: int
    steps: int


class EvaluateResponse(BaseModel):
    environment: str = "autoppia_affine_env"
    total_score: float
    success_rate: float
    evaluated: int
    details: List[TaskEvaluationDetail]


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _load_autobooks_task() -> Task:
    """
    Load the single Autobooks demo task used by the fixed agent benchmark.

    This mirrors entrypoints/evaluate_fixed_autobooks.py but is kept local
    so the Affine env can run without depending on that entrypoint module.

    Canonical location is inside this repo under:
        data/tasks/autoppia_books_tasks.json

    If that file is missing, we try to copy it once from the autoppia_iwa
    repo (either the installed package data tree or a sibling repo in the
    monorepo layout), so Docker images and local runs stay in sync.
    """
    # Resolve this repo's root:
    #   env.py -> affine_env -> src -> autoppia_rl (package) -> repo root
    repo_root = Path(__file__).resolve().parents[4]
    local_tasks_path = repo_root / "data" / "tasks" / "autoppia_books_tasks.json"

    # Fast path: use the copy tracked in this repo if present.
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
        #    Support both `<root>/autoppia_iwa` and `<root>/codex/autoppia_iwa`
        #    so this works in the monorepo on your laptop and in slimmer
        #    Docker images.
        dev_roots = [
            repo_root.parent / "autoppia_iwa",
            repo_root / "autoppia_iwa",
        ]
        for dev_root in dev_roots:
            candidates.append(
                dev_root
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
                "Could not locate autoppia_books_tasks.json in autoppia_rl data/ "
                "or in installed/sibling autoppia_iwa."
            )

        # Ensure local copy exists under data/tasks so the repo is self-contained.
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


def _evaluate_task_with_remote_agent_sync(
    task: Task,
    base_url: str,
    web_agent_name: str,
    max_steps: int,
) -> TaskEvaluationDetail:
    # Use the same web_agent_id as the benchmark FixedAutobooksAgent wiring
    # so backend events (e.g., BOOK_DETAIL) are tracked consistently.
    evaluator = StatefulEvaluator(task=task, web_agent_id="1")
    step_index = 0
    score = ScoreDetails()

    try:
        logger.info("[AffineEnv] reset evaluator for task %s", task.id)
        first = evaluator.reset()
        score = first.score
        snapshot = first.snapshot

        done = False

        session = httpx.Client(timeout=60.0)

        while step_index < max_steps and not done:
            payload = {
                "task_id": task.id,
                "step_index": step_index,
                "snapshot_html": snapshot.html,
                "current_url": snapshot.url,
            }

            resp = session.post(f"{base_url.rstrip('/')}/act", json=payload)
            resp.raise_for_status()
            resp_data = resp.json()

            navigate_url = resp_data.get("navigate_url")
            if navigate_url:
                base_action = NavigateAction(
                    type="NavigateAction",
                    url=str(navigate_url),
                )
            else:
                raise RuntimeError("Miner did not return navigate_url")

            if base_action is None:
                logger.info(
                    "[AffineEnv] miner returned no action; stepping with NOOP",
                )
                step_result = evaluator.step(None)
            else:
                step_result = evaluator.step(base_action)

            score = step_result.score
            snapshot = step_result.snapshot

            done = bool(score.success or resp_data.get("done", False))
            step_index += 1

        logger.info(
            "[AffineEnv] finished task %s after %d steps: raw_score=%.3f success=%s",
            task.id,
            step_index,
            score.raw_score,
            score.success,
        )

        return TaskEvaluationDetail(
            task_id=task.id,
            project_id=str(getattr(task, "web_project_id", "")),
            score=float(score.raw_score),
            raw_score=float(score.raw_score),
            success=bool(score.success),
            tests_passed=int(score.tests_passed),
            total_tests=int(score.total_tests),
            steps=step_index,
        )
    finally:
        try:
            session.close()
        except Exception:
            pass
        evaluator.close()


# --------------------------------------------------------------------------- #
# FastAPI endpoints
# --------------------------------------------------------------------------- #


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/evaluate", response_model=EvaluateResponse)
async def evaluate(request: EvaluateRequest) -> EvaluateResponse:
    """
    Evaluate a remote step-based agent on one or more IWA tasks.

    For now this uses the single Autobooks demo task, but the interface
    is prepared for multiple tasks.
    """
    max_steps = int(request.max_steps or _max_steps)
    if max_steps <= 0:
        raise HTTPException(
            status_code=400, detail="max_steps must be positive")

    # TODO: generalise to multiple tasks; for now we use the single Autobooks task.
    try:
        task = _load_autobooks_task()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to load Autobooks task")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    # Run the evaluator + miner loop in a worker thread so that the
    # internal event loop used by StatefulEvaluator does not conflict
    # with the FastAPI/uvicorn asyncio loop.
    import asyncio

    loop = asyncio.get_running_loop()
    detail = await loop.run_in_executor(
        None,
        _evaluate_task_with_remote_agent_sync,
        task,
        str(request.base_url),
        request.model,
        max_steps,
    )

    details = [detail]
    total_score = sum(d.score for d in details)
    success_rate = (
        sum(1 for d in details if d.success) / len(details) if details else 0.0
    )

    return EvaluateResponse(
        total_score=total_score,
        success_rate=success_rate,
        evaluated=len(details),
        details=details,
    )
