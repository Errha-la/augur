// Response shapes of the AUGUR backend (backend/src/augur/api.py). Every
// lap-scoped endpoint is cutoff-safe: it only contains data up to `lap`.

export type Compound = "SOFT" | "MEDIUM" | "HARD" | "INTERMEDIATE" | "WET";

export interface RaceSummary {
  race_id: string;
  year: number;
  round: number;
  event_name: string;
  date: string;
  total_laps: number;
}

export interface DriverState {
  code: string;
  team: string;
  team_color: string;
  position: number;
  laps_completed: number;
  last_lap_time_s: number | null;
  compound: Compound | string | null;
  tyre_age_laps: number | null;
  stint: number | null;
  pit_count: number | null;
  gap_to_leader_s: number | null;
  laps_behind_leader: number;
}

export interface RaceState {
  race_id: string;
  lap: number;
  total_laps: number;
  /** OpenF1 track status code: "1" green, "2" yellow, "4" SC, "5" red, "6"/"7" VSC. */
  track_status: string | null;
  drivers: DriverState[];
}

export interface LapRow {
  driver: string;
  team: string;
  lap: number;
  lap_time_s: number | null;
  session_time_s: number | null;
  stint: number | null;
  compound: string | null;
  tyre_life: number | null;
  pit_in: boolean;
  pit_out: boolean;
  track_status: string | null;
  is_accurate: boolean;
}

export interface DriverPrediction {
  code: string;
  predicted_next_lap_s: number | null;
  recent_pace_s: number | null;
  deg_s_per_lap: number | null;
  deg_laps: number;
  cliff: boolean;
}

export interface PredictionsResponse {
  race_id: string;
  lap: number;
  drivers: DriverPrediction[];
}

export type EventType = "degradation_warning" | "undercut_window" | "position_change" | "pace_drop";

export interface RaceEvent {
  id: string;
  lap: number;
  type: EventType | string;
  drivers: string[];
  severity: number;
  title: string;
  analysis: { what: string; why: string; next: string };
  evidence: Record<string, unknown>;
  /** Null until the replay reaches `outcome_lap`, and always null for types without an outcome rule. */
  outcome?: "hit" | "miss" | "void" | null;
  outcome_lap?: number | null;
  outcome_text?: string | null;
}

export interface EventsResponse {
  race_id: string;
  lap: number;
  model: string;
  analyzed: boolean;
  /** Lap descending, then severity descending. */
  events: RaceEvent[];
}

export interface DriverPositions {
  code: string;
  p_win: number | null;
  p_podium: number | null;
  p_points: number | null;
  expected_position: number | null;
  position_p10: number | null;
  position_p90: number | null;
}

export interface PositionsResponse {
  race_id: string;
  lap: number;
  model: string;
  analyzed: boolean;
  runs: number | null;
  seed: number | null;
  drivers: DriverPositions[];
}

export interface PositionsHistoryResponse {
  race_id: string;
  model: string;
  analyzed: boolean;
  laps: {
    lap: number;
    drivers: Pick<DriverPositions, "code" | "p_win" | "p_podium" | "expected_position">[];
  }[];
}

export interface Strategy {
  name: string;
  pit_lap: number | null;
  mean_s: number;
  p10_s: number;
  p90_s: number;
  win_probability: number;
}

export interface StrategyResponse {
  race_id: string;
  lap: number;
  driver: string;
  runs: number;
  seed: number;
  pit_loss_s: number;
  strategies: Strategy[];
}

/** Everything the dashboard shows for one lap; published only when complete. */
export interface LapData {
  raceId: string;
  lap: number;
  state: RaceState;
  laps: LapRow[];
  predictions: PredictionsResponse;
  events: EventsResponse;
  positions: PositionsResponse;
}

export interface HitRate {
  undercut: { hits: number; resolved: number };
  degradation: { hits: number; resolved: number };
  hits: number;
  resolved: number;
  overall_pct: number | null;
}

/** GET /api/races/{race_id}/wrapped at the final lap (backend augur/wrapped.py). */
export interface WrappedResponse {
  race_id: string;
  event_name: string;
  year: number;
  model: { name: string; author: string | null };
  summary: {
    winner: string | null;
    podium: string[];
    total_laps: number;
    n_events: number;
    n_events_by_type: Record<string, number>;
  };
  podium_call: {
    lap: number;
    predicted: { code: string; p_podium: number | null }[];
    actual: string[];
    correct: number;
  };
  score: {
    position_skill_pct: number | null;
    brier_model: number | null;
    brier_baseline: number | null;
    lap_improvement_pct: number | null;
    mae_model_s: number | null;
    mae_baseline_s: number | null;
  };
  hit_rate: HitRate;
  best_call: RaceEvent | null;
  biggest_miss: RaceEvent | null;
  biggest_moment: RaceEvent | null;
  driver: {
    code: string;
    team: string | null;
    team_color: string | null;
    grid_position: number | null;
    final_position: number | null;
    positions_by_lap: { lap: number; position: number | null }[];
    p_podium_by_lap: { lap: number; p_podium: number | null }[];
    stints: { compound: string | null; laps: number }[];
    events: RaceEvent[];
  };
}
