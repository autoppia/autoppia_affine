from __future__ import annotations

"""
Affinetes compatibility test for the Autoppia IWA env.

This test assumes:
- The env container is already running on http://localhost:8002
- The model container is running and reachable from the env as
  http://autoppia-affine-model:9000/act
- The local Python environment has `affinetes` installed, e.g.:
    cd ../affinetes && pip install -e .
"""

import asyncio
import time

import httpx

# Prefer the public affinetes API (`import affinetes as af_env`) as in the
# README examples. In this monorepo layout, the top-level `affinetes` package
# may be a namespace without `load_env`, so we fall back to the inner package
# when needed. For users outside this repo, `import affinetes as af_env`
# should be enough.
try:  # pragma: no cover - import shim logic
    import affinetes as af_env  # type: ignore[import]
    if not hasattr(af_env, "load_env"):
        raise AttributeError
except Exception:  # noqa: BLE001
    import importlib

    af_env = importlib.import_module("affinetes.affinetes")  # type: ignore[assignment]


GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"


def wait_for_health(url: str, timeout_s: float = 60.0) -> None:
    start = time.time()
    while time.time() - start < timeout_s:
        try:
            r = httpx.get(url, timeout=5.0)
            if r.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(1.0)
    raise RuntimeError(f"Service at {url} did not become healthy within {timeout_s} seconds")


async def main() -> None:
    env_url = "http://localhost:8002"
    # Full URL of the model's action endpoint
    model_base_url_for_env = "http://autoppia-affine-model:9000/act"

    print(f"[affinetes-test] Waiting for env at {env_url}/health")
    wait_for_health(f"{env_url}/health")

    print("[affinetes-test] Loading env via Affinetes URL backend...")
    env = af_env.load_env(
        mode="url",
        base_url=env_url,
    )

    try:
        # Task 1 should be solved by the fixed model (score == 1.0).
        print("[affinetes-test] Calling env.evaluate for autobooks-demo-task-1")
        res1 = await env.evaluate(
            model="hardcoded-model",
            base_url=model_base_url_for_env,
            task_id="autobooks-demo-task-1",
            max_steps=5,
        )
        print("[affinetes-test] Response for task 1:", res1)
        score1 = res1["details"][0]["score"]
        if not (res1["total_score"] == 1.0 and score1 == 1.0):
            print(
                f"{RED}[✗] Affinetes + env: autobooks-demo-task-1 expected score=1.0, "
                f"got total_score={res1['total_score']} detail_score={score1}{RESET}",
            )
            raise AssertionError("Expected total_score and detail score == 1.0 for task 1")
        else:
            print(f"{GREEN}[✓] Affinetes + env: autobooks-demo-task-1 score == 1.0{RESET}")

        # Task 2 is intentionally unsolved by the fixed model (score == 0.0).
        print("[affinetes-test] Calling env.evaluate for autobooks-demo-task-2-invalid")
        res2 = await env.evaluate(
            model="hardcoded-model",
            base_url=model_base_url_for_env,
            task_id="autobooks-demo-task-2-invalid",
            max_steps=5,
        )
        print("[affinetes-test] Response for task 2:", res2)
        score2 = res2["details"][0]["score"]
        if not (res2["total_score"] == 0.0 and score2 == 0.0):
            print(
                f"{RED}[✗] Affinetes + env: autobooks-demo-task-2-invalid expected score=0.0, "
                f"got total_score={res2['total_score']} detail_score={score2}{RESET}",
            )
            raise AssertionError("Expected total_score and detail score == 0.0 for task 2")
        else:
            print(f"{GREEN}[✓] Affinetes + env: autobooks-demo-task-2-invalid score == 0.0{RESET}")

        print(
            f"{GREEN}[✓] Affinetes URL mode is compatible with autoppia_affine env (scores 1.0 and 0.0 as expected).{RESET}",
        )
    finally:
        await env.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
