import { useState } from "react";
import { downloadAllCards, type CardExport } from "./download";

interface DownloadAllButtonProps {
  /** Mounts all cards at export size and runs the task with them (WrappedStory's exportAll). */
  exportAll: (task: (cards: CardExport[]) => Promise<void>) => Promise<void>;
  zipName: string;
}

export function DownloadAllButton({ exportAll, zipName }: DownloadAllButtonProps) {
  const [state, setState] = useState<"idle" | "saving" | "error">("idle");
  return (
    <>
      <button
        type="button"
        disabled={state === "saving"}
        className="rounded border border-purple-400 px-3 py-1 font-bold text-purple-300 disabled:opacity-50"
        onClick={async (e) => {
          e.stopPropagation(); // never also counts as a click on the card stage
          setState("saving");
          try {
            await exportAll((cards) => downloadAllCards(cards, zipName));
            setState("idle");
          } catch {
            setState("error");
          }
        }}
      >
        {state === "saving" ? "Saving..." : "Download all"}
      </button>
      {state === "error" && (
        <span role="alert" className="text-flag-red">
          Could not save the cards
        </span>
      )}
    </>
  );
}
