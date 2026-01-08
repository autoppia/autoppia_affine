from __future__ import annotations

from typing import Dict, List, Any

from fastapi import FastAPI
from pydantic import BaseModel


app = FastAPI(title="Autoppia Affine FixedAutobooks Model", version="0.1.0")


class ActRequest(BaseModel):
    task_id: str | None = None
    prompt: str | None = None
    url: str | None = None
    snapshot_html: str
    step_index: int
    web_project_id: str | None = None
    history: List[Dict[str, Any]] | None = None


class ActResponse(BaseModel):
    actions: List[Dict[str, Any]] | None = None
    done: bool = False


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/act", response_model=ActResponse)
def act(req: ActRequest) -> ActResponse:
    # Single-step fixed agent: on the first step, return a NavigateAction that
    # goes directly to a known book detail page. Subsequent calls return no actions.
    if req.step_index > 0:
        return ActResponse(actions=[], done=True)

    return ActResponse(
        actions=[
            {
                "type": "NavigateAction",
                "url": "http://localhost:8001/books/book-1?seed=1",
            }
        ],
        done=True,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=9000)
