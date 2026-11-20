import type { ReactNode } from "react";

interface LayoutProps {
  /** Race and lap of the data on screen (exposed for tests and debugging). */
  shownRaceId?: string;
  shownLap?: number;
  statusBar?: ReactNode;
  banner?: ReactNode;
  timing?: ReactNode;
  intelligence?: ReactNode;
  focus?: ReactNode;
  chart?: ReactNode;
  timeline?: ReactNode;
}

const card = "rounded-md border border-zinc-800 bg-card";

/**
 * Timing-screen grid after BENNNZO/f1-dashboard: status bar on top, the timing
 * column on the left, and on the right the intelligence panel above a bottom
 * row (focus panel + chart) with the event timeline under them.
 */
export function Layout({
  shownRaceId,
  shownLap,
  statusBar,
  banner,
  timing,
  intelligence,
  focus,
  chart,
  timeline,
}: LayoutProps) {
  return (
    <div
      data-testid="layout"
      data-race={shownRaceId ?? ""}
      data-lap={shownLap ?? ""}
      className="flex h-full min-h-screen flex-col gap-2 bg-zinc-950 p-2 font-mono text-zinc-100"
    >
      <header data-testid="status-bar" className={`${card} px-3 py-2`}>
        {statusBar}
      </header>
      {banner}
      <main className="grid min-h-0 flex-1 grid-cols-[minmax(560px,5fr)_7fr] gap-2">
        <section data-testid="timing" aria-label="Timing" className={`${card} min-h-0 overflow-auto`}>
          {timing}
        </section>
        <div className="flex min-h-0 flex-col gap-2">
          <section
            data-testid="intelligence"
            aria-label="Intelligence"
            className={`${card} min-h-0 flex-1 overflow-auto`}
          >
            {intelligence}
          </section>
          <div className="grid min-h-0 flex-1 grid-cols-2 gap-2">
            <section data-testid="focus" aria-label="Focus driver" className={`${card} min-h-0 overflow-auto`}>
              {focus}
            </section>
            <section data-testid="chart" aria-label="Lap times" className={`${card} min-h-0 overflow-hidden`}>
              {chart}
            </section>
          </div>
          <section data-testid="timeline" aria-label="Event timeline" className={`${card} px-3 py-2`}>
            {timeline}
          </section>
        </div>
      </main>
    </div>
  );
}
