.DEFAULT_GOAL := help

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
	@echo " docs                 Generate the documentation"
	@echo " docs-live            Generate the documentation in 'live' mode"
	@echo " clean                Remove unneeded files (__pycache__, .mypy_cache, etc.)"
	@echo " build                Build the python package"
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
	@echo " some                 Some of the above: requirements, forlint, test, toggle, smoke"
	@echo ""

.PHONY: format
format:
	python scripts/format.py --no-deps

.PHONY: lint
lint:
	python scripts/lint.py --no-deps

.PHONY: forlint
forlint: format lint

.PHONY: clean
clean:
	python scripts/clean.py

.PHONY: requirements
requirements:
	python scripts/requirements.py


.PHONY: test
test:
	python scripts/test.py
	@echo "html report: file://`pwd`/${.REPORTS_DIR}/html/index.html"

.PHONY: docs
docs:
	python -m mkdocs build -d site
	@echo "open:   file://`pwd`/site/index.html"
	@echo "or use: \`python -m http.server --directory site\`"

.PHONY: docs-live
docs-live:
	python -m pip install -r requirements/docs.txt
	python -m mkdocs serve --watch mkdocs.yml --watch docs --watch waldiez --dev-addr localhost:8400

.PHONY: build
build:
	python -c 'import os; os.makedirs("dist", exist_ok=True); os.makedirs("build", exist_ok=True)'
	python -c 'import shutil; shutil.rmtree("dist", ignore_errors=True); shutil.rmtree("build", ignore_errors=True)'
	python -m pip install --upgrade pip wheel
	python -m pip install -r requirements/main.txt
	python -m pip install build twine
	python -m build --sdist --wheel --outdir dist/
	python -m twine check dist/*.whl
	python -c 'import shutil; shutil.rmtree("build", ignore_errors=True)'
	@echo "Now you can upload the package with: \`python -m twine upload dist/*\`"

.PHONY: image
image:
	python scripts/image.py


.PHONY: secrets
secrets:
	python scripts/pre_start.py --secrets --no-force-ssl --dev


.PHONY: drop
drop:
	python scripts/drop.py


.PHONY: local
local:
	python scripts/pre_start.py --no-force-ssl --no-redis --no-postgres --dev
	python scripts/initial_data.py --no-force-ssl --no-redis --no-postgres --dev
	python -m waldiez_runner --reload --debug --no-force-ssl --no-redis --no-postgres --dev


.PHONY: dev
dev:
	python scripts/pre_start.py --no-force-ssl --redis --postgres --dev
	python scripts/initial_data.py --redis --postgres --dev
	python -m waldiez_runner --trusted-origins http://localhost:3000,http://localhost:8000 --trusted-hosts localhost --reload --debug --no-force-ssl --redis --postgres --dev

.PHONY: dev-no-debug
dev-no-debug:
	python scripts/pre_start.py --no-force-ssl --redis --postgres --dev
	python scripts/initial_data.py --redis --postgres --dev
	python -m waldiez_runner --trusted-origins http://localhost:3000,http://localhost:8000 --trusted-hosts localhost --log-level info --no-debug --no-force-ssl --redis --postgres --dev

.PHONY: dev-no-reload
dev-no-reload:
	python scripts/pre_start.py --no-force-ssl --redis --postgres --dev
	python scripts/initial_data.py --redis --postgres --dev
	python -m waldiez_runner --trusted-origins http://localhost:3000,http://localhost:8000  --trusted-hosts localhost --debug --no-force-ssl --redis --postgres --dev

.PHONY: dev-no-reload-local
dev-no-reload-local:
	python scripts/pre_start.py --no-force-ssl --no-redis --no-postgres --dev
	python scripts/initial_data.py --no-force-ssl --no-redis --no-postgres --dev
	python -m waldiez_runner --trusted-origins http://localhost:3000,http://localhost:8000 --trusted-hosts localhost --debug --no-force-ssl --no-redis --no-postgres --dev

.PHONY: smoke
smoke:
	python scripts/test.py --smoke

.PHONY: toggle
toggle:
	python scripts/toggle.py
	@echo "Now you can run the server with: \`make dev\`, \`make dev-no-reload\`, \`make dev-no-debug\`, or \`make local\`"
	@echo "or use: \`python -m waldiez_runner --trusted-origins http://localhost:3000,http://localhost:8000 --trusted-hosts localhost --reload --debug --no-force-ssl --redis --postgres --dev\`"
	@echo "or use: \`python -m waldiez_runner --trusted-origins http://localhost:3000,http://localhost:8000 --trusted-hosts localhost --debug --no-force-ssl --no-redis --no-postgres --dev\`"

.PHONY: some
some: requirements forlint test toggle smoke
