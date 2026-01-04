# Autoppia Affine

Affine-compatible evaluation harness for Autoppia IWA.

This repo contains a working Autoppia IWA environment adapted to Affine. It builds a Docker image that, when run, exposes an `/evaluate` HTTP endpoint that an Affine validator can call, pointing to a given miner/model URL. The environment then evaluates how good that model is at operating the web UI using the real Autoppia `StatefulEvaluator`.

Right now, the environment evaluates a fixed subset of the Autoppia Books (Autobooks) website: two small tasks, one that the reference model solves and one that it intentionally fails.

This repo provides:

- A minimal HTTP environment (`env.py`) that wraps the Autoppia IWA `StatefulEvaluator` and exposes `/health` and `/evaluate`.
- A simple hardcoded web agent model (`model/app.py`) that serves `/act` and always returns a single `NavigateAction` for the Autobooks site.
- Dockerfiles + scripts to run the env and model together as an end‑to‑end test of the evaluation pipeline.

At a high level, the env flow is:

- Load Autobooks tasks from `data/autoppia_books_tasks.json` (currently two tasks).
- When `/evaluate` is called, pick the task(s) to run and create a `StatefulEvaluator` for each task.
- For each task, run a loop up to `max_steps`:
  - Call the evaluator’s `reset()` once to open the initial page and get the initial web state (URL, HTML snapshot, score).
  - On each `step()`:
    - Build a request for the miner model at its `/act` endpoint that includes the current web state:
      - Current URL.
      - Current HTML snapshot.
      - Task metadata (prompt, task id, project id).
      - Step index and other context such as history.
    - The model returns a JSON body of the form:
      `{"actions": [ { "type": "...Action", ... }, ... ]}`.
    - The env converts those dicts into real IWA actions using `BaseAction.create_action(...)` and executes them with `StatefulEvaluator.step(...)`.
    - This produces a new score and new web state, and the loop continues until success or `max_steps` is reached.
- After all selected tasks finish, `/evaluate` returns a compact JSON result with:
  - `environment` name.
  - `total_score` and `success_rate`.
  - Per‑task `details` (task id, project id, score, success flag, tests passed, total tests, and steps).

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
