#!/usr/bin/env python3
"""Test autoppia_affine environment using affinetes."""

import asyncio
import subprocess
import sys
import time

import affinetes as af

GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"


def start_model_container() -> bool:
    """Build and start the model container."""
    print("[test] Building model container...")
    result = subprocess.run(
        ["docker", "build", "-t", "autoppia-affine-model:latest", "-f", "model/Dockerfile", "."],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"{RED}[FAIL] Model build failed: {result.stderr}{RESET}")
        return False

    print("[test] Starting model container...")
    # Remove existing container if any
    subprocess.run(["docker", "rm", "-f", "autoppia-affine-model"], capture_output=True)

    # Create network if not exists
    subprocess.run(["docker", "network", "create", "autoppia-net"], capture_output=True)

    result = subprocess.run(
        [
            "docker", "run", "-d",
            "--name", "autoppia-affine-model",
            "--network", "autoppia-net",
            "autoppia-affine-model:latest",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"{RED}[FAIL] Model start failed: {result.stderr}{RESET}")
        return False

    # Wait for model to be ready
    for _ in range(30):
        check = subprocess.run(
            [
                "docker", "exec", "autoppia-affine-model",
                "python", "-c",
                "import urllib.request; urllib.request.urlopen('http://localhost:9000/health')",
            ],
            capture_output=True,
        )
        if check.returncode == 0:
            print(f"{GREEN}[OK] Model container ready{RESET}")
            return True
        time.sleep(1)

    print(f"{RED}[FAIL] Model container not ready{RESET}")
    return False


def stop_model_container():
    """Stop the model container."""
    subprocess.run(["docker", "rm", "-f", "autoppia-affine-model"], capture_output=True)


async def main() -> int:
    # Start model container first
    if not start_model_container():
        return 1

    print("[test] Loading environment with affinetes...")

    try:
        env = af.load_env(
            image="autoppia-affine-env:latest",
            mode="docker",
            env_type="http_based",
            env_vars={},
            force_recreate=True,
            cleanup=False,
            volumes={
                "/var/run/docker.sock": {
                    "bind": "/var/run/docker.sock",
                    "mode": "rw",
                }
            },
        )

        print(f"{GREEN}[OK] Environment loaded{RESET}")

        print("[test] Calling evaluate for autobooks-demo-task-1...")

        result = await env.evaluate(
            model="test-model",
            base_url="http://autoppia-affine-model:9000/act",
            task_id="autobooks-demo-task-1",
            max_steps=5,
        )

        score = result.get("total_score", 0)
        success = result.get("details", [{}])[0].get("success", False)

        print(f"[test] Response: total_score={score}, success={success}")

        if score == 1.0 and success:
            print(f"{GREEN}[PASS] Score is 1.0{RESET}")
            return 0
        else:
            print(f"{RED}[FAIL] Expected score 1.0, got {score}{RESET}")
            return 1

    except Exception as e:
        print(f"{RED}[FAIL] Error: {e}{RESET}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        print("[test] Cleaning up...")
        try:
            await env.cleanup()
        except Exception:
            pass
        stop_model_container()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
