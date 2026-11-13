export function quantile(sorted: number[], q: number): number {
  if (sorted.length === 0) return NaN;
  const position = (sorted.length - 1) * q;
  const lower = Math.floor(position);
  const upper = Math.ceil(position);
  return sorted[lower] + (sorted[upper] - sorted[lower]) * (position - lower);
}

export const sortAscending = (values: number[]): number[] => [...values].sort((a, b) => a - b);

export function median(values: number[]): number {
  return quantile(sortAscending(values), 0.5);
}

export function percentileRank(sorted: number[], value: number): number {
  if (sorted.length === 0) return NaN;
  return (sorted.filter((item) => item <= value).length / sorted.length) * 100;
}
