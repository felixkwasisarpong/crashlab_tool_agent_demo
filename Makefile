.PHONY: test run

test:
	pytest

run:
	python runner.py --fixture fixtures/successful_tool_flow.json
