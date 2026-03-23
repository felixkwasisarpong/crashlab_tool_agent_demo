from __future__ import annotations

from dataclasses import dataclass, field

from schemas import CreateTicketInput, SendSlackInput


@dataclass
class PolicyContext:
    evidence_hits: int = 0


@dataclass
class PolicyDecision:
    allowed: bool
    code: str | None = None
    reason: str | None = None


@dataclass
class PolicyEngine:
    allowed_slack_channels: set[str] = field(
        default_factory=lambda: {"#incident-room", "#engineering-alerts"}
    )

    def check(self, tool_name: str, tool_args: object, context: PolicyContext) -> PolicyDecision:
        if tool_name == "send_slack":
            assert isinstance(tool_args, SendSlackInput)
            if tool_args.channel not in self.allowed_slack_channels:
                return PolicyDecision(
                    allowed=False,
                    code="unauthorized_action_attempt",
                    reason=f"channel {tool_args.channel} is not authorized",
                )

        if tool_name == "create_ticket":
            assert isinstance(tool_args, CreateTicketInput)
            if tool_args.severity == "high" and context.evidence_hits < 1:
                return PolicyDecision(
                    allowed=False,
                    code="unauthorized_action_attempt",
                    reason="high-severity tickets require prior evidence from search_docs",
                )

        return PolicyDecision(allowed=True)
