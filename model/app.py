from __future__ import annotations

import os
from typing import Dict, List, Any

from fastapi import FastAPI
from pydantic import BaseModel


app = FastAPI(title="Autoppia Affine FixedAutobooks Model", version="0.1.0")

# Chutes API key for LLM provider (injected via environment)
CHUTES_API_KEY = os.getenv("CHUTES_API_KEY", "")


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


@app.get("/config")
def config() -> Dict[str, Any]:
    """Return model configuration (useful for debugging)."""
    return {
        "chutes_api_key_configured": bool(CHUTES_API_KEY),
    }


@app.post("/act", response_model=ActResponse)
def act(req: ActRequest) -> ActResponse:
    """
    Fixed agent: wait for homepage to load books, then click on a book link.
    """
    import re
    html = req.snapshot_html or ""

    # Find book links in the HTML
    book_link_pattern = r'href="(/books/[^"?]+)'
    matches = re.findall(book_link_pattern, html)

    if matches:
        # Click on the first book link using XPath selector
        book_path = matches[0]
        return ActResponse(
            actions=[
                {
                    "type": "ClickAction",
                    "selector": {
                        "type": "xpathSelector",
                        "value": f'//a[starts-with(@href, "{book_path}")]',
                    },
                }
            ],
            done=False,
        )

    # No book links yet - wait for page to load (need ~5s for JS)
    if req.step_index < 3:
        return ActResponse(
            actions=[
                {
                    "type": "WaitAction",
                    "time_seconds": 3.0,
                }
            ],
            done=False,
        )

    # Give up after too many waits
    return ActResponse(actions=[], done=True)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=9000)
