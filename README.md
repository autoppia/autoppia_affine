# Autoppia Affine

Affine-compatible environment and miner harness for Autoppia IWA web agents.

## Overview

This repo packages:

- A FastAPI environment that wraps the Autoppia IWA `StatefulEvaluator` and exposes a `/evaluate` endpoint.
- A simple hardcoded miner exposing `/act` for smoke-testing the Autobooks BOOK_DETAIL task.
- Dockerfiles and helper scripts to build and run the env + miner pair.

The environment:

- Loads the Autobooks task definition from `data/tasks/autoppia_books_tasks.json`.
- For each evaluation, drives a `StatefulEvaluator` in a loop:
  - Sends the current snapshot (HTML, URL, etc.) to the miner `/act` endpoint.
  - Receives an action (navigate URL) from the miner.
  - Applies the action in the browser via `StatefulEvaluator.step(...)`.
  - Tracks success, test counts, and a scalar score.
- Returns an Affine-friendly JSON with `total_score`, `success_rate`, and per-task details.

## Layout

```
autoppia_affine/
├── autoppia_affine/
│   └── src/
│       └── affine_env/          # FastAPI HTTP env exposing /evaluate
│
├── affine/                      # Dockerized env + miner harness
│   ├── Dockerfile               # Env container (StatefulEvaluator + FastAPI)
│   ├── build_and_run_env.sh     # Build & run env container
│   ├── build_and_run_miner.sh   # Build & run miner container
│   ├── miner/                   # Hardcoded Autobooks miner (/act)
│   └── test_affine_env_with_miner.py  # Local integration test
│
├── data/
│   └── tasks/
│       └── autoppia_books_tasks.json  # Autobooks task used by the env
└── README.md
```

## Running the Env + Miner

From the monorepo root, with `autoppia_iwa` services reachable:

```bash
# Build & run miner (on Docker network autoppia-affine-net)
bash autoppia_affine/affine/build_and_run_miner.sh

# Build & run env (FastAPI + StatefulEvaluator on :8000)
bash autoppia_affine/affine/build_and_run_env.sh

# Local smoke test: should print a successful score
python autoppia_affine/affine/test_affine_env_with_miner.py
```

