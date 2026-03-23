from __future__ import annotations

import json
from pathlib import Path

from agent import run_agent


FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text())


def assert_fixture_matches(name: str) -> dict:
    fixture = load_fixture(name)
    result = run_agent(fixture["user_input"]).model_dump()
    assert result == fixture["expected_output"]
    return result


def test_successful_tool_call_flow() -> None:
    result = assert_fixture_matches("successful_tool_flow.json")
    assert result["errors"] == []
    assert len(result["tool_results"]) == 3


def test_blocked_policy_flow() -> None:
    result = assert_fixture_matches("blocked_policy_flow.json")
    assert result["errors"][0]["code"] == "unauthorized_action_attempt"


def test_malformed_tool_response() -> None:
    result = assert_fixture_matches("malformed_tool_response.json")
    assert result["errors"][0]["code"] == "malformed_tool_response"


def test_timeout_handling() -> None:
    result = assert_fixture_matches("timeout_flow.json")
    assert result["errors"][0]["code"] == "tool_timeout"


def test_no_tool_needed_response() -> None:
    result = assert_fixture_matches("no_tool_needed.json")
    assert result["tool_calls"] == []


def test_invalid_tool_arguments() -> None:
    result = assert_fixture_matches("invalid_tool_arguments.json")
    assert result["errors"][0]["code"] == "invalid_tool_arguments"


def test_unknown_tool_name() -> None:
    result = assert_fixture_matches("unknown_tool_name.json")
    assert result["errors"][0]["code"] == "unknown_tool_name"
