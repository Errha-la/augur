import { useState } from "react";
import { downloadCard } from "./download";

interface DownloadCardButtonProps {
  getNode: () => HTMLElement | null;
  fileName: string;
}

export function DownloadCardButton({ getNode, fileName }: DownloadCardButtonProps) {
  const [state, setState] = useState<"idle" | "saving" | "error">("idle");
  return (
    <>
      <button
        type="button"
        disabled={state === "saving"}
        className="rounded border border-purple-400 px-3 py-1 font-bold text-purple-300 disabled:opacity-50"
        onClick={async (e) => {
          e.stopPropagation(); // never also counts as a click on the card stage
          const node = getNode();
          if (!node) return;
          setState("saving");
          try {
            await downloadCard(node, fileName);
            setState("idle");
          } catch {
            setState("error");
          }
        }}
      >
        {state === "saving" ? "Saving..." : "Download card"}
      </button>
      {state === "error" && (
        <span role="alert" className="text-flag-red">
          Could not save the card
        </span>
      )}
    </>
  );
}
