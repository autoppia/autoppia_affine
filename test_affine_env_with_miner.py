from __future__ import annotations

import time

import httpx


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


def main() -> None:
    env_url = "http://localhost:8002"
    model_base_url_for_env = "http://autoppia-affine-model:9000"

    print(f"[test] Waiting for env at {env_url}/health")
    wait_for_health(f"{env_url}/health")

    def run_eval(task_id: str) -> dict:
        print(f"[test] Calling /evaluate for task_id={task_id}")
        resp = httpx.post(
            f"{env_url}/evaluate",
            json={
                "model": "hardcoded-model",
                "base_url": model_base_url_for_env,
                "task_id": task_id,
                "max_steps": 5,
            },
            timeout=120.0,
        )
        print(f"[test] Status for {task_id}: {resp.status_code}")
        data = resp.json()
        print(f"[test] Response JSON for {task_id}:", data)

        assert resp.status_code == 200, "Env /evaluate did not return HTTP 200"
        assert "total_score" in data and "success_rate" in data, "Missing score fields in response"
        assert "details" in data and isinstance(data["details"], list), "Missing details array"
        assert data["details"], "details array should not be empty"
        return data

    # Task 1 should be solved by the fixed model (score == 1.0).
    data_task1 = run_eval("autobooks-demo-task-1")
    score1 = data_task1["details"][0]["score"]
    if not (data_task1["total_score"] == 1.0 and score1 == 1.0):
        print(
            f"{RED}[✗] Task autobooks-demo-task-1 expected score=1.0, "
            f"got total_score={data_task1['total_score']} detail_score={score1}{RESET}",
        )
        raise AssertionError("Expected total_score and detail score == 1.0 for task 1")
    else:
        print(f"{GREEN}[✓] Task autobooks-demo-task-1 score == 1.0{RESET}")

    # Task 2 is intentionally unsolved by the fixed model (score == 0.0).
    data_task2 = run_eval("autobooks-demo-task-2-invalid")
    score2 = data_task2["details"][0]["score"]
    if not (data_task2["total_score"] == 0.0 and score2 == 0.0):
        print(
            f"{RED}[✗] Task autobooks-demo-task-2-invalid expected score=0.0, "
            f"got total_score={data_task2['total_score']} detail_score={score2}{RESET}",
        )
        raise AssertionError("Expected total_score and detail score == 0.0 for task 2")
    else:
        print(f"{GREEN}[✓] Task autobooks-demo-task-2-invalid score == 0.0{RESET}")

    print(
        f"{GREEN}[✓] Affine env + model integration looks healthy for both tasks (1.0 and 0.0 scores).{RESET}",
    )


if __name__ == "__main__":
    main()
