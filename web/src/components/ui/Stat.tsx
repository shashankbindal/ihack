import type { ReactNode } from "react";

interface StatProps {
  label: string;
  value: ReactNode;
  caption?: ReactNode;
}

export function Stat({ label, value, caption }: StatProps) {
  return (
    <div className="rounded-lg border border-line bg-surface p-5">
      <p className="text-xs font-medium text-muted">{label}</p>
      <p className="num mt-2 text-3xl font-semibold text-ink">{value}</p>
      {caption && <p className="mt-2 text-xs leading-relaxed text-muted">{caption}</p>}
    </div>
  );
}
