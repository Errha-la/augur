import { type KeyboardEvent, type PointerEvent, type ReactNode, useEffect, useLayoutEffect, useRef, useState } from "react";
import { type Board as BoardModel, moveWidget, removeWidget, resizeWidget, type WidgetInstance } from "../canvas/board";
import { bottom, cellDelta, columnWidth, heightPx, readingOrder, toPixels } from "../canvas/grid";
import { WidgetFrame } from "./WidgetFrame";

/** Below this viewport width the board is one read-only column. */
export const NARROW_PX = 760;
export const EMPTY_BOARD = "Add a widget with + Widget";

export interface WidgetView {
  subtitle?: string;
  controls?: ReactNode;
  body: ReactNode;
}

interface BoardProps {
  board: BoardModel;
  onChange: (board: BoardModel) => void;
  renderWidget: (widget: WidgetInstance) => WidgetView;
  /** Fixed board width in px for tests; the dashboard measures its container. */
  width?: number;
}

interface Drag {
  id: string;
  kind: "move" | "resize";
  pointerX: number;
  pointerY: number;
  origin: WidgetInstance;
  /** Pointer travel in px since the drag started. */
  dx: number;
  dy: number;
  /** Snapped layout if the widget were dropped now. */
  preview: BoardModel;
}

function useViewportWidth(): number {
  const [width, setWidth] = useState(() => window.innerWidth);
  useEffect(() => {
    const onResize = () => setWidth(window.innerWidth);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);
  return width;
}

function useElementWidth(ref: React.RefObject<HTMLElement | null>, fixed: number | undefined): number {
  const [width, setWidth] = useState(fixed ?? 0);
  useLayoutEffect(() => {
    if (fixed !== undefined) {
      setWidth(fixed);
      return;
    }
    const el = ref.current;
    if (!el) return;
    setWidth(el.clientWidth);
    const observer = new ResizeObserver(() => setWidth(el.clientWidth));
    observer.observe(el);
    return () => observer.disconnect();
  }, [ref, fixed]);
  return width;
}

const ARROWS: Record<string, [number, number]> = {
  ArrowLeft: [-1, 0],
  ArrowRight: [1, 0],
  ArrowUp: [0, -1],
  ArrowDown: [0, 1],
};

/** Controls inside a title bar keep their own pointer handling. */
function fromControl(target: EventTarget | null): boolean {
  return target instanceof Element && target.closest("button, select, input, label, a, [data-no-drag]") !== null;
}

export function Board({ board, onChange, renderWidget, width: fixedWidth }: BoardProps) {
  const ref = useRef<HTMLDivElement>(null);
  const width = useElementWidth(ref, fixedWidth);
  const narrow = useViewportWidth() < NARROW_PX;
  const col = columnWidth(width);

  const [drag, setDrag] = useState<Drag | null>(null);
  const dragRef = useRef<Drag | null>(null);
  dragRef.current = drag;
  const boardRef = useRef(board);
  boardRef.current = board;
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;

  // A drag listens on window so it keeps tracking outside the widget.
  const dragging = drag !== null;
  useEffect(() => {
    if (!dragging) return;
    const update = (e: globalThis.PointerEvent) => {
      const d = dragRef.current;
      if (!d) return;
      const dx = e.clientX - d.pointerX;
      const dy = e.clientY - d.pointerY;
      const cells = cellDelta(dx, dy, col);
      const base = boardRef.current;
      const preview =
        d.kind === "move"
          ? moveWidget(base, d.id, d.origin.x + cells.dx, d.origin.y + cells.dy)
          : resizeWidget(base, d.id, d.origin.w + cells.dx, d.origin.h + cells.dy);
      setDrag({ ...d, dx, dy, preview });
    };
    const drop = () => {
      const d = dragRef.current;
      setDrag(null);
      if (d && JSON.stringify(d.preview.widgets) !== JSON.stringify(boardRef.current.widgets)) {
        onChangeRef.current(d.preview);
      }
    };
    const cancel = () => setDrag(null);
    const onKey = (e: globalThis.KeyboardEvent) => {
      if (e.key === "Escape") cancel();
    };
    window.addEventListener("pointermove", update);
    window.addEventListener("pointerup", drop);
    window.addEventListener("pointercancel", cancel);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("pointermove", update);
      window.removeEventListener("pointerup", drop);
      window.removeEventListener("pointercancel", cancel);
      window.removeEventListener("keydown", onKey);
    };
  }, [dragging, col]);

  const start = (widget: WidgetInstance, kind: Drag["kind"]) => (e: PointerEvent<HTMLDivElement>) => {
    if (e.button !== 0 || (kind === "move" && fromControl(e.target))) return;
    e.preventDefault();
    setDrag({ id: widget.id, kind, pointerX: e.clientX, pointerY: e.clientY, origin: widget, dx: 0, dy: 0, preview: board });
  };

  const onTitleKeyDown = (widget: WidgetInstance) => (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.target !== e.currentTarget) return; // keys inside a picker stay with the picker
    const step = ARROWS[e.key];
    if (!step) return;
    e.preventDefault();
    e.stopPropagation(); // the replay's window-level ←/→ lap keys must not also fire
    const [dx, dy] = step;
    const next = e.shiftKey
      ? resizeWidget(board, widget.id, widget.w + dx, widget.h + dy)
      : moveWidget(board, widget.id, widget.x + dx, widget.y + dy);
    if (JSON.stringify(next.widgets) !== JSON.stringify(board.widgets)) onChange(next);
  };

  if (board.widgets.length === 0) {
    return (
      <div ref={ref} data-testid="board" data-board-id={board.id} className="flex min-h-40 items-center justify-center">
        <p role="status" className="text-sm text-zinc-500">
          {EMPTY_BOARD}
        </p>
      </div>
    );
  }

  if (narrow) {
    return (
      <div ref={ref} data-testid="board" data-board-id={board.id} data-narrow="true" className="flex flex-col gap-2">
        {readingOrder(board.widgets).map((w) => {
          const view = renderWidget(w);
          return (
            <WidgetFrame key={w.id} widget={w} editable={false} subtitle={view.subtitle} controls={view.controls}
              style={{ height: heightPx(w.h) }} onRemove={() => onChange(removeWidget(board, w.id))}>
              {view.body}
            </WidgetFrame>
          );
        })}
      </div>
    );
  }

  const layout = drag ? drag.preview.widgets : board.widgets;
  const placeholder = drag ? layout.find((w) => w.id === drag.id) : undefined;
  const rows = bottom(layout);

  return (
    <div
      ref={ref}
      data-testid="board"
      data-board-id={board.id}
      className="relative"
      style={{ height: heightPx(Math.max(rows, 1)) }}
    >
      {placeholder && (
        <div
          data-testid="drop-placeholder"
          data-cell={`${placeholder.x},${placeholder.y},${placeholder.w},${placeholder.h}`}
          className="absolute rounded-md border-2 border-dashed border-zinc-500 bg-zinc-500/10"
          style={toPixels(placeholder, col)}
        />
      )}
      {layout.map((w) => {
        const view = renderWidget(w);
        const active = drag?.id === w.id;
        let box = toPixels(w, col);
        if (active && drag) {
          const origin = toPixels(drag.origin, col);
          box =
            drag.kind === "move"
              ? { ...origin, left: origin.left + drag.dx, top: origin.top + drag.dy }
              : { ...origin, width: Math.max(col, origin.width + drag.dx), height: Math.max(heightPx(1), origin.height + drag.dy) };
        }
        return (
          <WidgetFrame
            key={w.id}
            widget={active && drag ? drag.origin : w}
            editable
            dragging={active}
            subtitle={view.subtitle}
            controls={view.controls}
            style={{ position: "absolute", ...box }}
            onTitlePointerDown={start(w, "move")}
            onResizePointerDown={start(w, "resize")}
            onTitleKeyDown={onTitleKeyDown(w)}
            onRemove={() => onChange(removeWidget(board, w.id))}
          >
            {view.body}
          </WidgetFrame>
        );
      })}
    </div>
  );
}
