## MODIFIED Requirements

### Requirement: Serve position predictions

`python -m augur.analyze` SHALL store predictions for every lap in `position_predictions` for the analyzed model, replacing earlier rows for that race and model. `GET /api/races/{race_id}/positions?lap=N` SHALL return `{race_id, lap, model, analyzed, runs, seed, drivers}` for the `AUGUR_MODEL` model, and `GET /api/races/{race_id}/positions/history?lap=N` SHALL return `{race_id, model, analyzed, laps}` with per-lap `p_win`, `p_podium`, `expected_position`, `position_p10`, and `position_p90` for laps 1 to N only, in ascending lap order. Both responses SHALL always include `analyzed`; when the race has no predictions for the model, `analyzed` SHALL be `false` with empty `drivers` or `laps`. Field names and nesting SHALL match the API contract in design.md, which the `race-dashboard` mocks follow. Unknown races SHALL return 404 and invalid laps 422.

#### Scenario: History stops at the current lap

- **WHEN** the client calls `positions/history?lap=12`
- **THEN** the response contains exactly laps 1 to 12

#### Scenario: Race not analyzed

- **WHEN** the client calls `positions?lap=5` and `positions/history?lap=5` for a race with no stored predictions for the `AUGUR_MODEL` model
- **THEN** both responses have status 200 and `analyzed` is `false`, `drivers` and `laps` are empty, and `runs` and `seed` are `null`

#### Scenario: Response shape matches the contract

- **WHEN** the client calls both endpoints for an analyzed race
- **THEN** `analyzed` is `true` and the field names and nesting are exactly those in the design.md API contract, with each history driver entry holding `code`, `p_win`, `p_podium`, `expected_position`, `position_p10`, and `position_p90`, and no extra or missing fields
