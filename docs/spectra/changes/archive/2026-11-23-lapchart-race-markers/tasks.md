## 1. Chart model

- [x] 1.1 Implement the model side of the "Lap-time chart" requirement and the design decision "Hide non-racing laps per driver, shade neutralised laps race-wide": extend `chartModel()` in `frontend/src/lib/chartModel.ts` so that rows of lap 1, `pit_in`, `pit_out`, or `track_status` 4/5/6 are `null` on their driver's line, the result adds `pitMarkers` (plotted drivers' `pit_in` laps with code and line colour) and `neutralised` (laps 1..N whose rows contain status 5, 4, or 6, labelled `RED`, `SC`, `VSC` in that priority), and the y-domain is computed from solid-line lap times only. Verify with new tests in `frontend/src/lib/chartModel.test.ts` that encode the spec examples "LEC at Abu Dhabi 2024, lap 40", "label per lap", the pit-marker scenario, and the y-axis scenario ([87, 92]); the existing `LapChart.test.tsx` suite still passes.

## 2. Chart rendering

- [x] 2.1 Implement the rendering side of the "Lap-time chart" requirement following the design decision "Markers inside Recharts": render the markers in `frontend/src/components/LapChart.tsx`: one shaded `ReferenceArea` per neutralised lap labelled with its label (`data-testid="neutralised-lap"`, `data-label`, `data-lap`), one `P` in the driver's line colour at the top of the plot per pit marker (`data-testid="pit-marker"`, `data-code`, `data-lap`; a second marker on the same lap offset 10 px right), and the legend keys `P pit stop` and `SC / VSC` only when present. Verify with `LapChart.test.tsx` cases for markers present and absent and for the legend keys, plus `npm --prefix frontend run test` and `npm --prefix frontend run build` passing. [after: 1.1]

## 3. Check on real data

- [x] 3.1 Run the API and the dashboard on 2024 Abu Dhabi, open the PACE board at lap 40 with LEC in focus and a lap-time number popover from an event, and record here what the lap chart shows (hidden laps, `P` markers for LEC 20, SAI 25, RUS 26, the `VSC` band on laps 2-3, y-axis range) with a screenshot kept in the job tmp directory. Write README notes for `portfolio-release` under this task (Lap times row of the chart catalogue, PACE screenshot caption, retake of `docs/images/board-pace.png`). Verify that no line leaves the plot area and that the frontend suite and build pass. [after: 2.1]

### 3.1 results (2026-11-23)

API from this worktree (`AUGUR_DATA_DIR` = main `data/`, model `lightgbm`, commentary `glm`), Vite dev server from this worktree (own `npm ci`), headless Chromium 1440x900, script and screenshots in the job tmp directory (`check-lapchart.cjs`, `board-pace.png`, `popover-laptimes.png`).

- PACE board, lap 40, focus LEC (neighbours SAI, RUS): `P` markers LEC@20, SAI@25, RUS@26 in the line colours; `VSC` bands on laps 2 and 3; laps 1-3 and every pit-in / pit-out lap are gaps; y-axis 1:27.000 to 1:33.000; line points above the plot area: 0 (before this change the out-laps of LEC 21, SAI 26, RUS 27 and laps 1-3 left the top). Legend: `Neighbours at lap 40 · SAI · LEC · RUS · dashed: predicted · P pit stop · SC / VSC`.
- Lap-time popover from LEC's pace drop at lap 22 (number 89.802, "Lap times · LEC · lap 22", neighbours GAS and HUL): `P` markers HUL@13, GAS@14, LEC@20; `VSC` bands on laps 2-3; points above the plot area: 0.
- Finding fixed during this task: in the 320 px popover the two adjacent `VSC` labels collided as "VSCVSC". A run of consecutive laps with the same label now shows the label once, on its first lap (spec text, design decision, `NeutralisedLap.showLabel`, and two tests updated); every lap is still shaded.
- No page or console errors. `npm --prefix frontend run test`: 42 files, 301 tests passed; `npm --prefix frontend run build`: passed.

### README notes for `portfolio-release`

- Chart catalogue, Lap times row: "lap times of the driver and the cars just ahead and behind, with the model's predicted laps as dashed lines; lap 1, pit-in and pit-out laps, and SC / VSC / red-flag laps are gaps in the lines; `P` marks each pit stop in the driver's colour and SC / VSC / red-flag laps are shaded." Computation column unchanged, plus "the y-axis covers the plotted laps only".
- PACE screenshot caption: "lap times with predicted laps dashed, pit stops marked P, the opening VSC laps shaded, a tyre cliff event, timing, and pace compare".
- Retake `docs/images/board-pace.png` from `main` after this change is merged (PACE, lap 40, focus LEC), and update both READMEs.
