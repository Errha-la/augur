import type { CSSProperties, KeyboardEvent, PointerEvent, ReactNode } from "react";
import type { WidgetInstance } from "../canvas/board";
import { REGISTRY, type WidgetType } from "../canvas/registry";

/** Body test ids and labels kept from the fixed layout, so panel tests move with the panels. */
export const WIDGET_BODY: Record<WidgetType, { testId: string; label: string; className: string }> = {
  timing: { testId: "timing", label: "Timing", className: "overflow-auto" },
  events: { testId: "intelligence", label: "Intelligence", className: "overflow-auto" },
  driver: { testId: "focus", label: "Focus driver", className: "overflow-auto" },
  lapchart: { testId: "chart", label: "Lap times", className: "overflow-hidden" },
  timeline: { testId: "timeline", label: "Event timeline", className: "overflow-auto px-3 py-2" },
  trace: { testId: "chart-trace", label: "Race trace", className: "overflow-hidden" },
  pitclock: { testId: "chart-pitclock", label: "Pit clock", className: "overflow-auto" },
  pitwindow: { testId: "chart-pitwindow", label: "Pit window", className: "overflow-hidden" },
  stints: { testId: "chart-stints", label: "Tyre stints", className: "overflow-auto" },
  degradation: { testId: "chart-degradation", label: "Degradation", className: "overflow-hidden" },
  pace: { testId: "chart-pace", label: "Pace compare", className: "overflow-hidden" },
  fan: { testId: "chart-fan", label: "Position fan", className: "overflow-hidden" },
  heatmap: { testId: "chart-heatmap", label: "Position odds", className: "overflow-auto" },
};

interface WidgetFrameProps {
  widget: WidgetInstance;
  /** Title-bar suffix, e.g. the driver the widget shows. */
  subtitle?: string;
  /** Title-bar controls: driver picker, event-type chips. */
  controls?: ReactNode;
  style?: CSSProperties;
  dragging?: boolean;
  /** False in the single-column view: no drag handles or resize corner. */
  editable: boolean;
  onTitlePointerDown?: (e: PointerEvent<HTMLDivElement>) => void;
  onResizePointerDown?: (e: PointerEvent<HTMLDivElement>) => void;
  onTitleKeyDown?: (e: KeyboardEvent<HTMLDivElement>) => void;
  onRemove?: () => void;
  children?: ReactNode;
}

export function WidgetFrame({
  widget,
  subtitle,
  controls,
  style,
  dragging,
  editable,
  onTitlePointerDown,
  onResizePointerDown,
  onTitleKeyDown,
  onRemove,
  children,
}: WidgetFrameProps) {
  const { title } = REGISTRY[widget.type];
  const body = WIDGET_BODY[widget.type];
  return (
    <div
      data-testid="widget"
      data-widget-id={widget.id}
      data-widget-type={widget.type}
      data-cell={`${widget.x},${widget.y},${widget.w},${widget.h}`}
      data-dragging={dragging || undefined}
      style={style}
      className={`relative flex min-h-0 flex-col overflow-hidden rounded-md border border-zinc-800 bg-card ${
        dragging ? "z-20 shadow-2xl shadow-black/60" : ""
      }`}
    >
      <div
        data-testid="widget-title"
        data-guide="title-bar"
        role="group"
        aria-label={`${title} widget`}
        aria-roledescription={editable ? "movable widget" : undefined}
        aria-keyshortcuts={editable ? "ArrowLeft ArrowRight ArrowUp ArrowDown Shift+ArrowLeft Shift+ArrowRight Shift+ArrowUp Shift+ArrowDown" : undefined}
        title={editable ? "Drag to move · arrow keys move · Shift+arrow keys resize" : undefined}
        tabIndex={editable ? 0 : undefined}
        onPointerDown={editable ? onTitlePointerDown : undefined}
        onKeyDown={editable ? onTitleKeyDown : undefined}
        className={`flex min-h-7 shrink-0 touch-none flex-wrap items-center gap-2 border-b border-zinc-800/70 px-2 py-1 text-[11px] select-none focus-visible:outline-2 focus-visible:outline-zinc-400 ${
          editable ? "cursor-grab active:cursor-grabbing" : ""
        }`}
      >
        <span className="font-bold tracking-wider text-zinc-400">
          {title.toUpperCase()}
          {subtitle && <span className="ml-1 text-zinc-200">· {subtitle}</span>}
        </span>
        <div className="flex min-w-0 flex-1 flex-wrap items-center gap-1">{controls}</div>
        {onRemove && (
          <button
            type="button"
            aria-label={`Remove ${title} widget`}
            title="Remove widget"
            className="rounded px-1 text-zinc-500 hover:bg-zinc-800 hover:text-zinc-100"
            onClick={onRemove}
          >
            ✕
          </button>
        )}
      </div>
      <section
        data-testid={body.testId}
        aria-label={body.label}
        className={`widget-body min-h-0 flex-1 ${body.className}`}
      >
        {children}
      </section>
      {editable && (
        <div
          data-testid="resize-handle"
          data-guide="resize"
          aria-hidden
          title="Drag to resize"
          onPointerDown={onResizePointerDown}
          className="absolute right-0 bottom-0 h-4 w-4 cursor-nwse-resize touch-none"
          style={{ background: "linear-gradient(135deg, transparent 50%, #52525b 50%, #52525b 60%, transparent 60%, transparent 75%, #52525b 75%, #52525b 85%, transparent 85%)" }}
        />
      )}
    </div>
  );
}
