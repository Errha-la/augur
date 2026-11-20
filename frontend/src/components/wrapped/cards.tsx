import type { ReactNode } from "react";
import type { RaceEvent, WrappedResponse } from "../../api/types";
import { formatPct } from "../../lib/format";
import { compoundColor, eventTypeLabel } from "../../lib/theme";

// Card accents (race-wrapped design "Card accent colours").
export const ACCENT = {
  podiumCall: "#fbcc1c",
  good: "#34d399", // emerald-400
  bad: "#f12f32",
  bestCall: "#c084fc", // purple-400
  moment: "#d4d4d8", // zinc-300
  neutral: "#d4d4d8",
};

export const NO_CALLS = "No resolved calls this race";
export const NO_EVENTS = "No events this race";
export const NO_SKILL = "Order never changed — nothing to beat";

export const CARD_WIDTH = 1080;
export const CARD_HEIGHT = 1920;

export interface CardSpec {
  slug: string;
  title: string;
  accent: string;
  body: ReactNode;
}

export function footerText(data: WrappedResponse): string {
  const author = data.model.author ?? "unknown";
  return `AUGUR · ${data.model.name} by ${author} · ${data.event_name} ${data.year}`;
}

export function skillText(skill: number | null): string {
  if (skill == null) return NO_SKILL;
  if (skill > 0) return `Podium calls: ${skill.toFixed(1)}% better than current order`;
  if (skill < 0) return `Podium calls: ${Math.abs(skill).toFixed(1)}% worse than current order`;
  return "Podium calls: level with current order";
}

export function lapText(improvement: number | null): string {
  if (improvement == null) return "Lap times: no clean laps to compare";
  if (improvement > 0) return `Lap times: beat baseline by ${improvement.toFixed(1)}%`;
  if (improvement < 0) return `Lap times: trail baseline by ${Math.abs(improvement).toFixed(1)}%`;
  return "Lap times: match baseline (0.0%)";
}

export function hitText(hr: WrappedResponse["hit_rate"]): string {
  if (hr.overall_pct == null) return "Event calls: none resolved";
  return `Event calls: ${hr.overall_pct.toFixed(0)}% right (${hr.hits}/${hr.resolved})`;
}

export function podiumCallText(call: WrappedResponse["podium_call"]): string {
  const codes = call.predicted.map((p) => p.code).join(", ");
  return `At lap ${call.lap} AUGUR's podium was ${codes} — ${call.correct} of ${call.predicted.length} correct`;
}

function Big({ children }: { children: ReactNode }) {
  return <div className="text-[96px] leading-none font-bold">{children}</div>;
}

function Label({ children }: { children: ReactNode }) {
  return <div className="text-[30px] tracking-[0.3em] text-zinc-500 uppercase">{children}</div>;
}

function Line({ children, testId }: { children: ReactNode; testId?: string }) {
  return (
    <p data-testid={testId} className="text-[44px] leading-tight">
      {children}
    </p>
  );
}

function EventBlock({ event, empty, accent }: { event: RaceEvent | null; empty: string; accent: string }) {
  if (!event) {
    return (
      <p data-testid="card-empty" className="text-[56px] text-zinc-400">
        {empty}
      </p>
    );
  }
  return (
    <div className="flex flex-col gap-10">
      <div className="flex items-baseline gap-8 text-[40px]">
        <span className="font-bold" style={{ color: accent }}>
          LAP {event.lap}
        </span>
        <span className="text-zinc-400">{eventTypeLabel(event.type)}</span>
      </div>
      <Big>{event.drivers.join(" · ")}</Big>
      <Line>{event.title}</Line>
      <div className="flex flex-col gap-4">
        <Label>AUGUR said</Label>
        <p className="text-[38px] leading-snug text-zinc-300">{event.analysis.what}</p>
        <p className="text-[38px] leading-snug text-zinc-300">{event.analysis.next}</p>
      </div>
      {event.outcome_text && (
        <div className="flex flex-col gap-4">
          <Label>What happened</Label>
          <p className="text-[42px] leading-snug" data-testid="card-outcome">
            <span className="mr-4 font-bold uppercase" style={{ color: accent }}>
              {event.outcome}
            </span>
            {event.outcome_text}
          </p>
        </div>
      )}
    </div>
  );
}

/** Polyline over laps 1..N; `invert` puts small values (P1) at the top. */
function LapLine({
  points,
  max,
  color,
  invert,
  label,
}: {
  points: { lap: number; value: number | null }[];
  max: number;
  color: string;
  invert?: boolean;
  label: string;
}) {
  const w = 900;
  const h = 220;
  const laps = Math.max(points.length, 2);
  const segments: string[] = [];
  let current: string[] = [];
  for (const p of points) {
    if (p.value == null) {
      if (current.length) segments.push(current.join(" "));
      current = [];
      continue;
    }
    const x = ((p.lap - 1) / (laps - 1)) * w;
    const frac = Math.min(Math.max(p.value / max, 0), 1);
    const y = invert ? frac * h : h - frac * h;
    current.push(`${x.toFixed(1)},${y.toFixed(1)}`);
  }
  if (current.length) segments.push(current.join(" "));
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} role="img" aria-label={label}>
      <rect x={0} y={0} width={w} height={h} fill="none" stroke="#27272a" />
      {segments.map((s, i) => (
        <polyline key={i} points={s} fill="none" stroke={color} strokeWidth={6} strokeLinejoin="round" />
      ))}
    </svg>
  );
}

export function buildCards(data: WrappedResponse, teamColors: Record<string, string>): CardSpec[] {
  const { summary, podium_call: call, score, driver } = data;
  const winnerColor = (summary.winner && teamColors[summary.winner]) || ACCENT.neutral;
  const driverColor = driver.team_color || teamColors[driver.code] || ACCENT.neutral;
  const skillGood = score.position_skill_pct != null && score.position_skill_pct > 0;
  const maxPosition = Math.max(1, ...driver.positions_by_lap.map((p) => p.position ?? 0));

  return [
    {
      slug: "summary",
      title: "Summary",
      accent: winnerColor,
      body: (
        <div className="flex flex-col gap-14">
          <Label>{`${data.event_name} ${data.year}`}</Label>
          <div>
            <Label>Winner</Label>
            <div className="text-[180px] leading-none font-bold" style={{ color: winnerColor }}>
              {summary.winner ?? "—"}
            </div>
          </div>
          <Line>Podium: {summary.podium.join(" · ")}</Line>
          <Line>{summary.total_laps} laps</Line>
          <Line>{summary.n_events} events called</Line>
        </div>
      ),
    },
    {
      slug: "podium-call",
      title: "Podium Call",
      accent: ACCENT.podiumCall,
      body: (
        <div className="flex flex-col gap-14">
          <Line testId="podium-call-text">{podiumCallText(call)}</Line>
          <ul className="flex flex-col gap-8">
            {call.predicted.map((p) => (
              <li key={p.code} data-testid="podium-call-driver" className="flex items-baseline justify-between">
                <span className="text-[96px] font-bold">{p.code}</span>
                <span className="text-[64px]" style={{ color: ACCENT.podiumCall }}>
                  {formatPct(p.p_podium) ?? "—"}
                </span>
                <span className="text-[40px] text-zinc-400">{call.actual.includes(p.code) ? "on the podium" : "missed"}</span>
              </li>
            ))}
          </ul>
          <Line>Actual podium: {call.actual.join(" · ")}</Line>
        </div>
      ),
    },
    {
      slug: "accuracy",
      title: "Accuracy",
      accent: skillGood ? ACCENT.good : ACCENT.bad,
      body: (
        <div className="flex flex-col gap-14">
          <Line testId="accuracy-skill">{skillText(score.position_skill_pct)}</Line>
          <p className="text-[32px] text-zinc-500">
            Brier {score.brier_model ?? "—"} vs {score.brier_baseline ?? "—"} (current order)
          </p>
          <Line testId="accuracy-laps">{lapText(score.lap_improvement_pct)}</Line>
          <p className="text-[32px] text-zinc-500">
            MAE {score.mae_model_s ?? "—"} s vs {score.mae_baseline_s ?? "—"} s
          </p>
          <Line testId="accuracy-hits">{hitText(data.hit_rate)}</Line>
        </div>
      ),
    },
    {
      slug: "best-call",
      title: "Best Call",
      accent: ACCENT.bestCall,
      body: <EventBlock event={data.best_call} empty={NO_CALLS} accent={ACCENT.bestCall} />,
    },
    {
      slug: "biggest-miss",
      title: "Biggest Miss",
      accent: ACCENT.bad,
      body: <EventBlock event={data.biggest_miss} empty={NO_CALLS} accent={ACCENT.bad} />,
    },
    {
      slug: "biggest-moment",
      title: "Biggest Moment",
      accent: ACCENT.moment,
      body: <EventBlock event={data.biggest_moment} empty={NO_EVENTS} accent={ACCENT.moment} />,
    },
    {
      slug: "driver",
      title: driver.code,
      accent: driverColor,
      body: (
        <div className="flex flex-col gap-12">
          <Label>{driver.team ?? ""}</Label>
          <div className="text-[120px] leading-none font-bold" data-testid="driver-positions">
            P{driver.grid_position ?? "?"} → P{driver.final_position ?? "?"}
          </div>
          <div className="flex flex-col gap-3">
            <Label>Position by lap</Label>
            <LapLine
              label="Position by lap"
              points={driver.positions_by_lap.map((p) => ({ lap: p.lap, value: p.position }))}
              max={maxPosition}
              color={driverColor}
              invert
            />
          </div>
          <div className="flex flex-col gap-3">
            <Label>Podium chance by lap</Label>
            <LapLine
              label="Podium chance by lap"
              points={driver.p_podium_by_lap.map((p) => ({ lap: p.lap, value: p.p_podium }))}
              max={1}
              color={ACCENT.podiumCall}
            />
          </div>
          <div className="flex h-12 w-[900px] gap-1 overflow-hidden rounded" data-testid="driver-stints">
            {driver.stints.map((s, i) => (
              <div key={i} style={{ flexGrow: s.laps, flexBasis: 0, backgroundColor: compoundColor(s.compound) }} />
            ))}
          </div>
          <ul className="flex flex-col gap-4 text-[34px]">
            {driver.events.slice(0, 5).map((e) => (
              <li key={e.id}>
                <span className="text-zinc-500">L{e.lap}</span> {eventTypeLabel(e.type)}
                {e.outcome && <span className="ml-3 font-bold uppercase">{e.outcome}</span>}
              </li>
            ))}
            {driver.events.length === 0 && <li className="text-zinc-500">{NO_EVENTS}</li>}
          </ul>
        </div>
      ),
    },
  ];
}
