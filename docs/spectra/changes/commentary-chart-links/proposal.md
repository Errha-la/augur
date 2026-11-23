## Why

Event analysis and AUGUR commentary quote numbers ("losing 0.081 s per lap", "1.4 s behind", "P7") that a viewer cannot check without finding the right chart, lap, and driver. Every quoted number is already grounded in the event's evidence, and the strategy charts now exist (`strategy-chart-widgets`, archived 2026-11-23), so each number can open the chart it comes from. This is Wave 3 of Stage 4 in `AGENTS.md` (backend and frontend, runs alone).

## What Changes

- `/events` adds `links` to every event: for each of `what`, `why`, `next`, and `commentary`, the numbers in the text that match an evidence field, with their character positions, the evidence field, the chart kind, and the drivers it concerns. Computed per request from the event alone with the grounding check's number rules; nothing is stored.
- In the intelligence panel, linked numbers in the analysis text and the commentary quote become buttons. Clicking one opens a popover next to it with a small chart of that value at the event's lap: degradation for a slope, lap times for a lap or predicted time, race trace for a gap, tyre stints for a tyre age or stint, pit window for a strategy pit lap or win share, position fan for a position change.
- The popover closes on Escape, on a click outside, or on a second click on the same number; it does not change the board.

## Capabilities

### New Capabilities

- `commentary-chart-links`: number links in `/events` (matching rules, field-to-chart table, response shape) and the clickable numbers with their chart popover in the intelligence panel.

### Modified Capabilities

(none)

## Impact

- Affected code: backend/src/augur/events/links.py (new), backend/src/augur/narration/grounding.py (number rules shared, behaviour unchanged), backend/src/augur/api.py (`/events` adds `links`), frontend/src/api/types.ts, frontend/src/components/IntelligencePanel.tsx, new frontend/src/components/links/ (linked text and popover), and their tests.
- APIs: `/events` gains one field per event; every existing field is unchanged.
- Dependencies: none added; popover charts reuse the `strategy-chart-widgets` chart views and existing endpoints.
- Stored data: none; cached commentary gets links without re-running `augur.narrate`.
- README: notes go to tasks.md for `portfolio-release`.
