## Context

`LapChart` (`frontend/src/components/LapChart.tsx`) renders the model built by `chartModel()` (`frontend/src/lib/chartModel.ts`): one row per lap 1..N with each plotted driver's `lap_time_s`, predicted values under `<code>:pred`, and a y-domain from `timeDomain()` = `[floor(min − 0.5), ceil(max(median + 3, min + 2))]` over every plotted lap time, with `allowDataOverflow`. The same component is used by the Lap times widget, the PACE preset, and the commentary popover for lap-time links (`frontend/src/components/links/ChartPopover.tsx`). `/laps` rows already carry `pit_in`, `pit_out`, and `track_status` (`frontend/src/api/types.ts` `LapRow`). Stack: React 19, Recharts 3, Vitest.

## Goals / Non-Goals

**Goals:** non-racing laps no longer spike off the chart; pit stops and SC/VSC/red-flag laps are visible and labelled; the y-axis fits racing laps.

**Non-Goals:** backend changes, predicted lines, Pace compare, tooltips for hidden laps, README edits (see proposal).

## Decisions

### Hide non-racing laps per driver, shade neutralised laps race-wide

A row leaves its driver's line when it is lap 1, `pit_in`, `pit_out`, or `track_status` in {4, 5, 6}, judged on that driver's own row. Shading uses every row at that lap number (all drivers, since `LapChart` receives the full `/laps` response), so a lap shows the neutralisation even if a plotted driver's own row was timed before it began. Severity order RED > SC > VSC. Every neutralised lap is shaded, but a run of consecutive laps with the same label shows the label once, on its first lap (added during 3.1: two adjacent `VSC` labels collided as "VSCVSC" in the 320 px popover). Alternative: draw hidden laps as a dotted line clipped at the top (rejected: still leaves off-chart strokes, the reason for this change).

### Markers inside Recharts

`chartModel()` returns `pitMarkers: { lap, code, color }[]` (plotted drivers' `pit_in` rows) and `neutralised: { lap, label }[]`. `LapChart` draws one `ReferenceArea` per neutralised lap (x from lap − 0.5 to lap + 0.5, low opacity, label at the top) and one `ReferenceDot` per pit marker at y = the domain's upper bound with a text label `P` in the driver colour. When two plotted drivers pit on the same lap, both markers are drawn at that lap with the later driver's label offset by 10 px to the right so both stay readable.

### Domain from solid-line laps only

`timeDomain()` receives only the lap times kept on the solid lines. If every plotted lap is hidden (for example at lap 1), the domain is null and Recharts falls back to auto, as today with no laps.

## Implementation Contract

- `chartModel(drivers, laps, focusCode, lap, predicted)` keeps its signature and adds `pitMarkers` and `neutralised` to its result; hidden rows are `null` in `rows` for the driver's key; prediction keys are unchanged.
- `LapChart` renders `data-testid="pit-marker"` (attribute `data-code`, `data-lap`) per marker and `data-testid="neutralised-lap"` (attribute `data-label`, `data-lap`) per shaded lap, and the legend keys `P pit stop` and `SC / VSC` only when present.
- Scope: `frontend/src/lib/chartModel.ts`, `frontend/src/components/LapChart.tsx`, and their tests. No other file changes. Capability-level behaviour outside the lap-time chart is unchanged.
- Failure modes: a row with `track_status` null is a racing lap unless another rule applies; unknown status codes are treated as racing.

## Risks / Trade-offs

- [Hiding lap 1 and SC laps removes real data from the line] -> They stay in the Timing widget and `/laps`; the markers say why the line breaks.
- [Many shaded laps (long SC) clutter the label row] -> Label every shaded lap but keep the band at 12% opacity; a 4-lap SC shows four adjacent bands that read as one block.
- [Recharts reference labels can collide with the top tick] -> Pit labels sit inside the plot area 2 px below the top edge; checked on screenshots in the manual task.

## Migration Plan

Frontend-only; ship with the next build. Rollback is reverting the commit.

## Open Questions

(none)
