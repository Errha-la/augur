## Why

Stage 4 Waves 1-3 are archived, and each of them left README notes in its `tasks.md` for this change instead of editing `README.md` (AGENTS.md: only Wave 4 edits `README.md`). The current README still shows the old benchmark (lightgbm podium skill -15.9%, from before `position-sim-calibration`), the manual setup steps that `release-setup` replaced with `make`, one old screenshot, and none of the dashboard canvas, chart widgets, or clickable commentary numbers. The repository has no GitHub remote yet. This change makes the project ready to show: a current README in English and Traditional Chinese with screenshots per feature, refreshed commentary for the demo race, and a public GitHub repository with a passing first CI run.

## What Changes

- **README rewrite (`README.md`, English).** Apply the README notes recorded in the archived `tasks.md` of `release-setup`, `position-sim-calibration`, `dashboard-canvas`, `strategy-chart-widgets`, `strategy-charts-api`, and `commentary-chart-links`: a hero screenshot, a quick start with `make setup`, `make demo`, `make dev-api`, `make dev-web`, `make test`, the manual commands kept as a reference, a feature section where each feature has its own screenshot and explanation, the benchmark headline and caveats from `bench/*.json`, the API endpoint table, LLM commentary (optional), known issues, CI badge, and the license line.
- **Whiteboard and chart catalogue (`README.md`).** A section that introduces the dashboard whiteboard as a feature (presets PIT WALL, BATTLE, PACE, STRATEGY; custom boards; drag, resize, per-widget driver; local save with JSON export/import) and lists all 13 widget types with, for each chart, what it shows, the API endpoint it reads, and the computation and assumptions behind it (for example: race trace reference pace, fuel correction, pit loss, the Monte Carlo position and strategy simulation with safety-car / VSC periods). Requested by the user on 2026-11-23.
- **LLM commentary section (`README.md`).** A Features subsection with a screenshot of an event card (commentary above the template analysis, one number popover open), a side-by-side example of one event's template text and its LLM commentary in English (and in Traditional Chinese in `README.zh-TW.md`), the grounding pipeline and its guarantees, measured counts from the refreshed run, and a "Switch the LLM" guide: any OpenAI-compatible server through environment variables, Gemini, turning commentary off, and adding a new provider through the `Narrator` protocol. Requested by the user on 2026-11-23.
- **Traditional Chinese README (`README.zh-TW.md`).** Same sections and screenshots as `README.md`, technical terms kept in English, with a language link at the top of both files.
- **Screenshots (`docs/images/`).** One hero image plus one image per feature, with every one of the 13 widget types visible in at least one image, taken with headless Chromium against the real backend on 2024 Abu Dhabi; `docs/screenshot.png` is replaced.
- **Commentary refresh.** Re-run `augur.narrate` on 2024 Abu Dhabi with the self-hosted `glm` server so cached commentary passes grounding again before the screenshots (27 of 116 texts failed grounding after re-analysis, measured 2026-11-23), and generate Traditional Chinese commentary (`AUGUR_COMMENTARY_LANG=zh-TW`) for the same race for the zh-TW example (none is cached yet).
- **Privacy before publishing.** Rewrite every commit's author and committer email and the `created_by` / `archived_by` values in `docs/spectra/changes/archive/*/.openspec.yaml` from the personal address to the GitHub noreply address `297833373+Errha-la@users.noreply.github.com`, set the repository `user.email` to that address, and replace absolute home paths in tracked files at the latest commit with repository-relative paths.
- **Publishing.** Create the public repository `Errha-la/augur`, push `main`, set its description and topics, and check that the first CI run passes.

## Non-Goals

- No change to backend or frontend code or behavior; a bug found while taking screenshots is recorded under Known issues, not fixed here.
- No change to the benchmark races, the headline podium-skill formula, or the bench numbers: the README reports `bench/*.json` as committed (`position-sim-calibration` non-goal "Benchmark races and the headline podium-skill formula do not change.").
- No hosted site or deployment (AGENTS.md: no hosted site).
- No fix for the stray tokens in GLM commentary (8 of 116 Abu Dhabi texts, recorded in `dashboard-canvas`); they are listed under Known issues.
- No history rewrite of absolute home paths; only the latest commit is changed (user default, 2026-11-23, may be revised).
- No branch protection, releases, or GitHub Pages.

## Impact

- Affected specs: none
- Affected code:
  - New: README.zh-TW.md, docs/images/ (hero and feature screenshots)
  - Modified: README.md, tracked files that contain absolute home paths (for example docs/spectra/changes/archive/2026-11-22-position-sim-calibration/measurements/run51.sh), docs/spectra/changes/archive/*/.openspec.yaml (email values, through the history rewrite)
  - Removed: docs/screenshot.png
- Compatibility: no capability-level observable behavior changes. The history rewrite changes every commit hash; no remote or other clone exists yet, and the merged branch `worktree-commentary-chart-links` and its worktree are removed first so no old commit stays reachable.
