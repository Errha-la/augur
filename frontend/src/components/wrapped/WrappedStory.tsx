import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import type { WrappedResponse } from "../../api/types";
import { buildCards, CARD_HEIGHT, CARD_WIDTH, footerText } from "./cards";

interface WrappedStoryProps {
  data: WrappedResponse;
  onClose: () => void;
  /** Team colours by driver code (the Summary card uses the winner's). */
  teamColors?: Record<string, string>;
  /** Rendered under the card; `getNode` returns the unscaled card node at click time. */
  actions?: (card: { getNode: () => HTMLElement | null; fileName: string }) => ReactNode;
}

function useViewport() {
  const [size, setSize] = useState(() => ({ w: window.innerWidth, h: window.innerHeight }));
  useEffect(() => {
    const onResize = () => setSize({ w: window.innerWidth, h: window.innerHeight });
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);
  return size;
}

export function cardFileName(raceId: string, index: number, slug: string): string {
  return `augur-wrapped-${raceId}-${index + 1}-${slug}.png`;
}

/**
 * Seven 1080×1920 cards, scaled to fit the viewport with a CSS transform on a
 * wrapper so the card node itself keeps its export size.
 */
export function WrappedStory({ data, onClose, teamColors = {}, actions }: WrappedStoryProps) {
  const cards = useMemo(() => buildCards(data, teamColors), [data, teamColors]);
  const [index, setIndex] = useState(0);
  const cardRef = useRef<HTMLDivElement>(null);
  const { w, h } = useViewport();
  const scale = Math.max(0.1, Math.min((h - 140) / CARD_HEIGHT, (w - 32) / CARD_WIDTH));
  const last = cards.length - 1;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight") {
        e.preventDefault();
        setIndex((i) => Math.min(i + 1, last));
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        setIndex((i) => Math.max(i - 1, 0));
      } else if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [last, onClose]);

  const card = cards[index];
  return (
    <div data-testid="wrapped-story" data-race={data.race_id} className="flex h-full w-full flex-col items-center gap-3 py-3">
      <div data-testid="story-progress" className="flex w-full max-w-xl gap-1 px-4">
        {cards.map((c, i) => (
          <div
            key={c.slug}
            data-testid="progress-segment"
            data-active={i === index || undefined}
            className="h-1 flex-1 rounded"
            style={{ backgroundColor: i <= index ? c.accent : "#3f3f46" }}
          />
        ))}
      </div>

      <div
        data-testid="story-stage"
        className="relative cursor-pointer"
        style={{ width: CARD_WIDTH * scale, height: CARD_HEIGHT * scale }}
        onClick={(e) => {
          const rect = e.currentTarget.getBoundingClientRect();
          const right = rect.width === 0 ? e.clientX >= window.innerWidth / 2 : e.clientX - rect.left >= rect.width / 2;
          setIndex((i) => (right ? Math.min(i + 1, last) : Math.max(i - 1, 0)));
        }}
      >
        <div style={{ transform: `scale(${scale})`, transformOrigin: "top left", width: CARD_WIDTH, height: CARD_HEIGHT }}>
          <div
            ref={cardRef}
            data-testid="wrapped-card"
            data-card={card.slug}
            data-index={index + 1}
            data-accent={card.accent}
            className="flex flex-col justify-between bg-zinc-950 p-[90px] font-mono text-zinc-100"
            style={{ width: CARD_WIDTH, height: CARD_HEIGHT, borderTop: `24px solid ${card.accent}` }}
          >
            <div className="flex flex-col gap-16">
              <div className="flex items-baseline justify-between">
                <span className="text-[34px] font-bold tracking-[0.4em] text-zinc-400">AUGUR WRAPPED</span>
                <span className="text-[34px] text-zinc-500">
                  {index + 1}/{cards.length}
                </span>
              </div>
              <h2 className="text-[72px] font-bold" style={{ color: card.accent }}>
                {card.title}
              </h2>
              {card.body}
            </div>
            <footer data-testid="card-footer" className="text-[30px] text-zinc-500">
              {footerText(data)}
            </footer>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3 text-sm">
        <span className="text-zinc-500">← → or click left / right · Esc closes</span>
        {actions?.({ getNode: () => cardRef.current, fileName: cardFileName(data.race_id, index, card.slug) })}
        <button type="button" className="rounded border border-zinc-700 px-3 py-1" onClick={onClose}>
          Close
        </button>
      </div>
    </div>
  );
}
