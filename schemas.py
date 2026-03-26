from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SearchDocsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=3, max_length=200)

    @field_validator("query")
    @classmethod
    def strip_query(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("query must not be blank")
        return cleaned


class SearchDocsOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hits: list[str]
    source: Literal["local_docs"]


class CreateTicketInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=3, max_length=120)
    severity: Literal["low", "medium", "high"]

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("title must not be blank")
        return cleaned


class CreateTicketOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_id: str
    status: Literal["created"]


class SendSlackInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel: str = Field(pattern=r"^#[a-z0-9-]+$")
    message: str = Field(min_length=1, max_length=500)

    @field_validator("message")
    @classmethod
    def strip_message(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("message must not be blank")
        return cleaned


class SendSlackOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str
    status: Literal["sent"]


class ToolCallRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str
    args: dict[str, Any]


class ToolResultRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str
    ok: bool
    output: dict[str, Any] | None = None
    error_code: str | None = None
    error_message: str | None = None


class AgentError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    tool_name: str | None = None


class AgentRunResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    final_response: str
    tool_calls: list[ToolCallRecord]
    tool_results: list[ToolResultRecord]
    errors: list[AgentError]
