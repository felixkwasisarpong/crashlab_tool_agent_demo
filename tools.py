from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from schemas import CreateTicketInput, SearchDocsInput, SendSlackInput


LOCAL_DOCS: dict[str, list[str]] = {
    "database timeout evidence": [
        "Runbook: DB timeouts are often connection-pool related.",
        "Postmortem: Incident 42 included query latency evidence.",
    ],
    "billing outage": [
        "Runbook: Billing outage triage checklist.",
        "Postmortem: Billing provider API saturation.",
    ],
}


@dataclass
class ToolExecutionError(Exception):
    code: str
    message: str

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


def _stable_id(prefix: str, payload: str) -> str:
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:10]
    return f"{prefix}-{digest}"


def search_docs(tool_input: SearchDocsInput) -> dict[str, Any]:
    normalized_query = tool_input.query.lower()

    if "__timeout__" in normalized_query:
        raise ToolExecutionError("tool_timeout", "search_docs exceeded timeout budget")
    if "__malformed__" in normalized_query:
        return {"bad": "shape"}

    hits = LOCAL_DOCS.get(normalized_query, [])
    return {"hits": hits, "source": "local_docs"}


def create_ticket(tool_input: CreateTicketInput) -> dict[str, Any]:
    normalized_title = tool_input.title.lower()

    if "__timeout__" in normalized_title:
        raise ToolExecutionError("tool_timeout", "create_ticket exceeded timeout budget")
    if "__malformed__" in normalized_title:
        return {"id": "broken"}

    ticket_id = _stable_id("TCK", f"{tool_input.title}|{tool_input.severity}")
    return {"ticket_id": ticket_id, "status": "created"}


def send_slack(tool_input: SendSlackInput) -> dict[str, Any]:
    normalized_message = tool_input.message.lower()

    if "__timeout__" in normalized_message:
        raise ToolExecutionError("tool_timeout", "send_slack exceeded timeout budget")
    if "__malformed__" in normalized_message:
        return {"ok": True}

    message_id = _stable_id("MSG", f"{tool_input.channel}|{tool_input.message}")
    return {"message_id": message_id, "status": "sent"}
