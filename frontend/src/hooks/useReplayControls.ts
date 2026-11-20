import { useEffect, type Dispatch } from "react";
import { TICK_MS, type ReplayAction, type ReplayState } from "../state/replay";

/**
 * Advances one lap per tick while playing. The next tick is scheduled only after
 * the current lap has rendered (`rendered`), so slow responses slow playback
 * down instead of skipping laps.
 */
export function usePlayback(replay: ReplayState, rendered: boolean, dispatch: Dispatch<ReplayAction>) {
  const { playing, speed, lap } = replay;
  useEffect(() => {
    if (!playing || !rendered) return;
    const timer = setTimeout(() => dispatch({ type: "tick" }), TICK_MS[speed]);
    return () => clearTimeout(timer);
  }, [playing, rendered, speed, lap, dispatch]);
}

function isTextEntry(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (target instanceof HTMLInputElement) return target.type !== "range";
  return target instanceof HTMLTextAreaElement || target instanceof HTMLSelectElement || target.isContentEditable;
}

/** Left / Right step one lap, Space toggles playback. */
export function useReplayKeys(dispatch: Dispatch<ReplayAction>, enabled = true) {
  useEffect(() => {
    // Off while an overlay (the Wrapped story) owns the arrow keys.
    if (!enabled) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.altKey || e.ctrlKey || e.metaKey || isTextEntry(e.target)) return;
      if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
        // Also overrides a focused slider's own arrow handling, so a key is one lap.
        e.preventDefault();
        dispatch({ type: "step", delta: e.key === "ArrowRight" ? 1 : -1 });
      } else if (e.key === " " || e.code === "Space") {
        e.preventDefault(); // no page scroll, no second toggle from a focused button
        dispatch({ type: "togglePlay" });
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [dispatch, enabled]);
}
