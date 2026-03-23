# crashlab_tool_agent_demo

Minimal open-source Python project for testing AI reliability and CI gating systems (for example Crash Lab) with deterministic tool-calling behavior.

## Project purpose

This repo intentionally keeps the agent tiny and observable so it is easy to:
- replay exact runs in CI,
- mutate requests/responses to inject failures,
- assert policy and schema behavior,
- gate merges on reliability regressions.

## Architecture

- `agent.py`: single `run_agent(user_input: str)` entrypoint, planner, tool dispatch, schema validation, error collection.
- `tools.py`: exactly 3 deterministic local/mock tools:
  - `search_docs(query: str)`
  - `create_ticket(title: str, severity: str)`
  - `send_slack(channel: str, message: str)`
- `policy.py`: risky-action policy checks (unauthorized Slack channels, high-severity evidence requirement).
- `schemas.py`: Pydantic input/output schemas and structured run result models.
- `runner.py`: CLI runner that accepts direct input or a fixture.
- `fixtures/`: deterministic conversations + expected structured outputs.
- `tests/`: pytest coverage for success and failure paths.

## Agent input format

To keep replay deterministic, the demo agent uses a tiny DSL:

- `search_docs:<query>`
- `create_ticket:<title>|<severity>`
- `send_slack:<channel>|<message>`
- Chain multiple calls with `;`

Example:

```text
search_docs:database timeout evidence;create_ticket:Database timeout incident|medium;send_slack:#incident-room|Opened ticket for DB timeout
```

If input does not include tool directives, the agent returns a no-tool response.

## Failure modes included

The agent exposes clear CI-friendly failures:
- `invalid_tool_arguments`
- `tool_timeout`
- `malformed_tool_response`
- `unauthorized_action_attempt`
- `unknown_tool_name`

You can trigger timeout/malformed responses deterministically by including:
- `__timeout__`
- `__malformed__`

in relevant tool payloads.

## Replay/mutation hooks

`agent.py` has inline comments marking where CI systems can:
- mutate planned tool calls before validation,
- mutate raw tool outputs before output validation.

These hooks are where a replay/mutation framework like Crash Lab can intercept and perturb behavior.

## How this fits Crash Lab-style CI gating

A typical CI loop:
1. Load fixture input.
2. Run `run_agent`.
3. Compare structured output to fixture expected output.
4. Run mutation scenarios (bad args, timeouts, malformed tool payloads, policy violations).
5. Fail CI if behavior deviates from reliability expectations.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

## Run tests

```bash
make test
```

## Run demo

```bash
make run
# or
python runner.py --input "search_docs:billing outage"
```

## License

MIT (see `LICENSE`).
