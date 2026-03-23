from __future__ import annotations

import argparse
import json
from pathlib import Path

from agent import run_agent


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
    args = parser.parse_args()

    if args.input is None and args.fixture is None:
        raise SystemExit("Provide either --input or --fixture")

    if args.fixture:
        payload = json.loads(Path(args.fixture).read_text())
        user_input = payload["user_input"]
    else:
        user_input = args.input

    result = run_agent(user_input)
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
