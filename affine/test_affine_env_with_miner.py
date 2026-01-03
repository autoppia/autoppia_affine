from __future__ import annotations

import time

import httpx


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
    env_url = "http://localhost:8000"
    # From inside the env container, the miner is reachable by its Docker
    # container name on the shared network.
    miner_base_url_for_env = "http://autoppia-affine-miner:9000"

    print(f"[test] Waiting for env at {env_url}/health")
    wait_for_health(f"{env_url}/health")

    print("[test] Calling /evaluate on env, pointing to miner /act endpoint")
    resp = httpx.post(
        f"{env_url}/evaluate",
        json={
            "model": "hardcoded-miner",
            "base_url": miner_base_url_for_env,
            "max_steps": 5,
        },
        timeout=120.0,
    )
    print(f"[test] Status: {resp.status_code}")
    data = resp.json()
    print("[test] Response JSON:", data)

    assert resp.status_code == 200, "Env /evaluate did not return HTTP 200"
    assert "total_score" in data and "success_rate" in data, "Missing score fields in response"
    assert "details" in data and isinstance(data["details"], list), "Missing details array"
    print("[test] Affine env + miner integration looks healthy.")


if __name__ == "__main__":
    main()
