export type Speed = 1 | 2 | 4;

export const TICK_MS: Record<Speed, number> = { 1: 1000, 2: 500, 4: 250 };

export interface ReplayState {
  raceId: string | null;
  totalLaps: number;
  lap: number;
  playing: boolean;
  speed: Speed;
}

export type ReplayAction =
  | { type: "selectRace"; raceId: string; totalLaps: number }
  | { type: "setLap"; lap: number }
  | { type: "step"; delta: 1 | -1 }
  | { type: "tick" }
  | { type: "togglePlay" }
  | { type: "stop" }
  | { type: "setSpeed"; speed: Speed };

export const initialReplay: ReplayState = {
  raceId: null,
  totalLaps: 1,
  lap: 1,
  playing: false,
  speed: 1,
};

function clamp(lap: number, totalLaps: number): number {
  if (!Number.isFinite(lap)) return 1;
  return Math.min(Math.max(Math.round(lap), 1), Math.max(totalLaps, 1));
}

/** Every transition keeps the lap within 1..totalLaps. */
export function replayReducer(state: ReplayState, action: ReplayAction): ReplayState {
  switch (action.type) {
    case "selectRace":
      return { ...state, raceId: action.raceId, totalLaps: Math.max(action.totalLaps, 1), lap: 1, playing: false };
    case "setLap":
      return { ...state, lap: clamp(action.lap, state.totalLaps) };
    case "step":
      return { ...state, lap: clamp(state.lap + action.delta, state.totalLaps) };
    case "tick": {
      const lap = clamp(state.lap + 1, state.totalLaps);
      return { ...state, lap, playing: state.playing && lap < state.totalLaps };
    }
    case "togglePlay":
      // Playing from the last lap would stop at once, so only allow it before the end.
      return { ...state, playing: !state.playing && state.lap < state.totalLaps };
    case "stop":
      return { ...state, playing: false };
    case "setSpeed":
      return { ...state, speed: action.speed };
  }
}
