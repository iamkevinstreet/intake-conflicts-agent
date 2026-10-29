########################################################################
#                               Makefile                               #
########################################################################
# Author:            Kevin Street
# Created on:        2026-10-14
# Last modified on:  2026-10-29
#
# Gives one command for each routine task: install, run, seed, check,
# test, eval, audit, build.
#
# CI runs the same targets. Run them from the repository root, where
# config/config.toml and data/ are found.

UV := uv run --project backend --no-sync
NPM := npm --prefix frontend
# Our own packages install from git, not PyPI, so the PyPI audit leaves them out.
KDS := kds-args kds-settings kds-logs kds-llm kds-evals kds-synthetic kds-standards kds-diagrams
AUDIT_FILE := data/generated/requirements-audit.txt

.PHONY: install run api web check check-backend check-frontend test test-backend test-frontend \
	eval audit audit-backend audit-frontend diagrams build seed

install:  ## The backend from uv.lock and the frontend from package-lock.json
	uv sync --project backend --locked
	$(NPM) ci

run:  ## The API on :8000 and the web app on :5173 together; Ctrl-C stops both
	$(MAKE) -j2 api web

api:  ## The API alone; it builds the made-up firm database on first start
	$(UV) python -m intake_agent.api

web:  ## The web app alone; it proxies the API's path to the service, as config/config.toml sets
	$(NPM) run dev

seed:  ## Rebuild the made-up firm database from data/samples/firm.json and the seed
	rm -f data/generated/firm.sqlite data/generated/firm.sqlite-wal data/generated/firm.sqlite-shm
	$(UV) python -c "from intake_agent.config import get_app_settings as s; \
	from intake_agent.core.store import Store; from intake_agent.core.seed import seed; \
	c = s(); print(seed(Store(c.data_database, timeout_s=c.store_timeout_s), c))"

check: check-backend check-frontend  ## Every linter, formatter, type check and the code standard

check-backend:
	$(UV) ruff check backend
	$(UV) ruff format --check backend
	cd backend && uv run --no-sync mypy
	$(UV) kds-standards check .

check-frontend:
	$(NPM) run lint
	$(NPM) run format:check
	$(NPM) run typecheck

test: test-backend test-frontend  ## Every test, offline and deterministic

test-backend:
	cd backend && uv run --no-sync pytest -W error

test-frontend:
	$(NPM) test

eval:  ## The offline evaluation: the stand-in plays the agent, whatever config/.env says; no key, no network
	LLM_PROVIDER=fake $(UV) python -m intake_agent.evals.run --name offline

audit: audit-backend audit-frontend  ## Known vulnerabilities in every locked dependency

audit-backend:
	mkdir -p data/generated
	uv export --project backend --locked --all-extras --all-groups --no-emit-project \
		$(addprefix --no-emit-package ,$(KDS)) --format requirements.txt -o $(AUDIT_FILE) --quiet
	$(UV) pip-audit --strict --require-hashes --disable-pip -r $(AUDIT_FILE)

audit-frontend:
	$(NPM) audit --audit-level=moderate

diagrams:  ## Redraw docs/architecture.svg and docs/flow.svg from docs/diagrams.toml
	$(UV) kds-diagrams docs/diagrams.toml

build:  ## The production web app, in frontend/dist
	$(NPM) run build
