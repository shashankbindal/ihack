import type { ReactNode } from "react";

export type Tone = "ok" | "warn" | "bad" | "neutral";

const TONES: Record<Tone, string> = {
  ok: "border-ok/30 bg-ok-tint text-ok-ink",
  warn: "border-warn/30 bg-warn-tint text-warn-ink",
  bad: "border-bad/30 bg-bad-tint text-bad-ink",
  neutral: "border-line bg-hover text-muted",
};

export function Badge({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span
      className={`inline-flex items-center whitespace-nowrap rounded border px-2 py-0.5 text-xs font-medium ${TONES[tone]}`}
    >
      {children}
    </span>
  );
}
