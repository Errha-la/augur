## Context

Stage 4 Waves 1-3 (`position-sim-calibration`, `strategy-charts-api`, `dashboard-canvas`, `release-setup`, `strategy-chart-widgets`, `commentary-chart-links`) are archived on `main` (head 634963c on 2026-11-23). Each recorded README notes in its archived `tasks.md` under docs/spectra/changes/archive/, because AGENTS.md lets only Wave 4 edit `README.md`. `release-setup` also recorded that a GitHub remote and publishing need the user's authorization and belong here.

Current state, measured 2026-11-23:

- `README.md` (188 lines) reports the bench of 2026-11-20 (lightgbm podium skill -15.9%), while `bench/lightgbm.json` now reports 49.8% (Bahrain -2.2% on its own) and `bench/lightgbm-eval.json` 4.2% over 2024 rounds 12-23 (per race from -430.1% Hungary to 65.2% Belgium). Its only image is `docs/screenshot.png`.
- Git history: 71 commits, all with author `Zaira <<personal address>>` from the repository's `.git/config`; the same address is in `archived_by` / `created_by` of `docs/spectra/changes/archive/*/.openspec.yaml` (96 occurrences over the full history). No lab server address appears in the history (tests use `lab:11400` and `10.9.8.7`). One tracked file at HEAD contains an absolute home path: `docs/spectra/changes/archive/2026-11-22-position-sim-calibration/measurements/run51.sh`.
- The user turned on GitHub "Keep my email addresses private" (2026-11-23); the account's noreply address is `297833373+Errha-la@users.noreply.github.com`. `gh` is logged in as `Errha-la`. No remote exists. `git filter-repo` is not installed.
- `augur.narrate` skips every event that already has cached text under the current key (`narration/cache.py` `cached_texts`), so a rerun does not replace the 27 of 116 Abu Dhabi texts that fail `check_grounding` after re-analysis.
- Worktree `.claude/worktrees/commentary-chart-links` and branch `worktree-commentary-chart-links` (5d3d6ce, merged) still exist.

Capability-level observable behavior is unchanged: this change touches documentation, images, local data, git metadata, and GitHub settings only.

## Goals / Non-Goals

**Goals:**

- `README.md` and `README.zh-TW.md` describe the shipped product accurately, with every number traceable to a committed file or a command in this repository.
- One hero screenshot and one screenshot per feature section, taken against the real backend.
- A public `Errha-la/augur` repository whose history contains no personal email address and whose first CI run passes.

**Non-Goals:**

- Backend or frontend code changes, bench re-runs, hosted site, branch protection, releases, GitHub Pages (see proposal Non-Goals).

## Decisions

### Publish as public `Errha-la/augur` in this change

User choice 2026-11-23. It follows the `release-setup` non-goal "No GitHub remote, repository settings, or publishing; those need the user's authorization and belong to `portfolio-release`.": the authorization is this choice. AGENTS.md "Commit only when asked" still applies to every commit before publishing; the push and repository creation are authorized by this decision, but the implementer confirms with the user once more right before `gh repo create`, because it cannot be undone once the repository is public. Alternative considered: create private first and switch later (rejected by the user).

### Rewrite the email in history to the GitHub noreply address

The personal address would be public in every commit and in the archived `.openspec.yaml` files. `git filter-repo` (installed with pip into a job-tmp venv, not into `backend/.venv`) runs with `--mailmap` (author and committer) and `--replace-text` (file contents) on a fresh clone used as a backup check first, then on the repository. The repository `user.email` is set to the noreply address before any later commit. Alternatives: keep the address (user enabled email privacy instead); squash into one new commit (loses the staged history that the Spectra archive refers to).

### Absolute home paths: latest commit only

Replace them in the current files with paths relative to the repository root; the old versions stay in history (low risk: it reveals a local account name, no secret). Default chosen by the implementer on 2026-11-23 because the user did not answer; the user may switch to a history rewrite, which reuses the same `--replace-text` run.

### Refresh stale commentary by deleting failing cache rows

A one-off script in the job tmp directory (not committed) loads each cached Abu Dhabi text for the serving key, runs `augur.narration.grounding.check_grounding` against the current event, and deletes the rows that fail; `augur.narrate` then regenerates only those. Rows that pass but contain stray tokens stay (user decision recorded in `dashboard-canvas`: model-quality issue, listed under Known issues). Alternative: add a `--refresh` flag to `augur.narrate` (rejected: no code change in this wave).

### Screenshots: one hero plus one per feature, PNG in `docs/images/`

User choice 2026-11-23. Taken with `playwright-core` from another local project's `node_modules/playwright-core` (no Playwright in AUGUR) against `make dev-api` / the Vite dev server on 2024 Abu Dhabi, viewport 1440x900 at device scale factor 1; Wrapped cards come from the app's own "Download card" (1080x1920). Every image under 500 KB (estimate; check with `ls -l` and recompress with lower PNG color depth if exceeded). `docs/screenshot.png` is removed; the dashboard-canvas drafts in `~/drafts/augur-screenshots/` are not reused because they predate the chart widgets.

### Whiteboard section explains every chart's computation

User request 2026-11-23: the whiteboard is a headline feature, so the README introduces it on its own and gives, for each widget type in `frontend/src/canvas/registry.ts` (`WIDGET_TYPES`, 13 types), what it shows, the endpoint it reads, and how the numbers are computed, in plain words with the constants that matter. The text is derived from the backend docstrings and `backend/src/augur/config.py` (table in the Implementation Contract, read on 2026-11-23); the implementer rechecks each row against that source before writing, since a README that misstates a method breaks the "do not invent metrics" rule. Alternative: link to the archived Spectra designs only (rejected: readers of a portfolio README do not open them).

### LLM commentary: example, pipeline, and how to switch the LLM

User request 2026-11-23: show what the LLM adds with a side-by-side example, include a zh-TW example, and explain how to switch the LLM API. The example uses one real cached event (same event in both languages, chosen from events that pass grounding and contain none of the recorded stray tokens), quoted verbatim from `data/augur.sqlite`, never edited. Alternative: a made-up example (rejected: AGENTS.md "Do not invent metrics" and the README would then show text the product did not produce).

### Two README files with the same structure

User choice 2026-11-23. `README.md` is the English source; `README.zh-TW.md` mirrors its headings, tables, commands, and images, and keeps technical terms, commands, and identifiers in English. Both start with a link to the other.

## Implementation Contract

README section order (both files, as shipped; revised 2026-11-23 after verify): language link; title and one-paragraph pitch; CI badge and license line; hero image; Quick start (`make setup`, `make demo`, `make dev-api` + `make dev-web`, open http://localhost:5173, `make test`); Features (one subsection each with its screenshot: lap-by-lap replay, the whiteboard and its chart catalogue, race events with clickable numbers and popovers, finishing-position forecasts, Race Wrapped, optional LLM commentary including its configuration: "Generate commentary" and "Switch the LLM"); Benchmark (headline, per-race table for both benchmark races and both models, evaluation-race summary with its range, method, caveats); Plug in your model (link to `docs/swap-model.md`); API endpoints table; Data source; Manual setup reference (commands without `make`, including the `--without-pip` fallback); Known issues; Tests; License. Quick start comes before Features so a visitor can run the demo first, and the LLM configuration stays next to the commentary it configures.

Whiteboard section content:

- Board operation: presets PIT WALL, BATTLE (default), PACE, STRATEGY; blank custom boards; drag by the title bar, resize from the corner, arrow keys move and Shift+arrow resize; the same widget type may appear more than once, each driver widget follows the focus driver or is pinned; boards saved in `localStorage` (`augur.boards.v1`) with Export / Import JSON; "?" reopens the guide.
- Common rule stated once: every widget reads only laps up to the replay lap N. "Clean lap" (`augur.features.clean_mask`): has a lap time, lap > 1, no pit in/out, green track status, accurate, dry compound, and at most `OUTLIER_PCT` slower than the fastest earlier clean lap. "Fuel-corrected" (`augur.features.fuel_corrected`): lap time + fuel effect × (lap − 1), with `FUEL_S_PER_KG` 0.03 s/kg and `FUEL_LOAD_KG` 110 kg spread over the race distance.
- Chart catalogue, one row per widget type (source read 2026-11-23; recheck before writing):

| Widget | Shows | Reads | Computation and assumptions |
|---|---|---|---|
| Timing | running order, gaps, tyres | `/state` (and positions) | positions from laps completed and session time at each driver's last lap |
| Events | event cards with analysis and commentary | `/events` | rule-based detectors (degradation warning, undercut / overcut window, position change, pace drop); outcome shown only once the replay reaches `outcome_lap` |
| Driver | focus driver: finishing-position probabilities and strategy table | `/positions`, `/strategy` | Monte Carlo of the remaining laps (see Position odds); strategy table assumes a green race |
| Lap times | one driver's lap times with predicted lap lines | `/laps`, `/predictions` | prediction = recent pace (median of last 3 clean laps) + lap-time model delta |
| Timeline | event markers along the race | `/events` | click jumps to the event lap |
| Race trace | time gained or lost per lap against a reference pace | `/trace` | race time = session time − race start (median over drivers of lap-1 session time − lap-1 lap time); reference = median over drivers of race time ÷ laps at their last timed lap |
| Pit clock | where the driver rejoins if it pits now | `/rejoin` | projected gap = own gap to leader + pit loss; pit loss = median observed in-lap + out-lap − 2 × recent pace, else 22 s fallback; other cars assumed not to pit |
| Pit window | expected race time for a stop on each remaining lap, best lap | `/pit-window` | same strategy simulator as the strategy table, 1000 runs, seed 42, pit-loss draw SD 1.5 s; "no further stop" only once two dry compounds are used |
| Tyre stints | stints so far per driver | `/stints` | compound and tyre age at stint start from the lap data |
| Degradation | fuel-corrected clean laps by tyre age per dry compound with a fitted line | `/degradation` | least-squares line; no line below the minimum point count |
| Pace compare | up to four drivers' fuel-corrected clean laps | `/degradation` points | same points as Degradation, filtered by driver |
| Position fan | expected finishing position with a P10-P90 band per lap | `/positions/history` | from the stored position simulation at each lap |
| Position odds | probability of each finishing position per driver (heatmap) | `/positions/distribution` | full-field Monte Carlo, 1000 runs: lap = recent pace + fading model delta (`MODEL_DELTA_DECAY`) + tyre degradation − fuel burn + noise, one pace offset per driver per run, dirty air penalty, compound offset after a stop, random safety car (0.8%/lap, 4 laps) or VSC (0.6%/lap, 3 laps) with slower laps, cheaper stops, and closed gaps |

LLM commentary section content (Features subsection plus the configuration reference):

- Screenshot: an event card with `AUGUR commentary · glm` above the template what / why / next and one number popover open.
- Side-by-side example for one event: template what / why / next on one side, the LLM text on the other; `README.md` uses the `en` text, `README.zh-TW.md` the `zh-TW` text of the same event. Name the race, lap, event type, and model next to it.
- Pipeline in one line or a small diagram: event evidence and template text -> LLM (never sees the outcome) -> grounding check (every number matches the event's lap, evidence, or template text; every three-letter driver code belongs to the event) -> cached in `data/augur.sqlite` -> the API only reads the cache. A rejected text leaves the template analysis only. Analysis, tests, and the benchmark never call an LLM; only `augur.narrate` does.
- Measured counts from task 1.2 (ok, rejected, failed per run, per language) and word or character lengths.
- "Switch the LLM" guide:
  - Any OpenAI-compatible server: `AUGUR_NARRATOR=openai_compat`, `AUGUR_LLM_BASE_URL` (for example a local Ollama, vLLM, or LM Studio server, or a hosted provider's `/v1` base URL), `AUGUR_LLM_MODEL`, optional `AUGUR_LLM_API_KEY` (sent as a Bearer token).
  - Gemini: `AUGUR_NARRATOR=gemini`, `GEMINI_API_KEY`, `GEMINI_MODEL` (fixed id for reproducible text; free-tier quota did not finish a full race, measured by the user 2026-11-23).
  - Off: `AUGUR_NARRATOR=none`.
  - Language: `AUGUR_COMMENTARY_LANG` `en` or `zh-TW`.
  - Commentary is cached per (event, model, narrator, LLM model, language, prompt version) (`augur.narration.cache`): after switching, run `augur.narrate` again and restart the API; old texts stay cached for their own settings.
  - New provider: a class with `name` and `narrate(event) -> str | None` (`augur.narration.base.Narrator`), registered with `augur.narration.base.register(name, factory)` in a module imported from `augur/narration/__init__.py`; raise `MissingSettingError` for an unset variable so `augur.narrate` exits 0.
  - No real server address, host name, or key in either README; placeholders only (`http://<host>:<port>/v1`).

Content rules:

- Every number is copied from `bench/*.json`, `data/models/lightgbm_metrics.json`, or a measurement recorded in an archived `tasks.md`, and its source is named next to it or in the section intro.
- Every command shown exists: `make` targets in `Makefile`, module flags in `python -m <module> --help`.
- Known issues lists at least: per-race podium skill varies widely and forecasts above 0.8 are overconfident on the evaluation races; 4x playback runs at about 354 ms per lap instead of 250 ms; GLM commentary can contain stray tokens that grounding does not catch; pit-clock code labels can overlap; the chart popover can jump when its number re-renders during playback (`commentary-chart-links` review Warning); OpenF1 can be slow, so `make demo` may need re-running; event `strategy.pit_lap` can differ from the current `/pit-window` best lap.
- No personal email, home path, or lab server address in either README.

Publishing acceptance: `git log --all --format='%ae %ce'` and `git grep` over all commits show no `<personal address>`; `gh repo view Errha-la/augur --json visibility` is `PUBLIC`; the first `CI` workflow run on `main` concludes `success`; the README badge renders that status.

Failure modes: if the CI run fails, record the failing job here and stop before announcing the repository (it stays public; a fix is a follow-up commit after the user agrees). If `gh repo create` fails because the name exists, stop and ask the user.

## Risks / Trade-offs

- [History rewrite breaks references to old hashes in archived artifacts and memory] -> Archived Spectra files refer to hashes in prose only; record the old-to-new mapping of `main`'s head in tasks.md. Run the rewrite on a backup clone first and compare `git log --oneline | wc -l` (71+ commits) and the tree of the head (`git rev-parse HEAD^{tree}` stays equal when only commit metadata changes; it differs only by the `.openspec.yaml` edits).
- [A public repository cannot be made fully private again once cloned or indexed] -> Confirm with the user immediately before `gh repo create`; run the privacy checks before it.
- [Screenshots show stray commentary tokens] -> Pick events whose commentary has none of the recorded stray tokens for the screenshots.
- [Lab LLM server unreachable from outside the university network] -> `augur.narrate` stops after 3 connection errors; retry from the university network; if still unavailable, keep the passing texts and note the count.

## Migration Plan

1. Remove the merged worktree and branch, refresh commentary, take screenshots, write both READMEs, fix home paths (commits on `main` only when the user asks).
2. Privacy rewrite on a backup clone, check, then on the repository.
3. Confirm with the user, create the public repository, push `main`, check CI.

Rollback: before step 3, the backup clone made in step 2 restores the pre-rewrite history. After step 3, a mistake is fixed by a new commit; deleting the repository is the user's decision.

## Open Questions

- The user may still choose to rewrite absolute home paths in history (see the decision above); default is latest commit only.
