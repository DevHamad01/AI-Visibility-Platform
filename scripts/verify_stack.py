"""Clean-checkout smoke checks. Failure exercise is for disposable CI stacks only.

No fixtures are shipped to the app. CI copies .env.example with EMPTY provider
keys; --exercise-failure creates and cleans up its own test profile and run.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.request


def request(base, path, *, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        base + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as response:
        raw = response.read()
        content_type = response.headers.get("Content-Type", "")
        return (
            json.loads(raw)
            if raw and "application/json" in content_type
            else raw.decode()
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:4200")
    parser.add_argument("--exercise-failure", action="store_true")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    assert "<app-root" in request(base, "/"), "Angular shell missing"
    assert "<app-root" in request(base, "/brands/new"), "SPA deep link missing"
    assert request("http://localhost:8000", "/readyz")["status"] == "ok"
    request(base, "/api/v1/overview")
    if not args.exercise_failure:
        print("Frontend, SPA routing, readiness and API proxy passed.")
        return
    brand = request(
        base,
        "/api/v1/brands",
        method="POST",
        body={"name": "CI checkout smoke", "domain": "example.com"},
    )
    path = f"/api/v1/brands/{brand['id']}"
    try:
        request(
            base,
            path + "/competitors",
            method="POST",
            body={"name": "CI competitor", "domain": "example.org"},
        )
        run = request(base, path + "/runs", method="POST", body={})
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            trace = request(base, f"/api/v1/runs/{run['id']}")
            if trace["status"] in {"succeeded", "partial", "failed"}:
                break
            time.sleep(1)
        else:
            raise AssertionError("Worker did not finish the keyless analysis")
        assert trace["status"] == "failed", "Empty provider keys must fail explicitly"
        assert trace["error_summary"], "Failure reason was not persisted"
        assert trace["dataforseo_cost_usd"] == 0, "Keyless check must never spend"
        assert all(s["status"] not in {"pending", "running"} for s in trace["stages"])
        events = request(base, f"/api/v1/runs/{run['id']}/events")
        assert '"status": "failed"' in events, "Terminal SSE event missing"
        for resource in [
            "visibility",
            "opportunities",
            "recommendations",
            "export?format=json",
        ]:
            request(base, f"/api/v1/runs/{run['id']}/{resource}")
        print(
            "Full stack, profile persistence, worker, terminal SSE and failure results passed. Cost $0."
        )
    finally:
        request(base, path, method="DELETE")


if __name__ == "__main__":
    main()
