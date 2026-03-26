from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel, ValidationError

from policy import PolicyContext, PolicyEngine
from schemas import (
    AgentError,
    AgentRunResult,
    CreateTicketInput,
    CreateTicketOutput,
    SearchDocsInput,
    SearchDocsOutput,
    SendSlackInput,
    SendSlackOutput,
    ToolCallRecord,
    ToolResultRecord,
)
from tools import ToolExecutionError, create_ticket, search_docs, send_slack


@dataclass(frozen=True)
class ToolSpec:
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    handler: Callable[[Any], dict[str, Any]]


TOOL_REGISTRY: dict[str, ToolSpec] = {
    "search_docs": ToolSpec(SearchDocsInput, SearchDocsOutput, search_docs),
    "create_ticket": ToolSpec(CreateTicketInput, CreateTicketOutput, create_ticket),
    "send_slack": ToolSpec(SendSlackInput, SendSlackOutput, send_slack),
}


@dataclass(frozen=True)
class PlannedToolCall:
    tool_name: str
    args: dict[str, Any]


def _format_validation_error(exc: ValidationError) -> str:
    pieces: list[str] = []
    for err in exc.errors(include_url=False):
        loc = ".".join(str(part) for part in err["loc"])
        pieces.append(f"{loc}:{err['type']}")
    return "; ".join(pieces)


def _parse_payload(tool_name: str, payload: str) -> dict[str, Any]:
    if tool_name == "search_docs":
        return {"query": payload.strip()}

    if tool_name == "create_ticket":
        if "|" not in payload:
            return {"title": payload.strip(), "severity": ""}
        title, severity = payload.split("|", 1)
        return {"title": title.strip(), "severity": severity.strip()}

    if tool_name == "send_slack":
        if "|" not in payload:
            return {"channel": payload.strip(), "message": ""}
        channel, message = payload.split("|", 1)
        return {"channel": channel.strip(), "message": message.strip()}

    return {"raw": payload.strip()}


def _plan_tool_calls(user_input: str) -> list[PlannedToolCall]:
    raw = user_input.strip()
    if not raw or ":" not in raw:
        return []

    planned_calls: list[PlannedToolCall] = []
    for segment in [part.strip() for part in raw.split(";") if part.strip()]:
        if ":" not in segment:
            continue
        tool_name, payload = segment.split(":", 1)
        planned_calls.append(
            PlannedToolCall(
                tool_name=tool_name.strip(),
                args=_parse_payload(tool_name.strip(), payload.strip()),
            )
        )
    return planned_calls


def _record_failure(
    *,
    tool_name: str,
    code: str,
    message: str,
    errors: list[AgentError],
    tool_results: list[ToolResultRecord],
) -> None:
    errors.append(AgentError(code=code, message=message, tool_name=tool_name))
    tool_results.append(
        ToolResultRecord(
            tool_name=tool_name,
            ok=False,
            error_code=code,
            error_message=message,
        )
    )


def run_agent(user_input: str) -> AgentRunResult:
    policy = PolicyEngine()
    context = PolicyContext()
    tool_calls: list[ToolCallRecord] = []
    tool_results: list[ToolResultRecord] = []
    errors: list[AgentError] = []

    planned_calls = _plan_tool_calls(user_input)
    if not planned_calls:
        return AgentRunResult(
            final_response="No tool needed. Responded without tool calls.",
            tool_calls=tool_calls,
            tool_results=tool_results,
            errors=errors,
        )

    for planned_call in planned_calls:
        # Replay/mutation hook: record and mutate this call before validation if needed.
        tool_calls.append(
            ToolCallRecord(tool_name=planned_call.tool_name, args=planned_call.args)
        )

        spec = TOOL_REGISTRY.get(planned_call.tool_name)
        if spec is None:
            _record_failure(
                tool_name=planned_call.tool_name,
                code="unknown_tool_name",
                message=f"tool '{planned_call.tool_name}' is not available",
                errors=errors,
                tool_results=tool_results,
            )
            continue

        try:
            validated_input = spec.input_model.model_validate(planned_call.args)
        except ValidationError as exc:
            _record_failure(
                tool_name=planned_call.tool_name,
                code="invalid_tool_arguments",
                message=_format_validation_error(exc),
                errors=errors,
                tool_results=tool_results,
            )
            continue

        decision = policy.check(planned_call.tool_name, validated_input, context)
        if not decision.allowed:
            _record_failure(
                tool_name=planned_call.tool_name,
                code=decision.code or "unauthorized_action_attempt",
                message=decision.reason or "blocked by policy",
                errors=errors,
                tool_results=tool_results,
            )
            continue

        try:
            raw_output = spec.handler(validated_input)
        except ToolExecutionError as exc:
            _record_failure(
                tool_name=planned_call.tool_name,
                code=exc.code,
                message=exc.message,
                errors=errors,
                tool_results=tool_results,
            )
            continue

        # Replay/mutation hook: mutate raw_output here to simulate provider/tool drift.
        try:
            validated_output = spec.output_model.model_validate(raw_output)
        except ValidationError as exc:
            _record_failure(
                tool_name=planned_call.tool_name,
                code="malformed_tool_response",
                message=_format_validation_error(exc),
                errors=errors,
                tool_results=tool_results,
            )
            continue

        output = validated_output.model_dump()
        if planned_call.tool_name == "search_docs":
            context.evidence_hits += len(output["hits"])

        tool_results.append(
            ToolResultRecord(tool_name=planned_call.tool_name, ok=True, output=output)
        )

    if errors:
        final_response = (
            f"Completed {len(tool_calls)} tool call(s) with {len(errors)} error(s)."
        )
    else:
        final_response = f"Completed {len(tool_calls)} tool call(s) successfully."

    return AgentRunResult(
        final_response=final_response,
        tool_calls=tool_calls,
        tool_results=tool_results,
        errors=errors,
    )
