# ifckit Makefile
# ----------------
# Targets:
#   make env        — create .venv and install all dependencies
#   make install    — install ifckit + api extras into active env
#   make dev        — install all extras (api + dev) into active env
#   make api        — start the FastAPI server (hot-reload)
#   make api-prod   — start without hot-reload (production-like)
#   make test       — run full pytest suite
#   make test-api   — run only API tests
#   make lint       — ruff check
#   make fmt        — ruff format
#   make clean      — remove build artefacts and __pycache__
#   make help       — print this message

PYTHON     ?= python3   # override: make env PYTHON=python3.12
VENV       := .venv
BIN        := $(VENV)/bin

# Use venv binaries when .venv exists, otherwise fall back to PATH
ifeq ($(wildcard $(VENV)/bin/python),)
  PIP      := pip
  UVICORN  := uvicorn
  PYTEST   := pytest
  RUFF     := ruff
  PDOC     := pdoc
else
  PIP      := $(BIN)/pip
  UVICORN  := $(BIN)/uvicorn
  PYTEST   := $(BIN)/pytest
  RUFF     := $(BIN)/ruff
  PDOC     := $(BIN)/pdoc
endif

HOST       ?= 127.0.0.1
PORT       ?= 8000
WORKERS    ?= 1

.DEFAULT_GOAL := help

# ── environment ────────────────────────────────────────────────────────────────

.PHONY: env
env:  ## Create .venv with Python $(PYTHON)
	@echo "→ creating virtual environment in $(VENV)/"
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip setuptools wheel
	@echo "→ installing ifckit[api,dev]"
	$(PIP) install -e ".[api,dev]"
	@echo ""
	@echo "✓ Done. Activate with:  source $(VENV)/bin/activate"

.PHONY: install
install:  ## Install ifckit + api extras (assumes active venv)
	pip install -e ".[api]"

.PHONY: dev
dev:  ## Install all extras: api + dev (assumes active venv)
	pip install -e ".[api,dev]"

# ── api server ─────────────────────────────────────────────────────────────────

.PHONY: api
api:  ## Start FastAPI with hot-reload  →  http://$(HOST):$(PORT)/docs
	@echo "→ Swagger UI:  http://$(HOST):$(PORT)/docs"
	@echo "→ ReDoc:       http://$(HOST):$(PORT)/redoc"
	@echo "→ OpenAPI:     http://$(HOST):$(PORT)/openapi.json"
	@echo ""
	$(UVICORN) api.app:app \
		--host $(HOST) \
		--port $(PORT) \
		--reload

.PHONY: api-prod
api-prod:  ## Start FastAPI without reload, $(WORKERS) worker(s)
	@echo "→ starting ifckit API on $(HOST):$(PORT) (workers=$(WORKERS))"
	$(UVICORN) api.app:app \
		--host $(HOST) \
		--port $(PORT) \
		--workers $(WORKERS)

# ── testing ────────────────────────────────────────────────────────────────────

.PHONY: test
test:  ## Run full pytest suite with coverage
	$(PYTEST) --tb=short -q --cov=ifckit --cov=api --cov-report=term-missing

.PHONY: test-api
test-api:  ## Run only the API tests
	$(PYTEST) tests/test_api.py -v

.PHONY: test-fast
test-fast:  ## Run tests, stop on first failure
	$(PYTEST) -x -q

# ── documentation ──────────────────────────────────────────────────────────

# Auto-discover all importable submodules for pdoc
PDOC_MODULES = ifckit $(shell python3 -c "import pkgutil, ifckit; print(' '.join(m.name for m in pkgutil.walk_packages(ifckit.__path__, prefix='ifckit.')))" 2>/dev/null)

.PHONY: docs
docs:  ## Build static API docs → docs/_build/
	$(PDOC) $(PDOC_MODULES) -o docs/_build -t docs/pdoc_templates

.PHONY: docs-serve
docs-serve:  ## Live API docs on http://localhost:8080
	$(PDOC) $(PDOC_MODULES) -t docs/pdoc_templates --host 0.0.0.0

# ── code quality ───────────────────────────────────────────────────────────────

.PHONY: lint
lint:  ## Ruff lint check (no fixes)
	$(RUFF) check ifckit/ api/ tests/

.PHONY: fmt
fmt:  ## Ruff format + auto-fix lint issues
	$(RUFF) format ifckit/ api/ tests/
	$(RUFF) check --fix ifckit/ api/ tests/

.PHONY: check
check: lint test  ## lint + full test suite

# ── cleanup ────────────────────────────────────────────────────────────────────

.PHONY: clean
clean:  ## Remove build artefacts, caches, and .venv
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info"  -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache"   -exec rm -rf {} + 2>/dev/null || true
	rm -rf .coverage htmlcov dist build
	@echo "✓ clean"

.PHONY: clean-venv
clean-venv: clean  ## clean + remove .venv
	rm -rf $(VENV)
	@echo "✓ .venv removed"

# ── help ───────────────────────────────────────────────────────────────────────

.PHONY: help
help:  ## Print available targets
	@echo ""
	@echo "ifckit — available make targets"
	@echo "────────────────────────────────────────────────"
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*##"}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Variables (override with make VAR=value):"
	@echo "  HOST=$(HOST)   PORT=$(PORT)   WORKERS=$(WORKERS)   PYTHON=$(PYTHON)"
	@echo ""
