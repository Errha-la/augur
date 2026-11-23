## Why

The lap-time chart draws every lap on one line, and its y-axis is cut at `max(median + 3 s, fastest + 2 s)` with overflow allowed (`frontend/src/lib/chartModel.ts` `timeDomain`). Pit-in and pit-out laps, the standing-start lap 1, and safety-car or VSC laps are 3 to 25 s slower, so their lines shoot off the top of the chart. On the published `docs/images/board-pace.png` (2024 Abu Dhabi, lap 40, focus LEC) the user read these spikes as a possible bug: LEC's out-lap (lap 21, 1:48.662), SAI's (lap 26, 1:47.557), RUS's (lap 27, 1:48.853) and the VSC laps 2-3 leave the plot with no label. The data is right; the chart does not say what those laps are.

## What Changes

- The lap-time chart leaves non-racing laps off the solid lines, so each line breaks there instead of spiking: lap 1, pit-in laps, pit-out laps, and laps under safety car (`track_status` 4), red flag (5), or virtual safety car (6).
- Each plotted driver's pit stop is marked with a "P" at the top edge of the chart on its pit-in lap, in that driver's line colour.
- Laps under safety car, VSC, or red flag are shaded across the chart and labelled `SC`, `VSC`, or `RED`.
- The y-axis range is computed from the plotted (racing) laps only.
- The legend adds `P pit stop` and, when a shaded lap is visible, `SC / VSC` keys.
- The same chart is used in the commentary number popover for lap-time links, so popovers get the markers too.

## Non-Goals

- No backend or API change: `/laps` already returns `pit_in`, `pit_out`, and `track_status` per row.
- No change to predicted (dashed) lines, the Pace compare widget (already clean laps only), or other charts.
- No tooltip for hidden laps: their lap time stays available in the Timing widget and `/laps`.
- No README edit here (AGENTS.md: only `portfolio-release` edits `README.md`); README notes go to `tasks.md` and are applied in `portfolio-release`, which is not archived yet.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `race-overview`: requirement "Lap-time chart" changes: non-racing laps leave the lines, pit stops and SC/VSC/red-flag laps are marked, and the y-axis uses racing laps only.

## Impact

- Affected specs: race-overview (modified requirement "Lap-time chart")
- Affected code:
  - Modified: frontend/src/lib/chartModel.ts, frontend/src/components/LapChart.tsx, frontend/src/components/LapChart.test.tsx
  - New: frontend/src/lib/chartModel.test.ts
- Follow-up outside this change: `portfolio-release` retakes `docs/images/board-pace.png` and updates the Lap times text in `README.md` and `README.zh-TW.md`.
