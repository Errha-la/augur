import { useEffect } from "react";
import type { WrappedState } from "../../hooks/useWrapped";
import { DownloadCardButton } from "./DownloadCardButton";
import { WrappedStory } from "./WrappedStory";

interface WrappedOverlayProps {
  state: WrappedState;
  onClose: () => void;
  teamColors?: Record<string, string>;
}

/** Full-screen layer for the Wrapped: loading and error states, then the story. */
export function WrappedOverlay({ state, onClose, teamColors }: WrappedOverlayProps) {
  useEffect(() => {
    if (state.status === "open" || state.status === "closed") return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [state.status, onClose]);

  if (state.status === "closed") return null;
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Race Wrapped"
      data-testid="wrapped-overlay"
      className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-950/95 font-mono text-zinc-100"
    >
      {state.status === "loading" && <p className="text-sm text-zinc-400">Building the Wrapped...</p>}
      {state.status === "error" && (
        <div role="alert" className="flex flex-col items-center gap-3 text-sm">
          <p>Wrapped unavailable: {state.message}</p>
          <button type="button" className="rounded border border-zinc-700 px-3 py-1" onClick={onClose}>
            Close
          </button>
        </div>
      )}
      {state.status === "open" && (
        <WrappedStory
          data={state.data}
          onClose={onClose}
          teamColors={teamColors}
          actions={({ getNode, fileName }) => <DownloadCardButton getNode={getNode} fileName={fileName} />}
        />
      )}
    </div>
  );
}
