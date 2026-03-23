.PHONY: test run run-trace

test:
	pytest

run:
	python runner.py --fixture fixtures/successful_tool_flow.json

run-trace:
	python runner.py --fixture fixtures/successful_tool_flow.json --trace
