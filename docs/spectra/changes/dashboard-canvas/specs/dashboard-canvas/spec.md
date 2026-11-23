## Purpose

Let viewers arrange AUGUR's dashboard as boards of widgets they can move, resize, duplicate, and point at different drivers, keep those boards in their browser, and share them as files, so the same race can be read from different angles such as pit strategy, position battles, or pace.

## ADDED Requirements

### Requirement: Board grid

The dashboard SHALL show the active board below the status bar as a 12-column grid with 44 px rows and 8 px gaps. Widgets SHALL have integer cell positions and sizes no smaller than their type's minimum, SHALL never overlap, and SHALL compact upward after every move, resize, add, or remove, with a moving or resized widget pushing others down. Dragging a widget's title bar SHALL move it and dragging its bottom-right corner SHALL resize it, with a placeholder showing the snapped target. With the title bar focused, arrow keys SHALL move the widget one cell and Shift with arrow keys SHALL resize it one cell. Below 760 px viewport width the board SHALL show widgets in one column ordered by row then column, with drag and resize disabled.

#### Scenario: Push down on drop

##### Example: dropping onto another widget

- **GIVEN** widget A at (0,0) size 6×4 and widget B at (0,4) size 6×4
- **WHEN** the viewer drags B to (0,2)
- **THEN** B is at (0,2) and A is at (0,6), and no widgets overlap

#### Scenario: Compaction after removal

- **WHEN** a widget at (0,0) size 12×3 is removed and another widget sits at (0,3)
- **THEN** the remaining widget moves to (0,0)

#### Scenario: Keyboard resize respects the minimum

- **WHEN** a `timing` widget at its minimum width is focused and the viewer presses Shift+Left
- **THEN** its width does not change

#### Scenario: Narrow screen

- **WHEN** the viewport is 700 px wide
- **THEN** widgets appear in one column in row-then-column order and dragging a title bar does not move a widget

### Requirement: Widget instances

A board SHALL hold widget instances, each with its own id, type, position, size, and settings, and SHALL allow any type to appear more than once, up to 24 widgets per board. The widget types SHALL be `timing`, `events`, `driver`, `lapchart`, and `timeline`. "+ Widget" SHALL list every type and SHALL add the chosen type below the lowest widget at its default size; when the board already has 24 widgets it SHALL show "A board holds at most 24 widgets" and add nothing. Each widget SHALL have a remove button in its title bar.

#### Scenario: Same type twice

- **WHEN** the viewer adds a `driver` widget to a board that already has one
- **THEN** the board shows two driver panels with different ids that can be moved and configured separately

#### Scenario: Board full

- **WHEN** a board has 24 widgets and the viewer chooses a type in "+ Widget"
- **THEN** the message "A board holds at most 24 widgets" appears and the board is unchanged

### Requirement: Per-widget driver

`driver` and `lapchart` widgets SHALL have a driver setting that is either "follow focus" (default) or a driver code, chosen from a picker in the title bar listing "Follow focus (<focus code>)" and every driver in the race. The widget SHALL apply the focus driver panel or lap-time chart requirements with its own driver in place of the focus driver. A pinned code not in the current race SHALL show "<code> is not in this race" and the widget SHALL follow the focus driver until the setting changes or the race has that driver again. Highlights of the timing list, events, and timeline SHALL keep following the focus driver. Identical API requests from several widgets at the same lap SHALL be sent once.

#### Scenario: Two pinned lap charts

- **WHEN** one `lapchart` widget is pinned to LEC and another to PIA, and the viewer clicks the NOR timing row
- **THEN** the first chart plots LEC and its neighbours, the second PIA and its neighbours, and the NOR row is highlighted

#### Scenario: Pinned driver missing

- **WHEN** a `driver` widget pinned to SAR is shown for a race without SAR and the focus driver is VER
- **THEN** the widget shows "SAR is not in this race" and VER's panel

#### Scenario: Shared request

- **WHEN** two `driver` widgets follow the focus driver NOR and playback is paused at lap 20
- **THEN** exactly one `/strategy?lap=20&driver=NOR` request is sent

### Requirement: Event type filter

An `events` widget SHALL have a setting listing the event types it shows, shown as toggle chips in its title bar, defaulting to all types. It SHALL apply the intelligence panel requirements to the events at lap N or earlier whose type is in the list, and when none match it SHALL show "No matching events yet".

#### Scenario: Filtered primary event

- **WHEN** an `events` widget shows only `position_change`, and at lap 22 the events are a `degradation_warning` (severity 80) and a `position_change` (severity 40)
- **THEN** its primary card is the `position_change`

### Requirement: Presets

The board menu SHALL offer three presets, PIT WALL, BATTLE, and PACE, with the widgets, settings, and positions in the design.md presets table, and SHALL open BATTLE on a first visit. Changing a preset SHALL keep the changed copy, mark the preset "edited" in the board menu, and offer "Reset to preset", which restores the built-in definition.

#### Scenario: Reset an edited preset

- **WHEN** the viewer removes a widget from PIT WALL, reloads the page, and chooses "Reset to preset"
- **THEN** after the reload PIT WALL is still missing the widget and marked "edited", and after the reset it matches the built-in definition and is no longer marked

### Requirement: Custom boards

The board menu SHALL offer "New blank board", which adds an empty custom board named "Board <n>" (the lowest n not in use) showing "Add a widget with + Widget", and SHALL offer Rename and Duplicate for any board and Delete for custom boards. Duplicate SHALL create a custom copy named "<name> copy". Delete SHALL ask for confirmation inside the page and, after deletion, SHALL switch to BATTLE when the deleted board was active.

#### Scenario: Blank board

- **WHEN** the viewer chooses "New blank board" with no custom boards
- **THEN** a board named "Board 1" with no widgets becomes active and shows "Add a widget with + Widget"

#### Scenario: Delete active board

- **WHEN** the viewer deletes the active custom board and confirms
- **THEN** the board is gone and BATTLE is active

### Requirement: Board persistence

Every board change SHALL be saved to `localStorage` under `augur.boards.v1` as `{version: 1, activeBoardId, presetEdits, customBoards}` within 300 ms, and reloading the page SHALL restore the active board, every board, and every widget's position, size, and settings. Restoring SHALL resolve any overlap in a stored board by pushing widgets down, without moving any widget up, so gaps the viewer left are kept. When nothing is stored (a first visit), the dashboard SHALL start from the presets without a notice. When the stored value is not valid JSON or has a version other than 1, the dashboard SHALL start from the presets and show "Saved boards could not be read; started from the presets." without overwriting the stored value until the viewer changes a board. When storage throws, boards SHALL stay in memory for the page and the dashboard SHALL show "Boards will not be saved in this browser."

#### Scenario: Reload keeps a custom board

- **WHEN** the viewer creates "Board 1", adds a `lapchart` pinned to PIA at (6,0) size 6×5, and reloads the page
- **THEN** "Board 1" is active with that widget, position, size, and driver

#### Scenario: First visit without a notice

- **WHEN** `augur.boards.v1` is not in storage
- **THEN** BATTLE is active and no notice is shown

#### Scenario: Corrupted storage

- **WHEN** `augur.boards.v1` holds `{not json`
- **THEN** the presets load, the notice "Saved boards could not be read; started from the presets." is shown, and the stored value is unchanged

### Requirement: Board export and import

Export SHALL download the active board as `augur-board-<name slug>.json` containing `{format: "augur-board", version: 1, board: {name, widgets}}`. Import SHALL accept one file up to 100 KB, add it as a new custom board, drop widgets of unknown types, clamp positions and sizes to the grid and type minimums, resolve overlaps by pushing widgets down without moving any widget up (so the file's gaps are kept), keep at most 24 widgets, make it active, and report "Imported <name>: <n> widgets, <m> skipped". A file that is not valid JSON, is larger than 100 KB, or has another `format` or `version` SHALL be rejected with "Not an AUGUR board file." and SHALL change nothing.

#### Scenario: Round trip

- **WHEN** the viewer exports a board and imports the downloaded file
- **THEN** a new custom board with the same name, widgets, positions, sizes, and settings becomes active

#### Scenario: Unknown widget type

##### Example: one unknown widget

- **GIVEN** a board file with widgets of types `timing`, `lapchart`, and `heatmap3d`
- **WHEN** it is imported
- **THEN** the report is "Imported <name>: 2 widgets, 1 skipped" and the board has the `timing` and `lapchart` widgets

#### Scenario: Wrong file

- **WHEN** the viewer imports a file containing `{"format": "other"}`
- **THEN** the message "Not an AUGUR board file." appears and no board is added

### Requirement: Text scales with the widget

Text in an `events` widget, including the AUGUR commentary quote, the event title, and What, Why, and Next, SHALL wrap to the full widget width with no fixed maximum line length, and its font size SHALL grow with the widget width between a minimum and a maximum (commentary 13–18 px, title 15–22 px, body 12–16 px).

#### Scenario: Wide and narrow widget

- **WHEN** the same event is shown in an `events` widget 3 columns wide and in one 12 columns wide
- **THEN** in both the commentary text spans the widget's content width without horizontal scrolling, and its font size is larger in the 12-column widget but at most 18 px

### Requirement: First-visit guide

When `augur.guide.v1` is absent, the dashboard SHALL open a four-step guide anchored to the elements it explains: moving a widget by its title bar, resizing from the corner, adding widgets and choosing a widget's driver, and switching, creating, exporting, and importing boards in the board menu. Each step SHALL offer Back (except the first), Next (Done on the last), and Skip; Done, Skip, and Escape SHALL close the guide and store `augur.guide.v1`. A "?" button in the status bar SHALL reopen it. The guide SHALL be usable by keyboard and SHALL not animate when the viewer prefers reduced motion.

#### Scenario: First visit

- **WHEN** the dashboard opens with no `augur.guide.v1` in storage
- **THEN** step 1 of 4 is shown, and after Skip the guide closes and does not open on reload

#### Scenario: Reopen

- **WHEN** the viewer presses the "?" button after finishing the guide
- **THEN** step 1 of 4 is shown again
