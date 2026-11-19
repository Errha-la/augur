<!-- SPECTRA:START v1.3.0 -->

# Spectra Instructions

This project uses Spectra for Spec-Driven Development(SDD). Specs live in `docs/spectra/specs/`, change proposals in `docs/spectra/changes/`.

## Use `$spectra-*` skills when:

- An explicitly requested Spectra decision needs structure → `$spectra-discuss`
- User explicitly requests a Spectra change proposal → `$spectra-propose`
- Continue tasks for an identified change → `$spectra-apply`
- Update requirements or plans for an identified change → `$spectra-ingest`
- Check implementation matches artifacts → `$spectra-verify`
- Review implementation quality and logic issues → `$spectra-review`
- Analyze artifact consistency before coding → `$spectra-analyze`
- Audit security sharp edges → `$spectra-audit`
- Check stale changes before resuming → `$spectra-drift`
- Debug a concrete bug systematically → `$spectra-debug`
- Implementation is done → `$spectra-archive`
- Commit only files related to a specific change → `$spectra-commit`

Explicit skill invocation takes precedence. Apply existing authorization within its unchanged scope.

## Workflow

discuss? → propose → apply ⇄ ingest → verify / review → archive

- `discuss` is optional — skip if requirements are clear
- Requirements change mid-work? Plan mode (`/plan`) → `ingest` → resume `apply`

## Parked Changes

Changes can be parked（暫存）— temporarily moved out of `docs/spectra/changes/`. Parked changes won't appear in `spxa list` but can be found with `spxa list --parked`. To restore: `spxa unpark <name>`. The `$spectra-apply` and `$spectra-ingest` skills disclose parking and restore when the named operation is already explicitly requested; respect a known refusal, otherwise ask for missing authorization.

<!-- SPECTRA:END -->

# AGENTS.md — AUGUR (F1 Race Intelligence Platform)

AUGUR replays historical Formula 1 races lap by lap, predicts finishing positions, and explains the race with ML and event-driven analysis. Historical data trains and validates the models; the long-term goal is a live viewer tool beyond the broadcast and ordinary race trackers. It answers three questions:
1. **What happened?** Detect significant race events.
2. **Why?** Explain them with lap times, tyre performance, and strategy.
3. **What next?** Predict with models and Monte Carlo strategy simulation.

Portfolio project, meant to be cloned locally so others can plug in their own model and show off its benchmark score in an end-of-race Wrapped. No hosted site. Deadline: 2 days. Choose the simplest working solution.

## Stack & layout

| Path | Contents |
|---|---|
| `backend/` | Python 3.12, FastAPI, OpenF1 API, pandas, LightGBM, pytest |
| `frontend/` | React + Vite + TypeScript |
| `data/` | OpenF1 response cache, Parquet (laps), SQLite (race metadata, events). Not in git. |
| `bench/` | Benchmark results per model (`bench/<model>.json`), tracked in git |
| `docs/spectra/` | Spectra specs and changes |

Pipeline: Race Data → Feature Engineering → ML Prediction → Event Detection → Analysis → Dashboard.

## Commands

Each Spectra change fills in the exact commands when it creates them.

```bash
# backend
python3 -m venv backend/.venv && backend/.venv/bin/pip install -e "backend[dev]"
backend/.venv/bin/uvicorn augur.api:app --reload --app-dir backend/src
backend/.venv/bin/pytest backend

# frontend
npm --prefix frontend install
npm --prefix frontend run dev
npm --prefix frontend run build
```

## Hard rules

- **No future information leakage.** At replay lap N, every model input, prediction, and event detection reads only data with `lap <= N`. Keep a test that proves results at lap N do not change when laps > N are altered.
- Public data only (OpenF1 API, no account or subscription needed). Local-first storage: Parquet + SQLite. No database server.
- Do not invent metrics. Every reported model number must be reproducible from code in this repo.
- Analysis text is deterministic templates in an analyst's voice: `next` is a probabilistic outlook, never an instruction. Gemini commentary (`llm-commentary`) is optional, runs only in `augur.narrate`, never sees event outcomes, and is discarded unless every number and driver code is grounded in the event evidence. Nothing else may need an API key.
- Every consumer reads race data through `RaceFeed` (`ReplayFeed` now, `LiveFeed` later), and the event engine steps lap by lap, so live data can replace replay later.
- The headline output is finishing-position probability; the headline benchmark score is podium skill against "current order holds".
- Lap-time models implement the `LapTimeModel` protocol and are selected by name. `docs/swap-model.md` is the user guide for swapping models; update it whenever the protocol, features, commands, or error messages change. Only the lap-time model is swappable; the position simulator, degradation, and strategy stay fixed. Benchmark races (2024 R1 Bahrain, 2024 R24 Abu Dhabi) must never be in a model's training set.
- Event outcomes may read future laps only at analyze time; the API reveals an outcome only when the replay lap reaches `outcome_lap`.
- UI follows the BENNNZO/f1-dashboard look (tokens in the `race-dashboard` design). Reuse its colours and layout ideas only; do not copy its source.

## Spectra workflow

- Specs and changes live in `docs/spectra/`. Plan with `$spectra-propose`, implement with `$spectra-apply <change>`. Do not deviate from an approved proposal; update the change first.
- Apply in stages, in this order. Finish a stage before starting the next.
  - **Stage 1 — core (must ship):** `race-data-replay` → `prediction-and-events` → `position-prediction` → `race-dashboard`
  - **Stage 2 — differentiator:** `race-wrapped`
  - **Stage 3 — extras:** `llm-commentary` → `polish`
- Spec files are written in English.

## Communication

- Talk to the user in Traditional Chinese; keep technical terms in English.
- Commit only when asked.
