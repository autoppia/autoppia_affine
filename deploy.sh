#!/usr/bin/env bash
set -euo pipefail

# One-shot local deployment:
# - Build & run model container
# - Build & run env container
# - Run the integration test against both

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd "${ROOT_DIR}"

echo "[deploy] Building and starting model container..."
bash model/build_and_run_model.sh

echo "[deploy] Building and starting env container..."
bash build_and_run_env.sh

echo "[deploy] Running integration test..."
python test_affine_env_with_miner.py

echo "[deploy] Done."
