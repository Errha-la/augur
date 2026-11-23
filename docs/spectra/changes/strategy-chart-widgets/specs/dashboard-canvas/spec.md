## MODIFIED Requirements

### Requirement: Widget instances

A board SHALL hold widget instances, each with its own id, type, position, size, and settings, and SHALL allow any type to appear more than once, up to 24 widgets per board. The widget types SHALL be `timing`, `events`, `driver`, `lapchart`, `timeline`, `trace`, `pitclock`, `pitwindow`, `stints`, `degradation`, `pace`, `fan`, and `heatmap`. "+ Widget" SHALL list every type and SHALL add the chosen type below the lowest widget at its default size; when the board already has 24 widgets it SHALL show "A board holds at most 24 widgets" and add nothing. Each widget SHALL have a remove button in its title bar. An imported or stored widget SHALL keep only the settings its type declares, and a `pace` widget's `drivers` setting SHALL keep at most four distinct valid driver codes in their original order.

#### Scenario: Same type twice

- **WHEN** the viewer adds a `driver` widget to a board that already has one
- **THEN** the board shows two driver panels with different ids that can be moved and configured separately

#### Scenario: Board full

- **WHEN** a board has 24 widgets and the viewer chooses a type in "+ Widget"
- **THEN** the message "A board holds at most 24 widgets" appears and the board is unchanged

#### Scenario: Chart types listed

- **WHEN** the viewer opens "+ Widget"
- **THEN** it lists Race trace, Pit clock, Pit window, Tyre stints, Degradation, Pace compare, Position fan, and Position odds after the five existing types

#### Scenario: Imported pace drivers

##### Example: cleaned driver list

- **GIVEN** an imported `pace` widget with `drivers` ["NOR", "nor", "LEC", "NOR", "PIA", "VER", "HAM"]
- **WHEN** the board file is imported
- **THEN** the widget's `drivers` setting is ["NOR", "LEC", "PIA", "VER"]

---
### Requirement: Per-widget driver

`driver`, `lapchart`, `pitclock`, `pitwindow`, and `fan` widgets SHALL have a driver setting that is either "follow focus" (default) or a driver code, chosen from a picker in the title bar listing "Follow focus (<focus code>)" and every driver in the race. The widget SHALL apply the focus driver panel, lap-time chart, pit clock, pit window, or position fan requirements with its own driver in place of the focus driver. A pinned code not in the current race SHALL show "<code> is not in this race" and the widget SHALL follow the focus driver until the setting changes or the race has that driver again. Highlights of the timing list, events, and timeline SHALL keep following the focus driver. Identical API requests from several widgets at the same lap SHALL be sent once.

#### Scenario: Two pinned lap charts

- **WHEN** one `lapchart` widget is pinned to LEC and another to PIA, and the viewer clicks the NOR timing row
- **THEN** the first chart plots LEC and its neighbours, the second PIA and its neighbours, and the NOR row is highlighted

#### Scenario: Pinned driver missing

- **WHEN** a `driver` widget pinned to SAR is shown for a race without SAR and the focus driver is VER
- **THEN** the widget shows "SAR is not in this race" and VER's panel

#### Scenario: Shared request

- **WHEN** two `driver` widgets follow the focus driver NOR and playback is paused at lap 20
- **THEN** exactly one `/strategy?lap=20&driver=NOR` request is sent

#### Scenario: Two pit windows

- **WHEN** one `pitwindow` widget is pinned to LEC and another to PIA, and playback is paused at lap 20
- **THEN** one `pit-window?lap=20&driver=LEC` and one `pit-window?lap=20&driver=PIA` request are sent and each chart shows its own driver

---
### Requirement: Presets

The board menu SHALL offer four presets, PIT WALL, BATTLE, PACE, and STRATEGY, with the widgets, settings, and positions in the `strategy-chart-widgets` design.md preset decision, and SHALL open BATTLE on a first visit. Changing a preset SHALL keep the changed copy, mark the preset "edited" in the board menu, and offer "Reset to preset", which restores the built-in definition.

#### Scenario: Reset an edited preset

- **WHEN** the viewer removes a widget from PIT WALL, reloads the page, and chooses "Reset to preset"
- **THEN** after the reload PIT WALL is still missing the widget and marked "edited", and after the reset it matches the built-in definition and is no longer marked

#### Scenario: STRATEGY preset

- **WHEN** the viewer chooses STRATEGY in the board menu
- **THEN** the board shows Pit window, Pit clock, Tyre stints, Degradation, and Race trace widgets, with the pit window and pit clock following the focus driver

#### Scenario: Stored edit survives the new definitions

- **WHEN** a viewer edited PIT WALL before this change and loads the dashboard after it
- **THEN** PIT WALL shows the viewer's stored copy, still marked "edited", and "Reset to preset" gives the new PIT WALL with a Pit window in place of the lap chart
