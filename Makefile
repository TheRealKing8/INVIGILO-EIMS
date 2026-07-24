# =============================================================================
# Invigilo — root Makefile
# =============================================================================
#
# One entry point for the dev workflow. All targets are thin wrappers
# around ``docker compose`` and the bash scripts under backend/scripts/
# and backend/docker/ — so anything you can do with ``make`` you can
# also do by hand, and ``make`` is a discoverability layer, not a
# gate.
#
# Targets:
#
#   make up             — bring the full stack up (postgres, redis,
#                         backend, mailhog). Waits for the backend
#                         to be healthy before returning.
#   make down           — stop the stack. The named volumes (postgres
#                         data + pip cache) are preserved.
#   make reset          — down + delete the named volumes + up. Use
#                         this when you want a fresh database.
#   make logs           — tail logs from the backend service.
#   make test           — run the backend pytest suite inside the
#                         backend container.
#   make shell          — open a Django shell on the backend container.
#   make migrate-data   — one-shot MariaDB -> Postgres data migration.
#                         See backend/docker/mariadb-to-postgres.sh
#                         for the env vars.
#   make lockdown       — run the trust -> scram-sha-256 lockdown
#                         flow. See backend/scripts/lockdown-postgres.sh.
#
# Windows: this Makefile uses GNU make. Install via
#   * Git for Windows (ships make as C:\Program Files\Git\usr\bin\make.exe), or
#   * choco install make
# Then run from any shell: ``make up``.
#
# macOS / Linux: ``make`` is in the Xcode CLT / build-essential.
# =============================================================================

SHELL := /bin/bash
COMPOSE := docker compose
BACKEND_SERVICE := backend
BACKEND_SCRIPTS := backend/scripts
DOCKER_SCRIPTS := backend/docker

.PHONY: help up down reset logs test shell migrate-data lockdown

help: ## Show this help.
	@awk 'BEGIN {FS = ":.*##"; printf "Targets:\n"} \
	  /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

up: ## Bring the full stack up.
	$(COMPOSE) up -d --build
	@echo "Waiting for $(BACKEND_SERVICE) to be healthy ..."
	@for i in $$(seq 1 60); do \
	  status=$$($(COMPOSE) ps --format json $(BACKEND_SERVICE) 2>/dev/null \
	    | python -c "import json,sys; d=json.load(sys.stdin); print(d[0]['Health'] if d else 'starting')" 2>/dev/null || echo starting); \
	  if [ "$$status" = "healthy" ]; then \
	    echo "  $(BACKEND_SERVICE) is healthy"; break; \
	  fi; \
	  sleep 2; \
	done

down: ## Stop the stack (named volumes preserved).
	$(COMPOSE) down

reset: ## Down + delete named volumes + up. Fresh database.
	$(COMPOSE) down -v
	$(MAKE) up

logs: ## Tail backend logs.
	$(COMPOSE) logs -f $(BACKEND_SERVICE)

test: ## Run the backend pytest suite inside the backend container.
	$(COMPOSE) exec $(BACKEND_SERVICE) python -m pytest --no-cov

shell: ## Open a Django shell on the backend container.
	$(COMPOSE) exec $(BACKEND_SERVICE) python manage.py shell

migrate-data: ## One-shot MariaDB -> Postgres data migration.
	$(COMPOSE) exec -T $(BACKEND_SERVICE) bash -c 'cd /app && bash docker/mariadb-to-postgres.sh'

lockdown: ## Run the trust -> scram-sha-256 lockdown flow.
	bash $(BACKEND_SCRIPTS)/lockdown-postgres.sh
