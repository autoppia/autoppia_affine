#!/usr/bin/env python3
"""Test autoppia_affine environment - expects score 1.0 for the solvable task."""

import sys
import time
import httpx

ENV_URL = "http://localhost:8000"
MODEL_URL = "http://autoppia-affine-model:9000/act"

GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"


def wait_for_health(timeout: float = 120.0) -> bool:
    """Wait for env to be healthy."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = httpx.get(f"{ENV_URL}/health", timeout=5.0)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(2.0)
    return False


def test_evaluate() -> bool:
    """Test /evaluate endpoint and verify score 1.0."""
    print(f"[test] Calling /evaluate for autobooks-demo-task-1...")

    resp = httpx.post(
        f"{ENV_URL}/evaluate",
        json={
            "model": "test-model",
            "base_url": MODEL_URL,
            "task_id": "autobooks-demo-task-1",
            "max_steps": 5,
        },
        timeout=120.0,
    )

    if resp.status_code != 200:
        print(f"{RED}[FAIL] HTTP {resp.status_code}: {resp.text}{RESET}")
        return False

    data = resp.json()
    score = data.get("total_score", 0)
    success = data.get("details", [{}])[0].get("success", False)

    print(f"[test] Response: total_score={score}, success={success}")

    if score == 1.0 and success:
        print(f"{GREEN}[PASS] Score is 1.0{RESET}")
        return True
    else:
        print(f"{RED}[FAIL] Expected score 1.0, got {score}{RESET}")
        return False


def main() -> int:
    print("[test] Waiting for env health...")
    if not wait_for_health():
        print(f"{RED}[FAIL] Env not healthy{RESET}")
        return 1

    print(f"{GREEN}[OK] Env is healthy{RESET}")

    if test_evaluate():
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
