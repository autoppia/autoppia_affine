from __future__ import annotations

import os
from typing import Dict, List

from fastapi import FastAPI, HTTPException
from loguru import logger
from pydantic import BaseModel, Field, HttpUrl

from autoppia_iwa.src.data_generation.tasks.classes import Task
from autoppia_iwa.src.execution.actions.actions import BaseAction
from autoppia_iwa.src.evaluation.stateful_evaluator import ScoreDetails, StatefulEvaluator
from autoppia_iwa.src.web_agents.cua.apified_cua import ApifiedWebCUA
from autoppia_affine.utils import load_autobooks_task


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
    base_url: HttpUrl = Field(..., description="Base URL of model /act API")
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

    The model is expected to implement the ApifiedWebCUA /act contract and
    return one or more BaseAction-compatible dicts per step:
      - {"actions": [ {type: "...", ...}, ... ]}
      - {"action": { ... }}
      - {"navigate_url": "http://..."}  (converted to NavigateAction)
    """
    evaluator = StatefulEvaluator(task=task, web_agent_id=web_agent_name or "1")
    step_index = 0
    score = ScoreDetails()

    # HTTP wrapper that knows how to call /act and parse actions.
    agent = ApifiedWebCUA(base_url=model_base_url, name=web_agent_name or "affine-model", id=web_agent_name or "1")

    try:
        logger.info("[AffineEnv] reset evaluator for task %s", task.id)
        first = evaluator.reset()
        score = first.score
        snapshot = first.snapshot

        done = False

        while step_index < max_steps and not done:
            html = snapshot.html or ""
            current_url = snapshot.url or task.url

            try:
                actions: List[BaseAction] = agent.act_sync(
                    task=task,
                    snapshot_html=html,
                    url=current_url,
                    step_index=step_index,
                )
            except Exception as exc:
                logger.warning(
                    "[AffineEnv] model /act failed at step %d for task %s: %s",
                    step_index,
                    task.id,
                    exc,
                )
                actions = []

            # Single-step semantics: execute at most one action per loop,
            # mirroring autoppia_web_agents_subnet.stateful_cua_eval.
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
        task = load_autobooks_task()
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
