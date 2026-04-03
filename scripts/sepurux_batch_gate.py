from __future__ import annotations

import os
import sys
import time
from typing import Any

import httpx
from sepurux import SepuruxClient


TERMINAL_BATCH_STATUSES = {"done", "completed", "failed", "error", "cancelled"}


def required_env(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value:
        raise SystemExit(f"{name} is missing or empty")
    return value


def parse_trace_ids(raw_value: str) -> list[str]:
    trace_ids: list[str] = []
    for chunk in raw_value.replace(",", "\n").splitlines():
        value = chunk.strip()
        if value and value not in trace_ids:
            trace_ids.append(value)
    return trace_ids


def request_headers(*, api_key: str, project_id: str | None) -> dict[str, str]:
    headers = {"X-API-Key": api_key}
    if project_id:
        headers["X-Project-Id"] = project_id
    return headers


def assert_resource_exists(
    client: httpx.Client,
    *,
    base_url: str,
    headers: dict[str, str],
    path: str,
    label: str,
) -> dict[str, Any]:
    response = client.get(f"{base_url}{path}", headers=headers, timeout=30.0)
    if response.status_code >= 400:
        raise SystemExit(
            f"{label} preflight failed: GET {path} -> {response.status_code}\n{response.text}"
        )
    payload = response.json()
    if not isinstance(payload, dict):
        raise SystemExit(f"{label} preflight returned a non-object payload for {path}")
    return payload


def main() -> None:
    base_url = required_env("SEPURUX_API_BASE_URL").rstrip("/")
    api_key = required_env("SEPURUX_API_KEY")
    campaign_id = required_env("SEPURUX_CAMPAIGN_ID")
    trace_ids = parse_trace_ids(required_env("SEPURUX_TRACE_IDS"))
    project_id = (os.getenv("SEPURUX_PROJECT_ID") or "").strip() or None

    if not trace_ids:
        raise SystemExit("SEPURUX_TRACE_IDS did not contain any trace ids")

    timeout_seconds = int((os.getenv("SEPURUX_TIMEOUT_SECONDS") or "900").strip())
    min_pass_rate = float((os.getenv("SEPURUX_MIN_PASS_RATE") or "0.8").strip())
    max_unsafe = int((os.getenv("SEPURUX_MAX_UNSAFE") or "0").strip())
    max_failures_raw = (os.getenv("SEPURUX_MAX_FAILURES") or "").strip()
    expected_attempts_raw = (os.getenv("SEPURUX_EXPECTED_ATTEMPTS") or "").strip()

    thresholds: dict[str, Any] = {
        "min_pass_rate": min_pass_rate,
        "max_unsafe": max_unsafe,
    }
    if max_failures_raw:
        thresholds["max_failures"] = int(max_failures_raw)

    headers = request_headers(api_key=api_key, project_id=project_id)

    with httpx.Client() as http_client:
        campaign = assert_resource_exists(
            http_client,
            base_url=base_url,
            headers=headers,
            path=f"/v1/campaigns/{campaign_id}",
            label="Campaign",
        )

        for trace_id in trace_ids:
            assert_resource_exists(
                http_client,
                base_url=base_url,
                headers=headers,
                path=f"/v1/traces/{trace_id}",
                label="Trace",
            )

    eval_set = campaign.get("eval_set")
    eval_set_obj = eval_set if isinstance(eval_set, dict) else {}
    existing_trace_ids = [
        str(item)
        for item in eval_set_obj.get("trace_ids", [])
        if isinstance(item, str) and item.strip()
    ]
    remove_trace_ids = [trace_id for trace_id in existing_trace_ids if trace_id not in trace_ids]

    attempts_count = eval_set_obj.get("attempts_count")
    if expected_attempts_raw:
        expected_attempts = int(expected_attempts_raw)
        if attempts_count != expected_attempts:
            raise SystemExit(
                "Campaign attempts_count does not match the expected value: "
                f"{attempts_count!r} != {expected_attempts}"
            )

    print(f"Campaign: {campaign_id}")
    print(f"Trace ids: {trace_ids}")
    print(f"Existing eval-set trace ids: {existing_trace_ids}")
    print(f"Eval-set attempts_count: {attempts_count!r}")

    with SepuruxClient(base_url=base_url, api_key=api_key, project_id=project_id) as client:
        client.register_eval_traces(
            campaign_id,
            trace_ids,
            remove_trace_ids=remove_trace_ids,
            min_scenarios=len(trace_ids),
        )
        print("Updated campaign eval-set to the exact trace set for this workflow run.")

        batch_id = client.start_run(
            trace_id=trace_ids[0],
            campaign_id=campaign_id,
            thresholds=thresholds,
            preflight=True,
        )
        print(f"Started Sepurux batch: {batch_id}")

        deadline = time.time() + timeout_seconds
        latest: dict[str, Any] = {"status": "unknown", "decision": "pending"}
        while time.time() < deadline:
            latest = client.get_ci_batch(batch_id)
            status = str(latest.get("status") or "unknown").lower()
            decision = str(latest.get("decision") or "pending").lower()
            pass_rate = float(latest.get("pass_rate") or 0.0) * 100.0
            print(
                "Batch status: "
                f"status={status} decision={decision} "
                f"pass_rate={pass_rate:.2f}% "
                f"coverage={latest.get('scenario_coverage_pct', 0.0)}%"
            )
            if status in TERMINAL_BATCH_STATUSES:
                break
            time.sleep(5)
        else:
            raise SystemExit(f"Sepurux batch timed out after {timeout_seconds}s")

    final_status = str(latest.get("status") or "unknown").lower()
    final_decision = str(latest.get("decision") or "pending").lower()
    final_pass_rate = float(latest.get("pass_rate") or 0.0) * 100.0
    failures = int(latest.get("failures") or 0)
    unsafe_attempts = int(latest.get("unsafe_attempts") or 0)
    trace_count = int(latest.get("trace_count") or 0)
    top_tools = latest.get("top_failing_tools") or []

    print("Final Sepurux batch result:")
    print(f"  status={final_status}")
    print(f"  decision={final_decision}")
    print(f"  pass_rate={final_pass_rate:.2f}%")
    print(f"  failures={failures}")
    print(f"  unsafe_attempts={unsafe_attempts}")
    print(f"  trace_count={trace_count}")
    print(f"  top_failing_tools={top_tools}")

    if final_status not in TERMINAL_BATCH_STATUSES:
        raise SystemExit(f"Sepurux batch ended in an unexpected state: {final_status}")
    if final_decision != "pass":
        raise SystemExit("Sepurux batch decision was not pass")


if __name__ == "__main__":
    main()
