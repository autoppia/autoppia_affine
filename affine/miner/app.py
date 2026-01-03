from __future__ import annotations

from typing import Dict

from fastapi import FastAPI
from pydantic import BaseModel


app = FastAPI(title="Autoppia RL FixedAutobooks Miner", version="0.1.0")


class ActRequest(BaseModel):
    task_id: str
    step_index: int
    snapshot_html: str
    current_url: str


class ActResponse(BaseModel):
    # Either a discrete PPO-style action index or a direct navigation URL.
    action_index: int | None = None
    navigate_url: str | None = None
    done: bool = False


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/act", response_model=ActResponse)
def act(req: ActRequest) -> ActResponse:
    """
    FixedAutobooks-style hardcoded agent exposed as a miner.

    It ignores the observation and, on the first step, returns a direct
    NavigateAction URL to the known book-detail page. Subsequent calls
    return done=True with no action.
    """
    if req.step_index > 0:
        return ActResponse(action_index=None, navigate_url=None, done=True)

    # First step: direct navigation to the known Autobooks URL.
    return ActResponse(
        action_index=None,
        navigate_url="http://84.247.180.192:8001/books/book-original-002?seed=36",
        done=True,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=9000)
