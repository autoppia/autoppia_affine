#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="autoppia-affine-model:latest"
CONTAINER_NAME="autoppia-affine-model"
NETWORK_NAME="autoppia-affine-net"

# Build context root is the autoppia_affine directory
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[model] Using build context root: ${ROOT_DIR}"
cd "${ROOT_DIR}"

if ! docker network ls --format '{{.Name}}' | grep -q "^${NETWORK_NAME}\$"; then
  echo "[model] Creating Docker network ${NETWORK_NAME}"
  docker network create "${NETWORK_NAME}"
fi

echo "[model] Building image ${IMAGE_NAME}"
docker build \
  -f model/Dockerfile \
  -t "${IMAGE_NAME}" \
  "${ROOT_DIR}"

if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}\$"; then
  echo "[model] Removing existing container ${CONTAINER_NAME}"
  docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
fi

echo "[model] Starting container ${CONTAINER_NAME} on network ${NETWORK_NAME}"
docker run -d \
  --name "${CONTAINER_NAME}" \
  --network "${NETWORK_NAME}" \
  "${IMAGE_NAME}"

echo "[model] Container running inside Docker network ${NETWORK_NAME} (no host port binding)."
