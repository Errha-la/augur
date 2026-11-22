## Why

A visitor who opens AUGUR on GitHub cannot tell under what terms the code may be used, sees no proof that the tests pass, and has to read the README to piece together eight commands before anything runs. This is the OPS track of Stage 4 Wave 1 in `AGENTS.md`; it prepares the repository so the Wave 4 `portfolio-release` change only has to write the README and publish.

## What Changes

- Add `LICENSE` with the MIT license text, copyright holder taken from the git author name of the repository's commits (the user can change it before publishing).
- Add `.github/workflows/ci.yml`: on push and pull request, a backend job (Python 3.12, `pip install -e "backend[dev]"`, `pytest backend`, offline tests only) and a frontend job (Node 22, `npm ci`, `npm run test`, `npm run build` in `frontend/`). Third-party actions are pinned to full commit SHAs.
- Add a root `Makefile` with targets:
  - `setup`: create `backend/.venv`, install the backend with dev extras, and run `npm ci` in `frontend/`; when `python3 -m venv` fails because the venv module is missing, print the README's `--without-pip` fallback and stop.
  - `demo`: ingest the races the default model needs (2024 rounds 1 to 11 and 24, 2023 prior races), train `lightgbm`, analyze both benchmark races, and print the two commands that start the API and the dashboard. It prints that the first run downloads from OpenF1 (about 575 s measured on 2026-11-19) and later runs use the cache.
  - `test`: run the backend and frontend test suites.
  - `dev-api` and `dev-web`: start the API and the dashboard.

## Non-Goals (optional)

- No README edit: the README's setup section moves to `make` in `portfolio-release`.
- No GitHub remote, repository settings, or publishing; those need the user's authorization and belong to `portfolio-release`.
- No network tests in CI (`--run-network` stays local) and no data, model files, or Docker image in the repository.
- No release automation, tags, or badges.
- No change to `backend/` or `frontend/`.

## Impact

- Affected specs: none
- Affected code:
  - New: LICENSE, Makefile, .github/workflows/ci.yml
  - Modified: (none)
  - Removed: (none)
- Compatibility: no capability-level observable behavior changes
- Open decision for the user before `portfolio-release`: MIT is the default chosen here; another license only changes `LICENSE`.
