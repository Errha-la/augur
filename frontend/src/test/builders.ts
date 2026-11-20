import type { DriverPositions, DriverPrediction, DriverState, LapRow, RaceEvent } from "../api/types";

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
