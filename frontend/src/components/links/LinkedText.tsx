import type { ReactNode } from "react";
import type { NumberLink } from "../../api/types";

export interface LinkedTextProps {
  text: string;
  /** /events links for this text (code-point offsets); missing or empty renders plain text. */
  links?: NumberLink[];
  /** Index of the link whose popover is open, if any. */
  openIndex?: number | null;
  onLinkClick?: (link: NumberLink, index: number, label: string, anchor: HTMLElement) => void;
}

/** Links that fit the text, in order and not overlapping; anything else is dropped. */
function validLinks(links: NumberLink[], length: number): { link: NumberLink; index: number }[] {
  const out: { link: NumberLink; index: number }[] = [];
  let last = 0;
  links.forEach((link, index) => {
    const ok =
      Number.isInteger(link.start) && Number.isInteger(link.end) && link.start >= last && link.end > link.start && link.end <= length;
    if (ok) {
      out.push({ link, index });
      last = link.end;
    }
  });
  return out;
}

/**
 * A text whose linked numbers are buttons ("<number>: show on chart"). The
 * text is split into code points with `Array.from`, matching the backend's
 * Python string offsets also for Chinese commentary.
 */
export function LinkedText({ text, links, openIndex = null, onLinkClick }: LinkedTextProps) {
  if (!links || links.length === 0) return <>{text}</>;
  const chars = Array.from(text);
  const parts: ReactNode[] = [];
  let pos = 0;
  for (const { link, index } of validLinks(links, chars.length)) {
    if (link.start > pos) parts.push(chars.slice(pos, link.start).join(""));
    const label = chars.slice(link.start, link.end).join("");
    parts.push(
      <button
        key={index}
        type="button"
        data-testid="number-link"
        data-field={link.field}
        aria-label={`${label}: show on chart`}
        aria-haspopup="dialog"
        aria-expanded={openIndex === index}
        className="cursor-pointer underline decoration-zinc-500 decoration-dotted underline-offset-2 hover:text-zinc-50 hover:decoration-zinc-200"
        onClick={(e) => onLinkClick?.(link, index, label, e.currentTarget)}
      >
        {label}
      </button>,
    );
    pos = link.end;
  }
  if (pos < chars.length) parts.push(chars.slice(pos).join(""));
  return <>{parts}</>;
}
