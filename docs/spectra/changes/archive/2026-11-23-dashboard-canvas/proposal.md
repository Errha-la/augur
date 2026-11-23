## Why

The dashboard is one fixed grid: a viewer cannot put the panels they care about side by side, cannot follow two drivers at once, and cannot keep a view for a particular angle (pit strategy, position battles, pace). A prototype with synthetic data (2026-11-22) showed that a whiteboard-style board of draggable, resizable widgets with a few presets works, and the user's review of it set four requirements: commentary text must reflow with the card size, widgets that follow a driver must each pick their own driver and may appear more than once, viewers can create and save their own blank boards, and the release needs short usage hints. This is the FE track of Stage 4 Wave 1 in `AGENTS.md`.

## What Changes

- Replace the fixed layout below the status bar with a board: widgets on a 12-column snap grid that the viewer drags by the title bar, resizes from the corner, adds, and removes; keyboard move and resize; one column below 760 px wide.
- Widget instances with their own id and settings: the same widget type can appear several times; driver-based widgets (driver panel, lap chart) follow the focus driver by default or are pinned to a chosen driver; the event widget filters by event type.
- Three built-in presets: PIT WALL, BATTLE, PACE, built from the existing panels (timing, events with commentary, driver panel, lap chart, event timeline). `strategy-chart-widgets` adds the new charts to them later.
- Custom boards: create a blank board, rename, duplicate, delete; edits to a preset are kept until the viewer resets it.
- Boards persist in the browser (`localStorage`), with JSON export to a file and import from a file.
- Event text, including AUGUR commentary, fills the widget width and scales with it instead of a fixed size.
- A first-visit guide of four short steps, reopened from a help button in the status bar.

## Non-Goals (optional)

Recorded in design.md.

## Capabilities

### New Capabilities

- `dashboard-canvas`: board grid, widget instances and settings, presets, custom boards, persistence, export and import, responsive text in widgets, and the first-visit guide.

### Modified Capabilities

(none: the existing panels keep their requirements; `dashboard-canvas` states how a widget's own driver and event filter apply them)

## Impact

- Affected specs: `dashboard-canvas` (new). Existing `focus-driver`, `race-overview`, and `intelligence-panel` requirements apply unchanged inside widgets.
- Affected code:
  - New: frontend/src/canvas/ (grid engine, board store, widget registry, presets, export and import, guide), frontend/src/components/Board.tsx, frontend/src/components/WidgetFrame.tsx, frontend/src/components/BoardMenu.tsx, frontend/src/components/Guide.tsx, and their tests
  - Modified: frontend/src/App.tsx, frontend/src/components/StatusBar.tsx, frontend/src/components/IntelligencePanel.tsx, frontend/src/components/FocusPanel.tsx, frontend/src/components/LapChart.tsx, frontend/src/index.css
  - Removed: frontend/src/components/Layout.tsx and frontend/src/components/Layout.test.tsx (after the board replaces it)
- No backend or API change; no new runtime dependency (decided in design.md).
