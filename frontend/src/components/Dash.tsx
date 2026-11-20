/** The "missing value" mark of the Design Source: a short dash in zinc-800. */
export function Dash() {
  return (
    <span data-testid="dash" aria-label="no value" className="inline-block h-0.5 w-3 rounded bg-zinc-800 align-middle" />
  );
}

/** Renders `text`, or the dash icon when it is null. */
export function OrDash({ text }: { text: string | null }) {
  return text == null ? <Dash /> : <>{text}</>;
}
