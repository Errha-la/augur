import type { Dispatch } from "react";
import type { RaceSummary } from "../api/types";
import { trackStatusStyle } from "../lib/theme";
import type { ReplayAction, ReplayState, Speed } from "../state/replay";

const SPEEDS: Speed[] = [1, 2, 4];

interface StatusBarProps {
  races: RaceSummary[];
  replay: ReplayState;
  dispatch: Dispatch<ReplayAction>;
  trackStatus: string | null | undefined;
  /** True until the final lap is on screen. */
  wrappedLocked?: boolean;
  onOpenWrapped?: () => void;
  onOpenSettings?: () => void;
}

export function TrackStatusPill({ status }: { status: string | null | undefined }) {
  const style = trackStatusStyle(status);
  return (
    <span
      data-testid="track-status"
      data-status={status ?? ""}
      className={`rounded px-2 py-0.5 text-xs font-bold tracking-wider ${style.className} ${
        style.pulse ? "animate-pulse" : ""
      }`}
    >
      {style.label}
    </span>
  );
}

const button =
  "rounded border border-zinc-800 px-2 py-1 text-sm text-zinc-300 hover:bg-zinc-800 disabled:opacity-40 disabled:hover:bg-transparent";

export function StatusBar({
  races,
  replay,
  dispatch,
  trackStatus,
  wrappedLocked = true,
  onOpenWrapped,
  onOpenSettings,
}: StatusBarProps) {
  const { raceId, lap, totalLaps, playing, speed } = replay;
  return (
    <div className="flex flex-wrap items-center gap-3">
      <span className="text-lg font-bold tracking-widest text-zinc-100">AUGUR</span>
      <select
        aria-label="Race"
        className="rounded border border-zinc-800 bg-zinc-950 px-2 py-1 text-sm"
        value={raceId ?? ""}
        onChange={(e) => {
          const race = races.find((r) => r.race_id === e.target.value);
          if (race) dispatch({ type: "selectRace", raceId: race.race_id, totalLaps: race.total_laps });
        }}
      >
        {races.map((r) => (
          <option key={r.race_id} value={r.race_id}>
            {r.event_name} {r.year}
          </option>
        ))}
      </select>

      <button
        type="button"
        aria-label="Previous lap"
        className={button}
        disabled={lap <= 1}
        onClick={() => dispatch({ type: "step", delta: -1 })}
      >
        ◀
      </button>
      <button
        type="button"
        aria-label={playing ? "Pause" : "Play"}
        className={`${button} w-16`}
        onClick={() => dispatch({ type: "togglePlay" })}
      >
        {playing ? "PAUSE" : "PLAY"}
      </button>
      <button
        type="button"
        aria-label="Next lap"
        className={button}
        disabled={lap >= totalLaps}
        onClick={() => dispatch({ type: "step", delta: 1 })}
      >
        ▶
      </button>
      <div role="group" aria-label="Playback speed" className="flex gap-1">
        {SPEEDS.map((s) => (
          <button
            key={s}
            type="button"
            aria-pressed={speed === s}
            className={`${button} ${speed === s ? "bg-zinc-800 text-zinc-100" : ""}`}
            onClick={() => dispatch({ type: "setSpeed", speed: s })}
          >
            {s}×
          </button>
        ))}
      </div>

      <input
        type="range"
        aria-label="Lap"
        className="min-w-40 flex-1 accent-zinc-300"
        min={1}
        max={totalLaps}
        step={1}
        value={lap}
        onChange={(e) => dispatch({ type: "setLap", lap: Number(e.target.value) })}
      />
      <span data-testid="lap-count" className="text-sm font-bold tabular-nums">
        LAP {lap}/{totalLaps}
      </span>
      <TrackStatusPill status={trackStatus} />
      {onOpenWrapped && (
        <button
          type="button"
          aria-label={wrappedLocked ? "Wrapped (unlocks at the final lap)" : "Wrapped"}
          title={wrappedLocked ? "Unlocks at the final lap" : "Open the race Wrapped"}
          data-locked={wrappedLocked || undefined}
          disabled={wrappedLocked}
          onClick={onOpenWrapped}
          className={`${button} font-bold tracking-wider ${wrappedLocked ? "" : "border-purple-400 text-purple-300"}`}
        >
          {wrappedLocked && (
            <span data-testid="wrapped-lock" aria-hidden className="mr-1">
              🔒
            </span>
          )}
          WRAPPED
        </button>
      )}
      {onOpenSettings && (
        <button type="button" aria-label="Settings" title="Settings" className={`${button} ml-auto`} onClick={onOpenSettings}>
          ⚙
        </button>
      )}
    </div>
  );
}
