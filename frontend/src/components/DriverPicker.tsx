import type { DriverState } from "../api/types";

/** Title-bar driver setting: "" follows the focus driver, a code pins the widget. */
export function DriverPicker({
  widgetTitle,
  value,
  focusCode,
  drivers,
  onChange,
}: {
  widgetTitle: string;
  value: string | null;
  focusCode: string | null;
  drivers: DriverState[];
  onChange: (code: string | null) => void;
}) {
  const sorted = [...drivers].sort((a, b) => a.position - b.position);
  const pinnedMissing = value !== null && !drivers.some((d) => d.code === value);
  return (
    <select
      aria-label={`Driver for ${widgetTitle} widget`}
      className="rounded border border-zinc-800 bg-zinc-950 px-1 py-0.5 text-[11px] text-zinc-300"
      value={value ?? ""}
      onChange={(e) => onChange(e.target.value || null)}
    >
      <option value="">Follow focus ({focusCode ?? "—"})</option>
      {pinnedMissing && <option value={value}>{value} (not in this race)</option>}
      {sorted.map((d) => (
        <option key={d.code} value={d.code}>
          {d.code}
        </option>
      ))}
    </select>
  );
}

export function missingDriverText(code: string): string {
  return `${code} is not in this race`;
}
