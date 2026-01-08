from __future__ import annotations

import os
from typing import Dict, List

import httpx
from fastapi import FastAPI, HTTPException
from loguru import logger
from pydantic import BaseModel, Field, HttpUrl

from autoppia_iwa.src.data_generation.tasks.classes import Task
from autoppia_iwa.src.execution.actions.actions import BaseAction
from autoppia_iwa.src.evaluation.stateful_evaluator import ScoreDetails, StatefulEvaluator
from utils import load_autobooks_tasks


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
    model: str = Field(..., description="Model identifier")
    base_url: HttpUrl = Field(
        ...,
        description=(
            "Full URL of the miner's action endpoint. "
            "This is the URL that will be POSTed to on each step "
            "(for example: http://miner-host:9000/act)."
        ),
    )
    task_id: str | None = Field(
        default=None,
        description="If set, evaluate only this task id.",
    )
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
def _evaluate_task_with_remote_agent_sync(
    task: Task,
    model_base_url: str,
    web_agent_name: str,
    max_steps: int,
) -> TaskEvaluationDetail:
    """
    Drive a remote step-based model using StatefulEvaluator.

    The model is expected to implement the same JSON contract used by
    ApifiedWebCUA /act:
      - {"actions": [ { "type": "...Action", ... }, ... ]}

    We use a fixed web_agent_id so backend events (e.g., BOOK_DETAIL) are
    grouped consistently in the demo webs service, mirroring the
    FixedAutobooksAgent wiring.
    """
    evaluator = StatefulEvaluator(task=task, web_agent_id="1")
    step_index = 0
    score = ScoreDetails()

    session = httpx.Client(timeout=60.0)

    try:
        logger.info("[AffineEnv] reset evaluator for task %s", task.id)
        first = evaluator.reset()
        score = first.score
        snapshot = first.snapshot

        done = False

        while step_index < max_steps and not done:
            payload = {
                "task_id": task.id,
                "prompt": getattr(task, "prompt", None),
                "url": snapshot.url or task.url,
                "snapshot_html": snapshot.html or "",
                "step_index": step_index,
                "web_project_id": getattr(task, "web_project_id", None),
            }

            try:
                # Treat model_base_url as the full endpoint URL (no extra suffix),
                # so that its format matches how other Affinetes environments
                # pass base_url around.
                resp = session.post(model_base_url, json=payload)
                resp.raise_for_status()
                resp_data = resp.json()
            except Exception as exc:
                logger.warning(
                    "[AffineEnv] model /act failed at step %d for task %s: %s",
                    step_index,
                    task.id,
                    exc,
                )
                resp_data = {}

            raw_actions = resp_data.get("actions") or []
            actions: List[BaseAction] = []
            for raw in raw_actions:
                if not isinstance(raw, dict):
                    continue
                try:
                    actions.append(BaseAction.create_action(raw))
                except Exception as exc:
                    logger.warning("[AffineEnv] failed to parse action %s: %s", raw, exc)
                    continue

            base_action: BaseAction | None = actions[0] if actions else None

            if base_action is None:
                logger.info(
                    "[AffineEnv] model returned no action; stepping with NOOP",
                )
                step_result = evaluator.step(None)
            else:
                step_result = evaluator.step(base_action)

            score = step_result.score
            snapshot = step_result.snapshot

            done = bool(score.success)
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

    try:
        tasks = load_autobooks_tasks()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to load Autobooks task")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if not tasks:
        raise HTTPException(status_code=500, detail="No tasks available for evaluation")

    # Optional filtering by task_id so tests can request specific tasks.
    if request.task_id is not None:
        filtered = [t for t in tasks if t.id == request.task_id]
        if not filtered:
            raise HTTPException(
                status_code=404,
                detail=f"Task with id={request.task_id} not found",
            )
        tasks = filtered

    # Run the evaluator + model loop in a worker thread so that the
    # internal event loop used by StatefulEvaluator does not conflict
    # with the FastAPI/uvicorn asyncio loop.
    import asyncio

    loop = asyncio.get_running_loop()
    details: List[TaskEvaluationDetail] = []
    for task in tasks:
        detail = await loop.run_in_executor(
            None,
            _evaluate_task_with_remote_agent_sync,
            task,
            str(request.base_url),
            request.model,
            max_steps,
        )
        details.append(detail)

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
