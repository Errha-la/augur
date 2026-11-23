## Context

The dashboard (`frontend/`, React 19 + Vite 8 + Tailwind 4 + Recharts 3) renders a fixed grid from `Layout.tsx`: status bar on top, timing list on the left, intelligence panel, focus panel, lap chart, and event timeline on the right. One focus driver drives the focus panel, the chart, and the highlights. Lap data for all drivers is fetched once per lap (`useLapData`); the focus panel additionally requests `/strategy` and `/positions/history` per driver on a schedule (paused, or laps divisible by 5 during playback).

A throwaway prototype with synthetic data (`~/drafts/augur-canvas-prototype.html`, artifact published 2026-11-22) tried a 12-column snap grid with drag, resize, presets, and chart-linked commentary. The user's review set four requirements (proposal.md). This is the FE track of Stage 4 Wave 1 (`AGENTS.md`): own worktree, `frontend/` only, boards stored only in the browser with JSON export and import.

## Goals / Non-Goals

**Goals:**

- Boards of widgets the viewer arranges: drag, resize, add, remove, by pointer and keyboard.
- Widget instances with settings, so a type can appear more than once and driver widgets can each follow their own driver.
- Three presets plus any number of custom boards, saved in `localStorage`, exported and imported as JSON files.
- Text in widgets, AUGUR commentary first, reflows and scales with the widget.
- A short first-visit guide.

**Non-Goals:**

- No new chart widgets (race trace, pit clock, pit window, stints, heatmap, fan, degradation, pace): `strategy-chart-widgets` (Wave 2).
- No clickable commentary numbers linked to charts: `commentary-chart-links` (Wave 3).
- No backend storage, accounts, or sharing of boards between browsers other than export and import.
- No free-form overlapping canvas; widgets snap to the grid and never overlap.
- No change to the Wrapped overlay, the settings sheet, the status bar controls, or replay behaviour.
- No change to what the existing panels show; only where they are placed and which driver they use.

## Decisions

### Boards of widgets on a snap grid

**Supersedes**: race-dashboard / Timing-screen layout after BENNNZO/f1-dashboard

The status bar stays fixed on top (BENNNZO look and tokens unchanged). Below it the active board is a 12-column grid with rows of 44 px and 8 px gaps (values from the prototype). Each widget has integer `x`, `y`, `w`, `h` in grid cells and a minimum size per type. After every move, resize, add, or remove, widgets compact upward and a moving widget pushes others down; widgets never overlap. A widget is moved by dragging its title bar and resized by dragging its bottom-right corner; while dragging, a dashed placeholder shows the snapped target. Below 760 px viewport width the board shows widgets in one column in reading order (y, then x) with drag and resize off. Reason: the prototype showed snap-and-compact keeps boards tidy without manual alignment. Alternative: free-form canvas with overlap. Rejected because overlapping panels hide data and do not reflow on small screens.

### Own grid engine instead of a library

The grid engine is a small pure module (`frontend/src/canvas/grid.ts`): collision test, vertical compaction with one fixed item, clamping to columns and minimum sizes, pixel conversion. The prototype's version was about 100 lines. React components only render positions and forward pointer and keyboard input. Keyboard: the title bar is focusable; arrow keys move the widget one cell, Shift+arrow keys resize it by one cell, Escape cancels an active drag. Alternative: `react-grid-layout`. Rejected because its React 19 support is unconfirmed (it would need checking before adoption) and the engine is small enough to own and unit-test.

### Widget instances with settings

A board holds widget instances `{id, type, x, y, w, h, settings}`; `id` is unique per board, so any type may appear several times. A registry maps each type to its title, default and minimum size, component, and settings schema. Types in this change: `timing` (timing list), `events` (intelligence panel with commentary and event history; setting `types`, the event types shown, default all), `driver` (focus panel; setting `driver`), `lapchart` (lap-time chart; setting `driver`), `timeline` (event timeline). A board holds at most 24 widgets (estimate to keep requests and rendering bounded; check by loading a 24-widget board during playback at 4×, recorded in tasks.md).

### Per-widget driver with follow-focus default

**Supersedes**: race-dashboard / One focus driver drives the detail views

The dashboard keeps one focus driver with the same rules: it defaults to the driver in position 1 at lap 1, changes when a timing row is clicked, and on race change is kept if that code exists in the new race, otherwise reset to position 1. Its timing row, events, and timeline markers keep the team-colour highlight. Driver widgets (`driver`, `lapchart`) have a `driver` setting: `null` (default) follows the focus driver; a driver code pins the widget to that driver. The title bar shows the widget's driver and a picker listing "Follow focus (<code>)" and every driver in the race. A pinned code that is not in the current race shows "<code> is not in this race" in the widget, which then follows the focus driver until the viewer picks again or the race changes back. The driver panel's `/strategy` and `/positions/history` requests keep the existing schedule (paused, or laps divisible by 5 during playback). Requests with the same URL from several widgets share one network request through a small in-memory cache keyed by URL, cleared when the race changes. Reason: the user asked for "Pit window 1 follows LEC, Pit window 2 follows PIA" (2026-11-22). Alternative: no global focus, every widget picks a driver. Rejected because clicking a timing row to follow a driver is the main interaction and the highlights need one driver.

### Presets and custom boards

Built-in presets, defined in code:

| Preset | Widgets (x, y, w, h) |
|---|---|
| PIT WALL | `driver` follow (0,0,5,9); `events` types degradation_warning, undercut_window, overcut_window (5,0,7,6); `lapchart` follow (5,6,7,5); `timing` (0,9,5,6) |
| BATTLE | `timing` (0,0,5,10); `events` types position_change, undercut_window, overcut_window (5,0,7,6); `driver` follow (5,6,7,7); `timeline` (0,13,12,2) |
| PACE | `lapchart` follow (0,0,8,6); `events` types pace_drop, degradation_warning (8,0,4,6); `timing` (0,6,7,8); `driver` follow (7,6,5,8) |

BATTLE is the first board on a first visit, since it is closest to today's layout. Editing a preset stores the edited copy; the board menu shows "edited" and offers "Reset to preset". Custom boards: "New blank board" (named "Board 1", "Board 2", … with an empty-state message "Add a widget with + Widget"), rename, duplicate (any board, the copy is custom), delete (custom only, confirmed in the page because `confirm()` is not used). `strategy-chart-widgets` will extend the presets; an edited preset keeps the viewer's copy.

### Boards in localStorage with JSON export and import

Storage key `augur.boards.v1` holds `{version: 1, activeBoardId, presetEdits: {<presetId>: board}, customBoards: [board]}`. Every change writes it (debounced 300 ms). Nothing stored (a first visit) starts from the presets without a notice; an unreadable or invalid value starts from the presets and shows a dismissible notice "Saved boards could not be read; started from the presets." Restoring a stored board removes overlaps by pushing widgets down only (`separate()` in `grid.ts`), never up, so gaps the viewer left survive a reload. Storage that throws (private mode, blocked) keeps boards in memory for the session and shows "Boards will not be saved in this browser." Export downloads `augur-board-<slug of name>.json` with `{format: "augur-board", version: 1, board: {name, widgets}}`. Import accepts one such file up to 100 KB, adds it as a new custom board, drops widgets of unknown types, clamps geometry to the grid and minimum sizes, removes overlaps by pushing widgets down only (no upward compaction, so an export then import keeps every position), keeps at most 24 widgets, and reports "Imported <name>: <n> widgets, <m> skipped". A file that is not valid JSON or has another `format` or `version` is rejected with "Not an AUGUR board file." and nothing changes. Reason: decided by the user on 2026-11-22 (no backend storage). Alternative: SQLite via `/api/boards`. Rejected by the user.

### Text that scales with the widget

Every widget body is a CSS size container (`container-type: inline-size`). Event text in the `events` widget (title, What, Why, Next, and the AUGUR commentary quote) has no fixed maximum width and fills the widget, with font size `clamp(<min>, <cqi value>, <max>)`: commentary quote 13–18 px, title 15–22 px, body 12–16 px (estimates; check at widget widths 3, 6, and 12 columns, screenshots recorded in tasks.md). Reason: the prototype capped text at `max-width: 62ch` with fixed sizes, so a wide card left empty space and a narrow card overflowed (user review, 2026-11-22).

### First-visit guide

When `augur.guide.v1` is absent, a guide of four steps opens over the board, each anchored to the element it explains: (1) drag a widget by its title bar; (2) resize from the bottom-right corner; (3) add widgets with "+ Widget" and pick a widget's driver in its title bar; (4) switch, create, export, and import boards in the board menu. Each step has Back, Next (Done on the last), and Skip. Done or Skip stores `augur.guide.v1`. A "?" button in the status bar reopens it. With storage unavailable it opens once per page load. It respects `prefers-reduced-motion` and is reachable by keyboard (focus moves into the step; Escape skips). Reason: user requirement 4 (2026-11-22).

### Wave 1 frontend track

This change follows the Stage 4 Wave 1 rules in `AGENTS.md`: own worktree, `frontend/` only, no API change, starts after `polish` is archived so it builds on the polished panels. README notes go to tasks.md for `portfolio-release`.

### Persistence and import align with the implementation (2026-11-23)

**Supersedes**: the earlier wording of "Boards in localStorage with JSON export and import" in this change (missing storage showed the notice; import removed overlaps by compaction)

Found during verify on 2026-11-23 and decided by the user: a first visit shows no notice, because every new visitor would otherwise see an error; restoring and importing push overlapping widgets down only, because upward compaction would move widgets the viewer placed below a gap and break the "Round trip" scenario. Live edits (move, resize, add, remove) still compact upward as in "Boards of widgets on a snap grid".

## Implementation Contract

**Behavior**

- Opening the dashboard shows the status bar and the active board (BATTLE on first visit); the race, lap, playback, focus driver, Wrapped, and settings behave as before.
- The board menu in the status bar lists the three presets (marked "edited" when changed) and custom boards, and offers New blank board, Rename, Duplicate, Delete (custom), Reset to preset (edited preset), Export, Import.
- "+ Widget" lists the five widget types; adding places the widget at the bottom with its default size.
- A widget title bar shows its title, its driver picker (driver widgets), its event-type chips (events widget), and a remove button.
- Reloading the page restores the active board and every board's widgets and settings from `augur.boards.v1`.

**Data shapes**

```ts
type WidgetType = "timing" | "events" | "driver" | "lapchart" | "timeline";
interface WidgetInstance { id: string; type: WidgetType; x: number; y: number; w: number; h: number;
  settings: { driver?: string | null; types?: string[] } }
interface Board { id: string; name: string; presetId: "pit" | "battle" | "pace" | null; widgets: WidgetInstance[] }
interface StoredBoards { version: 1; activeBoardId: string; presetEdits: Record<string, Board>; customBoards: Board[] }
interface BoardFile { format: "augur-board"; version: 1; board: { name: string; widgets: WidgetInstance[] } }
```

**Failure modes**: nothing stored (first visit) → presets, no notice; unreadable storage → presets plus notice; storage unavailable → in-memory with notice; invalid import → "Not an AUGUR board file." and no change; pinned driver not in the race → message in the widget and follow focus.

**Acceptance**: Vitest tests named in tasks.md pass; all existing frontend tests pass or are moved to the widget they test with the same assertions; `npm --prefix frontend run build` passes; a manual check against the real backend (tasks.md) covers drag, resize, keyboard move, duplicates with two pinned drivers, a custom board surviving reload, export then import, the guide, and the 760 px single-column view.

**Scope**: In: `frontend/src/canvas/`, new board components, App wiring, status-bar board menu and help button, widget-level driver and type settings on existing panels, CSS for container-scaled text. Out: backend, new charts, commentary links, README.

## Risks / Trade-offs

- [Several driver widgets multiply `/strategy` requests] → Shared request cache by URL and the existing paused-or-every-5-laps schedule; the 24-widget cap.
- [Existing tests assume `Layout` testids] → Keep `data-testid` values on widget bodies (`timing`, `intelligence`, `focus`, `chart`, `timeline`) so tests move with little change; duplicates use `getAllByTestId`.
- [A stored board from a future version] → `version` other than 1 is treated as unreadable: presets plus notice; the stored value is not overwritten until the viewer changes a board.
- [Pointer drag on touch devices] → Drag is off below 760 px; above it, pointer events cover mouse, pen, and touch.
- [Clamp sizes for text are estimates] → Checked by screenshots at three widths before archive.
