import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

// First-visit guide ("First-visit guide"): four steps anchored to the elements
// they explain. Not modal: the board stays usable behind it.

export const GUIDE_KEY = "augur.guide.v1";

export interface GuideStep {
  /** `data-guide` value of the element the step points at. */
  anchor: string;
  title: string;
  text: string;
}

export const GUIDE_STEPS: GuideStep[] = [
  { anchor: "title-bar", title: "Move a widget", text: "Drag a widget by its title bar. With the title bar focused, arrow keys move it one cell." },
  { anchor: "resize", title: "Resize a widget", text: "Drag the bottom-right corner. With the title bar focused, Shift + arrow keys resize it." },
  {
    anchor: "add-widget",
    title: "Add widgets and pick drivers",
    text: "Add widgets with + Widget; the same type can appear more than once. Driver widgets pick their own driver in the title bar, or follow the focus driver.",
  },
  {
    anchor: "board-menu",
    title: "Your boards",
    text: "Switch between PIT WALL, BATTLE, PACE and your own boards, create a blank board, and export or import boards as files. Boards are saved in this browser.",
  },
];

/** True when the guide should open on load: never finished, or storage is unavailable. */
function guideSeen(): boolean {
  try {
    return window.localStorage.getItem(GUIDE_KEY) !== null;
  } catch {
    return false; // unavailable: open once per page load
  }
}

function markSeen(): void {
  try {
    window.localStorage.setItem(GUIDE_KEY, "done");
  } catch {
    // Storage unavailable: the guide opens again on the next page load.
  }
}

export function useGuide() {
  const [open, setOpen] = useState(() => !guideSeen());
  const close = useCallback(() => {
    markSeen();
    setOpen(false);
  }, []);
  const reopen = useCallback(() => setOpen(true), []);
  return { open, close, reopen };
}

interface Box {
  top: number;
  left: number;
  width: number;
  height: number;
}

function anchorBox(anchor: string): Box | null {
  const el = document.querySelector<HTMLElement>(`[data-guide="${anchor}"]`);
  if (!el) return null;
  const r = el.getBoundingClientRect();
  if (r.width === 0 && r.height === 0) return null;
  return { top: r.top, left: r.left, width: r.width, height: r.height };
}

const CARD_WIDTH = 320;

export function Guide({ onClose }: { onClose: () => void }) {
  const [index, setIndex] = useState(0);
  const [box, setBox] = useState<Box | null>(null);
  const card = useRef<HTMLDivElement>(null);
  const step = GUIDE_STEPS[index];
  const last = index === GUIDE_STEPS.length - 1;

  useLayoutEffect(() => {
    const measure = () => setBox(anchorBox(step.anchor));
    measure();
    // The board measures its own width after mounting, so the anchor can still
    // grow and move: measure again on the next frame and whenever it resizes.
    const frame = requestAnimationFrame(measure);
    const el = document.querySelector(`[data-guide="${step.anchor}"]`);
    const observer = new ResizeObserver(measure);
    if (el) observer.observe(el);
    window.addEventListener("resize", measure);
    window.addEventListener("scroll", measure, true);
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      window.removeEventListener("resize", measure);
      window.removeEventListener("scroll", measure, true);
    };
  }, [step.anchor]);

  // Focus moves into each step so keyboard users start on its buttons.
  useEffect(() => {
    card.current?.focus();
  }, [index]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  let position: React.CSSProperties = { top: "50%", left: "50%", transform: "translate(-50%, -50%)" };
  if (box) {
    const below = box.top + box.height + 10;
    const top = below + 200 > window.innerHeight ? Math.max(8, box.top - 210) : below;
    const left = Math.min(Math.max(8, box.left), Math.max(8, window.innerWidth - CARD_WIDTH - 8));
    position = { top, left };
  }

  return (
    <>
      {box && (
        <div
          aria-hidden
          data-testid="guide-highlight"
          className="pointer-events-none fixed z-50 rounded-md ring-2 ring-purple-400 motion-safe:transition-all motion-safe:duration-200"
          style={{ top: box.top - 3, left: box.left - 3, width: box.width + 6, height: box.height + 6 }}
        />
      )}
      <div
        ref={card}
        role="dialog"
        aria-modal="false"
        aria-labelledby="guide-title"
        aria-describedby="guide-text"
        tabIndex={-1}
        data-testid="guide"
        data-anchor={box ? step.anchor : ""}
        className="fixed z-50 flex flex-col gap-2 rounded-md border border-purple-400/60 bg-card p-3 text-sm text-zinc-200 shadow-2xl shadow-black/60 outline-none motion-safe:transition-all motion-safe:duration-200"
        style={{ width: CARD_WIDTH, maxWidth: "calc(100vw - 16px)", ...position }}
      >
        <div className="text-[10px] font-bold tracking-wider text-purple-300">
          Step {index + 1} of {GUIDE_STEPS.length}
        </div>
        <h2 id="guide-title" className="font-bold text-zinc-50">
          {step.title}
        </h2>
        <p id="guide-text" className="text-xs leading-relaxed text-zinc-300">
          {step.text}
        </p>
        <div className="mt-1 flex items-center gap-2">
          <button type="button" className="text-xs text-zinc-500 hover:text-zinc-200" onClick={onClose}>
            Skip
          </button>
          <div className="ml-auto flex gap-2">
            {index > 0 && (
              <button
                type="button"
                className="rounded border border-zinc-700 px-2 py-1 text-xs hover:bg-zinc-800"
                onClick={() => setIndex(index - 1)}
              >
                Back
              </button>
            )}
            <button
              type="button"
              className="rounded border border-purple-400 px-2 py-1 text-xs font-bold text-purple-200 hover:bg-purple-400/10"
              onClick={() => (last ? onClose() : setIndex(index + 1))}
            >
              {last ? "Done" : "Next"}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
