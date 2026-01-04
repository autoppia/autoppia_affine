# Autoppia Affine

Affine‑compatible evaluation harness for the Autoppia IWA web‑agent benchmark.

This repo gives you a small, self‑contained environment that Affine can use to
evaluate web agents. It exposes a single `/evaluate` HTTP endpoint (inside a
Docker container) that an Affine validator calls, pointing it to a miner/model
URL. Under the hood it runs the real Autoppia IWA benchmark
(`StatefulEvaluator`) against that model.

Currently this environment covers a tiny slice of the Autoppia Books
("Autobooks") website: two simple tasks, one that the reference model solves
(score 1) and one that it intentionally fails (score 0).

In other words: this repo is a minimal, working example of “IWA as an Affine
environment”.

## What’s inside

- `env.py` – FastAPI environment:
  - Exposes `/health` and `/evaluate`.
  - Wraps the Autoppia IWA `StatefulEvaluator`.
- `model/app.py` – tiny reference model:
  - Exposes `/health` and `/act`.
  - Always returns a single `NavigateAction` that solves the first Autobooks task.
- `data/autoppia_books_tasks.json` – two Autobooks tasks:
  - Task 1: expected to succeed (BOOK_DETAIL event, score 1.0).
  - Task 2: expected to fail (impossible event, score 0.0).
- Dockerfiles + helper scripts:
  - Build and run the env and model containers.
  - Run an end‑to‑end test that checks you get scores 1.0 and 0.0.

## How `/evaluate` works (env flow)

At a high level, the `/evaluate` endpoint does this:

1. **Load tasks**
   - Read all Autobooks tasks from `data/autoppia_books_tasks.json`.
   - Optionally filter to a single `task_id` if the request specifies one.

2. **Set up the evaluator**
   - For each selected task, create a `StatefulEvaluator`.
   - Call `reset()` once:
     - Opens the task’s starting page in a headless browser.
     - Returns the initial web state (URL, HTML snapshot and initial score).

3. **Step the model**
   - For each environment step (up to `max_steps`):
     - Build a JSON request for the model’s `/act` endpoint containing:
       - Current URL.
       - Current HTML snapshot.
       - Task metadata (prompt, task id, project id).
       - `step_index`.
       - Optional history and other context.
     - Call the miner/model at its `/act` URL (provided to `/evaluate` as `base_url`).
     - The model must respond with:
       - `{"actions": [ { "type": "...Action", ... }, ... ]}`.
     - For each action dict:
       - Convert it to a real IWA action using `BaseAction.create_action(...)`.
     - Execute the first valid action (or a NOOP if there are none) via
       `StatefulEvaluator.step(...)`.
     - This yields:
       - Updated score (tests passed, total tests, raw score, success flag).
       - New web state (URL and HTML).
     - Stop early if the task is marked successful or `max_steps` is reached.

4. **Return metrics**
   - After all selected tasks finish, `/evaluate` returns:
     - `environment` – string identifier of this env.
     - `total_score` – sum of per‑task scores.
     - `success_rate` – fraction of tasks that succeeded.
     - `details` – one entry per task:
       - `task_id`, `project_id`.
       - `score` and `raw_score`.
       - `success` (bool).
       - `tests_passed`, `total_tests`.
       - `steps` taken.

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
│   └── autoppia_books_tasks.json  # Two Autobooks tasks used by the env
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
