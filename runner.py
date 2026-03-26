from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from agent import run_agent


def load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        cleaned_key = key.strip()
        cleaned_value = value.strip().strip('"').strip("'")
        os.environ.setdefault(cleaned_key, cleaned_value)


def tracing_enabled(force_trace: bool) -> bool:
    if force_trace:
        return True

    return os.getenv("SEPURUX_ENABLE_TRACING", "false").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def emit_sepurux_trace(user_input: str, result_json: dict) -> None:
    try:
        from sepurux import SepuruxClient
    except ImportError as exc:
        raise SystemExit(
            "Sepurux SDK is not installed. Install dependencies with: pip install -e .[dev]"
        ) from exc

    campaign = os.getenv("SEPURUX_CAMPAIGN", "").strip() or None
    mutation_pack = os.getenv("SEPURUX_MUTATION_PACK", "").strip() or None
    task_name = os.getenv("SEPURUX_TASK_NAME", "crashlab_tool_agent_demo.run_agent")

    with SepuruxClient.from_env() as client:
        resolved_campaign = campaign
        if mutation_pack and not resolved_campaign:
            print(
                "Sepurux warning: mutation pack set without campaign; ignoring mutation pack.",
                file=sys.stderr,
            )
            mutation_pack = None

        if campaign:
            try:
                resolved_campaign = client._resolve_campaign_id(campaign)  # type: ignore[attr-defined]
            except Exception:
                print(
                    f"Sepurux warning: campaign '{campaign}' not found; uploading trace without campaign run.",
                    file=sys.stderr,
                )
                resolved_campaign = None
                mutation_pack = None

        with client.trace(
            task_name=task_name,
            task_input={"user_input": user_input},
            campaign_id=resolved_campaign,
            mutation_pack=mutation_pack,
            raise_on_error=True,
        ) as trace:
            # Use tool_call/tool_result event types for broad backend compatibility.
            trace.tool_call("agent.run_agent", {"user_input": user_input})
            trace.tool_result(
                "agent.run_agent",
                {
                    "final_response": result_json["final_response"],
                    "errors": result_json["errors"],
                },
            )

            # Replay/mutation hook: CI can perturb tool payloads before trace upload.
            for tool_call, tool_result in zip(
                result_json["tool_calls"], result_json["tool_results"]
            ):
                trace.tool_call(tool_call["tool_name"], tool_call["args"])
                if tool_result["ok"]:
                    trace.tool_result(tool_call["tool_name"], tool_result["output"])
                else:
                    trace.tool_result(
                        tool_call["tool_name"],
                        {
                            "error_code": tool_result["error_code"],
                            "error_message": tool_result["error_message"],
                        },
                    )

        print(
            f"Sepurux trace uploaded: trace_id={trace.trace_id} run_id={trace.run_id}",
            file=sys.stderr,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the crashlab demo agent")
    parser.add_argument(
        "--input",
        default=None,
        help="Direct user input in tool DSL format",
    )
    parser.add_argument(
        "--fixture",
        default=None,
        help="Path to fixture JSON containing user_input",
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Path to dotenv-style env file (default: .env)",
    )
    parser.add_argument(
        "--trace",
        action="store_true",
        help="Force Sepurux trace upload for this run",
    )
    args = parser.parse_args()

    load_env_file(Path(args.env_file))

    if args.input is None and args.fixture is None:
        raise SystemExit("Provide either --input or --fixture")

    if args.fixture:
        payload = json.loads(Path(args.fixture).read_text())
        user_input = payload["user_input"]
    else:
        user_input = args.input

    result = run_agent(user_input)
    result_json = result.model_dump()

    if tracing_enabled(args.trace):
        emit_sepurux_trace(user_input=user_input, result_json=result_json)

    print(json.dumps(result_json, indent=2))


if __name__ == "__main__":
    main()
