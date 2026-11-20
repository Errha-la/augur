// Exact texts from specs/replay-controls "Backend status messages".

export const BACKEND_DOWN = "Backend not reachable at /api. Start it with: uvicorn augur.api:app";
export const NO_RACES = "No races ingested. Run: python -m augur.ingest --year 2024 --rounds 1 24";

export function notAnalyzedText(raceId: string): string {
  return `Race not analyzed. Run: python -m augur.analyze --race ${raceId}`;
}

export function Banner({ text, onRetry }: { text: string; onRetry?: () => void }) {
  return (
    <div
      role="alert"
      className="flex items-center justify-between gap-3 rounded-md border border-flag-red/50 bg-flag-red/10 px-3 py-2 text-sm text-zinc-200"
    >
      <span>{text}</span>
      {onRetry && (
        <button
          type="button"
          className="rounded border border-zinc-700 px-3 py-1 text-zinc-100 hover:bg-zinc-800"
          onClick={onRetry}
        >
          Retry
        </button>
      )}
    </div>
  );
}

export function PanelMessage({ text }: { text: string }) {
  return (
    <p role="status" className="p-4 text-sm text-zinc-400">
      {text}
    </p>
  );
}
