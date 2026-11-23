VENV := backend/.venv
PY := $(VENV)/bin/python
# backend/pyproject.toml: requires-python = ">=3.12"
PY_OK := import sys; sys.exit(sys.version_info < (3, 12))

define VENV_FALLBACK
Could not create a working $(VENV): the Python venv module or pip is missing.
On Ubuntu without python3.X-venv, create the venv without pip and install pip
into it with any other pip, then run make setup again:

  python3 -m venv --without-pip $(VENV)
  python -m pip --python $(PY) install pip
endef
export VENV_FALLBACK

.PHONY: setup demo test dev-api dev-web need-backend need-frontend

## setup: create backend/.venv, install the backend with dev extras, install frontend packages
setup:
	@if [ ! -x $(PY) ]; then \
		python3 -c '$(PY_OK)' || { echo "Python 3.12 or newer is required; python3 is $$(python3 --version 2>&1)."; exit 1; }; \
		python3 -m venv $(VENV) || { echo; echo "$$VENV_FALLBACK"; exit 1; }; \
	fi
	@$(PY) -c '$(PY_OK)' || { echo "Python 3.12 or newer is required; $(VENV) uses $$($(PY) --version 2>&1). Remove $(VENV) and run make setup with Python 3.12 or newer."; exit 1; }
	@$(PY) -m pip --version >/dev/null 2>&1 || { echo "$$VENV_FALLBACK"; exit 1; }
	$(PY) -m pip install -e "backend[dev]"
	npm --prefix frontend ci

need-backend:
	@[ -x $(VENV)/bin/uvicorn ] || { echo "The backend is not installed in $(VENV). Run make setup first."; exit 1; }

need-frontend:
	@[ -d frontend/node_modules ] || { echo "The frontend packages are not installed. Run make setup first."; exit 1; }

## demo: ingest the demo races, train lightgbm, analyze both benchmark races
demo: need-backend
	@echo "The first run downloads 22 races from OpenF1 into data/ (about 575 s, measured 2026-11-19); later runs read data/openf1-cache/."
	@echo "If a round fails (for example an OpenF1 timeout), run make demo again: downloaded responses stay cached."
	$(PY) -m augur.ingest --year 2024 --rounds 1 2 3 4 5 6 7 8 9 10 11 24
	$(PY) -m augur.ingest --year 2023 --rounds 1 2 3 5 6 7 8 9 16 22
	$(PY) -m augur.train
	$(PY) -m augur.analyze --race 2024-01-bahrain-grand-prix
	$(PY) -m augur.analyze --race 2024-24-abu-dhabi-grand-prix
	@echo
	@echo "Demo data is ready. Start the API and the dashboard in two terminals:"
	@echo "  make dev-api    # http://localhost:8000"
	@echo "  make dev-web    # http://localhost:5173"

## test: run the offline backend tests and the frontend tests
test: need-backend need-frontend
	$(VENV)/bin/pytest backend
	npm --prefix frontend run test

## dev-api: start the API on http://localhost:8000
dev-api: need-backend
	$(VENV)/bin/uvicorn augur.api:app --reload

## dev-web: start the dashboard on http://localhost:5173
dev-web: need-frontend
	npm --prefix frontend run dev
