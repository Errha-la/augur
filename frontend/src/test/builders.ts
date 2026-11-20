import type { DriverPositions, DriverPrediction, DriverState, LapRow, RaceEvent, WrappedResponse } from "../api/types";

export function driver(code: string, position: number, extra: Partial<DriverState> = {}): DriverState {
  return {
    code,
    team: "Team",
    team_color: "#888888",
    position,
    laps_completed: 1,
    last_lap_time_s: 90,
    compound: "MEDIUM",
    tyre_age_laps: 1,
    stint: 1,
    pit_count: 0,
    gap_to_leader_s: position === 1 ? 0 : position,
    laps_behind_leader: 0,
    ...extra,
  };
}

export function lapRow(driverCode: string, lap: number, lapTime: number | null, extra: Partial<LapRow> = {}): LapRow {
  return {
    driver: driverCode,
    team: "Team",
    lap,
    lap_time_s: lapTime,
    session_time_s: null,
    stint: 1,
    compound: "MEDIUM",
    tyre_life: lap,
    pit_in: false,
    pit_out: false,
    track_status: "1",
    is_accurate: true,
    ...extra,
  };
}

export function prediction(code: string, extra: Partial<DriverPrediction> = {}): DriverPrediction {
  return { code, predicted_next_lap_s: 90, recent_pace_s: 90, deg_s_per_lap: 0.05, deg_laps: 5, cliff: false, ...extra };
}

export function positions(code: string, extra: Partial<DriverPositions> = {}): DriverPositions {
  return {
    code,
    p_win: 0.1,
    p_podium: 0.3,
    p_points: 0.9,
    expected_position: 5,
    position_p10: 3,
    position_p90: 7,
    ...extra,
  };
}

export function raceEvent(id: string, lap: number, type: string, drivers: string[], severity = 50): RaceEvent {
  return {
    id,
    lap,
    type,
    drivers,
    severity,
    title: `${type} ${drivers.join(" ")} lap ${lap}`,
    analysis: { what: `What of ${id}`, why: `Why of ${id}`, next: `Next of ${id}` },
    evidence: { driver: drivers[0] },
  };
}

/** A Wrapped response using the spec's example values (podium call at lap 29, 2 of 3). */
export function wrappedResponse(
  extra: Partial<WrappedResponse> = {},
  driverExtra: Partial<WrappedResponse["driver"]> = {},
): WrappedResponse {
  const hit = { ...raceEvent("best", 18, "undercut_window", ["NOR", "PIA"], 60), outcome: "hit" as const, outcome_lap: 26, outcome_text: "NOR was ahead of PIA on lap 26 (P3 vs P4)." };
  const miss = { ...raceEvent("miss", 30, "degradation_warning", ["HAM"], 70), outcome: "miss" as const, outcome_lap: 38, outcome_text: "HAM did not pit by lap 38, 8 laps after the warning." };
  const moment = raceEvent("moment", 44, "position_change", ["VER"], 90);
  return {
    race_id: "2024-24-abu-dhabi-grand-prix",
    event_name: "Abu Dhabi Grand Prix",
    year: 2024,
    model: { name: "lightgbm", author: "AUGUR" },
    summary: {
      winner: "VER",
      podium: ["VER", "LEC", "PIA"],
      total_laps: 58,
      n_events: 3,
      n_events_by_type: { degradation_warning: 1, position_change: 1, undercut_window: 1 },
    },
    podium_call: {
      lap: 29,
      predicted: [
        { code: "VER", p_podium: 0.92 },
        { code: "NOR", p_podium: 0.71 },
        { code: "LEC", p_podium: 0.55 },
      ],
      actual: ["VER", "LEC", "PIA"],
      correct: 2,
    },
    score: {
      position_skill_pct: -3.2,
      brier_model: 0.1032,
      brier_baseline: 0.1,
      lap_improvement_pct: 12.5,
      mae_model_s: 0.875,
      mae_baseline_s: 1.0,
    },
    hit_rate: {
      undercut: { hits: 1, resolved: 1 },
      degradation: { hits: 0, resolved: 1 },
      hits: 1,
      resolved: 2,
      overall_pct: 50,
    },
    best_call: hit,
    biggest_miss: miss,
    biggest_moment: moment,
    driver: {
      code: "NOR",
      team: "McLaren",
      team_color: "#FF8000",
      grid_position: 1,
      final_position: 2,
      positions_by_lap: Array.from({ length: 58 }, (_, i) => ({ lap: i + 1, position: i < 20 ? 1 : 2 })),
      p_podium_by_lap: Array.from({ length: 58 }, (_, i) => ({ lap: i + 1, p_podium: i < 20 ? 0.9 : 0.7 })),
      stints: [
        { compound: "MEDIUM", laps: 25 },
        { compound: "HARD", laps: 33 },
      ],
      events: [hit],
      ...driverExtra,
    },
    ...extra,
  };
}
