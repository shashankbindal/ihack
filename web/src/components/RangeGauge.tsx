import { formatCompactInr } from "../lib/format";

interface RangeGaugeProps {
  low: number;
  point: number;
  high: number;
  level: number;
  marker?: { value: number; label: string } | null;
}

const clamp = (value: number) => Math.min(100, Math.max(0, value));

export function RangeGauge({ low, point, high, level, marker }: RangeGaugeProps) {
  const values = [low, high, marker?.value ?? low];
  const min = Math.min(...values) * 0.9;
  const max = Math.max(...values) * 1.05;
  const position = (value: number) => clamp(((value - min) / (max - min)) * 100);
  const markerOutside = marker !== null && marker !== undefined && (marker.value < low || marker.value > high);

  return (
    <figure
      aria-label={`${Math.round(level * 100)}% range from ${formatCompactInr(low)} to ${formatCompactInr(high)}`}
      className="select-none"
    >
      <div className="relative h-16">
        <div className="absolute inset-x-0 top-8 h-1.5 rounded-full bg-hover" />
        <div
          className="absolute top-8 h-1.5 rounded-full bg-ink/25"
          style={{ left: `${position(low)}%`, width: `${position(high) - position(low)}%` }}
        />
        <div className="absolute top-6 h-5 w-0.5 bg-ink" style={{ left: `${position(point)}%` }} />
        <span
          className="num absolute top-0 -translate-x-1/2 whitespace-nowrap text-xs font-semibold text-ink"
          style={{ left: `${clamp(position(point))}%` }}
        >
          Fair {formatCompactInr(point)}
        </span>
        {marker && (
          <>
            <div
              className={`absolute top-6 h-5 w-0.5 ${markerOutside ? "bg-bad" : "bg-ok"}`}
              style={{ left: `${position(marker.value)}%` }}
            />
            <span
              className={`num absolute top-[42px] -translate-x-1/2 whitespace-nowrap text-xs font-medium ${
                markerOutside ? "text-bad-ink" : "text-ok-ink"
              }`}
              style={{ left: `${clamp(position(marker.value))}%` }}
            >
              {marker.label} {formatCompactInr(marker.value)}
            </span>
          </>
        )}
      </div>
      <div className="num mt-1 flex justify-between text-xs text-muted">
        <span>
          Low {formatCompactInr(low)}
        </span>
        <span>High {formatCompactInr(high)}</span>
      </div>
      <figcaption className="mt-2 text-xs text-muted">
        {Math.round(level * 100)}% range. Measured coverage on held-out listings is lower than nominal in some cities,
        see Model audit.
      </figcaption>
    </figure>
  );
}
