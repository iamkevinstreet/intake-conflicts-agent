.PHONY: install lint test smoke run clean

PY ?= .venv/bin/python

install:
	uv venv .venv && uv pip install -e ".[dev]" && $(PY) -m pre_commit install

lint:
	.venv/bin/ruff check . && .venv/bin/ruff format --check .

test:
	.venv/bin/pytest

smoke:
	$(PY) -m intake_agent.evals.run --cases intake_agent/evals/cases/sample.jsonl --fake

run:
	.venv/bin/uvicorn intake_agent.api:app --reload

clean:
	rm -rf intake_agent/data/generated intake_agent/evals/results logs .pytest_cache .ruff_cache
