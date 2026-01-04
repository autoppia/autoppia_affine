# Autoppia Affine

Tiny Affine-compatible evaluation harness for Autoppia IWA.

This repo provides:

- A minimal HTTP environment (`env.py`) that wraps the Autoppia IWA `StatefulEvaluator` and exposes a `/evaluate` endpoint.
- A simple hardcoded web agent model (`model/app.py`) that serves `/act` and always navigates directly to a known Autobooks BOOK_DETAIL page.
- Dockerfiles + scripts to run the env and model together as a quick end‑to‑end smoke test of the validator wiring.

At a high level, the env:

- Loads a single Autobooks task from `data/autoppia_books_tasks.json`.
- Uses `StatefulEvaluator` to open the real web app in a browser.
- Calls the model’s `/act` endpoint each step with the current HTML + URL and expects a JSON body of the form:
  `{"actions": [ { "type": "...Action", ... }, ... ]}`.
- Uses `BaseAction.create_action(...)` to turn those dicts into real IWA actions and executes them via `StatefulEvaluator.step(...)`.
- Returns a compact JSON result with `total_score`, `success_rate`, and per‑task details for Affine validators.

## Layout

```
autoppia_affine/
├── env.py                       # FastAPI HTTP env exposing /evaluate
├── model/                       # Hardcoded Autobooks model (/act)
│   ├── app.py
│   ├── Dockerfile               # Model container
│   ├── build_and_run_model.sh   # Build & run model container
│   └── __init__.py
├── Dockerfile                   # Env container (StatefulEvaluator + FastAPI)
├── build_and_run_env.sh         # Build & run env container
├── test_affine_env_with_miner.py  # Local integration test
├── data/
│   └── autoppia_books_tasks.json  # Autobooks task used by the env
└── README.md
```

## Running the Env + Model

From the `autoppia_affine` directory (this folder), with `autoppia_iwa` services reachable:

```bash
# One-shot deploy + test (recommended)
cd autoppia_affine
bash deploy.sh

# Or run steps manually from autoppia_affine/:
#   1) Build & run model (on Docker network autoppia-affine-net)
#      bash model/build_and_run_model.sh
#   2) Build & run env (FastAPI + StatefulEvaluator on host :8002 -> container :8000)
#      bash build_and_run_env.sh
#   3) Local smoke test (talks to http://localhost:8002)
#      python test_affine_env_with_miner.py
```
