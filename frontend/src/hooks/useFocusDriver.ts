import { useCallback, useState } from "react";
import type { LapData } from "../api/types";

function leaderOf(data: LapData): string | null {
  let best: { code: string; position: number } | null = null;
  for (const d of data.state.drivers) {
    if (!best || d.position < best.position) best = d;
  }
  return best?.code ?? null;
}

interface Selection {
  raceId: string | null;
  code: string | null;
}

/**
 * Exactly one focus driver. When the first lap of a race is shown, the focus is
 * kept if that driver code is in the race, otherwise it becomes P1 at lap 1
 * (a race change always restarts at lap 1). Clicking a row sets it directly.
 * Resolved during render, so no frame is drawn without a focus driver.
 */
export function useFocusDriver(data: LapData | null): [string | null, (code: string) => void] {
  const [selection, setSelection] = useState<Selection>({ raceId: null, code: null });

  let current = selection;
  if (data && selection.raceId !== data.raceId) {
    const keep = selection.code !== null && data.state.drivers.some((d) => d.code === selection.code);
    current = { raceId: data.raceId, code: keep ? selection.code : leaderOf(data) };
    setSelection(current);
  }

  const raceId = data?.raceId ?? null;
  const setFocus = useCallback((code: string) => setSelection({ raceId, code }), [raceId]);
  return [current.code, setFocus];
}
