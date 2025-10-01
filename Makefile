.DEFAULT_GOAL := help
ifeq ($(OS),Windows_NT)
  PYTHON_PATH := $(shell where python 2>NUL || where py 2>NUL)
else
  PYTHON_PATH := $(shell command -v python || command -v python3)
endif

PYTHON_NAME := $(notdir $(firstword $(PYTHON_PATH)))
PYTHON := $(basename $(PYTHON_NAME))

.TESTS_DIR := tests
.REPORTS_DIR := coverage
.PACKAGE_NAME := waldiez_runner

.PHONY: help
help:
	@echo "Usage: make [target]"
	@echo ""
	@echo "Default target: help"
	@echo ""
	@echo "Targets:"
	@echo " help                 Show this message and exit"
	@echo " format               Format the code"
	@echo " lint                 Lint the code"
	@echo " forlint              Alias for 'make format && make lint'"
	@echo " requirements         Generate requirements/*.txt files"
	@echo " test                 Run the tests"
	@echo " openapi              Generate the OpenAPI documentation"
	@echo " docs                 Generate the documentation"
	@echo " docs-live            Generate the documentation in 'live' mode"
	@echo " clean                Remove unneeded files (__pycache__, .mypy_cache, etc.)"
	@echo " build                Build the $(PYTHON) package"
	@echo " image                Generate container image"
	@echo " drop                 Drop all the database tables and types"
	@echo " local                Start the server in development mode locally (no external services)"
	@echo " dev                  Start the server in development mode in a container (with external services)"
	@echo " dev-no-reload        Start the server in development mode (no reload) in a container (with external services)"
	@echo " dev-no-debug         Start the server in development mode (no debug) in a container (with external services)"
	@echo " dev-no-reload-local  Start the server in development mode (no reload) locally (no external services)"
	@echo " secrets              Make sure the secrets are set"
	@echo " smoke                Run a smoke test"
	@echo " toggle               Toggle between containerized and local development"
	@echo " header               Check and update header in py files"
	@echo " some                 Some (not all) of the above: requirements, forlint, test, toggle, smoke"
	@echo ""

.PHONY: format
format:
	$(PYTHON) scripts/format.py --no-deps

.PHONY: lint
lint:
	$(PYTHON) scripts/lint.py --no-deps

.PHONY: forlint
forlint: format lint

.PHONY: clean
clean:
	$(PYTHON) scripts/clean.py

.PHONY: requirements
requirements:
	$(PYTHON) scripts/requirements.py

.PHONY: test
test:
	$(PYTHON) scripts/test.py
	@echo "html report: file://`pwd`/${.REPORTS_DIR}/html/index.html"

.PHONY: openapi
openapi:
	$(PYTHON) scripts/openapi.py

.PHONY: .before-docs
.before-docs: openapi
	$(PYTHON) scripts/docs.py before

.PHONY: .after-docs
.after-docs:
	$(PYTHON) scripts/docs.py after

.PHONY: docs
docs: openapi
	$(PYTHON) scripts/docs.py
	$(PYTHON) scripts/docs.py after

.PHONY: docs-live
docs-live: .before-docs
	$(PYTHON) -m mkdocs serve --watch mkdocs.yml --watch docs --watch waldiez_runner --dev-addr localhost:8400

.PHONY: build
build:
	$(PYTHON) -c 'import os; os.makedirs("dist", exist_ok=True); os.makedirs("build", exist_ok=True)'
	$(PYTHON) -c 'import shutil; shutil.rmtree("dist", ignore_errors=True); shutil.rmtree("build", ignore_errors=True)'
	$(PYTHON) -m pip install --upgrade pip wheel
	$(PYTHON) -m pip install -r requirements/main.txt
	$(PYTHON) -m pip install build twine
	$(PYTHON) -m build --sdist --wheel --outdir dist/
	$(PYTHON) -m twine check dist/*.whl
	$(PYTHON) -c 'import shutil; shutil.rmtree("build", ignore_errors=True)'
	@echo "Now you can upload the package with: \`$(PYTHON) -m twine upload dist/*\`"

.PHONY: image
image:
	$(PYTHON) scripts/image.py

.PHONY: secrets
secrets:
	$(PYTHON) scripts/pre_start.py --secrets --no-force-ssl --dev

.PHONY: drop
drop:
	$(PYTHON) scripts/drop.py

.PHONY: toggle
toggle:
	$(PYTHON) scripts/toggle.py

.PHONY: toggle-local
toggle-local:
	$(PYTHON) scripts/toggle.py --mode local
	@echo "Now you can run the server with: \`make dev-no-reload-local\` or \`make local\`"
	@echo "or use: \`$(PYTHON) -m waldiez_runner --trusted-origins http://localhost:3000,http://localhost:8000 --trusted-hosts localhost --reload --debug --no-force-ssl --no-redis --no-postgres --dev --all\`"

.PHONY: toggle-container
toggle-container:
	$(PYTHON) scripts/toggle.py --mode container
	@echo "Now you can run the server with: \`make dev\` or \`make dev-no-reload\` or \`make dev-no-debug\`"

.PHONY: local
local: toggle-local drop
	$(PYTHON) scripts/pre_start.py --no-force-ssl --no-redis --no-postgres --dev
	$(PYTHON) scripts/initial_data.py --no-force-ssl --no-redis --no-postgres --dev
	$(PYTHON) -m waldiez_runner --reload --debug --no-force-ssl --no-redis --no-postgres --dev --all

.PHONY: dev-no-reload-local
dev-no-reload-local: toggle-local drop
	$(PYTHON) scripts/pre_start.py --no-force-ssl --no-redis --no-postgres --dev
	$(PYTHON) scripts/initial_data.py --no-force-ssl --no-redis --no-postgres --dev
	$(PYTHON) -m waldiez_runner --trusted-origins http://localhost:3000,http://localhost:8000 --trusted-hosts localhost --debug --no-force-ssl --no-redis --no-postgres --dev --all

.PHONY: dev
dev: toggle drop
	$(PYTHON) scripts/pre_start.py --no-force-ssl --redis --postgres --dev
	$(PYTHON) scripts/initial_data.py --redis --postgres --dev
	$(PYTHON) -m waldiez_runner --trusted-origins http://localhost:3000,http://localhost:8000 --trusted-hosts localhost --reload --debug --no-force-ssl --redis --postgres --dev --all

.PHONY: dev-no-debug
dev-no-debug: toggle drop
	$(PYTHON) scripts/pre_start.py --no-force-ssl --redis --postgres --dev
	$(PYTHON) scripts/initial_data.py --redis --postgres --dev
	$(PYTHON) -m waldiez_runner --trusted-origins http://localhost:3000,http://localhost:8000 --trusted-hosts localhost --log-level info --no-debug --no-force-ssl --redis --postgres --dev --all

.PHONY: dev-no-reload
dev-no-reload: toggle drop
	$(PYTHON) scripts/pre_start.py --no-force-ssl --redis --postgres --dev
	$(PYTHON) scripts/initial_data.py --redis --postgres --dev
	$(PYTHON) -m waldiez_runner --trusted-origins http://localhost:3000,http://localhost:8000  --trusted-hosts localhost --debug --no-force-ssl --redis --postgres --dev --all

.PHONY: smoke
smoke: toggle drop
	$(PYTHON) scripts/test.py --smoke

.PHONY: smoke-debug
smoke-debug: toggle drop
	$(PYTHON) scripts/test.py --smoke --debug

.PHONY: header
header:
	$(PYTHON) scripts/header.py

.PHONY: load
load:
	$(PYTHON) scripts/load.py run

.PHONY: some
some: requirements clean forlint test smoke
