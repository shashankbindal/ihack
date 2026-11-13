import { formatInr, formatSignedPct } from "../lib/format";
import type { Factor } from "../lib/types";

interface Step {
  factor: Factor;
  start: number;
  end: number;
}

export function Waterfall({ factors }: { factors: Factor[] }) {
  const ends = factors.reduce<number[]>((acc, factor) => [...acc, (acc.at(-1) ?? 0) + factor.effect_inr_per_sqft], []);
  const steps: Step[] = factors.map((factor, i) => ({ factor, start: i === 0 ? 0 : ends[i - 1], end: ends[i] }));
  const total = ends.at(-1) ?? 0;

  const bounds = steps.flatMap((s) => [s.start, s.end]).concat(0);
  const min = Math.min(...bounds);
  const max = Math.max(...bounds);
  const span = max - min || 1;
  const at = (value: number) => ((value - min) / span) * 100;

  return (
    <div className="space-y-1" role="list" aria-label="Value drivers in rupees per sq.ft">
      {steps.map(({ factor, start, end }) => {
        const positive = factor.effect_inr_per_sqft >= 0;
        return (
          <div
            key={factor.feature}
            role="listitem"
            className="grid grid-cols-1 items-center gap-x-4 gap-y-1 py-1.5 sm:grid-cols-[minmax(0,15rem)_minmax(0,1fr)_9rem]"
          >
            <p className="text-sm leading-snug text-ink">{factor.plain_text}</p>
            <div className="relative h-5">
              <div className="absolute inset-y-0 w-px bg-line" style={{ left: `${at(0)}%` }} />
              <div
                className={`absolute inset-y-0.5 rounded-sm ${positive ? "bg-ok" : "bg-bad"}`}
                style={{ left: `${at(Math.min(start, end))}%`, width: `${Math.max(Math.abs(at(end) - at(start)), 0.6)}%` }}
              />
            </div>
            <p className={`num text-sm sm:text-right ${positive ? "text-ok-ink" : "text-bad-ink"}`}>
              {positive ? "+" : "-"}
              {formatInr(Math.abs(factor.effect_inr_per_sqft))}
              <span className="ml-1.5 text-xs text-muted">{formatSignedPct(factor.effect_pct)}</span>
            </p>
          </div>
        );
      })}
      <div className="grid grid-cols-1 items-center gap-x-4 gap-y-1 border-t border-line pt-3 sm:grid-cols-[minmax(0,15rem)_minmax(0,1fr)_9rem]">
        <p className="text-sm font-semibold text-ink">Net of the factors shown</p>
        <div className="relative h-5">
          <div className="absolute inset-y-0 w-px bg-line" style={{ left: `${at(0)}%` }} />
          <div
            className="absolute inset-y-0.5 rounded-sm bg-ink"
            style={{ left: `${at(Math.min(0, total))}%`, width: `${Math.abs(at(total) - at(0))}%` }}
          />
        </div>
        <p className="num text-sm font-semibold sm:text-right">
          {total >= 0 ? "+" : "-"}
          {formatInr(Math.abs(total))}
        </p>
      </div>
    </div>
  );
}
